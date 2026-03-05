"""FastAPI dependencies for worker space management."""

from uuid import UUID

from fastapi import Depends, Request
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.user_worker_space import UserWorkerSpace
from app.core.worker_space_manager import get_worker_space_manager, WorkerSpaceManager
from app.core.stream_manager import get_stream_manager
from app.database import get_db
from app.logging_config import get_logger
from app.middleware.user_isolation import get_current_user_id
from app.models.user_project import UserProject
from app.qdrant_client import get_qdrant
from app.redis_client import get_redis
from app.vectorstore.agent_context_store import AgentContextStore

logger = get_logger(__name__)


def get_current_user(request: Request) -> UUID:
    """Get current authenticated user ID from request context."""
    return get_current_user_id(request)


async def get_worker_space(
    project_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    qdrant: AsyncQdrantClient | None = Depends(get_qdrant),
) -> UserWorkerSpace:
    """
    Get or create UserWorkerSpace for current user and project.

    This dependency ensures that:
    - UserWorkerSpace is initialized on first access to project
    - All backend resources (cache, agent_bus, qdrant) are per-project
    - User isolation is enforced at the workspace level

    Args:
        project_id: Project UUID from path parameter
        request: FastAPI request with user context
        db: Database session
        redis: Redis client
        qdrant: Qdrant client

    Returns:
        UserWorkerSpace for the current (user_id, project_id) pair

    Raises:
        HTTPException: If workspace cannot be created
    """
    user_id = get_current_user_id(request)

    manager = get_worker_space_manager()

    space = await manager.get_or_create(
        user_id=user_id,
        project_id=str(project_id),
        db=db,
        redis=redis,
        qdrant=qdrant,
    )

    # Attach project workspace root and stream manager for this request.
    project_result = await db.execute(
        select(UserProject).where(
            UserProject.id == project_id,
            UserProject.user_id == user_id,
        )
    )
    project = project_result.scalar_one_or_none()
    if project:
        space.set_workspace_root(project.workspace_path)

    stream_manager = await get_stream_manager(redis)
    space.set_stream_manager(stream_manager)
    
    # IMPORTANT: Configure executor BEFORE initializing agents
    # so that tool_executor is available when agents are loaded
    space.configure_executor()
    
    # Initialize agents AFTER executor is configured
    # This ensures tool_executor is passed to ContextualAgent
    if not space.initialized:
        await space.initialize()

    logger.debug(
        "workspace_obtained",
        user_id=str(user_id),
        project_id=str(project_id),
        initialized=space.initialized,
        active_agents=len(space.active_agents),
    )

    return space


async def get_agent_context_store(
    agent_id: UUID,
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> AgentContextStore | None:
    """
    Get agent context store (Qdrant) for RAG operations.

    This dependency retrieves the context store for a specific agent,
    which is used for vector search and context retrieval.

    Args:
        agent_id: Agent UUID
        workspace: User workspace from get_worker_space dependency

    Returns:
        AgentContextStore instance or None if agent not found or disabled

    Note:
        Returns None if Qdrant is disabled in settings
    """
    if not workspace.initialized:
        await workspace.initialize()

    context_store = await workspace.get_agent_context_store(agent_id)

    logger.debug(
        "context_store_obtained",
        agent_id=str(agent_id),
        enabled=context_store is not None and context_store.enabled,
    )

    return context_store
