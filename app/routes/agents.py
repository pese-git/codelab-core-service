"""Agent management endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.manager import AgentManager
from app.database import get_db
from app.middleware.user_isolation import get_current_user_id
from app.qdrant_client import get_qdrant
from app.redis_client import get_redis
from app.schemas.agent import AgentConfig, AgentListResponse, AgentResponse, AgentUpdate

router = APIRouter(prefix="/my/agents", tags=["agents"])


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
    config: AgentConfig,
    manager: AgentManager = Depends(get_agent_manager),
) -> AgentResponse:
    """Create new agent."""
    return await manager.create_agent(config)


@router.get("/", response_model=AgentListResponse)
async def list_agents(
    manager: AgentManager = Depends(get_agent_manager),
) -> AgentListResponse:
    """List all user agents."""
    agents = await manager.list_agents()
    return AgentListResponse(agents=agents, total=len(agents))


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    manager: AgentManager = Depends(get_agent_manager),
) -> AgentResponse:
    """Get agent by ID."""
    agent = await manager.get_agent(agent_id)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: UUID,
    update: AgentUpdate,
    manager: AgentManager = Depends(get_agent_manager),
) -> AgentResponse:
    """Update agent configuration."""
    agent = await manager.update_agent(agent_id, update.config)
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(
    agent_id: UUID,
    manager: AgentManager = Depends(get_agent_manager),
) -> None:
    """Delete agent."""
    success = await manager.delete_agent(agent_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
