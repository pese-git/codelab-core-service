"""Agent manager for CRUD operations."""

from typing import Any
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.contextual_agent import ContextualAgent
from app.logging_config import get_logger
from app.models.user_agent import UserAgent
from app.schemas.agent import AgentConfig, AgentResponse, AgentStatus

logger = get_logger(__name__)


class AgentManager:
    """Manager for agent CRUD operations."""

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        qdrant: AsyncQdrantClient,
        user_id: UUID,
    ):
        """Initialize agent manager."""
        self.db = db
        self.redis = redis
        self.qdrant = qdrant
        self.user_id = user_id

    async def create_agent(self, config: AgentConfig) -> AgentResponse:
        """Create new agent."""
        # Create database record
        # Exclude 'name' from config as it's stored separately in UserAgent.name
        config_dict = config.model_dump(exclude={'name'})
        agent = UserAgent(
            user_id=self.user_id,
            name=config.name,
            config=config_dict,
            status=AgentStatus.READY.value,
        )
        self.db.add(agent)
        await self.db.flush()

        # Initialize contextual agent
        contextual_agent = ContextualAgent(
            agent_id=agent.id,
            user_id=self.user_id,
            config=config,
            qdrant_client=self.qdrant,
        )
        await contextual_agent.initialize()

        # Cache config in Redis
        cache_key = f"agent:{agent.id}:config"
        await self.redis.setex(cache_key, 300, config.model_dump_json())

        logger.info(
            "agent_created",
            agent_id=str(agent.id),
            user_id=str(self.user_id),
            agent_name=config.name,
        )

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            config=config,
        )

    async def get_agent(self, agent_id: UUID) -> AgentResponse | None:
        """Get agent by ID."""
        result = await self.db.execute(
            select(UserAgent).where(
                UserAgent.id == agent_id,
                UserAgent.user_id == self.user_id,
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            config=AgentConfig(name=agent.name, **agent.config),
        )

    async def list_agents(self) -> list[AgentResponse]:
        """List all user agents."""
        result = await self.db.execute(
            select(UserAgent).where(UserAgent.user_id == self.user_id)
        )
        agents = result.scalars().all()

        return [
            AgentResponse(
                id=agent.id,
                name=agent.name,
                status=AgentStatus(agent.status),
                created_at=agent.created_at,
                config=AgentConfig(name=agent.name, **agent.config),
            )
            for agent in agents
        ]

    async def update_agent(self, agent_id: UUID, config: AgentConfig) -> AgentResponse | None:
        """Update agent configuration."""
        result = await self.db.execute(
            select(UserAgent).where(
                UserAgent.id == agent_id,
                UserAgent.user_id == self.user_id,
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        # Update config (exclude 'name' as it's stored separately)
        agent.name = config.name
        agent.config = config.model_dump(exclude={'name'})
        await self.db.flush()

        # Update cache
        cache_key = f"agent:{agent.id}:config"
        await self.redis.setex(cache_key, 300, config.model_dump_json())

        logger.info(
            "agent_updated",
            agent_id=str(agent.id),
            user_id=str(self.user_id),
        )

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            config=config,
        )

    async def delete_agent(self, agent_id: UUID) -> bool:
        """Delete agent."""
        result = await self.db.execute(
            select(UserAgent).where(
                UserAgent.id == agent_id,
                UserAgent.user_id == self.user_id,
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return False

        # Delete Qdrant collection
        collection_name = f"user{self.user_id}_{agent.name}_context"
        try:
            await self.qdrant.delete_collection(collection_name=collection_name)
        except Exception as e:
            logger.warning(
                "qdrant_collection_delete_failed",
                collection=collection_name,
                error=str(e),
            )

        # Delete cache
        cache_key = f"agent:{agent.id}:config"
        await self.redis.delete(cache_key)

        # Delete from database
        await self.db.delete(agent)
        await self.db.flush()

        logger.info(
            "agent_deleted",
            agent_id=str(agent.id),
            user_id=str(self.user_id),
        )

        return True

    async def get_agent_by_name(self, name: str) -> AgentResponse | None:
        """Get agent by name."""
        result = await self.db.execute(
            select(UserAgent).where(
                UserAgent.name == name,
                UserAgent.user_id == self.user_id,
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            config=AgentConfig(name=agent.name, **agent.config),
        )
