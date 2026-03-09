"""Unit tests for LLMProviderAuditService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from app.services.llm_provider_audit_service import LLMProviderAuditService
from app.models.llm_provider_audit_log import LLMProviderAuditLog


@pytest.fixture
def audit_service(db_session: AsyncSession) -> LLMProviderAuditService:
    """Create audit service instance."""
    return LLMProviderAuditService(db_session)


@pytest.mark.asyncio
async def test_log_action_create(
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test logging a create action."""
    log = await audit_service.log_action(
        user_id=test_user.id,
        action="create",
        provider_id=test_llm_provider.id,
        new_values={"display_name": "My Provider", "provider_type": "openai"},
        success=True,
        ip_address="192.168.1.1",
        user_agent="test-client",
    )

    assert log.id is not None
    assert log.user_id == test_user.id
    assert log.provider_id == test_llm_provider.id
    assert log.action == "create"
    assert log.new_values["display_name"] == "My Provider"
    assert log.success is True
    assert log.ip_address == "192.168.1.1"


@pytest.mark.asyncio
async def test_log_action_update(
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test logging an update action."""
    log = await audit_service.log_action(
        user_id=test_user.id,
        action="update",
        provider_id=test_llm_provider.id,
        old_values={"display_name": "Old Name"},
        new_values={"display_name": "New Name"},
        success=True,
    )

    assert log.action == "update"
    assert log.old_values["display_name"] == "Old Name"
    assert log.new_values["display_name"] == "New Name"


@pytest.mark.asyncio
async def test_log_action_delete(
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test logging a delete action."""
    log = await audit_service.log_action(
        user_id=test_user.id,
        action="delete",
        provider_id=test_llm_provider.id,
        old_values={"display_name": "My Provider", "use_count": 5},
        success=True,
    )

    assert log.action == "delete"
    assert log.old_values["use_count"] == 5
    assert log.new_values is None


@pytest.mark.asyncio
async def test_log_action_test(
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test logging a test action."""
    log = await audit_service.log_action(
        user_id=test_user.id,
        action="test",
        provider_id=test_llm_provider.id,
        success=True,
    )

    assert log.action == "test"


@pytest.mark.asyncio
async def test_log_action_use(
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test logging a use action."""
    log = await audit_service.log_action(
        user_id=test_user.id,
        action="use",
        provider_id=test_llm_provider.id,
        success=True,
    )

    assert log.action == "use"


@pytest.mark.asyncio
async def test_log_action_provider_reassigned(
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test logging a provider_reassigned action."""
    log = await audit_service.log_action(
        user_id=test_user.id,
        action="provider_reassigned",
        provider_id=test_llm_provider.id,
        old_values={"llm_provider_id": None},
        new_values={"llm_provider_id": str(test_llm_provider.id)},
        success=True,
    )

    assert log.action == "provider_reassigned"


@pytest.mark.asyncio
async def test_log_action_failed(
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test logging a failed action."""
    log = await audit_service.log_action(
        user_id=test_user.id,
        action="test",
        provider_id=test_llm_provider.id,
        success=False,
        error_message="Connection timeout after 60s",
    )

    assert log.success is False
    assert log.error_message == "Connection timeout after 60s"


@pytest.mark.asyncio
async def test_log_action_invalid_action(
    audit_service: LLMProviderAuditService,
    test_user,
):
    """Test logging with invalid action raises error."""
    with pytest.raises(ValueError, match="Invalid action"):
        await audit_service.log_action(
            user_id=test_user.id,
            action="invalid_action",
            success=True,
        )


@pytest.mark.asyncio
async def test_get_audit_log_all(
    db_session: AsyncSession,
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test getting all audit logs for a user."""
    # Create multiple audit logs
    await audit_service.log_action(
        user_id=test_user.id,
        action="create",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await audit_service.log_action(
        user_id=test_user.id,
        action="test",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await db_session.commit()

    logs, total = await audit_service.get_audit_log(user_id=test_user.id)

    assert total >= 2
    assert len(logs) >= 2
    # Should be ordered by created_at desc (newest first)
    assert logs[0].created_at >= logs[1].created_at


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_provider(
    db_session: AsyncSession,
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test filtering audit logs by provider."""
    provider2_id = uuid4()  # Fake provider ID
    
    # Create logs for two providers
    await audit_service.log_action(
        user_id=test_user.id,
        action="create",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await audit_service.log_action(
        user_id=test_user.id,
        action="create",
        provider_id=provider2_id,
        success=True,
    )
    await db_session.commit()

    logs, total = await audit_service.get_audit_log(
        user_id=test_user.id,
        provider_id=test_llm_provider.id,
    )

    for log in logs:
        assert log.provider_id == test_llm_provider.id


@pytest.mark.asyncio
async def test_get_audit_log_filter_by_action(
    db_session: AsyncSession,
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test filtering audit logs by action."""
    await audit_service.log_action(
        user_id=test_user.id,
        action="create",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await audit_service.log_action(
        user_id=test_user.id,
        action="test",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await db_session.commit()

    logs, total = await audit_service.get_audit_log(
        user_id=test_user.id,
        action="test",
    )

    for log in logs:
        assert log.action == "test"


@pytest.mark.asyncio
async def test_get_audit_log_pagination(
    db_session: AsyncSession,
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test audit log pagination."""
    # Create 15 logs
    for i in range(15):
        await audit_service.log_action(
            user_id=test_user.id,
            action="use",
            provider_id=test_llm_provider.id,
            success=True,
        )
    await db_session.commit()

    # Get first page (limit=5)
    logs1, total1 = await audit_service.get_audit_log(
        user_id=test_user.id,
        limit=5,
        offset=0,
    )

    # Get second page
    logs2, total2 = await audit_service.get_audit_log(
        user_id=test_user.id,
        limit=5,
        offset=5,
    )

    assert len(logs1) == 5
    assert len(logs2) == 5
    assert total1 == total2  # Total should be same
    # Logs should be different
    assert logs1[0].id != logs2[0].id


@pytest.mark.asyncio
async def test_get_provider_actions_summary(
    db_session: AsyncSession,
    audit_service: LLMProviderAuditService,
    test_user,
    test_llm_provider,
):
    """Test getting summary of provider actions."""
    # Create various action logs
    await audit_service.log_action(
        user_id=test_user.id,
        action="create",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await audit_service.log_action(
        user_id=test_user.id,
        action="test",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await audit_service.log_action(
        user_id=test_user.id,
        action="test",
        provider_id=test_llm_provider.id,
        success=False,
    )
    await audit_service.log_action(
        user_id=test_user.id,
        action="use",
        provider_id=test_llm_provider.id,
        success=True,
    )
    await db_session.commit()

    summary = await audit_service.get_provider_actions_summary(
        provider_id=test_llm_provider.id,
        user_id=test_user.id,
    )

    assert summary["create"] >= 1
    assert summary["test"] >= 2
    assert summary["use"] >= 1


@pytest.mark.asyncio
async def test_valid_actions_defined(audit_service: LLMProviderAuditService):
    """Test that all valid actions are defined."""
    expected_actions = {"create", "update", "delete", "test", "use", "provider_reassigned"}
    assert audit_service.VALID_ACTIONS == expected_actions
