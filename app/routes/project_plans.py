"""Task plan management endpoints."""

import json
import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.agent_helpers import find_agent_by_role, get_orchestrator
from app.core.approval_manager import ApprovalManager
from app.core.user_worker_space import UserWorkerSpace
from app.database import get_db
from app.dependencies import get_worker_space
from app.logging_config import get_logger
from app.middleware.project_validation import get_project_with_validation
from app.middleware.user_isolation import get_current_user_id
from app.models.task_plan import TaskPlan
from app.models.task_plan_task import TaskPlanTask
from app.models.user_project import UserProject
from app.schemas.plan import (
    PlanCreateRequest,
    PlanDetailResponse,
    PlanExecutionResponse,
    PlanListResponse,
    PlanResponse,
    TaskResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/my/projects/{project_id}/plans", tags=["plans"])


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=PlanResponse)
async def create_plan(
    project_id: UUID,
    request: Request,
    plan_request: PlanCreateRequest,
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
    db: AsyncSession = Depends(get_db),
) -> PlanResponse:
    """Create a new task plan through Architect Agent.

    The Architect Agent analyzes the task description and creates a plan
    with multiple tasks, dependencies, cost/duration estimates, and risk levels.

    Args:
        project_id: Project UUID from path
        request: FastAPI request
        plan_request: Plan creation request with description
        project: Validated project object
        workspace: User worker space
        db: Database session

    Returns:
        Created plan information

    Raises:
        HTTPException 400: If plan request is invalid
        HTTPException 404: If Architect Agent not found
        HTTPException 500: If Architect execution fails
    """
    user_id = get_current_user_id(request)

    logger.info(
        "plan_create_requested",
        user_id=str(user_id),
        project_id=str(project_id),
        description_len=len(plan_request.description),
    )

    # Find Architect Agent
    architect_id = await find_agent_by_role(db, user_id, project_id, "architect")
    if not architect_id:
        logger.error(
            "architect_agent_not_found",
            user_id=str(user_id),
            project_id=str(project_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Architect Agent not found in project. Please add it to starter pack.",
        )

    # Prepare Architect prompt
    architect_prompt = f"""Analyze this task request and create a detailed plan:

{plan_request.description}

Return a JSON object with this structure:
{{
    "title": "brief plan title",
    "tasks": [
        {{
            "task_id": "task_0",
            "description": "task description",
            "dependencies": [],
            "estimated_cost": 0.1,
            "estimated_duration": 300,
            "risk_level": "LOW"
        }}
    ]
}}

Be realistic with costs and durations. Include all necessary steps."""

    # Execute Architect Agent
    start_time = time.time()
    try:
        architect_result = await workspace.direct_execution(
            agent_id=architect_id,
            user_message=architect_prompt,
            task_id="plan_creation",
            metadata={
                "description": plan_request.description,
                "plan_type": "orchestration",
            },
        )

        execution_time = (time.time() - start_time) * 1000  # ms

        if not architect_result.get("success"):
            logger.error(
                "architect_execution_failed",
                user_id=str(user_id),
                project_id=str(project_id),
                response=architect_result.get("response"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Architect Agent failed: {architect_result.get('response')}",
            )

        # Parse plan from Architect response
        try:
            plan_data = json.loads(architect_result.get("response", "{}"))
        except json.JSONDecodeError:
            logger.error(
                "architect_response_parse_error",
                user_id=str(user_id),
                response=architect_result.get("response"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to parse Architect response",
            )

        # Calculate totals
        total_cost = 0.0
        total_duration = 0.0
        tasks_data = plan_data.get("tasks", [])

        for task in tasks_data:
            total_cost += task.get("estimated_cost", 0.0)
            total_duration += task.get("estimated_duration", 0.0)

        # Create TaskPlan in database
        task_plan = TaskPlan(
            user_id=user_id,
            project_id=project_id,
            session_id=plan_request.session_id,
            original_request=plan_request.description,
            status="created",
            total_estimated_cost=total_cost,
            total_estimated_duration=total_duration,
            requires_approval=total_cost > 10.0 or total_duration > 3600,  # > $10 or > 1 hour
            approval_reason="High cost or long duration" if total_cost > 10.0 or total_duration > 3600 else None,
        )

        db.add(task_plan)
        await db.flush()

        # Create TaskPlanTask entries
        for task_data in tasks_data:
            task_obj = TaskPlanTask(
                plan_id=task_plan.id,
                task_id=task_data.get("task_id", f"task_{tasks_data.index(task_data)}"),
                description=task_data.get("description", ""),
                agent_id=architect_id,  # Will be assigned during execution
                dependencies=task_data.get("dependencies", []),
                estimated_cost=task_data.get("estimated_cost", 0.0),
                estimated_duration=task_data.get("estimated_duration", 0.0),
                risk_level=task_data.get("risk_level", "LOW"),
                status="pending",
            )
            db.add(task_obj)

        await db.flush()

        # Cache plan data in Redis
        if workspace.redis:
            try:
                cache_key = f"plan:{task_plan.id}"
                plan_cache_data = {
                    "id": str(task_plan.id),
                    "title": plan_data.get("title", plan_request.description[:100]),
                    "status": "created",
                    "created_at": datetime.utcnow().isoformat(),
                }
                await workspace.redis.setex(
                    cache_key, 300, json.dumps(plan_cache_data, default=str)
                )
                logger.info(
                    "plan_cached",
                    plan_id=str(task_plan.id),
                    cache_key=cache_key,
                )
            except Exception as e:
                logger.warning(
                    "plan_cache_error",
                    plan_id=str(task_plan.id),
                    error=str(e),
                )

        logger.info(
            "plan_created_successfully",
            user_id=str(user_id),
            plan_id=str(task_plan.id),
            task_count=len(tasks_data),
            total_cost=total_cost,
            total_duration=total_duration,
            execution_time_ms=int(execution_time),
        )

        return PlanResponse(
            id=task_plan.id,
            title=plan_data.get("title", plan_request.description[:100]),
            description=plan_request.description,
            status=task_plan.status,
            total_estimated_cost=total_cost,
            total_estimated_duration=total_duration,
            requires_approval=task_plan.requires_approval,
            task_count=len(tasks_data),
            created_at=task_plan.created_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "plan_creation_error",
            user_id=str(user_id),
            project_id=str(project_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/", response_model=PlanListResponse)
async def list_plans(
    project_id: UUID,
    request: Request,
    offset: int = 0,
    limit: int = 10,
    status_filter: str | None = None,
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
    db: AsyncSession = Depends(get_db),
) -> PlanListResponse:
    """List all task plans in project with pagination.

    Args:
        project_id: Project UUID from path
        request: FastAPI request
        offset: Pagination offset
        limit: Pagination limit (max 100)
        status_filter: Optional status filter (created, executing, completed, failed)
        project: Validated project object
        workspace: User worker space
        db: Database session

    Returns:
        List of plans with pagination info

    Raises:
        HTTPException 400: If pagination parameters invalid
    """
    user_id = get_current_user_id(request)

    if offset < 0 or limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pagination parameters",
        )

    logger.info(
        "plan_list_requested",
        user_id=str(user_id),
        project_id=str(project_id),
        offset=offset,
        limit=limit,
        status_filter=status_filter,
    )

    # Build query
    query = select(TaskPlan).where(
        TaskPlan.user_id == user_id,
        TaskPlan.project_id == project_id,
    )

    if status_filter:
        query = query.where(TaskPlan.status == status_filter)

    # Get total count
    count_result = await db.execute(
        select(func.count(TaskPlan.id)).where(
            TaskPlan.user_id == user_id,
            TaskPlan.project_id == project_id,
        )
    )
    total = count_result.scalar_one()

    # Get paginated results
    result = await db.execute(
        query.order_by(TaskPlan.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    plans = result.scalars().all()

    plans_response = [
        PlanResponse(
            id=plan.id,
            title=plan.original_request[:100] if plan.original_request else None,
            description=plan.original_request,
            status=plan.status,
            total_estimated_cost=plan.total_estimated_cost,
            total_estimated_duration=plan.total_estimated_duration,
            requires_approval=plan.requires_approval,
            task_count=len(plan.tasks),
            created_at=plan.created_at,
        )
        for plan in plans
    ]

    logger.info(
        "plan_list_retrieved",
        user_id=str(user_id),
        project_id=str(project_id),
        count=len(plans_response),
        total=total,
    )

    return PlanListResponse(
        plans=plans_response,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/{plan_id}", response_model=PlanDetailResponse)
async def get_plan(
    project_id: UUID,
    plan_id: UUID,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
    db: AsyncSession = Depends(get_db),
) -> PlanDetailResponse:
    """Get detailed plan with all tasks.

    Args:
        project_id: Project UUID from path
        plan_id: Plan UUID from path
        request: FastAPI request
        project: Validated project object
        workspace: User worker space
        db: Database session

    Returns:
        Detailed plan information with tasks

    Raises:
        HTTPException 404: If plan not found
    """
    user_id = get_current_user_id(request)

    logger.info(
        "plan_detail_requested",
        user_id=str(user_id),
        project_id=str(project_id),
        plan_id=str(plan_id),
    )

    # Get plan with tasks
    result = await db.execute(
        select(TaskPlan)
        .where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == user_id,
            TaskPlan.project_id == project_id,
        )
        .options(selectinload(TaskPlan.tasks).selectinload(TaskPlanTask.agent))
    )
    plan = result.unique().scalar_one_or_none()

    if not plan:
        logger.warning(
            "plan_not_found",
            user_id=str(user_id),
            plan_id=str(plan_id),
            project_id=str(project_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Build task responses
    tasks_response = [
        TaskResponse(
            id=task.id,
            task_id=task.task_id,
            title=task.description[:50] if task.description else None,
            description=task.description,
            agent_id=task.agent_id,
            agent_name=task.agent.name if task.agent else "Unknown",
            dependencies=task.dependencies,
            estimated_cost=task.estimated_cost,
            estimated_duration=task.estimated_duration,
            risk_level=task.risk_level,
            status=task.status,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
        )
        for task in plan.tasks
    ]

    logger.info(
        "plan_detail_retrieved",
        user_id=str(user_id),
        plan_id=str(plan_id),
        task_count=len(tasks_response),
    )

    return PlanDetailResponse(
        id=plan.id,
        title=plan.original_request[:100] if plan.original_request else None,
        description=plan.original_request,
        status=plan.status,
        total_estimated_cost=plan.total_estimated_cost,
        total_estimated_duration=plan.total_estimated_duration,
        requires_approval=plan.requires_approval,
        task_count=len(plan.tasks),
        created_at=plan.created_at,
        tasks=tasks_response,
    )


@router.get("/{plan_id}/tasks", response_model=list[TaskResponse])
async def get_plan_tasks(
    project_id: UUID,
    plan_id: UUID,
    request: Request,
    status_filter: str | None = None,
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
    db: AsyncSession = Depends(get_db),
) -> list[TaskResponse]:
    """Get tasks for a specific plan.

    Args:
        project_id: Project UUID from path
        plan_id: Plan UUID from path
        request: FastAPI request
        status_filter: Optional status filter
        project: Validated project object
        workspace: User worker space
        db: Database session

    Returns:
        List of plan tasks

    Raises:
        HTTPException 404: If plan not found
    """
    user_id = get_current_user_id(request)

    logger.info(
        "plan_tasks_requested",
        user_id=str(user_id),
        plan_id=str(plan_id),
        status_filter=status_filter,
    )

    # Verify plan exists
    plan_result = await db.execute(
        select(TaskPlan).where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == user_id,
            TaskPlan.project_id == project_id,
        )
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Get tasks
    query = select(TaskPlanTask).where(TaskPlanTask.plan_id == plan_id)
    if status_filter:
        query = query.where(TaskPlanTask.status == status_filter)

    result = await db.execute(query.options(selectinload(TaskPlanTask.agent)))
    tasks = result.unique().scalars().all()

    tasks_response = [
        TaskResponse(
            id=task.id,
            task_id=task.task_id,
            title=task.description[:50] if task.description else None,
            description=task.description,
            agent_id=task.agent_id,
            agent_name=task.agent.name if task.agent else "Unknown",
            dependencies=task.dependencies,
            estimated_cost=task.estimated_cost,
            estimated_duration=task.estimated_duration,
            risk_level=task.risk_level,
            status=task.status,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
        )
        for task in tasks
    ]

    logger.info(
        "plan_tasks_retrieved",
        user_id=str(user_id),
        plan_id=str(plan_id),
        task_count=len(tasks_response),
    )

    return tasks_response


@router.post("/{plan_id}/execute", response_model=PlanExecutionResponse)
async def execute_plan(
    project_id: UUID,
    plan_id: UUID,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
    db: AsyncSession = Depends(get_db),
) -> PlanExecutionResponse:
    """Execute a task plan through Orchestrator Agent.

    The Orchestrator Agent coordinates execution of all tasks in the plan,
    respecting dependencies and handling failures.

    Args:
        project_id: Project UUID from path
        plan_id: Plan UUID from path
        request: FastAPI request
        project: Validated project object
        workspace: User worker space
        db: Database session

    Returns:
        Execution status and result

    Raises:
        HTTPException 404: If plan not found
        HTTPException 404: If Orchestrator Agent not found
        HTTPException 400: If plan not ready for execution
        HTTPException 500: If execution fails
    """
    user_id = get_current_user_id(request)

    logger.info(
        "plan_execute_requested",
        user_id=str(user_id),
        project_id=str(project_id),
        plan_id=str(plan_id),
    )

    # Get plan
    plan_result = await db.execute(
        select(TaskPlan)
        .where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == user_id,
            TaskPlan.project_id == project_id,
        )
        .options(selectinload(TaskPlan.tasks))
    )
    plan = plan_result.unique().scalar_one_or_none()

    if not plan:
        logger.warning(
            "plan_not_found_for_execution",
            user_id=str(user_id),
            plan_id=str(plan_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Check plan status and handle approval
    if plan.requires_approval and plan.status == "created":
        logger.info(
            "plan_requires_approval",
            plan_id=str(plan_id),
            reason=plan.approval_reason,
        )

        # Create ApprovalManager
        approval_manager = ApprovalManager(
            user_id=user_id,
            project_id=project_id,
            db=db,
            stream_manager=workspace.stream_manager,
        )

        # Request approval
        approval_req = await approval_manager.request_plan_approval(
            plan=plan,
            timeout=300,
        )

        # If auto-approved, continue execution
        if approval_req.status.value == "approved":
            logger.info(
                "plan_auto_approved",
                plan_id=str(plan_id),
                approval_id=str(approval_req.id),
            )
            # Continue to execute the plan
        else:
            # Return waiting for approval status
            logger.info(
                "plan_approval_pending",
                plan_id=str(plan_id),
                approval_id=str(approval_req.id),
            )
            return PlanExecutionResponse(
                plan_id=plan.id,
                status="waiting_for_approval",
                message="Plan requires user approval",
                approval_id=approval_req.id,
            )

    # Find Orchestrator Agent
    orchestrator = await get_orchestrator(db, user_id, project_id)
    if not orchestrator:
        logger.error(
            "orchestrator_agent_not_found",
            user_id=str(user_id),
            project_id=str(project_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Orchestrator Agent not found in project",
        )

    # Prepare tasks list for Orchestrator
    tasks_for_orchestrator = [
        {
            "task_id": task.task_id,
            "description": task.description,
            "dependencies": task.dependencies,
            "estimated_cost": task.estimated_cost,
            "estimated_duration": task.estimated_duration,
        }
        for task in plan.tasks
    ]

    # Update plan status
    plan.status = "pending_approval"
    await db.flush()

    # Execute Orchestrator Agent
    start_time = time.time()
    try:
        orchestrator_prompt = f"""Execute this task plan. For each task, call appropriate agents.

Tasks to execute:
{json.dumps(tasks_for_orchestrator, indent=2)}

Original request: {plan.original_request}

Return a JSON object with execution results for each task."""

        orchestrator_result = await workspace.direct_execution(
            agent_id=orchestrator.id,
            user_message=orchestrator_prompt,
            task_id=f"plan_execution_{plan_id}",
            metadata={
                "plan_id": str(plan_id),
                "task_count": len(plan.tasks),
            },
        )

        execution_time = int((time.time() - start_time) * 1000)  # ms

        if not orchestrator_result.get("success"):
            plan.status = "failed"
            await db.flush()

            logger.error(
                "orchestrator_execution_failed",
                plan_id=str(plan_id),
                response=orchestrator_result.get("response"),
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Orchestrator execution failed: {orchestrator_result.get('response')}",
            )

        # Update plan and tasks status
        plan.status = "executing"
        plan.started_at = datetime.utcnow()
        await db.flush()

        logger.info(
            "plan_execution_started",
            user_id=str(user_id),
            plan_id=str(plan_id),
            execution_time_ms=execution_time,
        )

        return PlanExecutionResponse(
            plan_id=plan.id,
            status="executing",
            message="Plan execution started",
            execution_time_ms=execution_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        plan.status = "failed"
        await db.flush()

        logger.error(
            "plan_execution_error",
            plan_id=str(plan_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.post("/{plan_id}/tasks/{task_id}/execute", response_model=TaskResponse)
async def execute_plan_task(
    project_id: UUID,
    plan_id: UUID,
    task_id: str,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    workspace: UserWorkerSpace = Depends(get_worker_space),
    db: AsyncSession = Depends(get_db),
) -> TaskResponse:
    """Execute a specific task within a plan.

    Args:
        project_id: Project UUID from path
        plan_id: Plan UUID from path
        task_id: Task ID (logical task_0, task_1, etc.)
        request: FastAPI request
        project: Validated project object
        workspace: User worker space
        db: Database session

    Returns:
        Updated task information

    Raises:
        HTTPException 404: If plan or task not found
        HTTPException 400: If task dependencies not satisfied
        HTTPException 500: If execution fails
    """
    user_id = get_current_user_id(request)

    logger.info(
        "plan_task_execute_requested",
        user_id=str(user_id),
        plan_id=str(plan_id),
        task_id=task_id,
    )

    # Get plan
    plan_result = await db.execute(
        select(TaskPlan).where(
            TaskPlan.id == plan_id,
            TaskPlan.user_id == user_id,
            TaskPlan.project_id == project_id,
        )
    )
    plan = plan_result.scalar_one_or_none()

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Get task
    task_result = await db.execute(
        select(TaskPlanTask)
        .where(
            TaskPlanTask.plan_id == plan_id,
            TaskPlanTask.task_id == task_id,
        )
        .options(selectinload(TaskPlanTask.agent))
    )
    task_obj = task_result.unique().scalar_one_or_none()

    if not task_obj:
        logger.warning(
            "plan_task_not_found",
            plan_id=str(plan_id),
            task_id=task_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found in plan",
        )

    # Check dependencies
    all_tasks = await db.execute(select(TaskPlanTask).where(TaskPlanTask.plan_id == plan_id))
    all_tasks_map = {t.task_id: t for t in all_tasks.scalars().all()}

    for dep_id in task_obj.dependencies:
        if dep_id in all_tasks_map:
            dep_task = all_tasks_map[dep_id]
            if dep_task.status != "completed":
                logger.warning(
                    "plan_task_dependency_not_satisfied",
                    task_id=task_id,
                    dependency=dep_id,
                    dependency_status=dep_task.status,
                )
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Dependency {dep_id} is not completed",
                )

    # Execute task
    task_obj.status = "executing"
    task_obj.started_at = datetime.utcnow()
    await db.flush()

    start_time = time.time()
    try:
        task_result_exec = await workspace.direct_execution(
            agent_id=task_obj.agent_id,
            user_message=task_obj.description,
            task_id=task_id,
            metadata={
                "plan_id": str(plan_id),
                "risk_level": task_obj.risk_level,
            },
        )

        execution_time = int((time.time() - start_time) * 1000)

        if task_result_exec.get("success"):
            task_obj.status = "completed"
            task_obj.result = {
                "response": task_result_exec.get("response"),
                "execution_time_ms": execution_time,
            }
            task_obj.completed_at = datetime.utcnow()

            logger.info(
                "plan_task_executed_successfully",
                plan_id=str(plan_id),
                task_id=task_id,
                execution_time_ms=execution_time,
            )
        else:
            task_obj.status = "failed"
            task_obj.error = task_result_exec.get("response", "Unknown error")
            task_obj.completed_at = datetime.utcnow()

            logger.error(
                "plan_task_execution_failed",
                plan_id=str(plan_id),
                task_id=task_id,
                error=task_obj.error,
            )

        await db.flush()

        return TaskResponse(
            id=task_obj.id,
            task_id=task_obj.task_id,
            title=task_obj.description[:50] if task_obj.description else None,
            description=task_obj.description,
            agent_id=task_obj.agent_id,
            agent_name=task_obj.agent.name if task_obj.agent else "Unknown",
            dependencies=task_obj.dependencies,
            estimated_cost=task_obj.estimated_cost,
            estimated_duration=task_obj.estimated_duration,
            risk_level=task_obj.risk_level,
            status=task_obj.status,
            result=task_obj.result,
            error=task_obj.error,
            created_at=task_obj.created_at,
        )

    except Exception as e:
        task_obj.status = "failed"
        task_obj.error = str(e)
        task_obj.completed_at = datetime.utcnow()
        await db.flush()

        logger.error(
            "plan_task_execution_error",
            plan_id=str(plan_id),
            task_id=task_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )
