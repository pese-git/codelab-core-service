"""Monitoring and diagnostics endpoints."""

from fastapi import APIRouter, Depends

from app.core.worker_space_manager import get_worker_space_manager, WorkerSpaceManager
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["monitoring"])


async def get_manager_dependency() -> WorkerSpaceManager:
    """Get WorkerSpaceManager instance."""
    return get_worker_space_manager()


@router.get("/workspaces/stats")
async def get_workspace_stats(
    manager: WorkerSpaceManager = Depends(get_manager_dependency),
) -> dict:
    """
    Get statistics about active worker spaces.

    Returns per-project workspace statistics:
    - active_spaces: total number of active workspaces
    - spaces: dictionary with stats for each workspace
      - user_id: workspace owner
      - project_id: project ID
      - initialized: whether workspace is initialized
      - active_agents: number of active agents
      - cache_size: size of agent cache
      - agent_ids: list of agent IDs
      - initialization_time: when workspace was initialized

    Example response:
    ```json
    {
        "active_spaces": 2,
        "spaces": {
            "user123_proj001": {
                "user_id": "user123",
                "project_id": "proj001",
                "initialized": true,
                "active_agents": 3,
                "cache_size": 3,
                "agent_ids": ["agent1", "agent2", "agent3"],
                "initialization_time": "2026-02-18T12:00:00"
            },
            "user123_proj002": {
                "user_id": "user123",
                "project_id": "proj002",
                "initialized": true,
                "active_agents": 2,
                "cache_size": 2,
                "agent_ids": ["agent4", "agent5"],
                "initialization_time": "2026-02-18T12:10:00"
            }
        }
    }
    ```
    """
    stats = manager.get_stats()
    logger.info("workspace_stats_requested", active_spaces=stats["active_spaces"])
    return stats


@router.get("/workspaces/health")
async def get_workspace_health(
    manager: WorkerSpaceManager = Depends(get_manager_dependency),
) -> dict:
    """
    Get health check status for all active workspaces.

    Returns:
    - healthy: boolean indicating if all workspaces are healthy
    - total_spaces: total number of active workspaces
    - healthy_spaces: number of healthy workspaces
    - unhealthy_spaces: list of unhealthy workspace keys
    - details: detailed health info for each workspace

    Example response:
    ```json
    {
        "healthy": true,
        "total_spaces": 2,
        "healthy_spaces": 2,
        "unhealthy_spaces": [],
        "details": {
            "user123_proj001": {
                "healthy": true,
                "agents": 3,
                "initialized": true
            },
            "user123_proj002": {
                "healthy": true,
                "agents": 2,
                "initialized": true
            }
        }
    }
    ```
    """
    stats = manager.get_stats()
    details = {}
    unhealthy_spaces = []

    for key, space_stats in stats.get("spaces", {}).items():
        is_healthy = space_stats.get("initialized", False) and space_stats.get(
            "active_agents", 0
        ) > 0

        details[key] = {
            "healthy": is_healthy,
            "agents": space_stats.get("active_agents", 0),
            "initialized": space_stats.get("initialized", False),
        }

        if not is_healthy:
            unhealthy_spaces.append(key)

    overall_healthy = len(unhealthy_spaces) == 0

    logger.info(
        "workspace_health_requested",
        healthy=overall_healthy,
        total_spaces=stats["active_spaces"],
        healthy_spaces=stats["active_spaces"] - len(unhealthy_spaces),
    )

    return {
        "healthy": overall_healthy,
        "total_spaces": stats["active_spaces"],
        "healthy_spaces": stats["active_spaces"] - len(unhealthy_spaces),
        "unhealthy_spaces": unhealthy_spaces,
        "details": details,
    }
