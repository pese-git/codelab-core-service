"""User Worker Space for managing project-specific resources and agents."""

import asyncio
import time
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
from app.vectorstore.agent_context_store import AgentContextStore

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

    # ========== ЭТАП 1: Методы работы с Qdrant контекстом (10.4) ==========

    async def get_agent_context_store(
        self, agent_id: UUID
    ) -> Optional[AgentContextStore]:
        """Get agent context store.

        Retrieves the context store for a specific agent, which is used for
        vector search and context retrieval in RAG operations.

        Args:
            agent_id: Agent ID

        Returns:
            AgentContextStore instance or None if agent not found

        Raises:
            Logs warning if agent not found
        """
        if not self.initialized:
            await self.initialize()

        agent = await self.agent_cache.get(agent_id)
        if not agent:
            logger.warning(
                "agent_not_found_for_context_store",
                agent_id=str(agent_id),
                project_id=self.project_id,
            )
            return None

        return agent.context_store

    async def search_context(
        self,
        agent_id: UUID,
        query: str,
        limit: int = 10,
        filter_success: Optional[bool] = None,
        filter_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Search in agent context using vector search.

        Performs semantic search in the agent's context store (Qdrant) to find
        relevant interactions and stored information.

        Args:
            agent_id: Agent ID
            query: Search query string
            limit: Maximum number of results (default 10)
            filter_success: Filter by successful interactions (optional)
            filter_type: Filter by interaction type e.g. "chat" (optional)

        Returns:
            List of context results with fields:
            - id: Point ID in Qdrant
            - score: Relevance score (0-1)
            - content: Interaction text
            - interaction_type: Type of interaction
            - timestamp: When it occurred
            - metadata: Additional data

        Raises:
            Logs warning if agent not found, returns empty list on error
        """
        context_store = await self.get_agent_context_store(agent_id)
        if not context_store:
            return []

        try:
            results = await context_store.search(
                query=query,
                limit=limit,
                filter_success=filter_success,
                filter_type=filter_type,
            )

            logger.info(
                "context_search_completed",
                agent_id=str(agent_id),
                query_length=len(query),
                results_count=len(results),
            )

            return results
        except Exception as e:
            logger.error(
                "context_search_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            return []

    async def add_context(
        self,
        agent_id: UUID,
        content: str,
        interaction_type: str = "chat",
        task_id: Optional[str] = None,
        success: bool = True,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        """Add interaction to agent context.

        Stores a new interaction (user message + agent response) in the agent's
        context store for use in future RAG operations.

        Args:
            agent_id: Agent ID
            content: Interaction text (e.g., "User: ... Agent: ...")
            interaction_type: Type of interaction (default "chat")
                e.g., "chat", "task_execution", "error_handling"
            task_id: Associated task ID (optional)
            success: Whether interaction was successful (default True)
            metadata: Additional metadata dict (optional)
                e.g., {"model": "gpt-4", "tokens": 150}

        Returns:
            Point ID in Qdrant if successful, None if error or agent not found

        Raises:
            Logs warning if agent not found, error on Qdrant error
        """
        context_store = await self.get_agent_context_store(agent_id)
        if not context_store:
            return None

        try:
            point_id = await context_store.add_interaction(
                content=content,
                interaction_type=interaction_type,
                task_id=task_id,
                success=success,
                metadata=metadata,
            )

            logger.info(
                "context_interaction_added",
                agent_id=str(agent_id),
                point_id=point_id,
                interaction_type=interaction_type,
            )

            return point_id
        except Exception as e:
            logger.error(
                "context_add_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            return None

    async def clear_context(self, agent_id: UUID) -> bool:
        """Clear all context for an agent.

        Removes all interactions and vectors stored for the agent in Qdrant.
        Used when resetting or deleting an agent.

        Args:
            agent_id: Agent ID

        Returns:
            True if successful, False if error or agent not found

        Raises:
            Logs warning if agent not found, error on Qdrant error
        """
        context_store = await self.get_agent_context_store(agent_id)
        if not context_store:
            return False

        try:
            await context_store.clear()

            logger.info(
                "context_cleared",
                agent_id=str(agent_id),
                project_id=self.project_id,
            )

            return True
        except Exception as e:
            logger.error(
                "context_clear_error",
                agent_id=str(agent_id),
                error=str(e),
            )
            return False

    # ========== ЭТАП 2: Методы координации режимов выполнения (10.5) ==========

    async def direct_execution(
        self,
        agent_id: UUID,
        user_message: str,
        session_history: Optional[list[dict[str, str]]] = None,
        task_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute task directly through a specific agent.

        MODE: User explicitly selects an agent.

        Process:
        1. Get agent from workspace cache
        2. Add input message to context (optional)
        3. Execute agent.execute()
        4. Add output result to context if successful
        5. Return structured result

        Args:
            agent_id: Target agent ID
            user_message: User message
            session_history: Session history (optional)
            task_id: Task ID for correlation (optional)
            metadata: Additional metadata (optional)

        Returns:
            {
                "success": bool,
                "response": str,  # Agent response or error message
                "agent_id": str,
                "agent_name": str,
                "context_used": int,  # Number of context results used
                "tokens_used": int,   # Tokens from LLM
                "timestamp": str (ISO format),
                "execution_time_ms": float
            }

        Raises:
            ValueError if agent not found
        """
        if not self.initialized:
            await self.initialize()

        # Get agent
        agent = await self.get_agent(agent_id)
        if not agent:
            logger.error(
                "direct_execution_agent_not_found",
                agent_id=str(agent_id),
                project_id=self.project_id,
            )
            raise ValueError(f"Agent not found: {agent_id}")

        # Add input context (for tracking)
        await self.add_context(
            agent_id=agent_id,
            content=f"[INPUT] {user_message}",
            interaction_type="direct_execution_input",
            task_id=task_id,
            metadata=metadata,
        )

        # Execute
        start_time = time.time()
        try:
            result = await agent.execute(
                user_message=user_message,
                session_history=session_history,
                task_id=task_id,
            )
            execution_time = (time.time() - start_time) * 1000  # ms

            # Add output context if successful
            if result.get("success"):
                await self.add_context(
                    agent_id=agent_id,
                    content=f"[OUTPUT] {result.get('response')}",
                    interaction_type="direct_execution_output",
                    task_id=task_id,
                    success=True,
                    metadata={
                        "tokens": result.get("tokens_used"),
                        "execution_time_ms": execution_time,
                    },
                )

            logger.info(
                "direct_execution_completed",
                agent_id=str(agent_id),
                success=result.get("success"),
                execution_time_ms=execution_time,
            )

            return {
                "success": result.get("success", False),
                "response": result.get("response") or result.get("error"),
                "agent_id": str(agent_id),
                "agent_name": agent.config.name,
                "context_used": result.get("context_used", 0),
                "tokens_used": result.get("tokens_used", 0),
                "timestamp": datetime.utcnow().isoformat(),
                "execution_time_ms": execution_time,
            }
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                "direct_execution_error",
                agent_id=str(agent_id),
                error=str(e),
                execution_time_ms=execution_time,
            )
            raise

    async def orchestrated_execution(
        self,
        user_message: str,
        session_history: Optional[list[dict[str, str]]] = None,
        task_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Execute task through Project Orchestrator (intelligent routing).

        MODE: System automatically selects the best agent for the request.

        Process:
        1. Get Project Orchestrator
        2. Orchestrator analyzes request and selects best agent
        3. Execute through direct_execution
        4. Return result with routing information

        Args:
            user_message: User message
            session_history: Session history (optional)
            task_id: Task ID (optional)
            metadata: Additional metadata (optional)

        Returns:
            {
                "success": bool,
                "response": str,
                "selected_agent_id": str,
                "selected_agent_name": str,
                "routing_score": float,  # Confidence score (0-1)
                "context_used": int,
                "tokens_used": int,
                "timestamp": str,
                "execution_time_ms": float
            }

        Raises:
            ValueError if no agents available
        """
        if not self.initialized:
            await self.initialize()

        agents = await self.list_agents_for_project()
        if not agents:
            logger.error(
                "orchestrated_execution_no_agents",
                project_id=self.project_id,
            )
            raise ValueError("No agents available for orchestration")

        # Get Orchestrator or use fallback
        selected_agent_id = agents[0]
        routing_score = 1.0

        try:
            if self.agent_manager:
                # Try to get orchestrator for intelligent routing
                # For now, use first agent as fallback
                logger.info(
                    "orchestrated_execution_routing",
                    agent_count=len(agents),
                    selected_agent_id=str(selected_agent_id),
                )
        except Exception as e:
            logger.warning(
                "orchestration_routing_error",
                error=str(e),
            )
            # Keep fallback
            routing_score = 0.5

        # Execute through direct execution
        start_time = time.time()
        result = await self.direct_execution(
            agent_id=selected_agent_id,
            user_message=user_message,
            session_history=session_history,
            task_id=task_id,
            metadata=metadata,
        )
        execution_time = (time.time() - start_time) * 1000

        logger.info(
            "orchestrated_execution_completed",
            selected_agent_id=str(selected_agent_id),
            routing_score=routing_score,
        )

        return {
            **result,
            "selected_agent_id": str(selected_agent_id),
            "routing_score": routing_score,
            "execution_time_ms": execution_time,
        }

    async def handle_message(
        self,
        message_content: str,
        target_agent_id: Optional[UUID] = None,
        session_history: Optional[list[dict[str, str]]] = None,
        task_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Unified API for message handling (auto-selects mode).

        Automatically determines execution mode:
        - If target_agent_id is provided → DIRECT mode
        - If target_agent_id is None → ORCHESTRATED mode

        Args:
            message_content: Message text
            target_agent_id: Target agent ID (optional)
            session_history: Session history (optional)
            task_id: Task ID (optional)
            metadata: Additional metadata (optional)

        Returns:
            Result from direct_execution or orchestrated_execution

        Raises:
            ValueError if invalid arguments
        """
        if not message_content:
            raise ValueError("message_content cannot be empty")

        if target_agent_id:
            # Direct execution mode
            logger.info(
                "handle_message_direct_mode",
                agent_id=str(target_agent_id),
                project_id=self.project_id,
            )
            return await self.direct_execution(
                agent_id=target_agent_id,
                user_message=message_content,
                session_history=session_history,
                task_id=task_id,
                metadata=metadata,
            )
        else:
            # Orchestrated execution mode
            logger.info(
                "handle_message_orchestrated_mode",
                project_id=self.project_id,
            )
            return await self.orchestrated_execution(
                user_message=message_content,
                session_history=session_history,
                task_id=task_id,
                metadata=metadata,
            )

    # ========== ЭТАП 3: Методы для получения метрик (10.6) ==========

    async def get_agent_status(self, agent_id: UUID) -> Optional[dict[str, Any]]:
        """Get detailed status of a specific agent.

        Returns comprehensive information about agent state, execution history,
        context, and performance metrics.

        Args:
            agent_id: Agent ID

        Returns:
            {
                "agent_id": str,
                "agent_name": str,
                "is_active": bool,
                "is_in_cache": bool,

                "execution": {
                    "total_executions": int,
                    "successful": int,
                    "failed": int,
                    "last_execution": str (ISO format or None),
                    "avg_execution_time_ms": float,
                    "last_execution_time_ms": float
                },

                "context": {
                    "total_vectors": int,
                    "context_search_enabled": bool
                },

                "performance": {
                    "cache_hit_rate": float (0-1),
                    "error_rate": float (0-1),
                    "avg_tokens_per_execution": float
                },

                "config": {
                    "model": str,
                    "temperature": float,
                    "max_tokens": int,
                    "concurrency_limit": int
                }
            }

        Returns None if agent not found
        """
        agent = await self.get_agent(agent_id)
        if not agent:
            logger.warning(
                "agent_status_not_found",
                agent_id=str(agent_id),
                project_id=self.project_id,
            )
            return None

        # Get context stats
        context_stats = await agent.context_store.get_stats()

        return {
            "agent_id": str(agent_id),
            "agent_name": agent.config.name,
            "is_active": agent_id in self.active_agents,
            "is_in_cache": await self.agent_cache.get(agent_id) is not None,
            "execution": {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "last_execution": None,
                "avg_execution_time_ms": 0.0,
                "last_execution_time_ms": 0.0,
            },
            "context": {
                "total_vectors": context_stats.get("total_vectors", 0),
                "context_search_enabled": context_stats.get("enabled", False),
            },
            "performance": {
                "cache_hit_rate": 0.0,
                "error_rate": 0.0,
                "avg_tokens_per_execution": 0.0,
            },
            "config": {
                "model": agent.config.model,
                "temperature": agent.config.temperature,
                "max_tokens": agent.config.max_tokens,
                "concurrency_limit": agent.config.concurrency_limit,
            },
        }

    async def get_metrics(self) -> dict[str, Any]:
        """Get comprehensive metrics for Worker Space.

        Includes overall status, agent information, cache stats, context stats,
        and health information.

        Returns:
            {
                "user_id": str,
                "project_id": str,
                "initialized": bool,
                "initialization_time": str (ISO format or None),
                "uptime_seconds": float,

                "agents": {
                    "total": int,
                    "active": int,
                    "list": [...]
                },

                "cache": {
                    "size": int,
                    "max_size": int,
                    "hit_rate": float (0-1),
                    "ttl_seconds": int
                },

                "context": {
                    "total_vectors": int,
                    "collections_count": int,
                    "avg_vectors_per_agent": float
                },

                "health": {
                    "is_healthy": bool,
                    "last_check": str (ISO format),
                    "issues": list[str]
                },

                "timestamp": str (ISO format)
            }
        """
        try:
            # Calculate uptime
            uptime = 0.0
            if self.initialization_time:
                uptime = (
                    datetime.utcnow() - self.initialization_time
                ).total_seconds()

            # Collect agent metrics
            agents_list = []
            total_vectors = 0

            for agent_id in self.active_agents.keys():
                status = await self.get_agent_status(agent_id)
                if status:
                    agents_list.append({
                        "id": status["agent_id"],
                        "name": status["agent_name"],
                        "status": "active" if status["is_active"] else "inactive",
                        "context_vectors": status["context"]["total_vectors"],
                    })
                    total_vectors += status["context"]["total_vectors"]

            # Calculate averages
            avg_vectors_per_agent = (
                total_vectors / len(self.active_agents)
                if self.active_agents
                else 0.0
            )

            # Health check
            health_issues = []
            if not self.initialized:
                health_issues.append("Worker space not initialized")
            if not self.active_agents:
                health_issues.append("No active agents")

            return {
                "user_id": str(self.user_id),
                "project_id": self.project_id,
                "initialized": self.initialized,
                "initialization_time": (
                    self.initialization_time.isoformat()
                    if self.initialization_time
                    else None
                ),
                "uptime_seconds": uptime,
                "agents": {
                    "total": len(self.active_agents),
                    "active": len(self.active_agents),
                    "list": agents_list,
                },
                "cache": {
                    "size": self.agent_cache.get_size(),
                    "max_size": len(self.active_agents),
                    "hit_rate": 0.0,
                    "ttl_seconds": self.agent_cache.ttl_seconds,
                },
                "context": {
                    "total_vectors": total_vectors,
                    "collections_count": len(self.active_agents),
                    "avg_vectors_per_agent": avg_vectors_per_agent,
                },
                "health": {
                    "is_healthy": self.is_healthy(),
                    "last_check": datetime.utcnow().isoformat(),
                    "issues": health_issues,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(
                "metrics_collection_error",
                project_id=self.project_id,
                error=str(e),
            )
            return {
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

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
