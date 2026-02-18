"""User Worker Space for managing project-specific resources and agents."""

import asyncio
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.contextual_agent import ContextualAgent
from app.agents.manager import AgentManager
from app.config import settings
from app.core.agent_bus import AgentBus
from app.logging_config import get_logger
from app.schemas.agent import AgentConfig

logger = get_logger(__name__)


class AgentCache:
    """Cache for agent instances and configurations."""

    def __init__(self, redis: Optional[Redis] = None, ttl_seconds: int = 300):
        """Initialize agent cache.

        Args:
            redis: Redis client for distributed caching
            ttl_seconds: Cache TTL in seconds
        """
        self.redis = redis
        self.ttl_seconds = ttl_seconds
        self.local_cache: dict[UUID, ContextualAgent] = {}
        self.cache_metadata: dict[UUID, datetime] = {}

    async def get(self, agent_id: UUID) -> Optional[ContextualAgent]:
        """Get agent from cache.

        Args:
            agent_id: Agent ID

        Returns:
            Agent instance or None
        """
        if agent_id in self.local_cache:
            return self.local_cache[agent_id]
        return None

    async def set(self, agent_id: UUID, agent: ContextualAgent) -> None:
        """Store agent in cache.

        Args:
            agent_id: Agent ID
            agent: Agent instance
        """
        self.local_cache[agent_id] = agent
        self.cache_metadata[agent_id] = datetime.utcnow()

        if self.redis:
            try:
                # Store in Redis for distributed cache
                cache_key = f"agent:{agent_id}"
                # Note: In production, serialize agent config instead of agent instance
                await self.redis.setex(
                    cache_key, self.ttl_seconds, str(agent_id)
                )
            except Exception as e:
                logger.warning(
                    "redis_cache_error",
                    agent_id=str(agent_id),
                    error=str(e),
                )

    async def invalidate(self, agent_id: UUID) -> None:
        """Invalidate cache for agent.

        Args:
            agent_id: Agent ID
        """
        if agent_id in self.local_cache:
            del self.local_cache[agent_id]

        if agent_id in self.cache_metadata:
            del self.cache_metadata[agent_id]

        if self.redis:
            try:
                cache_key = f"agent:{agent_id}"
                await self.redis.delete(cache_key)
            except Exception as e:
                logger.warning(
                    "redis_invalidate_error",
                    agent_id=str(agent_id),
                    error=str(e),
                )

    async def clear(self) -> None:
        """Clear all cached agents."""
        self.local_cache.clear()
        self.cache_metadata.clear()

        if self.redis:
            try:
                await self.redis.delete("agent:*")
            except Exception as e:
                logger.warning("redis_clear_error", error=str(e))

    def get_size(self) -> int:
        """Get cache size.

        Returns:
            Number of cached agents
        """
        return len(self.local_cache)


class UserWorkerSpace:
    """Worker space for managing user's project resources."""

    def __init__(
        self,
        user_id: UUID,
        project_id: str,
        db: AsyncSession,
        redis: Optional[Redis],
        qdrant: Optional[AsyncQdrantClient],
        agent_bus: AgentBus,
    ):
        """Initialize user worker space.

        Args:
            user_id: User ID
            project_id: Project ID
            db: Database session
            redis: Redis client
            qdrant: Qdrant client
            agent_bus: Agent bus instance
        """
        self.user_id = user_id
        self.project_id = project_id
        self.user_prefix = f"user{user_id}"
        self.project_prefix = f"project{project_id}"

        self.db = db
        self.redis = redis
        self.qdrant = qdrant
        self.agent_bus = agent_bus

        self.agent_cache = AgentCache(redis=redis)
        self.agent_manager: Optional[AgentManager] = None
        self.initialized = False
        self.initialization_time: Optional[datetime] = None
        self.active_agents: dict[UUID, ContextualAgent] = {}
        self.task_queue: dict[UUID, asyncio.Queue[Any]] = {}
        self.lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize worker space.

        This includes:
        - Creating agent manager
        - Loading project agents
        - Registering agents in Agent Bus
        """
        async with self.lock:
            if self.initialized:
                logger.info(
                    "worker_space_already_initialized",
                    user_id=str(self.user_id),
                    project_id=self.project_id,
                )
                return

            try:
                self.agent_manager = AgentManager(
                    db=self.db,
                    redis=self.redis,
                    qdrant=self.qdrant,
                    user_id=self.user_id,
                )

                # Load all agents for this project
                agents = await self.agent_manager.list_agents()

                for agent_db_model in agents:
                    await self._register_agent(agent_db_model)

                self.initialized = True
                self.initialization_time = datetime.utcnow()

                logger.info(
                    "worker_space_initialized",
                    user_id=str(self.user_id),
                    project_id=self.project_id,
                    agent_count=len(agents),
                )
            except Exception as e:
                logger.error(
                    "worker_space_initialization_error",
                    user_id=str(self.user_id),
                    project_id=self.project_id,
                    error=str(e),
                )
                raise

    async def _register_agent(self, agent_db_model: Any) -> None:
        """Register agent in worker space and Agent Bus.

        Args:
            agent_db_model: Agent database model
        """
        try:
            # Parse agent config
            config_dict = agent_db_model.config
            if isinstance(config_dict, dict):
                agent_config = AgentConfig.model_validate(config_dict)
            else:
                agent_config = config_dict

            # Create ContextualAgent
            agent = ContextualAgent(
                agent_id=agent_db_model.id,
                user_id=self.user_id,
                config=agent_config,
                qdrant_client=self.qdrant,
            )

            # Cache agent
            await self.agent_cache.set(agent_db_model.id, agent)
            self.active_agents[agent_db_model.id] = agent

            # Register in Agent Bus
            concurrency_limit = agent_config.concurrency_limit

            async def agent_handler(task_item: Any) -> Any:
                """Handle agent task."""
                return await agent.execute(task_item.payload)

            await self.agent_bus.register_agent(
                agent_id=agent_db_model.id,
                handler=agent_handler,
                max_concurrency=concurrency_limit,
            )

            logger.info(
                "agent_registered_in_workspace",
                agent_id=str(agent_db_model.id),
                user_id=str(self.user_id),
                project_id=self.project_id,
            )
        except Exception as e:
            logger.error(
                "agent_registration_error",
                agent_id=str(agent_db_model.id),
                error=str(e),
            )
            raise

    async def get_agent(self, agent_id: UUID) -> Optional[ContextualAgent]:
        """Get agent from cache.

        Args:
            agent_id: Agent ID

        Returns:
            Agent instance or None
        """
        if not self.initialized:
            await self.initialize()

        return await self.agent_cache.get(agent_id)

    async def add_agent(self, agent_config: AgentConfig) -> UUID:
        """Add new agent to worker space.

        Args:
            agent_config: Agent configuration

        Returns:
            Agent ID
        """
        if not self.initialized:
            await self.initialize()

        # Create agent in database
        agent = await self.agent_manager.create_agent(agent_config)

        # Register in worker space
        agent_db = await self.agent_manager.get_agent(agent.id)
        if agent_db:
            await self._register_agent(agent_db)

        return agent.id

    async def remove_agent(self, agent_id: UUID) -> bool:
        """Remove agent from worker space.

        Args:
            agent_id: Agent ID

        Returns:
            True if removed, False if not found
        """
        try:
            # Deregister from Agent Bus
            await self.agent_bus.deregister_agent(agent_id)

            # Remove from cache
            await self.agent_cache.invalidate(agent_id)

            # Remove from active agents
            if agent_id in self.active_agents:
                del self.active_agents[agent_id]

            # Delete from database
            await self.agent_manager.delete_agent(agent_id)

            logger.info(
                "agent_removed_from_workspace",
                agent_id=str(agent_id),
                user_id=str(self.user_id),
                project_id=self.project_id,
            )

            return True
        except Exception as e:
            logger.error(
                "agent_removal_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            return False

    async def get_agent_stats(self) -> dict[str, Any]:
        """Get worker space statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "user_id": str(self.user_id),
            "project_id": self.project_id,
            "initialized": self.initialized,
            "initialization_time": (
                self.initialization_time.isoformat()
                if self.initialization_time
                else None
            ),
            "active_agents": len(self.active_agents),
            "cache_size": self.agent_cache.get_size(),
            "agent_ids": [str(aid) for aid in self.active_agents.keys()],
        }

    async def reload_agent(self, agent_id: UUID) -> Optional[ContextualAgent]:
        """Reload agent configuration from database.

        Args:
            agent_id: Agent ID

        Returns:
            Reloaded agent or None
        """
        await self.agent_cache.invalidate(agent_id)

        if agent_id in self.active_agents:
            del self.active_agents[agent_id]

        return await self.get_agent(agent_id)

    async def list_agents_for_project(self) -> list[UUID]:
        """Get all agent IDs for this project.

        Returns:
            List of agent IDs
        """
        return list(self.active_agents.keys())

    async def send_task_to_agent(
        self, agent_id: UUID, task_payload: dict[str, Any]
    ) -> bool:
        """Send task to agent via Agent Bus.

        Args:
            agent_id: Agent ID
            task_payload: Task payload

        Returns:
            True if task sent, False otherwise
        """
        if agent_id not in self.active_agents:
            logger.warning(
                "agent_not_active",
                agent_id=str(agent_id),
                project_id=self.project_id,
            )
            return False

        try:
            await self.agent_bus.send_task(
                agent_id=agent_id,
                payload=task_payload,
                callback=None,
            )
            return True
        except Exception as e:
            logger.error(
                "task_send_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            return False

    async def cleanup(self) -> None:
        """Cleanup worker space.

        This includes:
        - Deregistering all agents from Agent Bus
        - Clearing cache
        - Closing connections
        """
        async with self.lock:
            if not self.initialized:
                return

            try:
                # Deregister all agents
                for agent_id in list(self.active_agents.keys()):
                    try:
                        await self.agent_bus.deregister_agent(agent_id)
                    except Exception as e:
                        logger.warning(
                            "agent_deregister_error",
                            agent_id=str(agent_id),
                            error=str(e),
                        )

                # Clear cache
                await self.agent_cache.clear()
                self.active_agents.clear()

                self.initialized = False

                logger.info(
                    "worker_space_cleanup",
                    user_id=str(self.user_id),
                    project_id=self.project_id,
                )
            except Exception as e:
                logger.error(
                    "worker_space_cleanup_error",
                    user_id=str(self.user_id),
                    project_id=self.project_id,
                    error=str(e),
                )

    async def reset(self) -> None:
        """Reset worker space.

        This stops all agents and reinitializes.
        """
        await self.cleanup()
        await self.initialize()

    def is_healthy(self) -> bool:
        """Check if worker space is healthy.

        Returns:
            True if healthy
        """
        if not self.initialized:
            return False

        # Check if all agents are still registered
        return len(self.active_agents) > 0
