"""Сервис для автоматического сбора метрик качества в Langfuse."""

import structlog

from app.logging_config import get_logger
from app.services.langfuse_integration import get_langfuse

logger = get_logger(__name__)


class QualityMetricsCollector:
    """Автоматический сбор и запись метрик качества в Langfuse."""

    @staticmethod
    async def record_task_completion(
        trace_id: str,
        success: bool,
        error_type: str | None = None,
        duration_ms: int | None = None,
    ) -> bool:
        """
        Записать метрику завершения задачи.

        Args:
            trace_id: ID trace для записи метрики
            success: Успешно ли выполнена задача
            error_type: Тип ошибки (если success=False)
            duration_ms: Длительность выполнения в миллисекундах

        Returns:
            True если успешно записано, False если ошибка
        """
        langfuse = get_langfuse()

        score = 1.0 if success else 0.0
        comment = None

        if error_type:
            comment = f"Error: {error_type}"

        success_recorded = langfuse.record_score(
            trace_id=trace_id,
            name="task_success",
            value=score,
            comment=comment,
        )

        if duration_ms is not None:
            langfuse.create_event(
                trace_id=trace_id,
                name="task_duration",
                metadata={
                    "duration_ms": duration_ms,
                    "success": success,
                },
            )

        logger.debug(
            "task_completion_metric_recorded",
            trace_id=trace_id,
            success=success,
            error_type=error_type,
            duration_ms=duration_ms,
        )

        return success_recorded

    @staticmethod
    async def record_context_relevance(
        trace_id: str,
        relevance_score: float,
        documents_count: int,
        score_name: str = "context_relevance",
    ) -> bool:
        """
        Записать метрику релевантности контекста.

        Args:
            trace_id: ID trace
            relevance_score: Оценка релевантности (0.0-1.0)
            documents_count: Количество найденных документов
            score_name: Имя метрики в Langfuse

        Returns:
            True если успешно записано
        """
        langfuse = get_langfuse()

        comment = f"Retrieved {documents_count} documents"

        success = langfuse.record_score(
            trace_id=trace_id,
            name=score_name,
            value=relevance_score,
            comment=comment,
        )

        logger.debug(
            "context_relevance_metric_recorded",
            trace_id=trace_id,
            relevance_score=relevance_score,
            documents_count=documents_count,
        )

        return success

    @staticmethod
    async def record_tool_execution(
        trace_id: str,
        tool_name: str,
        success: bool,
        execution_time_ms: int,
        error_message: str | None = None,
    ) -> bool:
        """
        Записать метрику выполнения инструмента.

        Args:
            trace_id: ID trace
            tool_name: Имя инструмента
            success: Успешно ли выполнен инструмент
            execution_time_ms: Время выполнения в миллисекундах
            error_message: Сообщение об ошибке (если success=False)

        Returns:
            True если успешно записано
        """
        langfuse = get_langfuse()

        score = 1.0 if success else 0.0
        comment = f"Tool: {tool_name}, Time: {execution_time_ms}ms"

        if error_message:
            comment += f", Error: {error_message}"

        success_recorded = langfuse.record_score(
            trace_id=trace_id,
            name="tool_execution_success",
            value=score,
            comment=comment,
        )

        langfuse.create_event(
            trace_id=trace_id,
            name="tool_execution_metric",
            metadata={
                "tool_name": tool_name,
                "success": success,
                "execution_time_ms": execution_time_ms,
                "error": error_message,
            },
        )

        logger.debug(
            "tool_execution_metric_recorded",
            trace_id=trace_id,
            tool_name=tool_name,
            success=success,
            execution_time_ms=execution_time_ms,
        )

        return success_recorded

    @staticmethod
    async def record_response_quality(
        trace_id: str,
        quality_score: float,
        quality_reason: str | None = None,
    ) -> bool:
        """
        Записать оценку качества ответа.

        Args:
            trace_id: ID trace
            quality_score: Оценка качества (0.0-1.0)
            quality_reason: Причина оценки (опционально)

        Returns:
            True если успешно записано
        """
        langfuse = get_langfuse()

        success = langfuse.record_score(
            trace_id=trace_id,
            name="response_quality",
            value=quality_score,
            comment=quality_reason,
        )

        logger.debug(
            "response_quality_metric_recorded",
            trace_id=trace_id,
            quality_score=quality_score,
            reason=quality_reason,
        )

        return success

    @staticmethod
    async def record_llm_cost(
        trace_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cost: float,
    ) -> bool:
        """
        Записать стоимость LLM вызова.

        Args:
            trace_id: ID trace
            model: Имя модели
            prompt_tokens: Количество prompt токенов
            completion_tokens: Количество completion токенов
            cost: Стоимость в USD

        Returns:
            True если успешно записано
        """
        langfuse = get_langfuse()

        langfuse.create_event(
            trace_id=trace_id,
            name="llm_cost",
            metadata={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "cost": cost,
                "total_tokens": prompt_tokens + completion_tokens,
            },
        )

        logger.debug(
            "llm_cost_metric_recorded",
            trace_id=trace_id,
            model=model,
            tokens=prompt_tokens + completion_tokens,
            cost=cost,
        )

        return True

    @staticmethod
    async def record_agent_handoff(
        trace_id: str,
        from_agent: str,
        to_agent: str,
        handoff_reason: str | None = None,
    ) -> bool:
        """
        Записать событие передачи управления между агентами.

        Args:
            trace_id: ID trace
            from_agent: Имя агента, передавшего управление
            to_agent: Имя агента, получившего управление
            handoff_reason: Причина передачи (опционально)

        Returns:
            True если успешно записано
        """
        langfuse = get_langfuse()

        langfuse.create_event(
            trace_id=trace_id,
            name="agent_handoff",
            metadata={
                "from_agent": from_agent,
                "to_agent": to_agent,
                "reason": handoff_reason,
            },
        )

        logger.debug(
            "agent_handoff_recorded",
            trace_id=trace_id,
            from_agent=from_agent,
            to_agent=to_agent,
            reason=handoff_reason,
        )

        return True
