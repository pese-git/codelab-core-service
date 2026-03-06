"""REST API endpoints for Tool execution - Project Tools API"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.outbox_repository import OutboxRepository
from app.dependencies import get_worker_space, get_current_user
from app.database import get_db
from app.logging_config import get_logger
from app.middleware.project_validation import get_project_with_validation
from app.models.tool_execution import ToolExecution
from app.models.user_project import UserProject
from app.schemas.event import StreamEventType
from app.schemas.tool import (
    ToolExecutionRequest,
    ToolExecutionResponse,
    ToolExecutionResultRequest,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/my/projects", tags=["project-tools"])


@router.post("/{project_id}/tools/execute")
async def execute_tool(
    project_id: UUID,
    request: ToolExecutionRequest,
    worker_space=Depends(get_worker_space),
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    project: UserProject = Depends(get_project_with_validation),
) -> ToolExecutionResponse:
    """Execute a tool with full validation and approval workflow
    
    Supported tools:
    - read_file: Read file contents from workspace
    - write_file: Write or append content to file
    - execute_command: Execute shell command
    - list_directory: List files in directory
    
    Workflow:
    1. Validate parameters (path, command, size, etc.)
    2. Assess risk level (LOW/MEDIUM/HIGH)
    3. Request approval if needed (MEDIUM/HIGH risk)
    4. Send execution request to client
    5. Return result or error
    
    Args:
        project_id: UUID of the project
        request: ToolExecutionRequest with tool_name and tool_params
        worker_space: Injected worker space
        user_id: Current user UUID
        
    Returns:
        ToolExecutionResponse with status and result
        
    Raises:
        HTTPException: 400 if validation fails, 500 if execution error
        
    Example:
        POST /my/projects/{project_id}/tools/execute
        {
            "tool_name": "read_file",
            "tool_params": {"path": "src/main.py"},
            "session_id": "550e8400-e29b-41d4-a716-446655440000"
        }
    """
    try:
        # Extract and validate session_id
        session_id = request.session_id or request.chat_session_id
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="session_id is required. Include it in the request as 'session_id' or 'chat_session_id' field",
            )

        logger.info(
            "tool_execution_request_received",
            project_id=str(project_id),
            tool_name=request.tool_name,
            user_id=str(user_id),
            session_id=str(session_id),
        )

        if worker_space.executor is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace root is not configured for tool execution",
            )

        # Execute tool through worker_space executor
        result = await worker_space.executor.execute_tool(
            tool_name=request.tool_name,
            tool_params=request.tool_params,
            session_id=session_id,
        )

        logger.info(
            "tool_execution_response_sent",
            project_id=str(project_id),
            tool_id=result.tool_id,
            tool_name=result.tool_name,
            status=result.status,
        )

        return result

    except ValueError as e:
        logger.error(
            "tool_execution_validation_error",
            project_id=str(project_id),
            tool_name=request.tool_name,
            error=str(e),
        )
        raise HTTPException(status_code=400, detail=f"Validation error: {str(e)}")

    except Exception as e:
        logger.error(
            "tool_execution_error",
            project_id=str(project_id),
            tool_name=request.tool_name,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Tool execution error: {str(e)}")


@router.get("/{project_id}/tools/{tool_id}", response_model=ToolExecutionResponse)
async def get_tool_execution_status(
    project_id: UUID,
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    project: UserProject = Depends(get_project_with_validation),
) -> ToolExecutionResponse:
    """Get execution status of a tool
    
    Args:
        project_id: UUID of the project
        tool_id: ID of the tool execution
        user_id: Current user UUID
        
    Returns:
        Tool execution status dict
        
    Raises:
        HTTPException: 404 if not found, 403 if not authorized
    """
    try:
        logger.info(
            "get_tool_execution_status_request",
            project_id=str(project_id),
            tool_id=tool_id,
            user_id=str(user_id),
        )

        result = await db.execute(
            select(ToolExecution).where(
                ToolExecution.id == tool_id,
                ToolExecution.user_id == user_id,
                ToolExecution.project_id == project_id,
            )
        )
        execution = result.scalar_one_or_none()
        if not execution:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tool execution not found",
            )

        return ToolExecutionResponse(
            tool_id=str(execution.id),
            tool_name=execution.tool_name,
            status=execution.status,
            approval_id=execution.approval_id,
            requires_approval=execution.approval_id is not None,
            result=execution.result,
            error=execution.error,
            created_at=execution.created_at.isoformat(),
            completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "get_tool_execution_status_error",
            tool_id=tool_id,
            error=str(e),
        )
        raise HTTPException(status_code=500, detail="Failed to get tool status")


@router.get("/{project_id}/tools")
async def list_tool_executions(
    project_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    project: UserProject = Depends(get_project_with_validation),
) -> dict:
    """List tool execution history
    
    Args:
        project_id: UUID of the project
        limit: Maximum number of results (1-100, default 50)
        offset: Number of results to skip (default 0)
        user_id: Current user UUID
        
    Returns:
        Dict with tools list and metadata
        
    Raises:
        HTTPException: 500 if query fails
    """
    logger.info(
        "list_tool_executions_request",
        project_id=str(project_id),
        limit=limit,
        offset=offset,
    )

    count_result = await db.execute(
        select(func.count(ToolExecution.id)).where(
            ToolExecution.user_id == user_id,
            ToolExecution.project_id == project_id,
        )
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(ToolExecution)
        .where(
            ToolExecution.user_id == user_id,
            ToolExecution.project_id == project_id,
        )
        .order_by(ToolExecution.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    executions = result.scalars().all()

    return {
        "items": [
            ToolExecutionResponse(
                tool_id=str(execution.id),
                tool_name=execution.tool_name,
                status=execution.status,
                approval_id=execution.approval_id,
                requires_approval=execution.approval_id is not None,
                result=execution.result,
                error=execution.error,
                created_at=execution.created_at.isoformat(),
                completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
            )
            for execution in executions
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post(
    "/{project_id}/tools/{tool_id}/result",
    response_model=ToolExecutionResponse,
)
async def submit_tool_execution_result(
    project_id: UUID,
    tool_id: UUID,
    result_request: ToolExecutionResultRequest,
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    project: UserProject = Depends(get_project_with_validation),
) -> ToolExecutionResponse:
    """Submit tool execution result from client."""
    result = await db.execute(
        select(ToolExecution).where(
            ToolExecution.id == tool_id,
            ToolExecution.user_id == user_id,
            ToolExecution.project_id == project_id,
        )
    )
    execution = result.scalar_one_or_none()
    if not execution:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool execution not found",
        )

    execution.status = result_request.status
    execution.result = result_request.result
    execution.error = result_request.error
    execution.completed_at = result_request.completed_at or datetime.utcnow()
    await db.flush()

    # Record outbox event for tool result
    await OutboxRepository.record_event(
        session=db,
        aggregate_type="tool_execution",
        aggregate_id=execution.id,
        user_id=user_id,
        project_id=project_id,
        event_type=(
            StreamEventType.TOOL_RESULT.value
            if result_request.status == "completed"
            else StreamEventType.TOOL_ERROR.value
        ),
        payload={
            "tool_id": str(execution.id),
            "tool_name": execution.tool_name,
            "status": execution.status,
            "result": execution.result,
            "error": execution.error,
            "session_id": str(execution.session_id) if execution.session_id else None,
            "timestamp": execution.completed_at.isoformat(),
        },
    )

    return ToolExecutionResponse(
        tool_id=str(execution.id),
        tool_name=execution.tool_name,
        status=execution.status,
        approval_id=execution.approval_id,
        requires_approval=execution.approval_id is not None,
        result=execution.result,
        error=execution.error,
        created_at=execution.created_at.isoformat(),
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
    )


@router.get("/{project_id}/tools/available")
async def list_available_tools(
    project_id: UUID,
    user_id: UUID = Depends(get_current_user),
) -> dict:
    """List available tools for this project
    
    Returns metadata about each available tool including:
    - Name and description
    - Parameters and types
    - Risk level
    - Approval requirements
    
    Args:
        project_id: UUID of the project
        user_id: Current user UUID
        
    Returns:
        Dict with available tools metadata
    """
    try:
        from app.core.tools import AVAILABLE_TOOLS, RiskAssessor

        logger.info(
            "list_available_tools_request",
            project_id=str(project_id),
        )

        assessor = RiskAssessor()
        tools_info = []

        for tool_name, tool_def in AVAILABLE_TOOLS.items():
            # Assess default risk
            default_risk = assessor.assess_tool_risk(tool_name.value, {})

            tools_info.append({
                "name": tool_def.name.value,
                "description": tool_def.description,
                "parameters": tool_def.parameters,
                "requires_approval": tool_def.requires_approval,
                "risk_level": default_risk.value,
                "timeout_seconds": assessor.get_timeout_for_risk_level(default_risk),
            })

        logger.info(
            "available_tools_returned",
            project_id=str(project_id),
            tool_count=len(tools_info),
        )

        return {
            "success": True,
            "tools": tools_info,
            "total_count": len(tools_info),
        }

    except Exception as e:
        logger.error(
            "list_available_tools_error",
            project_id=str(project_id),
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Failed to list available tools")
