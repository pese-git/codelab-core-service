"""Langfuse интеграция для LLM observability."""

import asyncio
import logging
import json
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from langfuse import Langfuse

from app.config import settings
from app.logging_config import get_logger
from app.metrics import (
    record_callback_failure,
    record_span_created,
    record_trace_created,
    trace_latency,
)
from app.metrics import (
    record_score as record_score_metric,
)

logger = logging.getLogger(__name__)
struct_logger = get_logger(__name__)


@dataclass(frozen=True)
class LangfuseTraceRef:
    """Lightweight reference to a Langfuse trace."""
    id: str


@dataclass
class ToolExecutionSpan:
    """
    Обертка для tool execution span в Langfuse.
    
    Хранит информацию о span для инструмента с поддержкой
    отслеживания статуса и завершения.
    """
    span: Any  # Underlying Langfuse span object
    tool_name: str  # Имя инструмента (например, "search_docs")
    span_id: str = ""  # ID span для связывания nested spans
    status: str = "pending"  # Статус: pending, success, error
    start_time: float = 0.0  # Время начала выполнения
    end_time: float | None = None  # Время завершения


class LangfuseIntegration:
    """
    Обертка вокруг Langfuse SDK для unified интеграции с LLM observability.

    Обеспечивает:
    - Управление lifecycle (инициализация, shutdown, reconnection)
    - Graceful degradation при ошибках (все методы возвращают None при disabled/error)
    - Context propagation (user_id, workspace_id из structlog)
    - Unified API для создания traces, spans, scores
    """

    def __init__(self) -> None:
        """
        Инициализация LangfuseIntegration с graceful обработкой.

        При инициализации выполняется:
        1. Проверка конфигурации (LANGFUSE_ENABLED)
        2. Health check (если enabled)
        3. Инициализация клиента (если langfuse_enabled)
        4. Логирование статуса
        """
        self.enabled = settings.langfuse_enabled
        self.client: Langfuse | None = None
        self._current_trace: Any | None = None

        if not self.enabled:
            struct_logger.info("langfuse_disabled", reason="LANGFUSE_ENABLED=false")
            return

        try:
            # Инициализируем Langfuse клиент
            self.client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                base_url=settings.langfuse_host,
                debug=True,  # Отключаем debug для продакшена
            )

            # Выполняем health check
            self._perform_health_check()

            struct_logger.info(
                "langfuse_initialized",
                host=settings.langfuse_host,
            )
        except Exception as e:
            struct_logger.error(
                "langfuse_initialization_failed",
                error=str(e),
                host=settings.langfuse_host,
            )
            # Graceful degradation: сохраняем enabled=False и продолжаем работу
            self.enabled = False
            self.client = None

    @staticmethod
    def _mask_sensitive(text: str) -> str:
        """Mask common sensitive patterns in text."""
        # Emails
        text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "***@***", text)
        # Phone numbers (very rough)
        text = re.sub(r"\+?\d[\d\-\s\(\)]{7,}\d", "***", text)
        # API keys / tokens in key=value or key: value formats
        text = re.sub(
            r"(?i)\b(api[_-]?key|token|secret|password)\b\s*[:=]\s*([^\s,;]+)",
            r"\1=***",
            text,
        )
        # OpenAI-style keys
        text = re.sub(r"\bsk-[A-Za-z0-9]{20,}\b", "sk-***", text)
        # Bearer tokens
        text = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9\._\-]+\b", "Bearer ***", text)
        return text

    def _sanitize_payload(self, payload: Any | None) -> Any | None:
        """Sanitize payloads before sending to Langfuse."""
        if payload is None:
            return None
        if settings.langfuse_full_prompts:
            return payload

        if isinstance(payload, (dict, list)):
            text = json.dumps(payload, ensure_ascii=True, default=str)
        else:
            text = str(payload)

        text = self._mask_sensitive(text)

        max_chars = settings.langfuse_payload_max_chars
        if max_chars > 0 and len(text) > max_chars:
            text = text[:max_chars] + "...(truncated)"

        return text

    def _perform_health_check(self) -> None:
        """
        Выполняет health check Langfuse сервиса.

        Raises:
            Exception: Если сервер недоступен или некорректно сконфигурирован
        """
        if not self.client:
            raise RuntimeError("Langfuse client не инициализирован")

        try:
            # Пытаемся выполнить простой запрос
            # Langfuse SDK не имеет встроенного health check,
            # поэтому просто проверяем что клиент создан успешно
            _ = self.client
        except Exception as e:
            struct_logger.error(
                "langfuse_health_check_failed",
                error=str(e),
            )
            raise

    def create_trace(
        self,
        name: str,
        user_id: UUID | None = None,
        workspace_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        otel_trace_id: str | None = None,
    ) -> Any | None:
        """
        Создает новый trace в Langfuse.

        Args:
            name: Имя trace (например, "agent_process_message")
            user_id: ID пользователя (опционально, используется из structlog если не передан)
            workspace_id: ID workspace (опционально, используется из structlog если не передан)
            metadata: Дополнительные метаданные trace

        Returns:
            Trace object или None если disabled/error
        """
        if not self.enabled or not self.client:
            return None

        try:
            # Извлекаем контекст из structlog если не передан
            if user_id is None or workspace_id is None:
                context = structlog.contextvars.get_contextvars()
                if user_id is None:
                    user_id = context.get("user_id")
                if workspace_id is None:
                    workspace_id = context.get("workspace_id")

            # Готовим метаданные trace
            trace_metadata = metadata or {}
            if user_id:
                trace_metadata["user_id"] = str(user_id)
            if workspace_id:
                trace_metadata["workspace_id"] = str(workspace_id)
            if otel_trace_id:
                trace_metadata["otel_trace_id"] = otel_trace_id

            # Измеряем latency создания trace
            with trace_latency():
                trace_id = self.client.create_trace_id()
                self.client.create_event(
                    trace_context={"trace_id": trace_id},
                    name=name,
                    metadata=trace_metadata,
                )

            trace = LangfuseTraceRef(id=trace_id)
            self._current_trace = trace

            # Записываем метрику
            if workspace_id:
                record_trace_created(str(workspace_id))

            struct_logger.info(
                "langfuse_trace_created",
                trace_id=trace.id,
                name=name,
                user_id=str(user_id) if user_id else None,
            )

            return trace

        except Exception as e:
            # Записываем ошибку callback
            record_callback_failure("trace_creation", type(e).__name__)

            struct_logger.error(
                "langfuse_trace_creation_failed",
                error=str(e),
                name=name,
            )
            return None

    def create_span(
        self,
        trace: Any,
        name: str,
        input_data: Any | None = None,
        output_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "success",
    ) -> Any | None:
        """
        Создает span внутри trace.

        Args:
            trace: Родительский trace (из create_trace)
            name: Имя span (например, "prepare_context")
            input_data: Входные данные span (опционально)
            output_data: Выходные данные span (опционально)
            metadata: Дополнительные метаданные
            status: Статус span ("success", "error", etc)

        Returns:
            Span object или None если disabled/error
        """
        if not self.enabled or not self.client or not trace:
            return None

        try:
            # Создаем событие как span-эквивалент в Langfuse
            span = self.client.create_event(
                trace_context={"trace_id": trace.id},
                name=name,
                input=self._sanitize_payload(input_data) if input_data is not None else None,
                output=self._sanitize_payload(output_data) if output_data is not None else None,
                metadata=metadata,
                level="ERROR" if status == "error" else "DEFAULT",
            )

            # Записываем метрику
            record_span_created(str(trace.id))

            struct_logger.info(
                "langfuse_span_created",
                trace_id=trace.id,
                span_name=name,
                status=status,
            )

            return span

        except Exception as e:
            # Записываем ошибку callback
            record_callback_failure("span_creation", type(e).__name__)

            struct_logger.error(
                "langfuse_span_creation_failed",
                error=str(e),
                name=name,
            )
            return None

    def create_event(
        self,
        trace_id: str,
        name: str,
        input_data: Any | None = None,
        output_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """
        Создает event в trace.

        Args:
            trace_id: ID trace для создания event
            name: Имя event
            input_data: Входные данные event (опционально)
            output_data: Выходные данные event (опционально)
            metadata: Дополнительные метаданные

        Returns:
            True если успешно, False если ошибка
        """
        if not self.enabled or not self.client:
            return False

        try:
            # Готовим параметры для event
            event_kwargs: dict[str, Any] = {
                "trace_context": {"trace_id": trace_id},
                "name": name,
            }

            if input_data is not None:
                event_kwargs["input"] = self._sanitize_payload(input_data)
            if output_data is not None:
                event_kwargs["output"] = self._sanitize_payload(output_data)
            if metadata:
                event_kwargs["metadata"] = metadata

            # Создаем event в Langfuse
            self.client.create_event(**event_kwargs)

            struct_logger.info(
                "langfuse_event_created",
                trace_id=trace_id,
                event_name=name,
            )

            return True

        except Exception as e:
            # Записываем ошибку callback
            record_callback_failure("event_creation", type(e).__name__)

            struct_logger.error(
                "langfuse_event_creation_failed",
                error=str(e),
                trace_id=trace_id,
                event_name=name,
            )
            return False

    def record_score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> bool:
        """
        Записывает score (оценку качества) для trace.

        Args:
            trace_id: ID trace для которого записываем score
            name: Имя score (например, "user_satisfaction")
            value: Значение score (обычно 0-1 или 1-5)
            comment: Опциональный комментарий

        Returns:
            True если успешно, False если ошибка
        """
        if not self.enabled or not self.client:
            return False

        try:
            self.client.score(
                trace_id=trace_id,
                name=name,
                value=value,
                comment=comment,
            )

            # Записываем метрику
            record_score_metric(name)

            struct_logger.info(
                "langfuse_score_recorded",
                trace_id=trace_id,
                score_name=name,
                value=value,
            )

            return True

        except Exception as e:
            # Записываем ошибку callback
            record_callback_failure("score_recording", type(e).__name__)

            struct_logger.error(
                "langfuse_score_recording_failed",
                error=str(e),
                trace_id=trace_id,
                score_name=name,
            )
            return False

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """
        Получает информацию о trace по ID.

        Args:
            trace_id: ID trace для получения

        Returns:
            Словарь с информацией о trace или None если ошибка
        """
        if not self.enabled or not self.client:
            return None

        try:
            # Langfuse SDK не имеет встроенного метода get_trace,
            # поэтому пока возвращаем None
            # В будущем можно добавить REST API клиент для получения traces
            struct_logger.warning(
                "langfuse_get_trace_not_implemented",
                trace_id=trace_id,
            )
            return None

        except Exception as e:
            struct_logger.error(
                "langfuse_trace_retrieval_failed",
                error=str(e),
                trace_id=trace_id,
            )
            return None

    def flush(self) -> bool:
        """
        Флашит очередь Langfuse (отправляет всех pending данных).

        Returns:
            True если успешно, False если ошибка
        """
        if not self.enabled or not self.client:
            return False

        try:
            self.client.flush()
            struct_logger.info("langfuse_flushed")
            return True

        except Exception as e:
            struct_logger.error(
                "langfuse_flush_failed",
                error=str(e),
            )
            return False

    def shutdown(self) -> None:
        """Graceful shutdown Langfuse клиента."""
        if not self.enabled or not self.client:
            return

        try:
            self.client.flush()
            struct_logger.info("langfuse_shutdown")
        except Exception as e:
            struct_logger.error(
                "langfuse_shutdown_failed",
                error=str(e),
            )

    @asynccontextmanager
    async def trace_context(
        self,
        name: str,
        user_id: UUID | None = None,
        workspace_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Context manager для автоматического управления trace lifetime.

        Usage:
            async with langfuse.trace_context(
                name="agent_process_message",
                user_id=user_id,
                workspace_id=workspace_id
            ) as trace:
                # Use trace to create spans
                await process_message(trace)

        Args:
            name: Имя trace
            user_id: ID пользователя (опционально)
            workspace_id: ID workspace (опционально)
            metadata: Дополнительные метаданные

        Yields:
            Trace object или None если disabled
        """
        trace = self.create_trace(
            name=name,
            user_id=user_id,
            workspace_id=workspace_id,
            metadata=metadata,
        )

        try:
            yield trace
        except Exception as e:
            struct_logger.error(
                "langfuse_trace_context_error",
                error=str(e),
                trace_name=name,
            )
            # Re-raise the exception after logging
            raise
        finally:
            # Флашим данные при завершении context
            if trace:
                self.flush()

    @asynccontextmanager
    async def span_context(
        self,
        trace: Any,
        name: str,
        input_data: Any | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Context manager для автоматического управления span lifetime.

        Usage:
            async with langfuse.span_context(
                trace=trace,
                name="context_retrieval",
                input_data={"query": "..."}
            ) as span:
                context = await retrieve_context()

        Args:
            trace: Родительский trace (обязательно)
            name: Имя span
            input_data: Входные данные span (опционально)
            metadata: Дополнительные метаданные

        Yields:
            Span object или None если disabled
        """
        if not self.enabled or not trace:
            yield None
            return

        import time
        start_time = time.time()
        span = None

        try:
            # Создать span с начальными данными
            span = self.create_span(
                trace=trace,
                name=name,
                input_data=input_data,
                metadata=metadata,
                status="success",
            )

            yield span

            # Записать успешное завершение
            latency_ms = int((time.time() - start_time) * 1000)
            self.create_event(
                trace_id=trace.id,
                name=f"{name}_completed",
                metadata={
                    "latency_ms": latency_ms,
                    "status": "completed",
                },
            )

        except Exception as e:
            # Записать ошибку
            latency_ms = int((time.time() - start_time) * 1000)
            self.create_event(
                trace_id=trace.id,
                name=f"{name}_error",
                metadata={
                    "latency_ms": latency_ms,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            struct_logger.error(
                "langfuse_span_context_error",
                error=str(e),
                span_name=name,
                trace_id=trace.id,
                latency_ms=latency_ms,
            )

            raise

    def create_tool_execution_span(
        self,
        tool_name: str,
        input_params: dict[str, Any] | None = None,
        parent_span_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolExecutionSpan | None:
        """
        Создает span для tool execution с поддержкой nested spans.

        Args:
            tool_name: Имя инструмента (например, 'search_docs')
            input_params: Параметры инструмента (опционально)
            parent_span_id: ID parent span для nested связывания (опционально)
            metadata: Дополнительные метаданные (user_id, workspace_id, agent_id)

        Returns:
            ToolExecutionSpan объект или None если disabled/ошибка
        """
        # Graceful degradation: если Langfuse отключен или клиент не инициализирован,
        # возвращаем None без создания span. Tool execution продолжится без трейсинга.
        if not self.enabled or not self.client:
            return None

        try:
            # Если parent_span_id не указан - пытаемся получить из context.
            # Это необходимо для автоматического связывания nested spans.
            # Например, если это вложенный span внутри другого span,
            # мы хотим установить parent отношение.
            if parent_span_id is None:
                parent_span_id = self._get_current_span_id()

            # Если context не содержит metadata - извлекаем из structlog context.
            # Это обеспечивает изоляцию пользователей: каждый span получит правильные
            # user_id и workspace_id из контекста текущего request.
            if metadata is None:
                metadata = {}

            context_vars = structlog.contextvars.get_contextvars()
            if "user_id" not in metadata and "user_id" in context_vars:
                metadata["user_id"] = str(context_vars["user_id"])
            if "workspace_id" not in metadata and "workspace_id" in context_vars:
                metadata["workspace_id"] = str(context_vars["workspace_id"])
            if "agent_id" not in metadata and "agent_id" in context_vars:
                metadata["agent_id"] = str(context_vars["agent_id"])

            # Измеряем время начала для вычисления latency
            start_time = time.time()

            # Создаем span в Langfuse используя Span API.
            # parent_observation_id создает иерархию spans (parent → children).
            # Это необходимо для просмотра полного дерева execution в Langfuse dashboard.
            span = self.client.span(
                name=f"tool_{tool_name}",
                input={"params": input_params} if input_params else {},
                metadata=metadata,
                parent_observation_id=parent_span_id,
            )

            # Извлекаем span_id из объекта. Это нужно для связывания
            # дочерних spans (validation, risk_assessment, execution).
            # Если span не имеет атрибута id, используем string представление.
            span_id = span.id if hasattr(span, "id") else str(span)

            # Создаем ToolExecutionSpan обертку для удобства работы.
            # Эта обертка хранит как Langfuse span объект, так и metadata для
            # использования при завершении span (end_tool_execution_span).
            tool_span = ToolExecutionSpan(
                span=span,
                tool_name=tool_name,
                span_id=span_id,
                status="pending",
                start_time=start_time,
            )

            struct_logger.info(
                "tool_execution_span_created",
                tool_name=tool_name,
                span_id=span_id,
                parent_span_id=parent_span_id,
                user_id=metadata.get("user_id"),
            )

            return tool_span

        except Exception as e:
            # Важно: логируем ошибку но НЕ пробрасываем исключение.
            # Это обеспечивает graceful degradation: tool execution
            # продолжит работать даже если Langfuse недоступен.
            # Метрика инкрементируется для мониторинга ошибок трейсинга.
            record_callback_failure("tool_execution_span_creation", type(e).__name__)

            struct_logger.error(
                "tool_execution_span_creation_failed",
                error=str(e),
                tool_name=tool_name,
                exc_info=True,
            )
            return None

    def end_tool_execution_span(
        self,
        span_obj: ToolExecutionSpan | None,
        result: Any | None = None,
        error: Exception | None = None,
    ) -> None:
        """
        Завершает tool execution span с результатом или ошибкой.

        Отправка в Langfuse происходит асинхронно (fire-and-forget).

        Args:
            span_obj: ToolExecutionSpan объект из create_tool_execution_span
            result: Результат выполнения инструмента
            error: Exception если произошла ошибка
        """
        # Graceful exit если span не был создан (например, потому что Langfuse отключен)
        # или если трейсинг отключен. Это необходимо для безопасного вызова из
        # finally блоков tool executor.
        if not span_obj or not self.enabled:
            return

        try:
            # Вычисляем latency между началом execution (span_obj.start_time)
            # и завершением. Это нужно для отслеживания производительности инструмента.
            end_time = time.time()
            latency_ms = (end_time - span_obj.start_time) * 1000

            # Готовим output данные для отправки в Langfuse.
            # success флаг показывает был ли инструмент выполнен без ошибок.
            # latency_ms нужна для аналитики производительности.
            output = {
                "success": error is None,
                "latency_ms": latency_ms,
            }

            if result is not None:
                output["result"] = result

            if error is not None:
                output["error"] = {
                    "type": type(error).__name__,
                    "message": str(error),
                }

            # ВАЖНО: используем asyncio.create_task для fire-and-forget отправки.
            # Это обеспечивает что tool execution не блокируется на отправку в Langfuse.
            # Даже если Langfuse медленный или недоступный, инструмент вернет результат
            # пользователю немедленно. Span будет отправлен в фоне с таймаутом 5 секунд.
            asyncio.create_task(
                self._end_span_async(span_obj, output, error, latency_ms)
            )

        except Exception as e:
            struct_logger.error(
                "tool_execution_span_end_error",
                error=str(e),
                tool_name=span_obj.tool_name,
            )

    async def _end_span_async(
        self,
        span_obj: ToolExecutionSpan,
        output: dict[str, Any],
        error: Exception | None,
        latency_ms: float,
    ) -> None:
        """
        Асинхронно завершает span в Langfuse.

        Не блокирует основной flow выполнения.

        Args:
            span_obj: ToolExecutionSpan объект
            output: Выходные данные span
            error: Exception если ошибка
            latency_ms: Время выполнения в миллисекундах
        """
        try:
            # Используем asyncio.wait_for с таймаутом 5 секунд для отправки span.
            # asyncio.to_thread используется потому что span.end() может быть блокирующим.
            # Таймаут предотвращает зависание если Langfuse не отвечает.
            # Это критично для graceful degradation: даже если Langfuse медленный,
            # основной task завершится и не будет занимать ресурсы.
            await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: span_obj.span.end(output=output),
                ),
                timeout=5.0,
            )

            struct_logger.info(
                "tool_execution_span_ended",
                tool_name=span_obj.tool_name,
                span_id=span_obj.span_id,
                latency_ms=latency_ms,
                success=error is None,
            )

            # Инкрементируем метрику успеха
            self._metrics_increment("langfuse.span_success")

        except asyncio.TimeoutError:
            # Timeout обработка: логируем но не пробрасываем.
            # Важно что span не был отправлен в Langfuse, но это не должно
            # влиять на основное выполнение. Tool execution уже завершился с результатом.
            struct_logger.warning(
                "tool_execution_span_timeout",
                tool_name=span_obj.tool_name,
                span_id=span_obj.span_id,
                timeout_sec=5,
                latency_ms=latency_ms,
            )
            # Инкрементируем метрику timeout для мониторинга
            self._metrics_increment("langfuse.span_timeout")
            record_callback_failure("tool_execution_span_end", "TimeoutError")

        except Exception as e:
            # Обработка других ошибок при отправке span.
            # Может быть: ConnectionError (нет интернета), ConnectionRefusedError (Langfuse down),
            # или другие ошибки сериализации. Все они логируются но не пробрасываются.
            error_type = type(e).__name__
            struct_logger.error(
                "tool_execution_span_end_failed",
                error=str(e),
                error_type=error_type,
                tool_name=span_obj.tool_name,
                span_id=span_obj.span_id,
                latency_ms=latency_ms,
                exc_info=False,
            )
            # Инкрементируем метрику ошибок для Prometheus/мониторинга
            record_callback_failure("tool_execution_span_end", error_type)
            self._metrics_increment("langfuse.send_errors")

    def _get_current_span_id(self) -> str | None:
        """
        Получить ID текущего span из context.

        Используется для автоматического связывания nested spans.

        Returns:
            Span ID или None если нет текущего span
        """
        try:
            context = structlog.contextvars.get_contextvars()
            return context.get("current_span_id")
        except Exception:
            return None

    def _create_nested_span(
        self,
        parent_span_id: str,
        span_name: str,
        input_params: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ToolExecutionSpan | None:
        """
        Создает nested span для operations внутри tool execution.

        Используется для создания child spans для:
        - tool_validation
        - tool_risk_assessment
        - tool_approval
        - tool_execution_run

        Args:
            parent_span_id: ID parent span
            span_name: Имя nested span (например, "tool_search_validation")
            input_params: Параметры для span (опционально)
            metadata: Метаданные для span (опционально)

        Returns:
            ToolExecutionSpan объект или None если disabled/ошибка
        """
        # Graceful degradation если Langfuse отключен
        if not self.enabled or not self.client:
            return None

        # Nested spans требуют parent_span_id для иерархии.
        # Если parent_span_id не указан, мы не можем создать иерархию,
        # поэтому логируем warning и возвращаем None.
        if not parent_span_id:
            struct_logger.warning(
                "nested_span_creation_skipped",
                reason="parent_span_id is required",
                span_name=span_name,
            )
            return None

        try:
            # Инициализируем metadata если не передан
            if metadata is None:
                metadata = {}

            # Фиксируем время начала для вычисления latency
            start_time = time.time()

            # Создаем nested span с явным parent_observation_id.
            # Это связывает child span с parent span в Langfuse иерархии.
            # Пример иерархии:
            #   tool_search (root span)
            #   ├── tool_search_validation (nested)
            #   ├── tool_search_risk_assessment (nested)
            #   └── tool_search_execution (nested)
            # Эта иерархия видна в Langfuse dashboard для анализа.
            span = self.client.span(
                name=span_name,
                input={"params": input_params} if input_params else {},
                metadata=metadata,
                parent_observation_id=parent_span_id,
            )

            # Извлекаем span_id для связывания будущих nested spans
            span_id = span.id if hasattr(span, "id") else str(span)

            # Парсим tool_name из span_name.
            # Примеры:
            # - "tool_search_validation" → tool_name = "search"
            # - "tool_calculator_execution" → tool_name = "calculator"
            # Это используется для логирования и аналитики.
            tool_name = span_name.replace("tool_", "").split("_")[0]

            # Создаем обертку для удобства работы
            tool_span = ToolExecutionSpan(
                span=span,
                tool_name=tool_name,
                span_id=span_id,
                status="pending",
                start_time=start_time,
            )

            struct_logger.info(
                "nested_span_created",
                span_name=span_name,
                span_id=span_id,
                parent_span_id=parent_span_id,
                tool_name=tool_name,
            )

            return tool_span

        except Exception as e:
            # Логируем но не пробрасываем ошибку для graceful degradation
            record_callback_failure("nested_span_creation", type(e).__name__)

            struct_logger.error(
                "nested_span_creation_failed",
                error=str(e),
                span_name=span_name,
                parent_span_id=parent_span_id,
                exc_info=True,
            )
            return None

    def _metrics_increment(self, metric_name: str, value: int = 1) -> None:
        """
        Инкрементировать метрику (опционально, для monitoring).

        Args:
            metric_name: Имя метрики
            value: Значение для инкремента
        """
        # Это может быть расширено для интеграции с Prometheus или другим мониторингом
        pass

    def get_tool_metrics(
        self,
        workspace_id: str,
        tool_name: str | None = None,
        period_days: int = 7,
    ) -> dict[str, Any] | None:
        """
        Получить метрики выполнения инструмента из Langfuse.

        Args:
            workspace_id: ID рабочей области
            tool_name: Опциональное имя инструмента (если не указано, получить для всех)
            period_days: Период в днях для анализа (по умолчанию 7)

        Returns:
            Словарь с метриками или None если трейсинг отключен/ошибка
        """
        if not self.enabled:
            return None

        try:
            from app.services.langfuse_rest_client import get_langfuse_rest_client
            
            rest_client = get_langfuse_rest_client()
            
            # Получить traces за период
            traces = asyncio.run(
                rest_client.get_traces(
                    limit=1000,
                    tags=[f"workspace_id:{workspace_id}"]
                    + ([f"tool_name:{tool_name}"] if tool_name else []),
                )
            )
            
            if not traces:
                return {
                    "workspace_id": workspace_id,
                    "tool_name": tool_name,
                    "count": 0,
                    "success_rate": 0.0,
                    "error_rate": 0.0,
                    "latency_p50_ms": 0.0,
                    "latency_p95_ms": 0.0,
                    "latency_p99_ms": 0.0,
                }
            
            # Агрегировать метрики
            total_count = len(traces)
            successful_count = sum(
                1 for trace in traces
                if trace.get("status") in ["success", "completed"]
            )
            error_count = total_count - successful_count
            
            # Вычислить latencies
            latencies = []
            for trace in traces:
                if trace.get("duration_ms"):
                    latencies.append(trace["duration_ms"])
            
            latencies.sort()
            latency_p50 = latencies[int(len(latencies) * 0.5)] if latencies else 0
            latency_p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
            latency_p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
            
            return {
                "workspace_id": workspace_id,
                "tool_name": tool_name or "all",
                "count": total_count,
                "success_count": successful_count,
                "error_count": error_count,
                "success_rate": successful_count / total_count if total_count > 0 else 0,
                "error_rate": error_count / total_count if total_count > 0 else 0,
                "latency_p50_ms": round(latency_p50, 2),
                "latency_p95_ms": round(latency_p95, 2),
                "latency_p99_ms": round(latency_p99, 2),
            }
        except Exception as e:
            self.logger.error(
                "get_tool_metrics_error",
                workspace_id=workspace_id,
                tool_name=tool_name,
                error=str(e),
                exc_info=True,
            )
            return None

    def get_tool_ranking(
        self,
        workspace_id: str,
        metric: str = "success_rate",
        limit: int = 10,
    ) -> list[dict[str, Any]] | None:
        """
        Получить рейтинг инструментов по выбранной метрике.

        Args:
            workspace_id: ID рабочей области
            metric: Метрика для сортировки ("success_rate", "latency_p99_ms", "count")
            limit: Максимальное количество инструментов в рейтинге

        Returns:
            Список инструментов, отсортированный по выбранной метрике, или None при ошибке
        """
        if not self.enabled:
            return None

        try:
            from app.services.langfuse_rest_client import get_langfuse_rest_client
            
            rest_client = get_langfuse_rest_client()
            
            # Получить все traces для workspace
            traces = asyncio.run(
                rest_client.get_traces(
                    limit=5000,
                    tags=[f"workspace_id:{workspace_id}"],
                )
            )
            
            if not traces:
                return []
            
            # Группировать метрики по tool_name
            tool_metrics: dict[str, dict[str, Any]] = {}
            
            for trace in traces:
                tool_name = trace.get("metadata", {}).get("tool_name", "unknown")
                
                if tool_name not in tool_metrics:
                    tool_metrics[tool_name] = {
                        "tool_name": tool_name,
                        "count": 0,
                        "success_count": 0,
                        "latencies": [],
                    }
                
                tool_metrics[tool_name]["count"] += 1
                
                if trace.get("status") in ["success", "completed"]:
                    tool_metrics[tool_name]["success_count"] += 1
                
                if trace.get("duration_ms"):
                    tool_metrics[tool_name]["latencies"].append(trace["duration_ms"])
            
            # Вычислить финальные метрики для каждого инструмента
            ranked_tools = []
            for tool_name, metrics in tool_metrics.items():
                latencies = sorted(metrics["latencies"])
                latency_p99 = (
                    latencies[int(len(latencies) * 0.99)]
                    if latencies
                    else 0
                )
                
                success_rate = (
                    metrics["success_count"] / metrics["count"]
                    if metrics["count"] > 0
                    else 0
                )
                
                tool_data = {
                    "tool_name": tool_name,
                    "count": metrics["count"],
                    "success_rate": round(success_rate, 4),
                    "latency_p99_ms": round(latency_p99, 2),
                }
                ranked_tools.append(tool_data)
            
            # Сортировать по выбранной метрике
            if metric == "success_rate":
                ranked_tools.sort(
                    key=lambda x: x["success_rate"],
                    reverse=True
                )
            elif metric == "latency_p99_ms":
                ranked_tools.sort(
                    key=lambda x: x["latency_p99_ms"],
                    reverse=False
                )
            elif metric == "count":
                ranked_tools.sort(
                    key=lambda x: x["count"],
                    reverse=True
                )
            else:
                self.logger.warning(
                    "unknown_ranking_metric",
                    metric=metric,
                    workspace_id=workspace_id,
                )
                return None
            
            return ranked_tools[:limit]
        except Exception as e:
            self.logger.error(
                "get_tool_ranking_error",
                workspace_id=workspace_id,
                metric=metric,
                error=str(e),
                exc_info=True,
            )
            return None

    def record_tool_score(
        self,
        trace_id: str,
        score: float,
        name: str = "quality",
        comment: str | None = None,
        workspace_id: str | None = None,
    ) -> bool:
        """
        Записать оценку качества (score) для tool execution trace в Langfuse.

        Args:
            trace_id: ID trace в Langfuse
            score: Оценка от 0.0 до 1.0
            name: Имя метрики (quality, accuracy, relevance, и т.д.)
            comment: Опциональный комментарий к оценке
            workspace_id: ID рабочей области для invalidation cache

        Returns:
            True если успешно, False при ошибке
        """
        if not self.enabled:
            return True

        try:
            # Валидировать score
            if not 0.0 <= score <= 1.0:
                self.logger.warning(
                    "invalid_score_value",
                    trace_id=trace_id,
                    score=score,
                )
                return False

            from app.services.langfuse_rest_client import get_langfuse_rest_client
            
            rest_client = get_langfuse_rest_client()
            
            # Записать score через REST API
            success = asyncio.run(
                rest_client.record_score(
                    trace_id=trace_id,
                    name=name,
                    value=score,
                    comment=comment,
                )
            )
            
            if success:
                self.logger.debug(
                    "tool_score_recorded",
                    trace_id=trace_id,
                    name=name,
                    score=score,
                )
                
                # Invalidate cache for this workspace
                if workspace_id:
                    self._invalidate_metrics_cache(workspace_id)
            else:
                self.logger.warning(
                    "tool_score_recording_failed",
                    trace_id=trace_id,
                    name=name,
                    score=score,
                )
            
            return success
        except Exception as e:
            self.logger.error(
                "record_tool_score_error",
                trace_id=trace_id,
                name=name,
                score=score,
                error=str(e),
                exc_info=True,
            )
            return False

    def _get_cache_key(
        self,
        workspace_id: str,
        tool_name: str | None = None,
        period_days: int = 7,
        metric: str = "metrics",
    ) -> str:
        """
        Генерировать cache key для metrics.

        Args:
            workspace_id: ID рабочей области
            tool_name: Имя инструмента
            period_days: Период в днях
            metric: Тип метрики (metrics, ranking)

        Returns:
            Cache key в формате workspace_id:tool_name:period:metric
        """
        tool_part = tool_name or "all"
        return f"tool_metrics:{workspace_id}:{tool_part}:{period_days}:{metric}"

    def _get_cached_metrics(
        self,
        workspace_id: str,
        tool_name: str | None = None,
        period_days: int = 7,
    ) -> dict[str, Any] | None:
        """
        Получить кэшированные metrics из Redis.

        Args:
            workspace_id: ID рабочей области
            tool_name: Имя инструмента
            period_days: Период в днях

        Returns:
            Кэшированные metrics или None если нет в кэше
        """
        try:
            import redis
            import json
            
            cache_key = self._get_cache_key(workspace_id, tool_name, period_days)
            
            # Подключиться к Redis
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=True,
            )
            
            cached = redis_client.get(cache_key)
            
            if cached:
                self.logger.debug(
                    "metrics_cache_hit",
                    cache_key=cache_key,
                )
                return json.loads(cached)
            
            return None
        except Exception as e:
            self.logger.warning(
                "get_cached_metrics_error",
                workspace_id=workspace_id,
                error=str(e),
            )
            return None

    def _cache_metrics(
        self,
        workspace_id: str,
        metrics: dict[str, Any],
        tool_name: str | None = None,
        period_days: int = 7,
        ttl_seconds: int = 3600,
    ) -> bool:
        """
        Кэшировать metrics в Redis.

        Args:
            workspace_id: ID рабочей области
            metrics: Metrics для кэширования
            tool_name: Имя инструмента
            period_days: Период в днях
            ttl_seconds: Time to live в секундах (по умолчанию 1 час)

        Returns:
            True если успешно, False при ошибке
        """
        try:
            import redis
            import json
            
            cache_key = self._get_cache_key(workspace_id, tool_name, period_days)
            
            # Подключиться к Redis
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=True,
            )
            
            redis_client.setex(
                cache_key,
                ttl_seconds,
                json.dumps(metrics),
            )
            
            self.logger.debug(
                "metrics_cached",
                cache_key=cache_key,
                ttl_seconds=ttl_seconds,
            )
            
            return True
        except Exception as e:
            self.logger.warning(
                "cache_metrics_error",
                workspace_id=workspace_id,
                error=str(e),
            )
            return False

    def _invalidate_metrics_cache(self, workspace_id: str) -> bool:
        """
        Инвалидировать все кэшированные metrics для workspace.

        Args:
            workspace_id: ID рабочей области

        Returns:
            True если успешно, False при ошибке
        """
        try:
            import redis
            
            # Подключиться к Redis
            redis_client = redis.Redis(
                host="localhost",
                port=6379,
                db=0,
                decode_responses=True,
            )
            
            # Инвалидировать все keys для workspace
            pattern = f"tool_metrics:{workspace_id}:*"
            keys = redis_client.keys(pattern)
            
            if keys:
                redis_client.delete(*keys)
                self.logger.debug(
                    "metrics_cache_invalidated",
                    workspace_id=workspace_id,
                    invalidated_keys=len(keys),
                )
            
            return True
        except Exception as e:
            self.logger.warning(
                "invalidate_cache_error",
                workspace_id=workspace_id,
                error=str(e),
            )
            return False


# Глобальный экземпляр LangfuseIntegration
_langfuse_instance: LangfuseIntegration | None = None


def get_langfuse() -> LangfuseIntegration:
    """
    Получить глобальный экземпляр LangfuseIntegration.

    Returns:
        LangfuseIntegration экземпляр (инициализируется при первом вызове)
    """
    global _langfuse_instance
    if _langfuse_instance is None:
        _langfuse_instance = LangfuseIntegration()
    return _langfuse_instance
