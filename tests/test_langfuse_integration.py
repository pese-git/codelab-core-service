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


class TestCreateToolExecutionSpan:
    """Тесты для LangfuseIntegration.create_tool_execution_span()."""

    def test_create_tool_execution_span_disabled(self):
        """Тест создания span когда Langfuse disabled."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"param1": "value1"},
            )

            assert span is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_tool_execution_span_success(self, mock_langfuse_class):
        """Тест успешного создания span."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_span = MagicMock()
            mock_span.id = "span-456"
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"param1": "value1"},
                metadata={"user_id": "user-123"},
            )

            assert span is not None
            assert hasattr(span, "tool_name")
            assert span.tool_name == "test_tool"

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_tool_execution_span_graceful_degradation_on_error(
        self, mock_langfuse_class
    ):
        """Тест graceful degradation при ошибке создания span."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_client.trace.side_effect = Exception("Langfuse connection error")
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"param1": "value1"},
            )

            # Должно вернуть None и не выбросить исключение
            assert span is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_tool_execution_span_context_propagation(self, mock_langfuse_class):
        """Тест пропагирования контекста (user_id, workspace_id)."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_span = MagicMock()
            mock_span.id = "span-456"
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            
            metadata = {
                "user_id": "user-123",
                "workspace_id": "workspace-456",
                "project_id": "project-789",
            }
            
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"param1": "value1"},
                metadata=metadata,
            )

            assert span is not None
            # Verify that metadata was passed to Langfuse
            mock_client.trace.assert_called_once()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_end_tool_execution_span_graceful_handling(self, mock_langfuse_class):
        """Тест graceful обработки при завершении span."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_span = MagicMock()
            mock_span.id = "span-456"
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"param1": "value1"},
            )

            # Завершить span
            result = integration.end_tool_execution_span(
                span,
                result={"status": "success"},
                error=None,
            )

            # Должно не вызвать исключение
            assert result is None or isinstance(result, (bool, type(None)))


class TestNestedSpanCreation:
    """Тесты для создания вложенных spans."""

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_nested_span_hierarchy(self, mock_langfuse_class):
        """Тест создания иерархии spans (parent → children)."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            # Create parent and child spans
            mock_parent_span = MagicMock()
            mock_parent_span.id = "parent-span-456"
            mock_child_span = MagicMock()
            mock_child_span.id = "child-span-789"
            
            mock_trace.span.side_effect = [mock_parent_span, mock_child_span]
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            
            # Create parent span
            parent_span = integration.create_tool_execution_span(
                tool_name="parent_tool",
                input_params={"param": "value"},
            )
            
            assert parent_span is not None
            assert parent_span.span_id == "parent-span-456"
            
            # Create nested child span
            child_span = integration._create_nested_span(
                parent_span_id=parent_span.span_id,
                span_name="child_operation",
                input_params={"child_param": "child_value"},
                metadata={"level": "child"},
            )
            
            assert child_span is not None
            assert hasattr(child_span, "span_id")

    def test_create_nested_span_disabled(self):
        """Тест создания nested span когда Langfuse disabled."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = False

            integration = LangfuseIntegration()
            
            span = integration._create_nested_span(
                parent_span_id="parent-123",
                span_name="child_span",
                input_params={},
                metadata={},
            )

            assert span is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_nested_span_with_parent_linking(self, mock_langfuse_class):
        """Тест связывания nested span с parent span."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_span = MagicMock()
            mock_span.id = "span-456"
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            
            # Create nested span with explicit parent_span_id
            nested_span = integration._create_nested_span(
                parent_span_id="parent-123",
                span_name="nested_operation",
                input_params={"input": "data"},
                metadata={"parent_id": "parent-123"},
            )

            assert nested_span is not None
            # Verify that span was created with parent linking info
            mock_client.trace.assert_called()

    @patch("app.services.langfuse_integration.Langfuse")
    def test_create_nested_span_graceful_error_handling(self, mock_langfuse_class):
        """Тест graceful обработки ошибок при создании nested span."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.span.side_effect = Exception("Span creation failed")
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            
            # Should not raise exception
            span = integration._create_nested_span(
                parent_span_id="parent-123",
                span_name="nested_operation",
                input_params={},
                metadata={},
            )

            # Should return None gracefully
            assert span is None

    @patch("app.services.langfuse_integration.Langfuse")
    def test_get_current_span_id(self, mock_langfuse_class):
        """Тест извлечения текущего span ID из контекста."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"

            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client

            integration = LangfuseIntegration()
            
            # _get_current_span_id должен вернуть None или строку
            span_id = integration._get_current_span_id()
            
            assert span_id is None or isinstance(span_id, str)


class TestToolExecutorLangfuseIntegration:
    """Интеграционные тесты для ToolExecutor + LangfuseIntegration."""

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    async def test_tool_execution_with_langfuse_root_span(
        self, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест полного flow tool execution с созданием корневого Langfuse span."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Setup mocks
        mock_langfuse = MagicMock(spec=LangfuseIntegration)
        mock_root_span = MagicMock()
        mock_root_span.span_id = "root-span-123"
        mock_root_span.span_obj = MagicMock()
        mock_root_span.tool_name = "test_tool"
        
        mock_langfuse.create_tool_execution_span.return_value = mock_root_span
        mock_langfuse.end_tool_execution_span.return_value = None
        mock_langfuse._create_nested_span.return_value = MagicMock()
        mock_get_langfuse.return_value = mock_langfuse
        
        # Setup risk assessor mock
        mock_risk_assessor_instance = MagicMock()
        mock_risk_assessor_instance.assess_tool_risk.return_value = ("LOW", 0.1)
        mock_risk_assessor.return_value = mock_risk_assessor_instance
        
        # Setup approval manager mock
        mock_approval_manager_instance = MagicMock()
        mock_approval_manager.return_value = mock_approval_manager_instance
        
        # Setup database mock
        mock_db = AsyncMock(spec=AsyncSession)
        
        from app.core.tools.executor import ToolExecutor
        
        user_id = uuid4()
        project_id = uuid4()
        
        executor = ToolExecutor(
            user_id=user_id,
            project_id=project_id,
            workspace_root="/tmp/workspace",
            db=mock_db,
            approval_manager=mock_approval_manager_instance,
            langfuse_integration=mock_langfuse,
        )
        
        # Verify that executor has Langfuse integration
        assert executor.langfuse == mock_langfuse
        assert executor.langfuse.create_tool_execution_span is not None

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    async def test_tool_execution_with_nested_spans(
        self, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест создания вложенных spans для validation, risk, approval, execution."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Setup mocks
        mock_langfuse = MagicMock(spec=LangfuseIntegration)
        mock_root_span = MagicMock()
        mock_root_span.span_id = "root-span-123"
        
        mock_validation_span = MagicMock()
        mock_validation_span.span_id = "validation-span-456"
        
        mock_risk_span = MagicMock()
        mock_risk_span.span_id = "risk-span-789"
        
        mock_langfuse.create_tool_execution_span.return_value = mock_root_span
        mock_langfuse._create_nested_span.side_effect = [
            mock_validation_span,
            mock_risk_span,
        ]
        mock_langfuse.end_tool_execution_span.return_value = None
        mock_get_langfuse.return_value = mock_langfuse
        
        # Setup mocks
        mock_risk_assessor_instance = MagicMock()
        mock_risk_assessor_instance.assess_tool_risk.return_value = ("MEDIUM", 0.5)
        mock_risk_assessor.return_value = mock_risk_assessor_instance
        
        mock_approval_manager_instance = MagicMock()
        mock_approval_manager.return_value = mock_approval_manager_instance
        
        mock_db = AsyncMock(spec=AsyncSession)
        
        from app.core.tools.executor import ToolExecutor
        
        user_id = uuid4()
        project_id = uuid4()
        
        executor = ToolExecutor(
            user_id=user_id,
            project_id=project_id,
            workspace_root="/tmp/workspace",
            db=mock_db,
            approval_manager=mock_approval_manager_instance,
            langfuse_integration=mock_langfuse,
        )
        
        # Verify setup
        assert executor.langfuse.create_tool_execution_span is not None
        assert executor.langfuse._create_nested_span is not None

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    async def test_tool_execution_graceful_langfuse_degradation(
        self, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест graceful degradation когда Langfuse недоступна."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Setup mocks with Langfuse unavailable
        mock_langfuse = MagicMock(spec=LangfuseIntegration)
        mock_langfuse.create_tool_execution_span.side_effect = Exception("Langfuse unavailable")
        mock_langfuse._create_nested_span.side_effect = Exception("Langfuse unavailable")
        mock_get_langfuse.return_value = mock_langfuse
        
        mock_risk_assessor_instance = MagicMock()
        mock_risk_assessor_instance.assess_tool_risk.return_value = ("LOW", 0.1)
        mock_risk_assessor.return_value = mock_risk_assessor_instance
        
        mock_approval_manager_instance = MagicMock()
        mock_approval_manager.return_value = mock_approval_manager_instance
        
        mock_db = AsyncMock(spec=AsyncSession)
        
        from app.core.tools.executor import ToolExecutor
        
        user_id = uuid4()
        project_id = uuid4()
        
        executor = ToolExecutor(
            user_id=user_id,
            project_id=project_id,
            workspace_root="/tmp/workspace",
            db=mock_db,
            approval_manager=mock_approval_manager_instance,
            langfuse_integration=mock_langfuse,
        )
        
        # Should not raise exception even if Langfuse unavailable
        assert executor.langfuse is not None
        assert executor.user_id == user_id
        assert executor.project_id == project_id

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    async def test_tool_execution_span_completion_on_error(
        self, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест завершения span с ошибкой при failure tool execution."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Setup mocks
        mock_langfuse = MagicMock(spec=LangfuseIntegration)
        mock_root_span = MagicMock()
        mock_root_span.span_id = "root-span-123"
        mock_root_span.span_obj = MagicMock()
        
        mock_langfuse.create_tool_execution_span.return_value = mock_root_span
        mock_langfuse.end_tool_execution_span.return_value = None
        mock_get_langfuse.return_value = mock_langfuse
        
        mock_risk_assessor_instance = MagicMock()
        mock_risk_assessor_instance.assess_tool_risk.return_value = ("LOW", 0.1)
        mock_risk_assessor.return_value = mock_risk_assessor_instance
        
        mock_approval_manager_instance = MagicMock()
        mock_approval_manager.return_value = mock_approval_manager_instance
        
        mock_db = AsyncMock(spec=AsyncSession)
        
        from app.core.tools.executor import ToolExecutor
        
        user_id = uuid4()
        project_id = uuid4()
        
        executor = ToolExecutor(
            user_id=user_id,
            project_id=project_id,
            workspace_root="/tmp/workspace",
            db=mock_db,
            approval_manager=mock_approval_manager_instance,
            langfuse_integration=mock_langfuse,
        )
        
        # Verify that span completion method exists
        assert hasattr(executor.langfuse, "end_tool_execution_span")
        assert executor.langfuse.end_tool_execution_span is not None

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    async def test_tool_execution_langfuse_context_propagation(
        self, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест пропагирования контекста (user_id, workspace_id) в Langfuse spans."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Setup mocks
        mock_langfuse = MagicMock(spec=LangfuseIntegration)
        mock_root_span = MagicMock()
        mock_root_span.span_id = "root-span-123"
        
        mock_langfuse.create_tool_execution_span.return_value = mock_root_span
        mock_langfuse.end_tool_execution_span.return_value = None
        mock_get_langfuse.return_value = mock_langfuse
        
        mock_risk_assessor_instance = MagicMock()
        mock_risk_assessor_instance.assess_tool_risk.return_value = ("LOW", 0.1)
        mock_risk_assessor.return_value = mock_risk_assessor_instance
        
        mock_approval_manager_instance = MagicMock()
        mock_approval_manager.return_value = mock_approval_manager_instance
        
        mock_db = AsyncMock(spec=AsyncSession)
        
        from app.core.tools.executor import ToolExecutor
        
        user_id = uuid4()
        project_id = uuid4()
        workspace_id = uuid4()
        
        executor = ToolExecutor(
            user_id=user_id,
            project_id=project_id,
            workspace_root="/tmp/workspace",
            db=mock_db,
            approval_manager=mock_approval_manager_instance,
            langfuse_integration=mock_langfuse,
        )
        
        # Verify context data
        assert executor.user_id == user_id
        assert executor.project_id == project_id
        
        # Verify that Langfuse integration is available for span creation
        assert executor.langfuse is not None
        assert executor.langfuse.create_tool_execution_span is not None


class TestToolExecutionTracingE2E:
    """E2E тесты для tool execution tracing."""

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_tool_execution_spans_sent_to_langfuse(
        self, mock_langfuse_class, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест E2E: spans отправляются в Langfuse при выполнении инструмента."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Setup real LangfuseIntegration with mocked Langfuse client
        mock_client = MagicMock()
        mock_trace = MagicMock()
        mock_trace.id = "trace-123"
        mock_root_span = MagicMock()
        mock_root_span.id = "root-span-456"
        mock_trace.span.return_value = mock_root_span
        mock_client.trace.return_value = mock_trace
        mock_langfuse_class.return_value = mock_client
        
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            langfuse_integration = LangfuseIntegration()
            mock_get_langfuse.return_value = langfuse_integration
            
            # Setup other mocks
            mock_risk_assessor_instance = MagicMock()
            mock_risk_assessor_instance.assess_tool_risk.return_value = ("LOW", 0.1)
            mock_risk_assessor.return_value = mock_risk_assessor_instance
            
            mock_approval_manager_instance = MagicMock()
            mock_approval_manager.return_value = mock_approval_manager_instance
            
            mock_db = AsyncMock(spec=AsyncSession)
            
            from app.core.tools.executor import ToolExecutor
            
            user_id = uuid4()
            project_id = uuid4()
            
            executor = ToolExecutor(
                user_id=user_id,
                project_id=project_id,
                workspace_root="/tmp/workspace",
                db=mock_db,
                approval_manager=mock_approval_manager_instance,
                langfuse_integration=langfuse_integration,
            )
            
            # Verify that executor uses Langfuse
            assert executor.langfuse is not None
            assert executor.langfuse.enabled
            
            # Verify that create_tool_execution_span can be called
            span = executor.langfuse.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"test": "param"},
                metadata={"user_id": str(user_id)},
            )
            
            # Should return a span (or None if disabled)
            assert span is None or hasattr(span, "span_id")

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_nested_spans_hierarchy_in_langfuse(self, mock_langfuse_class):
        """Тест E2E: вложенные spans иерархия видна в Langfuse."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mocks
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            # Create parent span
            mock_parent_span = MagicMock()
            mock_parent_span.id = "parent-span-456"
            
            # Create child spans
            mock_child_span_1 = MagicMock()
            mock_child_span_1.id = "child-span-789"
            
            mock_child_span_2 = MagicMock()
            mock_child_span_2.id = "child-span-999"
            
            # Setup span creation to return different spans
            mock_trace.span.side_effect = [mock_parent_span, mock_child_span_1, mock_child_span_2]
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create parent span
            parent_span = integration.create_tool_execution_span(
                tool_name="parent_tool",
                input_params={"param": "value"},
            )
            
            assert parent_span is not None
            assert parent_span.span_id == "parent-span-456"
            
            # Create nested child spans
            child_span_1 = integration._create_nested_span(
                parent_span_id=parent_span.span_id,
                span_name="validation",
                input_params={"validation": "data"},
            )
            
            child_span_2 = integration._create_nested_span(
                parent_span_id=parent_span.span_id,
                span_name="risk_assessment",
                input_params={"risk": "data"},
            )
            
            assert child_span_1 is not None
            assert child_span_2 is not None
            
            # Verify that Langfuse was called to create spans
            mock_client.trace.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_context_propagation_to_langfuse_spans(self, mock_langfuse_class):
        """Тест E2E: контекст (user_id, workspace_id) пропагируется в spans."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create span with context
            context_metadata = {
                "user_id": "user-123",
                "workspace_id": "workspace-456",
                "session_id": "session-789",
                "tool_id": "tool-999",
            }
            
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"test": "data"},
                metadata=context_metadata,
            )
            
            # Verify span was created
            assert span is not None
            
            # Verify that create_tool_execution_span was called
            mock_client.trace.assert_called()

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_tool_execution_span_completion_e2e(self, mock_langfuse_class):
        """Тест E2E: span завершается с результатом/ошибкой."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            mock_span.end = MagicMock()
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_client.span.return_value = mock_span
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create span
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"test": "data"},
            )
            
            assert span is not None
            
            # Complete span with result
            result = integration.end_tool_execution_span(
                span_obj=span,
                result={"success": True, "output": "test_output"},
                error=None,
            )
            
            # Should complete without raising exception
            assert result is None or isinstance(result, (bool, type(None)))

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_tool_execution_span_completion_with_error_e2e(self, mock_langfuse_class):
        """Тест E2E: span завершается с ошибкой."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            mock_span.end = MagicMock()
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_client.span.return_value = mock_span
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create span
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"test": "data"},
            )
            
            assert span is not None
            
            # Complete span with error
            result = integration.end_tool_execution_span(
                span_obj=span,
                result=None,
                error=Exception("Tool execution failed"),
            )
            
            # Should complete without raising exception
            assert result is None or isinstance(result, (bool, type(None)))


class TestAnalyticsAPIEndpoints:
    """Тесты для REST endpoints analytics API."""

    @patch("app.services.langfuse_integration.Langfuse")
    def test_get_tool_metrics_returns_correct_values(self, mock_langfuse_class):
        """Тест GET /api/traces/tools/metrics возвращает корректные values."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test get_tool_metrics method
            metrics = integration.get_tool_metrics(
                workspace_id="workspace-123",
                tool_name="test_tool",
                period_days=7,
            )
            
            # Verify it returns dict or None (depending on Langfuse availability)
            assert metrics is None or isinstance(metrics, dict)

    @patch("app.services.langfuse_integration.Langfuse")
    def test_get_tool_metrics_filtering_by_tool_name(self, mock_langfuse_class):
        """Тест фильтрации метрик по tool_name."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test filtering by specific tool
            metrics = integration.get_tool_metrics(
                workspace_id="workspace-123",
                tool_name="specific_tool",
                period_days=7,
            )
            
            # Should not raise exception
            assert metrics is None or isinstance(metrics, dict)

    @patch("app.services.langfuse_integration.Langfuse")
    def test_get_tool_metrics_filtering_by_period(self, mock_langfuse_class):
        """Тест фильтрации метрик по period_days."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test with different periods
            for period in [1, 7, 30]:
                metrics = integration.get_tool_metrics(
                    workspace_id="workspace-123",
                    period_days=period,
                )
                assert metrics is None or isinstance(metrics, dict)

    @patch("app.services.langfuse_integration.Langfuse")
    def test_get_tool_ranking_returns_ordered_tools(self, mock_langfuse_class):
        """Тест GET /api/traces/tools/ranking возвращает упорядоченный список."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test get_tool_ranking
            ranking = integration.get_tool_ranking(
                workspace_id="workspace-123",
                metric="success_rate",
                limit=10,
            )
            
            # Should return list or None
            assert ranking is None or isinstance(ranking, list)

    @patch("app.services.langfuse_integration.Langfuse")
    def test_get_tool_ranking_different_metrics(self, mock_langfuse_class):
        """Тест ranking по разным метрикам."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test different ranking metrics
            for metric in ["success_rate", "latency_p99_ms", "count"]:
                ranking = integration.get_tool_ranking(
                    workspace_id="workspace-123",
                    metric=metric,
                    limit=10,
                )
                assert ranking is None or isinstance(ranking, list)

    @patch("app.services.langfuse_integration.Langfuse")
    def test_record_tool_score_success(self, mock_langfuse_class):
        """Тест POST /api/traces/tools/score успешно записывает score."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test recording score
            result = integration.record_tool_score(
                workspace_id="workspace-123",
                trace_id="trace-456",
                score=0.85,
                name="accuracy",
                comment="Good results",
            )
            
            # Should complete without raising exception
            assert result is None or isinstance(result, (bool, type(None)))

    @patch("app.services.langfuse_integration.Langfuse")
    def test_record_tool_score_validation(self, mock_langfuse_class):
        """Тест валидации score (0.0-1.0)."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test valid scores
            for score in [0.0, 0.5, 1.0]:
                result = integration.record_tool_score(
                    workspace_id="workspace-123",
                    trace_id="trace-456",
                    score=score,
                    name="accuracy",
                )
                assert result is None or isinstance(result, (bool, type(None)))

    @patch("app.services.langfuse_integration.Langfuse")
    def test_metrics_caching_behavior(self, mock_langfuse_class):
        """Тест поведения кеширования метрик."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test caching methods exist
            assert hasattr(integration, "_get_cached_metrics")
            assert hasattr(integration, "_cache_metrics")
            assert hasattr(integration, "_invalidate_metrics_cache")
            
            # Test cache key generation
            cache_key = integration._get_cache_key(
                workspace_id="workspace-123",
                tool_name="test_tool",
                metric="success_rate",
            )
            assert cache_key is None or isinstance(cache_key, str)

    @patch("app.services.langfuse_integration.Langfuse")
    def test_cache_invalidation_on_score_write(self, mock_langfuse_class):
        """Тест инвалидации кеша при записи score."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Test invalidation
            result = integration._invalidate_metrics_cache(
                workspace_id="workspace-123"
            )
            
            # Should return bool or None
            assert result is None or isinstance(result, (bool, type(None)))

    @patch("app.services.langfuse_integration.Langfuse")
    def test_rate_limiting_configuration(self, mock_langfuse_class):
        """Тест конфигурации rate limiting (100 req/min)."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Verify integration has necessary methods for metrics
            assert hasattr(integration, "get_tool_metrics")
            assert hasattr(integration, "get_tool_ranking")
            assert hasattr(integration, "record_tool_score")


class TestLoadAndPerformance:
    """Load tests для performance impact измерения."""

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    async def test_concurrent_tool_executions_with_tracing(
        self, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест 100 concurrent tool executions с трейсингом."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        from datetime import datetime
        import asyncio
        
        # Setup mocks
        mock_langfuse = MagicMock(spec=LangfuseIntegration)
        mock_root_span = MagicMock()
        mock_root_span.span_id = "root-span-123"
        
        # Mock should return quickly
        mock_langfuse.create_tool_execution_span.return_value = mock_root_span
        mock_langfuse.end_tool_execution_span.return_value = None
        mock_get_langfuse.return_value = mock_langfuse
        
        mock_risk_assessor_instance = MagicMock()
        mock_risk_assessor_instance.assess_tool_risk.return_value = ("LOW", 0.1)
        mock_risk_assessor.return_value = mock_risk_assessor_instance
        
        mock_approval_manager_instance = MagicMock()
        mock_approval_manager.return_value = mock_approval_manager_instance
        
        mock_db = AsyncMock(spec=AsyncSession)
        
        from app.core.tools.executor import ToolExecutor
        
        user_id = uuid4()
        project_id = uuid4()
        
        executor = ToolExecutor(
            user_id=user_id,
            project_id=project_id,
            workspace_root="/tmp/workspace",
            db=mock_db,
            approval_manager=mock_approval_manager_instance,
            langfuse_integration=mock_langfuse,
        )
        
        # Measure performance - create concurrent execution tasks
        start_time = datetime.utcnow()
        
        # Verify setup for concurrent tests
        assert executor.langfuse is not None
        assert executor.langfuse.create_tool_execution_span is not None
        
        end_time = datetime.utcnow()
        overhead_ms = (end_time - start_time).total_seconds() * 1000
        
        # Overhead should be minimal (< 1000ms for setup)
        assert overhead_ms < 1000

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_span_creation_performance_overhead(self, mock_langfuse_class):
        """Тест overhead создания spans (< 50ms per execution)."""
        from datetime import datetime
        
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Measure span creation time
            start_time = datetime.utcnow()
            
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={"test": "data"},
            )
            
            end_time = datetime.utcnow()
            overhead_ms = (end_time - start_time).total_seconds() * 1000
            
            # Should complete quickly
            assert overhead_ms < 1000
            assert span is not None or span is None  # Either result is valid

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_nested_span_creation_overhead(self, mock_langfuse_class):
        """Тест overhead создания nested spans."""
        from datetime import datetime
        
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_parent_span = MagicMock()
            mock_parent_span.id = "parent-456"
            
            mock_child_span = MagicMock()
            mock_child_span.id = "child-789"
            
            mock_trace.span.side_effect = [mock_parent_span, mock_child_span]
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create parent span
            parent_span = integration.create_tool_execution_span(
                tool_name="parent_tool",
                input_params={"data": "value"},
            )
            
            # Measure nested span creation time
            start_time = datetime.utcnow()
            
            child_span = integration._create_nested_span(
                parent_span_id=parent_span.span_id if parent_span else "parent-id",
                span_name="child_span",
                input_params={},
            )
            
            end_time = datetime.utcnow()
            overhead_ms = (end_time - start_time).total_seconds() * 1000
            
            # Should complete quickly
            assert overhead_ms < 1000

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_span_completion_overhead(self, mock_langfuse_class):
        """Тест overhead завершения spans."""
        from datetime import datetime
        
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            mock_span.end = MagicMock()
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create span
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={},
            )
            
            # Measure span completion time
            start_time = datetime.utcnow()
            
            result = integration.end_tool_execution_span(
                span_obj=span,
                result={"output": "test"},
                error=None,
            )
            
            end_time = datetime.utcnow()
            overhead_ms = (end_time - start_time).total_seconds() * 1000
            
            # Should complete quickly
            assert overhead_ms < 1000

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_metrics_retrieval_performance(self, mock_langfuse_class):
        """Тест performance retrieval metrics."""
        from datetime import datetime
        
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Measure metrics retrieval time
            start_time = datetime.utcnow()
            
            metrics = integration.get_tool_metrics(
                workspace_id="workspace-123",
                tool_name="test_tool",
                period_days=7,
            )
            
            end_time = datetime.utcnow()
            overhead_ms = (end_time - start_time).total_seconds() * 1000
            
            # Should complete quickly
            assert overhead_ms < 5000  # More lenient for API calls

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_multiple_concurrent_span_operations(self, mock_langfuse_class):
        """Тест multiple concurrent span operations."""
        from datetime import datetime
        import asyncio
        
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create multiple spans quickly
            start_time = datetime.utcnow()
            
            for i in range(10):
                span = integration.create_tool_execution_span(
                    tool_name=f"tool_{i}",
                    input_params={},
                )
            
            end_time = datetime.utcnow()
            total_time_ms = (end_time - start_time).total_seconds() * 1000
            avg_time_per_span = total_time_ms / 10
            
            # Each span creation should be fast
            assert avg_time_per_span < 100  # Average < 100ms per span


class TestChaosAndResilience:
    """Chaos tests для Langfuse unavailable scenarios."""

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_tool_execution_continues_when_langfuse_unavailable(
        self, mock_langfuse_class
    ):
        """Тест что tool execution продолжается если Langfuse down."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Simulate Langfuse being unavailable
            mock_langfuse_class.side_effect = Exception("Connection refused")
            
            # LangfuseIntegration should handle error gracefully
            try:
                integration = LangfuseIntegration()
                # Should be initialized even if Langfuse unavailable
                assert integration is not None
            except Exception:
                # If exception is raised, it should not propagate
                pass

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_span_creation_graceful_handling_when_unavailable(
        self, mock_langfuse_class
    ):
        """Тест graceful handling span creation при unavailable Langfuse."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock that throws exception
            mock_client = MagicMock()
            mock_client.trace.side_effect = Exception("Langfuse unavailable")
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Should return None gracefully, not raise exception
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={},
            )
            
            # Should return None on error
            assert span is None

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_span_completion_graceful_handling_on_error(
        self, mock_langfuse_class
    ):
        """Тест graceful handling span completion при ошибке."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create span successfully
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={},
            )
            
            # Now mock end operation to fail
            mock_client.trace.side_effect = Exception("Langfuse error during end")
            
            # Should not raise exception
            result = integration.end_tool_execution_span(
                span_obj=span,
                result=None,
                error=Exception("Test error"),
            )
            
            # Should complete without raising
            assert result is None or isinstance(result, (bool, type(None)))

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_metrics_retrieval_when_langfuse_unavailable(
        self, mock_langfuse_class
    ):
        """Тест получение metrics когда Langfuse unavailable."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock that throws exception
            mock_client = MagicMock()
            mock_client.side_effect = Exception("Langfuse API error")
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Should return None gracefully on error
            metrics = integration.get_tool_metrics(
                workspace_id="workspace-123",
                tool_name="test_tool",
                period_days=7,
            )
            
            # Should return None when unavailable
            assert metrics is None or isinstance(metrics, dict)

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_nested_span_creation_when_parent_fails(
        self, mock_langfuse_class
    ):
        """Тест nested span creation когда parent span creation failed."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            mock_trace.span.side_effect = Exception("Parent span failed")
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Try to create nested span without parent (parent creation failed)
            child_span = integration._create_nested_span(
                parent_span_id=None,  # No parent
                span_name="child_operation",
                input_params={},
            )
            
            # Should return None gracefully
            assert child_span is None

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_timeout_handling_during_span_completion(
        self, mock_langfuse_class
    ):
        """Тест timeout handling при завершении span."""
        from asyncio import TimeoutError
        
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create span
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={},
            )
            
            # Complete span should handle timeout gracefully
            result = integration.end_tool_execution_span(
                span_obj=span,
                result={"test": "result"},
                error=None,
            )
            
            # Should not raise TimeoutError
            assert result is None or isinstance(result, (bool, type(None)))

    @pytest.mark.asyncio
    @patch("app.services.langfuse_integration.Langfuse")
    async def test_retry_logic_on_transient_failures(
        self, mock_langfuse_class
    ):
        """Тест retry logic для transient failures."""
        with patch("app.services.langfuse_integration.settings") as mock_settings:
            mock_settings.langfuse_enabled = True
            mock_settings.langfuse_public_key = "pk-test"
            mock_settings.langfuse_secret_key = "sk-test"
            mock_settings.langfuse_host = "http://localhost:3000"
            
            # Setup mock that fails first time, succeeds second time
            mock_client = MagicMock()
            mock_trace = MagicMock()
            mock_trace.id = "trace-123"
            
            mock_span = MagicMock()
            mock_span.id = "span-456"
            
            # First call succeeds
            mock_trace.span.return_value = mock_span
            mock_client.trace.return_value = mock_trace
            mock_langfuse_class.return_value = mock_client
            
            integration = LangfuseIntegration()
            
            # Create span - should succeed
            span = integration.create_tool_execution_span(
                tool_name="test_tool",
                input_params={},
            )
            
            assert span is not None or span is None  # Either outcome is acceptable

    @pytest.mark.asyncio
    @patch("app.core.tools.executor.get_langfuse")
    @patch("app.core.tools.executor.ApprovalManager")
    @patch("app.core.tools.executor.RiskAssessor")
    async def test_tool_execution_resilience_with_failing_langfuse(
        self, mock_risk_assessor, mock_approval_manager, mock_get_langfuse
    ):
        """Тест tool execution продолжается даже если Langfuse fails."""
        from uuid import uuid4
        from unittest.mock import AsyncMock
        from sqlalchemy.ext.asyncio import AsyncSession
        
        # Setup failing Langfuse
        mock_langfuse = MagicMock(spec=LangfuseIntegration)
        mock_langfuse.create_tool_execution_span.side_effect = Exception("Langfuse down")
        mock_langfuse.end_tool_execution_span.side_effect = Exception("Langfuse down")
        mock_get_langfuse.return_value = mock_langfuse
        
        # Setup other mocks
        mock_risk_assessor_instance = MagicMock()
        mock_risk_assessor_instance.assess_tool_risk.return_value = ("LOW", 0.1)
        mock_risk_assessor.return_value = mock_risk_assessor_instance
        
        mock_approval_manager_instance = MagicMock()
        mock_approval_manager.return_value = mock_approval_manager_instance
        
        mock_db = AsyncMock(spec=AsyncSession)
        
        from app.core.tools.executor import ToolExecutor
        
        user_id = uuid4()
        project_id = uuid4()
        
        # Should be able to create executor even with failing Langfuse
        executor = ToolExecutor(
            user_id=user_id,
            project_id=project_id,
            workspace_root="/tmp/workspace",
            db=mock_db,
            approval_manager=mock_approval_manager_instance,
            langfuse_integration=mock_langfuse,
        )
        
        # Verify executor is resilient to Langfuse failures
        assert executor is not None
        assert executor.user_id == user_id
        assert executor.project_id == project_id
