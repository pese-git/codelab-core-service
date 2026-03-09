"""Unit and integration tests for LLMProviderService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.services.llm_provider_service import (
    LLMProviderService,
    LLMProviderNotFoundError,
    LLMProviderInUseError,
)
from app.models.user_llm_provider import UserLLMProvider


@pytest.fixture
def llm_provider_service(db_session: AsyncSession) -> LLMProviderService:
    """Create LLMProviderService instance."""
    return LLMProviderService(db_session)


@pytest.mark.asyncio
async def test_create_user_provider_success(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
):
    """Test successful provider creation."""
    with patch.object(llm_provider_service.litellm_client, "add_model") as mock_add:
        mock_add.return_value = "user550e8400_openai_test123"

        provider = await llm_provider_service.create_user_provider(
            user_id=test_user.id,
            provider_type="openai",
            display_name="My OpenAI",
            api_key="sk-test123",
            config={"model": "gpt-4o"},
            ip_address="127.0.0.1",
        )

        assert provider.id is not None
        assert provider.user_id == test_user.id
        assert provider.provider_type == "openai"
        assert provider.display_name == "My OpenAI"
        assert provider.litellm_model_name == "user550e8400_openai_test123"
        mock_add.assert_called_once()

        # Verify audit log was created
        await db_session.refresh(provider)
        assert provider.created_at is not None


@pytest.mark.asyncio
async def test_get_user_provider_success(
    llm_provider_service: LLMProviderService,
    test_user,
    test_llm_provider,
):
    """Test getting a provider."""
    provider = await llm_provider_service.get_user_provider(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
    )

    assert provider.id == test_llm_provider.id
    assert provider.user_id == test_user.id


@pytest.mark.asyncio
async def test_get_user_provider_not_found(
    llm_provider_service: LLMProviderService,
    test_user,
):
    """Test getting non-existent provider raises error."""
    with pytest.raises(LLMProviderNotFoundError):
        await llm_provider_service.get_user_provider(
            user_id=test_user.id,
            provider_id=uuid4(),
        )


@pytest.mark.asyncio
async def test_get_user_providers(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
    test_llm_provider,
):
    """Test getting list of providers."""
    # Create another provider
    provider2 = UserLLMProvider(
        user_id=test_user.id,
        provider_type="anthropic",
        display_name="My Claude",
        litellm_model_name="user550e8400_anthropic_xyz789",
    )
    db_session.add(provider2)
    await db_session.commit()

    providers, total = await llm_provider_service.get_user_providers(
        user_id=test_user.id,
        limit=10,
    )

    assert total >= 2
    assert len(providers) >= 2


@pytest.mark.asyncio
async def test_update_user_provider(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
    test_llm_provider,
):
    """Test updating provider."""
    updated = await llm_provider_service.update_user_provider(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
        display_name="Updated Name",
        config={"model": "gpt-4-turbo"},
    )

    assert updated.display_name == "Updated Name"
    assert updated.config["model"] == "gpt-4-turbo"


@pytest.mark.asyncio
async def test_delete_user_provider_success(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
):
    """Test successful provider deletion."""
    # Create a provider to delete
    provider = UserLLMProvider(
        user_id=test_user.id,
        provider_type="openai",
        display_name="To Delete",
        litellm_model_name="user550e8400_openai_del123",
    )
    db_session.add(provider)
    await db_session.commit()

    with patch.object(llm_provider_service.litellm_client, "delete_model") as mock_delete:
        await llm_provider_service.delete_user_provider(
            user_id=test_user.id,
            provider_id=provider.id,
        )

        mock_delete.assert_called_once_with("user550e8400_openai_del123")

        # Verify provider is deleted
        with pytest.raises(LLMProviderNotFoundError):
            await llm_provider_service.get_user_provider(
                user_id=test_user.id,
                provider_id=provider.id,
            )


@pytest.mark.asyncio
async def test_delete_user_provider_in_use(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
    test_project,
    test_llm_provider,
):
    """Test deleting provider that is in use by agents raises error."""
    from app.models.user_agent import UserAgent

    # Create agent using provider
    agent = UserAgent(
        user_id=test_user.id,
        project_id=test_project.id,
        name="test_agent",
        config={"model": "gpt-4o"},
        llm_provider_id=test_llm_provider.id,
    )
    db_session.add(agent)
    await db_session.commit()

    with pytest.raises(LLMProviderInUseError):
        await llm_provider_service.delete_user_provider(
            user_id=test_user.id,
            provider_id=test_llm_provider.id,
        )


@pytest.mark.asyncio
async def test_test_provider_success(
    llm_provider_service: LLMProviderService,
    test_user,
    test_llm_provider,
):
    """Test provider testing."""
    with patch.object(llm_provider_service.litellm_client, "test_model") as mock_test:
        mock_test.return_value = {
            "success": True,
            "response": "Hello!",
            "latency_ms": 100.0,
            "error": None,
        }

        result = await llm_provider_service.test_provider(
            user_id=test_user.id,
            provider_id=test_llm_provider.id,
            test_prompt="Hello!",
        )

        assert result["success"] is True
        assert "Hello!" in result["response"]
        assert result["latency_ms"] == 100.0
        mock_test.assert_called_once()


@pytest.mark.asyncio
async def test_test_provider_failure(
    llm_provider_service: LLMProviderService,
    test_user,
    test_llm_provider,
):
    """Test provider testing failure."""
    with patch.object(llm_provider_service.litellm_client, "test_model") as mock_test:
        mock_test.return_value = {
            "success": False,
            "response": None,
            "latency_ms": None,
            "error": "Connection timeout",
        }

        result = await llm_provider_service.test_provider(
            user_id=test_user.id,
            provider_id=test_llm_provider.id,
        )

        assert result["success"] is False
        assert result["error"] == "Connection timeout"


@pytest.mark.asyncio
async def test_record_provider_usage(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
    test_llm_provider,
):
    """Test recording provider usage."""
    initial_count = test_llm_provider.use_count
    initial_last_used = test_llm_provider.last_used_at

    await llm_provider_service.record_provider_usage(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
    )

    # Reload provider from database
    from sqlalchemy import select
    result = await db_session.execute(
        select(UserLLMProvider).where(UserLLMProvider.id == test_llm_provider.id)
    )
    updated_provider = result.scalar_one()

    assert updated_provider.use_count == initial_count + 1
    assert updated_provider.last_used_at is not None
    if initial_last_used is not None:
        assert updated_provider.last_used_at > initial_last_used


@pytest.mark.asyncio
async def test_count_agents_using_provider(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
    test_project,
    test_llm_provider,
):
    """Test counting agents using provider."""
    from app.models.user_agent import UserAgent

    # Initially no agents
    count = await llm_provider_service._count_agents_using_provider(test_llm_provider.id)
    assert count == 0

    # Create agent using provider
    agent = UserAgent(
        user_id=test_user.id,
        project_id=test_project.id,
        name="test_agent",
        config={"model": "gpt-4o"},
        llm_provider_id=test_llm_provider.id,
    )
    db_session.add(agent)
    await db_session.commit()

    count = await llm_provider_service._count_agents_using_provider(test_llm_provider.id)
    assert count == 1


@pytest.mark.asyncio
async def test_create_provider_failure_logs_audit(
    db_session: AsyncSession,
    llm_provider_service: LLMProviderService,
    test_user,
):
    """Test that creation failure is logged to audit."""
    from sqlalchemy import select
    from app.models.llm_provider_audit_log import LLMProviderAuditLog
    
    with patch.object(llm_provider_service.litellm_client, "add_model") as mock_add:
        mock_add.side_effect = Exception("LiteLLM error")

        with pytest.raises(Exception):
            await llm_provider_service.create_user_provider(
                user_id=test_user.id,
                provider_type="openai",
                display_name="Failed",
                api_key="sk-test",
            )

        # Verify audit log was created for failure
        result = await db_session.execute(
            select(LLMProviderAuditLog)
            .where(LLMProviderAuditLog.user_id == test_user.id)
            .where(LLMProviderAuditLog.action == "create")
            .where(LLMProviderAuditLog.success == False)
        )
        failed_audit = result.scalar()
        assert failed_audit is not None
        assert failed_audit.error_message is not None
