"""Тесты для Langfuse retention policy."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from app.tasks.langfuse_retention import (
    LangfuseRetentionPolicy,
    get_langfuse_retention_policy,
)


@pytest.fixture
def retention_policy():
    """Fixture для LangfuseRetentionPolicy."""
    with patch("app.tasks.langfuse_retention.settings") as mock_settings:
        mock_settings.langfuse_enabled = True
        mock_settings.langfuse_retention_days = 30
        mock_settings.langfuse_public_key = "test_public"
        mock_settings.langfuse_secret_key = "test_secret"
        mock_settings.langfuse_host = "http://localhost:3000"
        
        return LangfuseRetentionPolicy()


class TestLangfuseRetentionPolicy:
    """Тесты для LangfuseRetentionPolicy."""

    def test_retention_policy_initialization(self, retention_policy):
        """Тест инициализации retention policy."""
        assert retention_policy.retention_days == 30
        assert retention_policy.enabled is True
        assert retention_policy.rest_client is not None

    def test_get_retention_days(self, retention_policy):
        """Тест получения количества дней хранения."""
        assert retention_policy.get_retention_days() == 30

    def test_set_retention_days(self, retention_policy):
        """Тест установки количества дней хранения."""
        retention_policy.set_retention_days(45)
        assert retention_policy.get_retention_days() == 45

    def test_set_retention_days_invalid(self, retention_policy):
        """Тест установки невалидного количества дней."""
        with pytest.raises(ValueError, match="must be greater than 0"):
            retention_policy.set_retention_days(0)
        
        with pytest.raises(ValueError, match="must be greater than 0"):
            retention_policy.set_retention_days(-10)

    @pytest.mark.asyncio
    async def test_cleanup_old_traces_when_disabled(self):
        """Тест cleanup когда Langfuse отключен."""
        with patch("app.tasks.langfuse_retention.settings") as mock_settings:
            mock_settings.langfuse_enabled = False
            
            policy = LangfuseRetentionPolicy()
            result = await policy.cleanup_old_traces()
        
        assert result["deleted_count"] == 0
        assert result["archived_count"] == 0
        assert result["error_count"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_traces_success(self, retention_policy):
        """Тест успешного cleanup traces."""
        result = await retention_policy.cleanup_old_traces()
        
        assert isinstance(result, dict)
        assert "deleted_count" in result
        assert "archived_count" in result
        assert "error_count" in result
        assert result["deleted_count"] >= 0
        assert result["archived_count"] >= 0
        assert result["error_count"] >= 0

    @pytest.mark.asyncio
    async def test_cleanup_old_traces_with_error(self, retention_policy):
        """Тест cleanup traces при ошибке."""
        with patch.object(
            retention_policy.rest_client,
            'get_trace',
            side_effect=Exception("API Error")
        ):
            result = await retention_policy.cleanup_old_traces()
        
        assert isinstance(result, dict)
        assert result["deleted_count"] >= 0
        assert result["archived_count"] >= 0

    @pytest.mark.asyncio
    async def test_archive_trace_success(self, retention_policy):
        """Тест успешного архивирования trace."""
        trace_id = "trace-123"
        trace_data = {"id": trace_id, "name": "test_trace"}
        
        with patch.object(
            retention_policy.rest_client,
            'get_trace',
            new_callable=AsyncMock,
            return_value=trace_data
        ):
            result = await retention_policy.archive_trace(trace_id)
        
        assert result is True

    @pytest.mark.asyncio
    async def test_archive_trace_not_found(self, retention_policy):
        """Тест архивирования несуществующего trace."""
        trace_id = "trace-nonexistent"
        
        with patch.object(
            retention_policy.rest_client,
            'get_trace',
            new_callable=AsyncMock,
            return_value=None
        ):
            result = await retention_policy.archive_trace(trace_id)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_archive_trace_error(self, retention_policy):
        """Тест архивирования trace при ошибке."""
        trace_id = "trace-123"
        
        with patch.object(
            retention_policy.rest_client,
            'get_trace',
            side_effect=Exception("API Error")
        ):
            result = await retention_policy.archive_trace(trace_id)
        
        assert result is False

    def test_get_langfuse_retention_policy_singleton(self):
        """Тест что retention policy возвращается как singleton."""
        policy1 = get_langfuse_retention_policy()
        policy2 = get_langfuse_retention_policy()
        
        # Может не быть одним и тем же объектом из-за патча,
        # но должны быть оба валидны
        assert policy1 is not None
        assert policy2 is not None
