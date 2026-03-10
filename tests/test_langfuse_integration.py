"""Модульные тесты для LangfuseIntegration сервиса."""

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.services.langfuse_integration import (
    LangfuseIntegration,
    get_langfuse,
)


class TestLangfuseIntegrationInit:
    """Тесты инициализации LangfuseIntegration."""

    def test_init_disabled(self):
        """Тест инициализации с disabled режимом (LANGFUSE_ENABLED=false)."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()

            assert integration.enabled is False
            assert integration.client is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_init_enabled_success(self, mock_langfuse_class):
        """Тест успешной инициализации с enabled режимом."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            assert integration.enabled is True
            assert integration.client is not None
            mock_langfuse_class.assert_called_once()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_init_enabled_graceful_degradation_on_error(self, mock_langfuse_class):
        """Тест graceful degradation при ошибке инициализации."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            # Симулируем ошибку при инициализации Langfuse клиента
            mock_langfuse_class.side_effect = Exception("Connection refused")

            integration = LangfuseIntegration()

            # После ошибки enabled должен быть False для graceful degradation
            assert integration.enabled is False
            assert integration.client is None


class TestLangfuseIntegrationCreateTrace:
    """Тесты метода create_trace."""

    def test_create_trace_disabled(self):
        """Тест создания trace при disabled режиме."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            result = integration.create_trace(name="test_trace")

            assert result is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_trace_success(self, mock_langfuse_class):
        """Тест успешного создания trace."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            user_id = uuid4()
            workspace_id = uuid4()

            result = integration.create_trace(
                name="agent_process_message",
                user_id=user_id,
                workspace_id=workspace_id,
                metadata={"custom": "metadata"},
            )

            assert result is not None
            mock_client.trace.assert_called_once()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_trace_error_graceful(self, mock_langfuse_class):
        """Тест graceful обработки ошибки при создании trace."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_client.trace.side_effect = Exception("API error")
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            # Должно вернуть None вместо raise
            result = integration.create_trace(name="test_trace")

            assert result is None


class TestLangfuseIntegrationCreateSpan:
    """Тесты метода create_span."""

    def test_create_span_disabled(self):
        """Тест создания span при disabled режиме."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            mock_trace = MagicMock()

            result = integration.create_span(
                trace=mock_trace,
                name="test_span",
            )

            assert result is None

    def test_create_span_with_none_trace(self):
        """Тест создания span с None trace."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            with patch("app.services.langfuse_integration.Langfuse"):
                integration = LangfuseIntegration()
                result = integration.create_span(trace=None, name="test_span")

                assert result is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_span_success(self, mock_langfuse_class):
        """Тест успешного создания span."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_span = MagicMock()
            mock_trace = MagicMock()
            mock_trace.span.return_value = mock_span
            mock_langfuse_class.return_value = MagicMock()

            integration = LangfuseIntegration()
            integration.client = MagicMock()

            result = integration.create_span(
                trace=mock_trace,
                name="prepare_context",
                input_data={"message": "hello"},
                output_data={"context_size": 100},
                metadata={"step": 1},
                status="success",
            )

            assert result is not None
            mock_trace.span.assert_called_once()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_span_error_graceful(self, mock_langfuse_class):
        """Тест graceful обработки ошибки при создании span."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_trace = MagicMock()
            mock_trace.span.side_effect = Exception("Span creation failed")
            mock_langfuse_class.return_value = MagicMock()

            integration = LangfuseIntegration()
            integration.client = MagicMock()

            result = integration.create_span(trace=mock_trace, name="test_span")

            assert result is None


class TestLangfuseIntegrationRecordScore:
    """Тесты метода record_score."""

    def test_record_score_disabled(self):
        """Тест записи score при disabled режиме."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            result = integration.record_score(
                trace_id="trace-123",
                name="user_satisfaction",
                value=0.9,
            )

            assert result is False

    @patch("app.services.langfuse_integration.Langfuse")
    def test_record_score_success(self, mock_langfuse_class):
        """Тест успешной записи score."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            result = integration.record_score(
                trace_id="trace-123",
                name="user_satisfaction",
                value=0.9,
                comment="Great response",
            )

            assert result is True
            mock_client.score.assert_called_once()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_record_score_error_graceful(self, mock_langfuse_class):
        """Тест graceful обработки ошибки при записи score."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_client.score.side_effect = Exception("Score API error")
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            result = integration.record_score(
                trace_id="trace-123",
                name="user_satisfaction",
                value=0.9,
            )

            assert result is False


class TestLangfuseIntegrationGetTrace:
    """Тесты метода get_trace."""

    def test_get_trace_disabled(self):
        """Тест получения trace при disabled режиме."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            result = integration.get_trace(trace_id="trace-123")

            assert result is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_get_trace_not_implemented(self, mock_langfuse_class):
        """Тест что get_trace не реализован (требует REST API)."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_langfuse_class.return_value = MagicMock()

            integration = LangfuseIntegration()

            result = integration.get_trace(trace_id="trace-123")

            # На данный момент get_trace возвращает None
            # (требуется REST API для получения traces)
            assert result is None


class TestLangfuseIntegrationFlush:
    """Тесты метода flush."""

    def test_flush_disabled(self):
        """Тест flush при disabled режиме."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            result = integration.flush()

            assert result is False

    @patch("app.services.langfuse_integration.Langfuse")
    def test_flush_success(self, mock_langfuse_class):
        """Тест успешного flush."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            result = integration.flush()

            assert result is True
            mock_client.flush.assert_called_once()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_flush_error_graceful(self, mock_langfuse_class):
        """Тест graceful обработки ошибки при flush."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_client.flush.side_effect = Exception("Flush failed")
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            result = integration.flush()

            assert result is False


class TestLangfuseIntegrationShutdown:
    """Тесты метода shutdown."""

    def test_shutdown_disabled(self):
        """Тест shutdown при disabled режиме."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            # Не должно вызвать ошибку
            integration.shutdown()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_shutdown_success(self, mock_langfuse_class):
        """Тест успешного shutdown."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            integration.shutdown()

            mock_client.flush.assert_called_once()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_shutdown_error_graceful(self, mock_langfuse_class):
        """Тест graceful обработки ошибки при shutdown."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_client.flush.side_effect = Exception("Shutdown failed")
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            # Не должно вызвать ошибку
            integration.shutdown()


class TestGetLangfuseFunction:
    """Тесты функции get_langfuse()."""

    def test_get_langfuse_singleton(self):
        """Тест что get_langfuse возвращает singleton."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            # Очищаем глобальный экземпляр
            import app.services.langfuse_integration as module
            module._langfuse_instance = None

            first = get_langfuse()
            second = get_langfuse()

            assert first is second


class TestLangfuseIntegrationContextManager:
    """Тесты context manager trace_context."""

    @pytest.mark.asyncio
    async def test_trace_context_disabled(self):
        """Тест trace_context при disabled режиме."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()

            async with integration.trace_context(name="test_trace") as trace:
                assert trace is None

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_trace_context_success(self, mock_langfuse_class):
        """Тест успешного использования trace_context."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            async with integration.trace_context(name="test_trace") as trace:
                assert trace is not None

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_trace_context_error_handling(self, mock_langfuse_class):
        """Тест обработки ошибок в trace_context."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()

            with pytest.raises(RuntimeError):
                async with integration.trace_context(name="test_trace"):
                    raise RuntimeError("Test error")
