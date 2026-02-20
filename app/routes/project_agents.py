"""Per-project agent management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.manager import AgentManager
from app.core.user_worker_space import UserWorkerSpace
from app.database import get_db
from app.dependencies import get_worker_space
from app.middleware.project_validation import get_project_with_validation
from app.middleware.user_isolation import get_current_user_id
from app.models.user_project import UserProject
from app.qdrant_client import get_qdrant
from app.redis_client import get_redis
from app.schemas.agent import AgentConfig, AgentCreate, AgentListResponse, AgentResponse, AgentUpdate

router = APIRouter(prefix="/my/projects/{project_id}/agents", tags=["project-agents"])


async def get_agent_manager(
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    qdrant: AsyncQdrantClient | None = Depends(get_qdrant),
) -> AgentManager:
    """Get agent manager dependency."""
    user_id = get_current_user_id(request)
    return AgentManager(db=db, redis=redis, qdrant=qdrant, user_id=user_id)


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=AgentResponse)
async def create_agent(
    project_id: UUID,
    agent_data: AgentCreate,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    manager: AgentManager = Depends(get_agent_manager),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> AgentResponse:
    """Create new agent in project.

    Args:
        project_id: Project UUID from path
        agent_data: Agent creation data (name + config)
        request: FastAPI request
        project: Validated project object
        manager: Agent manager

    Returns:
        Created agent information
    """
    return await manager.create_agent_with_project(agent_data.name, agent_data.config, project_id)


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    project_id: UUID,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    manager: AgentManager = Depends(get_agent_manager),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> AgentListResponse:
    """List all agents in project.

    Args:
        project_id: Project UUID from path
        request: FastAPI request
        project: Validated project object
        manager: Agent manager

    Returns:
        List of agents in project
    """
    agents = await manager.list_agents_by_project(project_id)
    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    project_id: UUID,
    agent_id: UUID,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    manager: AgentManager = Depends(get_agent_manager),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> AgentResponse:
    """Get agent by ID from project.

    Args:
        project_id: Project UUID from path
        agent_id: Agent UUID from path
        request: FastAPI request
        project: Validated project object
        manager: Agent manager

    Returns:
        Agent information

    Raises:
        HTTPException: 404 if agent not found in project
    """
    agent = await manager.get_agent_by_project(agent_id, project_id)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found in project",
        )

    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    project_id: UUID,
    agent_id: UUID,
    agent_data: AgentUpdate,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    manager: AgentManager = Depends(get_agent_manager),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> AgentResponse:
    """Update agent in project.

    Args:
        project_id: Project UUID from path
        agent_id: Agent UUID from path
        agent_data: Updated agent data (name + config)
        request: FastAPI request
        project: Validated project object
        manager: Agent manager

    Returns:
        Updated agent information

    Raises:
        HTTPException: 404 if agent not found in project
    """
    agent = await manager.update_agent_with_project(agent_id, project_id, agent_data.name, agent_data.config)

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found in project",
        )

    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    project_id: UUID,
    agent_id: UUID,
    request: Request,
    project: UserProject = Depends(get_project_with_validation),
    manager: AgentManager = Depends(get_agent_manager),
    workspace: UserWorkerSpace = Depends(get_worker_space),
) -> None:
    """Delete agent from project.

    Args:
        project_id: Project UUID from path
        agent_id: Agent UUID from path
        request: FastAPI request
        project: Validated project object
        manager: Agent manager

    Raises:
        HTTPException: 404 if agent not found in project
    """
    deleted = await manager.delete_agent_with_project(agent_id, project_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found in project",
        )
