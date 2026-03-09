"""Integration tests for agent management with LLM providers."""

import pytest
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import AsyncMock, MagicMock

from app.agents.manager import AgentManager, AgentProviderNotFoundError
from app.models.user import User
from app.models.user_project import UserProject
from app.models.user_llm_provider import UserLLMProvider
from app.models.user_agent import UserAgent
from app.schemas.agent import AgentConfig


class TestAgentManagerWithProviders:
    """Tests for agent management with LLM provider integration."""

    @pytest.mark.asyncio
    async def test_create_agent_with_provider(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
        test_llm_provider: UserLLMProvider,
    ):
        """Test creating agent with LLM provider."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_qdrant = AsyncMock()
        mock_qdrant.create_collection = AsyncMock(return_value=True)

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        config = AgentConfig(
            name="test_agent",
            system_prompt="You are helpful",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=2048,
        )

        response = await manager.create_agent(
            name="test_agent",
            config=config,
            llm_provider_id=test_llm_provider.id,
        )

        assert response.id is not None
        assert response.name == "test_agent"

        # Verify provider was set in database
        result = await db_session.execute(
            __import__("sqlalchemy").select(UserAgent).where(
                UserAgent.id == response.id
            )
        )
        agent = result.scalar_one()
        assert agent.llm_provider_id == test_llm_provider.id

    @pytest.mark.asyncio
    async def test_create_agent_with_invalid_provider(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating agent with invalid provider raises error."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_qdrant = AsyncMock()
        mock_qdrant.create_collection = AsyncMock(return_value=True)

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        config = AgentConfig(
            name="test_agent",
            system_prompt="You are helpful",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=2048,
        )

        fake_provider_id = uuid4()

        with pytest.raises(AgentProviderNotFoundError):
            await manager.create_agent(
                name="test_agent",
                config=config,
                llm_provider_id=fake_provider_id,
            )

    @pytest.mark.asyncio
    async def test_create_agent_without_provider(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating agent without provider (provider_id is optional)."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_qdrant = AsyncMock()
        mock_qdrant.create_collection = AsyncMock(return_value=True)

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        config = AgentConfig(
            name="test_agent",
            system_prompt="You are helpful",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=2048,
        )

        response = await manager.create_agent(
            name="test_agent",
            config=config,
        )

        assert response.id is not None
        assert response.name == "test_agent"

        # Verify provider is not set
        result = await db_session.execute(
            __import__("sqlalchemy").select(UserAgent).where(
                UserAgent.id == response.id
            )
        )
        agent = result.scalar_one()
        assert agent.llm_provider_id is None

    @pytest.mark.asyncio
    async def test_create_agent_with_project_and_provider(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
        test_llm_provider: UserLLMProvider,
    ):
        """Test creating agent in project with provider."""
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_qdrant = AsyncMock()
        mock_qdrant.create_collection = AsyncMock(return_value=True)

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        config = AgentConfig(
            name="test_agent",
            system_prompt="You are helpful",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=2048,
        )

        response = await manager.create_agent_with_project(
            name="test_agent",
            config=config,
            project_id=test_project.id,
            llm_provider_id=test_llm_provider.id,
        )

        assert response.id is not None
        assert response.name == "test_agent"

        # Verify provider was set
        result = await db_session.execute(
            __import__("sqlalchemy").select(UserAgent).where(
                UserAgent.id == response.id
            )
        )
        agent = result.scalar_one()
        assert agent.llm_provider_id == test_llm_provider.id
        assert agent.project_id == test_project.id

    @pytest.mark.asyncio
    async def test_update_agent_provider(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
        test_llm_provider: UserLLMProvider,
    ):
        """Test updating agent's LLM provider."""
        # Create second provider
        provider2 = UserLLMProvider(
            user_id=test_user.id,
            provider_type="anthropic",
            display_name="My Anthropic",
            litellm_model_name=f"user{test_user.id}_anthropic_xyz789",
            config={"model": "claude-3"},
            use_count=0,
        )
        db_session.add(provider2)
        await db_session.commit()

        # Create agent with first provider
        agent = UserAgent(
            user_id=test_user.id,
            project_id=test_project.id,
            name="test_agent",
            config={"model": "gpt-4o"},
            status="ready",
            llm_provider_id=test_llm_provider.id,
        )
        db_session.add(agent)
        await db_session.commit()

        # Create manager and update provider
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_qdrant = AsyncMock()

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        response = await manager.update_agent_provider(
            agent_id=agent.id,
            llm_provider_id=provider2.id,
        )

        assert response is not None
        assert response.id == agent.id

        # Verify provider was updated in database
        result = await db_session.execute(
            __import__("sqlalchemy").select(UserAgent).where(
                UserAgent.id == agent.id
            )
        )
        updated_agent = result.scalar_one()
        assert updated_agent.llm_provider_id == provider2.id

    @pytest.mark.asyncio
    async def test_update_agent_provider_with_audit_log(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_project: UserProject,
        test_llm_provider: UserLLMProvider,
    ):
        """Test that updating agent provider creates audit log entry."""
        from app.models.llm_provider_audit_log import LLMProviderAuditLog

        # Create second provider
        provider2 = UserLLMProvider(
            user_id=test_user.id,
            provider_type="anthropic",
            display_name="My Anthropic",
            litellm_model_name=f"user{test_user.id}_anthropic_xyz789",
            config={"model": "claude-3"},
            use_count=0,
        )
        db_session.add(provider2)
        await db_session.commit()

        # Create agent
        agent = UserAgent(
            user_id=test_user.id,
            project_id=test_project.id,
            name="test_agent",
            config={"model": "gpt-4o"},
            status="ready",
            llm_provider_id=test_llm_provider.id,
        )
        db_session.add(agent)
        await db_session.commit()

        # Update provider
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_qdrant = AsyncMock()

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        await manager.update_agent_provider(
            agent_id=agent.id,
            llm_provider_id=provider2.id,
        )
        await db_session.commit()

        # Check audit log
        result = await db_session.execute(
            __import__("sqlalchemy").select(LLMProviderAuditLog).where(
                LLMProviderAuditLog.user_id == test_user.id,
                LLMProviderAuditLog.action == "provider_reassigned",
            )
        )
        audit_logs = result.scalars().all()
        assert len(audit_logs) > 0

        # Verify audit log entry
        audit_log = audit_logs[0]
        assert audit_log.provider_id == provider2.id
        assert audit_log.action == "provider_reassigned"
        assert audit_log.success is True

    @pytest.mark.asyncio
    async def test_update_agent_provider_nonexistent(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test updating provider for nonexistent agent returns None."""
        mock_redis = AsyncMock()
        mock_qdrant = AsyncMock()
        fake_provider_id = uuid4()

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        result = await manager.update_agent_provider(
            agent_id=uuid4(),
            llm_provider_id=fake_provider_id,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_validate_provider_with_valid_id(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_llm_provider: UserLLMProvider,
    ):
        """Test validating a valid provider."""
        mock_redis = AsyncMock()
        mock_qdrant = AsyncMock()

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        provider = await manager._validate_provider(test_llm_provider.id)

        assert provider is not None
        assert provider.id == test_llm_provider.id
        assert provider.provider_type == "openai"

    @pytest.mark.asyncio
    async def test_validate_provider_with_invalid_id(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test validating invalid provider raises error."""
        mock_redis = AsyncMock()
        mock_qdrant = AsyncMock()

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        fake_id = uuid4()

        with pytest.raises(AgentProviderNotFoundError):
            await manager._validate_provider(fake_id)

    @pytest.mark.asyncio
    async def test_validate_provider_with_none(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test validating None provider returns None."""
        mock_redis = AsyncMock()
        mock_qdrant = AsyncMock()

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        provider = await manager._validate_provider(None)

        assert provider is None

    @pytest.mark.asyncio
    async def test_create_agent_with_other_user_provider(
        self,
        db_session: AsyncSession,
        test_user: User,
    ):
        """Test creating agent with another user's provider raises error."""
        # Create another user with provider
        other_user = User(id=uuid4(), email="other@example.com")
        db_session.add(other_user)
        await db_session.commit()

        other_provider = UserLLMProvider(
            user_id=other_user.id,
            provider_type="openai",
            display_name="Other User Provider",
            litellm_model_name=f"user{other_user.id}_openai_123",
            config={"model": "gpt-4o"},
            use_count=0,
        )
        db_session.add(other_provider)
        await db_session.commit()

        # Try to create agent with other user's provider
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock(return_value=True)
        mock_qdrant = AsyncMock()
        mock_qdrant.create_collection = AsyncMock(return_value=True)

        manager = AgentManager(
            db=db_session,
            redis=mock_redis,
            qdrant=mock_qdrant,
            user_id=test_user.id,
        )

        config = AgentConfig(
            name="test_agent",
            system_prompt="You are helpful",
            model="gpt-4o",
            temperature=0.7,
            max_tokens=2048,
        )

        with pytest.raises(AgentProviderNotFoundError):
            await manager.create_agent(
                name="test_agent",
                config=config,
                llm_provider_id=other_provider.id,
            )
