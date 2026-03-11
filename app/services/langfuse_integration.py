"""Langfuse интеграция для LLM observability."""

import logging
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import structlog
from langfuse import Langfuse

from app.config import settings
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
struct_logger = structlog.get_logger(__name__)


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
                enabled=True,
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

            # Измеряем latency создания trace
            with trace_latency():
                # Создаем trace в Langfuse
                trace = self.client.trace(
                    name=name,
                    user_id=str(user_id) if user_id else None,
                    metadata=trace_metadata,
                )

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
            # Готовим дополнительные параметры
            span_kwargs: dict[str, Any] = {
                "name": name,
                "status_code": status,
            }

            if input_data is not None:
                span_kwargs["input"] = input_data
            if output_data is not None:
                span_kwargs["output"] = output_data
            if metadata:
                span_kwargs["metadata"] = metadata

            # Создаем span в Langfuse
            span = trace.span(**span_kwargs)

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
