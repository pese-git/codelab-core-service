"""Agent manager for CRUD operations."""

from typing import Any, TYPE_CHECKING
from uuid import UUID

from qdrant_client import AsyncQdrantClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.contextual_agent import ContextualAgent
from app.logging_config import get_logger
from app.models.user_agent import UserAgent
from app.models.user_llm_provider import UserLLMProvider
from app.schemas.agent import AgentConfig, AgentResponse, AgentStatus

if TYPE_CHECKING:
    from app.core.tools.executor import ToolExecutor

logger = get_logger(__name__)


class AgentProviderNotFoundError(Exception):
    """Raised when LLM provider not found."""
    pass


class InvalidAgentProviderError(Exception):
    """Raised when LLM provider is invalid."""
    pass


class AgentManager:
    """Manager for agent CRUD operations."""

    def __init__(
        self,
        db: AsyncSession,
        redis: Redis,
        qdrant: AsyncQdrantClient | None,
        user_id: UUID,
        tool_executor: 'ToolExecutor | None' = None,
    ):
        """Initialize agent manager.
        
        Args:
            db: Database session
            redis: Redis client instance
            qdrant: Qdrant client instance, or None if Qdrant is disabled
            user_id: User ID
            tool_executor: ToolExecutor instance for tool support, or None if disabled
        """
        self.db = db
        self.redis = redis
        self.qdrant = qdrant
        self.user_id = user_id
        self.tool_executor = tool_executor

    async def _validate_provider(self, provider_id: UUID | None) -> UserLLMProvider | None:
        """Validate and retrieve LLM provider.
        
        Args:
            provider_id: ID of the LLM provider (optional)
            
        Returns:
            UserLLMProvider instance or None if not provided
            
        Raises:
            AgentProviderNotFoundError: If provider not found
            InvalidAgentProviderError: If provider is invalid
        """
        if provider_id is None:
            return None
            
        # Query provider
        result = await self.db.execute(
            select(UserLLMProvider).where(
                UserLLMProvider.id == provider_id,
                UserLLMProvider.user_id == self.user_id,
            )
        )
        provider = result.scalar_one_or_none()
        
        if not provider:
            raise AgentProviderNotFoundError(
                f"LLM provider {provider_id} not found for user {self.user_id}"
            )
        
        logger.debug(
            "provider_validated",
            agent_name="unknown",
            provider_id=str(provider_id),
            provider_type=provider.provider_type,
        )
        
        return provider

    async def create_agent(
        self, 
        name: str, 
        config: AgentConfig,
        llm_provider_id: UUID | None = None,
    ) -> AgentResponse:
        """Create new agent.
        
        Args:
            name: Agent name
            config: Agent configuration
            llm_provider_id: Optional LLM provider ID
            
        Returns:
            Created agent response
            
        Raises:
            AgentProviderNotFoundError: If provider not found
        """
        # Validate provider if provided
        provider = await self._validate_provider(llm_provider_id)
        
        # Create database record
        config_dict = config.model_dump()
        agent = UserAgent(
            user_id=self.user_id,
            name=name,
            config=config_dict,
            status=AgentStatus.READY.value,
            llm_provider_id=provider.id if provider else None,
        )
        self.db.add(agent)
        await self.db.flush()

        # Initialize contextual agent with provider info
        # Use the same provider for embeddings (unless there's a specific embedding provider)
        contextual_agent = ContextualAgent(
            agent_id=agent.id,
            user_id=self.user_id,
            agent_name=name,
            config=config,
            qdrant_client=self.qdrant,
            tool_executor=self.tool_executor,
            llm_provider=provider,
            embedding_llm_provider=None,
        )
        await contextual_agent.initialize()

        # Cache config in Redis
        cache_key = f"agent:{agent.id}:config"
        await self.redis.setex(cache_key, 300, config.model_dump_json())

        logger.info(
            "agent_created",
            agent_id=str(agent.id),
            user_id=str(self.user_id),
            agent_name=name,
            llm_provider_id=str(provider.id) if provider else None,
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
            config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config,
        )

    async def list_agents(self) -> list[AgentResponse]:
        """List all user agents."""
        agents_db = await self.list_agents_db()
        
        return [
            AgentResponse(
                id=agent.id,
                name=agent.name,
                status=AgentStatus(agent.status),
                created_at=agent.created_at,
                config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config,
            )
            for agent in agents_db
        ]
    
    async def list_agents_db(self) -> list:
        """List all user agents with relationships loaded."""
        from sqlalchemy.orm import joinedload
        
        result = await self.db.execute(
            select(UserAgent)
            .where(UserAgent.user_id == self.user_id)
            .options(joinedload(UserAgent.llm_provider))
        )
        return result.scalars().unique().all()

    async def list_agents_by_project(self, project_id: UUID) -> list[AgentResponse]:
        """List all agents in a specific project."""
        from sqlalchemy.orm import joinedload
        
        result = await self.db.execute(
            select(UserAgent)
            .where(
                (UserAgent.user_id == self.user_id)
                & (UserAgent.project_id == project_id)
            )
            .options(joinedload(UserAgent.llm_provider))
        )
        agents = result.scalars().unique().all()

        return [
            AgentResponse(
                id=agent.id,
                name=agent.name,
                status=AgentStatus(agent.status),
                created_at=agent.created_at,
                config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config,
            )
            for agent in agents
        ]

    async def get_agent_by_project(
        self, agent_id: UUID, project_id: UUID
    ) -> AgentResponse | None:
        """Get agent by ID from a specific project."""
        result = await self.db.execute(
            select(UserAgent).where(
                (UserAgent.id == agent_id)
                & (UserAgent.user_id == self.user_id)
                & (UserAgent.project_id == project_id)
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
            config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config,
        )

    async def create_agent_with_project(
        self, 
        name: str, 
        config: AgentConfig, 
        project_id: UUID,
        llm_provider_id: UUID | None = None,
    ) -> AgentResponse:
        """Create new agent in a specific project.
        
        Args:
            name: Agent name
            config: Agent configuration
            project_id: Project ID
            llm_provider_id: Optional LLM provider ID
            
        Returns:
            Created agent response
            
        Raises:
            AgentProviderNotFoundError: If provider not found
        """
        # Validate provider if provided
        provider = await self._validate_provider(llm_provider_id)
        
        config_dict = config.model_dump()
        agent = UserAgent(
            user_id=self.user_id,
            project_id=project_id,
            name=name,
            config=config_dict,
            status=AgentStatus.READY.value,
            llm_provider_id=provider.id if provider else None,
        )
        self.db.add(agent)
        await self.db.flush()

        # Initialize contextual agent with provider info
        # Use the same provider for embeddings (unless there's a specific embedding provider)
        contextual_agent = ContextualAgent(
            agent_id=agent.id,
            user_id=self.user_id,
            agent_name=name,
            config=config,
            qdrant_client=self.qdrant,
            tool_executor=self.tool_executor,
            llm_provider=provider,
            embedding_llm_provider=None,
        )
        await contextual_agent.initialize()

        # Cache config in Redis
        cache_key = f"agent:{agent.id}:config"
        await self.redis.setex(cache_key, 300, config.model_dump_json())

        logger.info(
            "agent_created_in_project",
            agent_id=str(agent.id),
            user_id=str(self.user_id),
            project_id=str(project_id),
            agent_name=name,
            llm_provider_id=str(provider.id) if provider else None,
        )

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            config=config,
        )

    async def update_agent_with_project(
        self, agent_id: UUID, project_id: UUID, name: str, config: AgentConfig
    ) -> AgentResponse | None:
        """Update agent in a specific project."""
        result = await self.db.execute(
            select(UserAgent).where(
                (UserAgent.id == agent_id)
                & (UserAgent.user_id == self.user_id)
                & (UserAgent.project_id == project_id)
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        agent.name = name
        agent.config = config.model_dump()
        await self.db.flush()

        # Update cache
        cache_key = f"agent:{agent.id}:config"
        await self.redis.setex(cache_key, 300, config.model_dump_json())

        logger.info(
            "agent_updated_in_project",
            agent_id=str(agent.id),
            user_id=str(self.user_id),
            project_id=str(project_id),
        )

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config,
        )

    async def delete_agent_with_project(
        self, agent_id: UUID, project_id: UUID
    ) -> bool:
        """Delete agent from a specific project."""
        result = await self.db.execute(
            select(UserAgent).where(
                (UserAgent.id == agent_id)
                & (UserAgent.user_id == self.user_id)
                & (UserAgent.project_id == project_id)
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
            "agent_deleted_from_project",
            agent_id=str(agent.id),
            user_id=str(self.user_id),
            project_id=str(project_id),
        )

        return True

    async def update_agent(self, agent_id: UUID, name: str, config: AgentConfig) -> AgentResponse | None:
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

        # Update config
        agent.name = name
        agent.config = config.model_dump()
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
            config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config,
        )

    async def update_agent_provider(
        self, agent_id: UUID, llm_provider_id: UUID | None
    ) -> AgentResponse | None:
        """Update agent's LLM provider.
        
        Args:
            agent_id: Agent ID
            llm_provider_id: New LLM provider ID (or None to unset)
            
        Returns:
            Updated agent response or None if agent not found
            
        Raises:
            AgentProviderNotFoundError: If provider not found
        """
        # Get agent
        result = await self.db.execute(
            select(UserAgent).where(
                UserAgent.id == agent_id,
                UserAgent.user_id == self.user_id,
            )
        )
        agent = result.scalar_one_or_none()

        if not agent:
            return None

        # Validate new provider if provided
        new_provider = await self._validate_provider(llm_provider_id)
        
        # Update provider
        old_provider_id = agent.llm_provider_id
        agent.llm_provider_id = new_provider.id if new_provider else None
        await self.db.flush()

        logger.info(
            "agent_provider_reassigned",
            agent_id=str(agent_id),
            user_id=str(self.user_id),
            old_provider_id=str(old_provider_id) if old_provider_id else None,
            new_provider_id=str(new_provider.id) if new_provider else None,
            agent_name=agent.name,
        )

        # Log audit event
        from app.services.llm_provider_audit_service import LLMProviderAuditService
        audit_service = LLMProviderAuditService(self.db)
        
        if new_provider:
            await audit_service.log_action(
                user_id=self.user_id,
                provider_id=new_provider.id,
                action="provider_reassigned",
                old_values={"agent_id": str(agent_id), "old_provider_id": str(old_provider_id)} if old_provider_id else None,
                new_values={"agent_id": str(agent_id), "agent_name": agent.name},
                success=True,
            )

        return AgentResponse(
            id=agent.id,
            name=agent.name,
            status=AgentStatus(agent.status),
            created_at=agent.created_at,
            config=AgentConfig(**agent.config) if isinstance(agent.config, dict) else agent.config,
        )
