"""Сервис для управления traces из Langfuse."""

from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import UUID

import structlog

from app.config import settings
from app.services.langfuse_rest_client import get_langfuse_rest_client

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
        self.rest_client = get_langfuse_rest_client()
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
            struct_logger.info(
                "traces_query",
                user_id=str(user_id),
                workspace_id=str(workspace_id) if workspace_id else None,
                agent_name=agent_name,
                limit=limit,
                offset=offset,
            )

            # Получаем traces из Langfuse REST API
            result = await self.rest_client.get_traces(
                user_id=user_id,
                workspace_id=workspace_id,
                agent_name=agent_name,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
                offset=offset,
            )

            # Применяем сортировку если необходимо
            traces = result.get("traces", [])
            if traces and order_by == "created_at":
                traces.sort(
                    key=lambda t: t.get("createdAt", ""),
                    reverse=(order_direction == "desc"),
                )
            elif traces and order_by == "duration":
                traces.sort(
                    key=lambda t: t.get("duration", 0),
                    reverse=(order_direction == "desc"),
                )

            return {
                "traces": traces,
                "total_count": result.get("total_count", 0),
                "limit": limit,
                "offset": offset,
                "order_by": order_by,
                "order_direction": order_direction,
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
            struct_logger.info(
                "trace_retrieval",
                trace_id=trace_id,
            )

            # Получаем trace из Langfuse REST API
            trace = await self.rest_client.get_trace(trace_id)

            if trace:
                # Получаем spans для trace
                spans = await self.rest_client.get_spans(trace_id)
                trace["spans"] = spans

            return trace

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
                period_days = 7
            elif period == "30d":
                start_date = end_date - timedelta(days=30)
                period_days = 30
            else:
                start_date = None
                period_days = 365

            struct_logger.info(
                "traces_summary_query",
                user_id=str(user_id),
                period=period,
            )

            # Получаем аналитику из REST API
            analytics = await self.rest_client.get_analytics_summary(
                user_id=user_id,
                workspace_id=workspace_id,
                period_days=period_days,
            )

            return {
                "period": period,
                "total_traces": analytics.get("trace_count", 0),
                "avg_latency_ms": int(analytics.get("avg_duration", 0)),
                "total_cost": analytics.get("total_cost", 0.0),
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

            # Получаем traces для workspace
            result = await self.get_traces(
                user_id=user_id,
                workspace_id=workspace_id,
                limit=1000,
            )

            traces = result.get("traces", [])

            # Агрегируем по агентам
            agents_stats: dict[str, Any] = {}

            for trace in traces:
                agent_name = trace.get("name", "unknown")
                if agent_name not in agents_stats:
                    agents_stats[agent_name] = {
                        "name": agent_name,
                        "trace_count": 0,
                        "total_cost": 0.0,
                        "avg_duration": 0,
                    }

                agents_stats[agent_name]["trace_count"] += 1
                agents_stats[agent_name]["total_cost"] += trace.get("cost", 0.0)
                agents_stats[agent_name]["avg_duration"] += trace.get("duration", 0)

            # Вычисляем средние значения
            for agent_data in agents_stats.values():
                if agent_data["trace_count"] > 0:
                    agent_data["avg_duration"] = (
                        agent_data["avg_duration"] / agent_data["trace_count"]
                    )

            return {
                "workspace_id": str(workspace_id),
                "agents": list(agents_stats.values()),
                "total_agents": len(agents_stats),
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

            # Получаем traces для workspace
            result = await self.get_traces(
                user_id=user_id,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
                limit=1000,
            )

            traces = result.get("traces", [])

            # Агрегируем стоимость
            total_cost = 0.0
            by_model: dict[str, float] = {}
            by_agent: dict[str, float] = {}

            for trace in traces:
                cost = trace.get("cost", 0.0)
                total_cost += cost

                # По моделям (из metadata)
                model = trace.get("metadata", {}).get("model", "unknown")
                by_model[model] = by_model.get(model, 0.0) + cost

                # По агентам
                agent_name = trace.get("name", "unknown")
                by_agent[agent_name] = by_agent.get(agent_name, 0.0) + cost

            return {
                "workspace_id": str(workspace_id),
                "total_cost": total_cost,
                "by_model": by_model,
                "by_agent": by_agent,
                "currency": "USD",
                "trace_count": len(traces),
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
