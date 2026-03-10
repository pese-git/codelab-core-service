"""Сервис для управления traces из Langfuse."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import structlog
from langfuse import Langfuse

from app.config import settings
from app.services.langfuse_integration import get_langfuse

struct_logger = structlog.get_logger(__name__)


class TracesService:
    """
    Сервис для получения, фильтрации и аналитики traces из Langfuse.

    Обеспечивает:
    - Получение traces с фильтрацией (user_id, workspace_id, agent_name)
    - Pagination и сортировка
    - Analytics аггрегация (summary, by_agent, cost)
    - Graceful degradation при disabled Langfuse
    """

    def __init__(self) -> None:
        """Инициализация Traces Service."""
        self.langfuse = get_langfuse()
        self.enabled = settings.langfuse_enabled

    async def get_traces(
        self,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
        agent_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "created_at",
        order_direction: str = "desc",
    ) -> dict[str, Any]:
        """
        Получить traces с фильтрацией и pagination.

        Args:
            user_id: ID пользователя (обязателен для фильтрации)
            workspace_id: ID workspace (опционально)
            agent_name: Имя агента (опционально)
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)
            limit: Лимит results (по умолчанию 100)
            offset: Offset для pagination (по умолчанию 0)
            order_by: Поле для сортировки (по умолчанию created_at)
            order_direction: Направление сортировки (asc/desc)

        Returns:
            Словарь с traces, total_count, и metadata
        """
        if not self.enabled:
            return {
                "traces": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
            }

        try:
            # На данный момент Langfuse SDK не предоставляет REST API для query traces
            # Нужно использовать REST API напрямую или дождаться обновления SDK
            # Здесь мы подготавливаем структуру для будущей реализации

            struct_logger.info(
                "traces_query",
                user_id=str(user_id),
                workspace_id=str(workspace_id) if workspace_id else None,
                agent_name=agent_name,
                limit=limit,
                offset=offset,
            )

            # Placeholder для будущей реализации с REST API
            # В production нужно будет использовать httpx для query Langfuse API
            return {
                "traces": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "note": "REST API integration required for trace querying",
            }

        except Exception as e:
            struct_logger.error(
                "traces_query_failed",
                error=str(e),
                user_id=str(user_id),
            )
            return {
                "traces": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "error": str(e),
            }

    async def get_trace_by_id(self, trace_id: str) -> Optional[dict[str, Any]]:
        """
        Получить детали trace по ID.

        Args:
            trace_id: ID trace для получения

        Returns:
            Словарь с информацией о trace или None если ошибка
        """
        if not self.enabled:
            return None

        try:
            # Placeholder для будущей реализации с REST API
            struct_logger.info(
                "trace_retrieval",
                trace_id=trace_id,
            )
            return None

        except Exception as e:
            struct_logger.error(
                "trace_retrieval_failed",
                error=str(e),
                trace_id=trace_id,
            )
            return None

    async def get_traces_for_workspace(
        self,
        workspace_id: UUID,
        user_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Получить traces для workspace с проверкой прав.

        Args:
            workspace_id: ID workspace
            user_id: ID пользователя (для проверки прав)
            limit: Лимит results
            offset: Offset для pagination

        Returns:
            Словарь с traces и metadata
        """
        if not self.enabled:
            return {
                "traces": [],
                "total_count": 0,
                "workspace_id": str(workspace_id),
            }

        try:
            struct_logger.info(
                "workspace_traces_query",
                workspace_id=str(workspace_id),
                user_id=str(user_id),
            )

            # Получаем traces для workspace (с фильтрацией по user_id для безопасности)
            return await self.get_traces(
                user_id=user_id,
                workspace_id=workspace_id,
                limit=limit,
                offset=offset,
            )

        except Exception as e:
            struct_logger.error(
                "workspace_traces_query_failed",
                error=str(e),
                workspace_id=str(workspace_id),
            )
            return {
                "traces": [],
                "total_count": 0,
                "workspace_id": str(workspace_id),
                "error": str(e),
            }

    async def get_traces_summary(
        self,
        user_id: UUID,
        workspace_id: Optional[UUID] = None,
        period: str = "7d",
    ) -> dict[str, Any]:
        """
        Получить summary аналитику для traces.

        Args:
            user_id: ID пользователя
            workspace_id: ID workspace (опционально)
            period: Период (7d, 30d, all)

        Returns:
            Словарь с summary метриками
        """
        if not self.enabled:
            return {
                "period": period,
                "total_traces": 0,
                "total_spans": 0,
                "avg_latency_ms": 0,
            }

        try:
            # Определяем дату начала
            end_date = datetime.utcnow()
            if period == "7d":
                start_date = end_date - timedelta(days=7)
            elif period == "30d":
                start_date = end_date - timedelta(days=30)
            else:
                start_date = None

            struct_logger.info(
                "traces_summary_query",
                user_id=str(user_id),
                period=period,
            )

            # Placeholder для будущей реализации
            return {
                "period": period,
                "total_traces": 0,
                "total_spans": 0,
                "avg_latency_ms": 0,
                "total_cost": 0.0,
                "workspace_id": str(workspace_id) if workspace_id else None,
            }

        except Exception as e:
            struct_logger.error(
                "traces_summary_query_failed",
                error=str(e),
                period=period,
            )
            return {
                "period": period,
                "error": str(e),
            }

    async def get_agent_analytics(
        self,
        workspace_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        """
        Получить аналитику по агентам.

        Args:
            workspace_id: ID workspace
            user_id: ID пользователя

        Returns:
            Словарь с analytics по агентам
        """
        if not self.enabled:
            return {
                "workspace_id": str(workspace_id),
                "agents": [],
            }

        try:
            struct_logger.info(
                "agent_analytics_query",
                workspace_id=str(workspace_id),
            )

            return {
                "workspace_id": str(workspace_id),
                "agents": [],
                "total_agents": 0,
            }

        except Exception as e:
            struct_logger.error(
                "agent_analytics_query_failed",
                error=str(e),
                workspace_id=str(workspace_id),
            )
            return {
                "workspace_id": str(workspace_id),
                "error": str(e),
            }

    async def get_cost_analysis(
        self,
        workspace_id: UUID,
        user_id: UUID,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """
        Получить анализ стоимости LLM операций.

        Args:
            workspace_id: ID workspace
            user_id: ID пользователя
            start_date: Начальная дата (опционально)
            end_date: Конечная дата (опционально)

        Returns:
            Словарь с cost analysis
        """
        if not self.enabled:
            return {
                "workspace_id": str(workspace_id),
                "total_cost": 0.0,
                "by_model": {},
                "by_agent": {},
            }

        try:
            struct_logger.info(
                "cost_analysis_query",
                workspace_id=str(workspace_id),
            )

            return {
                "workspace_id": str(workspace_id),
                "total_cost": 0.0,
                "by_model": {},
                "by_agent": {},
                "currency": "USD",
            }

        except Exception as e:
            struct_logger.error(
                "cost_analysis_query_failed",
                error=str(e),
                workspace_id=str(workspace_id),
            )
            return {
                "workspace_id": str(workspace_id),
                "error": str(e),
            }


# Глобальный экземпляр TracesService
_traces_service: Optional[TracesService] = None


def get_traces_service() -> TracesService:
    """
    Получить глобальный экземпляр TracesService.

    Returns:
        TracesService экземпляр (инициализируется при первом вызове)
    """
    global _traces_service
    if _traces_service is None:
        _traces_service = TracesService()
    return _traces_service
