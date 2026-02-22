"""Plan executor for parallel task execution with dependency management."""

import asyncio
import time
from uuid import UUID
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.task_graph_builder import TaskGraphBuilder
from app.core.agent_helpers import find_agent_by_name, get_agents_by_role
from app.core.user_worker_space import UserWorkerSpace
from app.core.approval_manager import ApprovalManager
from app.schemas.agent_role import AgentRole
from app.logging_config import get_logger

logger = get_logger(__name__)


class PlanExecutor:
    """Executes task plans with parallel execution respecting dependencies."""

    def __init__(
        self,
        max_concurrent_tasks: int = 3,
        task_timeout: float = 300.0,
    ):
        """Initialize plan executor.

        Args:
            max_concurrent_tasks: Maximum number of tasks to run in parallel
            task_timeout: Timeout in seconds for individual task execution
        """
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_timeout = task_timeout

    async def execute_plan_parallel(
        self,
        db: AsyncSession,
        workspace: UserWorkerSpace,
        user_id: UUID,
        project_id: UUID,
        plan: dict,
        approval_manager: Optional[ApprovalManager] = None,
    ) -> dict:
        """Execute task graph respecting dependencies with parallelism.

        Strategy:
        1. Validate the task graph (no cycles, all refs valid)
        2. Topologically sort to get execution levels
        3. For each level, execute tasks in parallel (up to max_concurrent)
        4. Wait for level to complete before proceeding to next
        5. Collect results and aggregate

        Args:
            db: Database session
            workspace: User workspace for agent execution
            user_id: User ID
            project_id: Project ID
            plan: Plan dict with 'tasks' and 'dependencies' fields
            approval_manager: Optional approval manager for approval gates

        Returns:
            Aggregated execution result:
                {
                    "success": bool,
                    "total_tasks": int,
                    "completed_tasks": int,
                    "failed_tasks": int,
                    "total_cost": float,
                    "total_duration": float,
                    "task_results": {task_id: result},
                    "errors": [error_messages]
                }

        Example:
            >>> plan = {
            ...     "tasks": [
            ...         {"task_id": "t0", "description": "...", "assigned_to": "Code"},
            ...         {"task_id": "t1", "description": "...", "assigned_to": "Code"}
            ...     ],
            ...     "dependencies": [{"from": "t0", "to": "t1"}]
            ... }
            >>> result = await executor.execute_plan_parallel(
            ...     db, workspace, user_id, project_id, plan
            ... )
            >>> result["success"]
            True
        """
        tasks = plan.get("tasks", [])
        dependencies = plan.get("dependencies", [])

        # Validate graph
        is_valid, error = TaskGraphBuilder.validate_graph(tasks, dependencies)
        if not is_valid:
            logger.error("plan_validation_failed", error=error)
            return {
                "success": False,
                "total_tasks": len(tasks),
                "completed_tasks": 0,
                "failed_tasks": len(tasks),
                "total_cost": 0.0,
                "total_duration": 0.0,
                "task_results": {},
                "errors": [f"Plan validation failed: {error}"],
            }

        # Get execution levels
        levels = TaskGraphBuilder.topological_sort(tasks, dependencies)
        logger.info(
            "plan_execution_started",
            total_tasks=len(tasks),
            levels=len(levels),
            max_concurrent=self.max_concurrent_tasks,
        )

        # Execution state
        start_time = time.time()
        task_results: dict[str, Any] = {}
        failed_tasks: list[str] = []
        errors: list[str] = []

        # Execute level by level
        for level_idx, level_tasks in enumerate(levels):
            logger.info(
                "executing_level",
                level=level_idx + 1,
                task_count=len(level_tasks),
            )

            # Execute tasks in this level in parallel
            level_results = await self._execute_level_parallel(
                db,
                workspace,
                user_id,
                project_id,
                level_tasks,
                tasks,
                task_results,
            )

            # Collect results
            for task_id, result in level_results.items():
                task_results[task_id] = result
                if result.get("success") is False:
                    failed_tasks.append(task_id)
                    errors.append(result.get("error", f"Task {task_id} failed"))

            # Check if we should continue on errors
            if failed_tasks:
                logger.warning(
                    "level_execution_with_failures",
                    level=level_idx + 1,
                    failed_count=len(failed_tasks),
                )
                # For now, continue to next level
                # In production, might want to stop here

        total_duration = time.time() - start_time
        total_cost = TaskGraphBuilder.calculate_total_cost(tasks)

        return {
            "success": len(failed_tasks) == 0,
            "total_tasks": len(tasks),
            "completed_tasks": len(tasks) - len(failed_tasks),
            "failed_tasks": len(failed_tasks),
            "total_cost": round(total_cost, 4),
            "total_duration": round(total_duration, 1),
            "task_results": task_results,
            "errors": errors,
        }

    async def _execute_level_parallel(
        self,
        db: AsyncSession,
        workspace: UserWorkerSpace,
        user_id: UUID,
        project_id: UUID,
        level_tasks: list[str],
        all_tasks: list[dict],
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute all tasks in a level in parallel (max concurrent limit).

        Args:
            db: Database session
            workspace: User workspace
            user_id: User ID
            project_id: Project ID
            level_tasks: List of task IDs to execute in this level
            all_tasks: All tasks in plan (for lookup)
            previous_results: Results from previous levels (for context)

        Returns:
            Dict of {task_id: result}
        """
        # Create semaphore to limit concurrency
        semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        async def execute_with_limit(task_id: str) -> tuple[str, Any]:
            async with semaphore:
                return task_id, await self._execute_single_task(
                    db,
                    workspace,
                    user_id,
                    project_id,
                    task_id,
                    all_tasks,
                    previous_results,
                )

        # Launch all tasks concurrently
        tasks = [
            asyncio.create_task(execute_with_limit(task_id))
            for task_id in level_tasks
        ]

        # Wait for all tasks to complete
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        # Parse results
        level_results = {}
        for result in results_list:
            if isinstance(result, Exception):
                logger.error("task_execution_exception", error=str(result))
                continue

            task_id, task_result = result
            level_results[task_id] = task_result

        return level_results

    async def _execute_single_task(
        self,
        db: AsyncSession,
        workspace: UserWorkerSpace,
        user_id: UUID,
        project_id: UUID,
        task_id: str,
        all_tasks: list[dict],
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a single task with agent.

        Args:
            db: Database session
            workspace: User workspace
            user_id: User ID
            project_id: Project ID
            task_id: Task ID to execute
            all_tasks: All tasks in plan
            previous_results: Results from previous executions

        Returns:
            Task result dict with success/error info
        """
        try:
            # Find task definition
            task = TaskGraphBuilder.get_task_by_id(all_tasks, task_id)
            if not task:
                return {
                    "task_id": task_id,
                    "success": False,
                    "error": f"Task {task_id} not found in plan",
                }

            # Determine which agent to use
            assigned_to = task.get("assigned_to", "Code")
            agent_id = await find_agent_by_name(
                db, user_id, project_id, assigned_to
            )

            if not agent_id:
                # Try by role as fallback
                role_agents = await get_agents_by_role(
                    db, project_id, AgentRole(assigned_to.lower()), user_id=user_id
                )
                if role_agents:
                    agent_id = role_agents[0].id
                else:
                    return {
                        "task_id": task_id,
                        "success": False,
                        "error": f"No agent found for {assigned_to}",
                    }

            # Prepare task message
            task_message = task.get("description", "")

            # Add context from previous results if available
            task_context = []
            for dep_task_id, dep_result in previous_results.items():
                if dep_result.get("success"):
                    task_context.append(
                        f"Previous result from {dep_task_id}: {dep_result.get('result', '')}"
                    )

            if task_context:
                task_message += "\n\nContext from previous tasks:\n"
                task_message += "\n".join(task_context)

            # Execute task on agent
            logger.info(
                "executing_task",
                task_id=task_id,
                agent_id=str(agent_id),
                assigned_to=assigned_to,
            )

            start_time = time.time()
            try:
                result = await asyncio.wait_for(
                    workspace.direct_execution(
                        agent_id=agent_id,
                        user_message=task_message,
                        task_id=task_id,
                    ),
                    timeout=self.task_timeout,
                )

                duration = time.time() - start_time

                return {
                    "task_id": task_id,
                    "success": True,
                    "result": result,
                    "duration": round(duration, 1),
                    "assigned_agent": assigned_to,
                }

            except asyncio.TimeoutError:
                return {
                    "task_id": task_id,
                    "success": False,
                    "error": f"Task execution timeout ({self.task_timeout}s)",
                    "assigned_agent": assigned_to,
                }

        except Exception as e:
            logger.error(
                "task_execution_error",
                task_id=task_id,
                error=str(e),
            )
            return {
                "task_id": task_id,
                "success": False,
                "error": str(e),
            }
