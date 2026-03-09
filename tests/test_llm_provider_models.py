"""Unit tests for LLM provider models."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.models.user import User
from app.models.user_llm_provider import UserLLMProvider
from app.models.llm_provider_audit_log import LLMProviderAuditLog


@pytest.mark.asyncio
async def test_user_llm_provider_creation(db_session: AsyncSession, test_user: User):
    """Test creating a UserLLMProvider."""
    provider = UserLLMProvider(
        user_id=test_user.id,
        provider_type="openai",
        display_name="Test OpenAI",
        litellm_model_name="user550e8400_openai_test123",
        config={"model": "gpt-4o", "max_tokens": 2048},
    )
    db_session.add(provider)
    await db_session.commit()
    await db_session.refresh(provider)

    assert provider.id is not None
    assert provider.user_id == test_user.id
    assert provider.provider_type == "openai"
    assert provider.display_name == "Test OpenAI"
    assert provider.litellm_model_name == "user550e8400_openai_test123"
    assert provider.config == {"model": "gpt-4o", "max_tokens": 2048}
    assert provider.use_count == 0
    assert provider.created_at is not None
    assert provider.updated_at is not None
    assert provider.last_used_at is None


@pytest.mark.asyncio
async def test_user_llm_provider_update(
    db_session: AsyncSession, test_llm_provider: UserLLMProvider
):
    """Test updating a UserLLMProvider."""
    test_llm_provider.display_name = "Updated Name"
    test_llm_provider.config = {"model": "gpt-4-turbo", "max_tokens": 4096}
    await db_session.commit()
    await db_session.refresh(test_llm_provider)

    assert test_llm_provider.display_name == "Updated Name"
    assert test_llm_provider.config["model"] == "gpt-4-turbo"
    assert test_llm_provider.config["max_tokens"] == 4096


@pytest.mark.asyncio
async def test_user_llm_provider_use_count(
    db_session: AsyncSession, test_llm_provider: UserLLMProvider
):
    """Test incrementing use_count on UserLLMProvider."""
    initial_count = test_llm_provider.use_count
    test_llm_provider.use_count += 1
    test_llm_provider.use_count += 1
    await db_session.commit()
    await db_session.refresh(test_llm_provider)

    assert test_llm_provider.use_count == initial_count + 2


@pytest.mark.asyncio
async def test_llm_provider_audit_log_creation(
    db_session: AsyncSession, test_user: User, test_llm_provider: UserLLMProvider
):
    """Test creating a LLMProviderAuditLog."""
    audit_log = LLMProviderAuditLog(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
        action="create",
        new_values={"display_name": "My OpenAI Provider", "provider_type": "openai"},
        success=True,
        ip_address="127.0.0.1",
        user_agent="test-client",
    )
    db_session.add(audit_log)
    await db_session.commit()
    await db_session.refresh(audit_log)

    assert audit_log.id is not None
    assert audit_log.user_id == test_user.id
    assert audit_log.provider_id == test_llm_provider.id
    assert audit_log.action == "create"
    assert audit_log.new_values == {"display_name": "My OpenAI Provider", "provider_type": "openai"}
    assert audit_log.success is True
    assert audit_log.ip_address == "127.0.0.1"
    assert audit_log.user_agent == "test-client"
    assert audit_log.created_at is not None


@pytest.mark.asyncio
async def test_llm_provider_audit_log_failed_action(
    db_session: AsyncSession, test_user: User
):
    """Test creating a failed audit log entry."""
    audit_log = LLMProviderAuditLog(
        user_id=test_user.id,
        provider_id=None,
        action="test",
        success=False,
        error_message="Connection timeout after 60s",
        ip_address="192.168.1.1",
    )
    db_session.add(audit_log)
    await db_session.commit()
    await db_session.refresh(audit_log)

    assert audit_log.success is False
    assert audit_log.error_message == "Connection timeout after 60s"
    assert audit_log.provider_id is None


@pytest.mark.asyncio
async def test_llm_provider_audit_log_delete_action(
    db_session: AsyncSession, test_user: User, test_llm_provider: UserLLMProvider
):
    """Test audit log for delete action."""
    audit_log = LLMProviderAuditLog(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
        action="delete",
        old_values={
            "display_name": "My OpenAI Provider",
            "provider_type": "openai",
            "use_count": 5,
        },
        success=True,
    )
    db_session.add(audit_log)
    await db_session.commit()
    await db_session.refresh(audit_log)

    assert audit_log.action == "delete"
    assert audit_log.old_values["use_count"] == 5
    assert audit_log.new_values is None


@pytest.mark.asyncio
async def test_user_llm_providers_relationship(
    db_session: AsyncSession, test_user: User
):
    """Test User relationship with LLM providers."""
    # Create multiple providers
    provider1 = UserLLMProvider(
        user_id=test_user.id,
        provider_type="openai",
        display_name="Provider 1",
        litellm_model_name="user_openai_1",
    )
    provider2 = UserLLMProvider(
        user_id=test_user.id,
        provider_type="anthropic",
        display_name="Provider 2",
        litellm_model_name="user_anthropic_1",
    )
    db_session.add_all([provider1, provider2])
    await db_session.commit()

    # Refresh user to load relationships
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    result = await db_session.execute(
        select(User).where(User.id == test_user.id).options(selectinload(User.llm_providers))
    )
    user_with_providers = result.scalar_one()

    assert len(user_with_providers.llm_providers) == 2


@pytest.mark.asyncio
async def test_llm_provider_audit_log_relationship(
    db_session: AsyncSession, test_user: User, test_llm_provider: UserLLMProvider
):
    """Test LLMProviderAuditLog relationship with UserLLMProvider."""
    # Create multiple audit logs for same provider
    audit1 = LLMProviderAuditLog(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
        action="create",
        success=True,
    )
    audit2 = LLMProviderAuditLog(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
        action="update",
        success=True,
    )
    db_session.add_all([audit1, audit2])
    await db_session.commit()

    # Reload provider with relationships
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    result = await db_session.execute(
        select(UserLLMProvider).where(UserLLMProvider.id == test_llm_provider.id).options(selectinload(UserLLMProvider.audit_logs))
    )
    provider_with_logs = result.scalar_one()

    assert len(provider_with_logs.audit_logs) >= 2
    actions = [log.action for log in provider_with_logs.audit_logs]
    assert "create" in actions
    assert "update" in actions


@pytest.mark.asyncio
async def test_user_agent_llm_provider_relationship(
    db_session: AsyncSession, test_user: User, test_project, test_llm_provider: UserLLMProvider
):
    """Test UserAgent relationship with LLMProvider."""
    from app.models.user_agent import UserAgent

    agent = UserAgent(
        user_id=test_user.id,
        project_id=test_project.id,
        name="test_agent_with_provider",
        config={"model": "gpt-4o-mini"},
        llm_provider_id=test_llm_provider.id,
    )
    db_session.add(agent)
    await db_session.commit()
    await db_session.refresh(agent)

    assert agent.llm_provider_id == test_llm_provider.id
    await db_session.refresh(agent)  # Load relationship
    assert agent.llm_provider.id == test_llm_provider.id
    assert agent.llm_provider.display_name == "My OpenAI Provider"


@pytest.mark.asyncio
async def test_llm_provider_repr(test_llm_provider: UserLLMProvider):
    """Test string representation of UserLLMProvider."""
    repr_str = repr(test_llm_provider)
    assert "UserLLMProvider" in repr_str
    assert "openai" in repr_str
    assert "My OpenAI Provider" in repr_str


@pytest.mark.asyncio
async def test_llm_provider_audit_log_repr(test_llm_provider_audit_log: LLMProviderAuditLog):
    """Test string representation of LLMProviderAuditLog."""
    repr_str = repr(test_llm_provider_audit_log)
    assert "LLMProviderAuditLog" in repr_str
    assert "create" in repr_str
