"""REST API клиент для Langfuse для получения traces, spans и analytics данных."""

import base64
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx
import structlog

from app.config import settings

struct_logger = structlog.get_logger(__name__)


class LangfuseRestClient:
    """
    REST API клиент для Langfuse.

    Обеспечивает:
    - Получение traces с фильтрацией (user_id, workspace_id, agent_name)
    - Получение spans для trace
    - Запись scores (feedback)
    - Graceful degradation при ошибках
    """

    def __init__(
        self,
        public_key: str,
        secret_key: str,
        base_url: str = "http://localhost:3000",
        timeout: int = 30,
    ) -> None:
        """
        Инициализация REST API клиента Langfuse.

        Args:
            public_key: Публичный ключ Langfuse (для аутентификации)
            secret_key: Секретный ключ Langfuse (для аутентификации)
            base_url: Базовый URL Langfuse сервера
            timeout: Timeout для HTTP запросов в секундах
        """
        self.public_key = public_key
        self.secret_key = secret_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._auth_header = self._create_auth_header()

    def _create_auth_header(self) -> dict[str, str]:
        """
        Создать HTTP Basic Auth header.

        Langfuse использует HTTP Basic Auth с public_key:secret_key.
        """
        credentials = f"{self.public_key}:{self.secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {"Authorization": f"Basic {encoded}"}

    async def get_traces(
        self,
        user_id: UUID,
        workspace_id: UUID | None = None,
        agent_name: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        Получить traces из Langfuse с фильтрацией.

        Args:
            user_id: ID пользователя (используется для фильтрации)
            workspace_id: ID workspace (используется для фильтрации)
            agent_name: Имя агента (используется для фильтрации)
            start_date: Начальная дата для фильтрации
            end_date: Конечная дата для фильтрации
            limit: Максимальное количество traces для возврата
            offset: Offset для pagination

        Returns:
            Словарь с traces и metadata (total_count, remaining, etc.)
        """
        if not self.public_key or not self.secret_key:
            struct_logger.warning("langfuse_rest_client_credentials_missing")
            return {
                "traces": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
            }

        try:
            # Построить параметры запроса
            params: dict[str, Any] = {
                "limit": limit,
                "page": offset // limit if limit > 0 else 0,
            }

            # Добавить фильтры к метаданным
            # Langfuse хранит user_id и workspace_id в metadata traces
            filters = []

            if user_id:
                filters.append({"key": "user_id", "value": str(user_id), "operator": "="})

            if workspace_id:
                filters.append(
                    {"key": "workspace_id", "value": str(workspace_id), "operator": "="}
                )

            if agent_name:
                filters.append({"key": "name", "value": agent_name, "operator": "contains"})

            if start_date:
                params["startDate"] = start_date.isoformat()

            if end_date:
                params["endDate"] = end_date.isoformat()

            # Использовать httpx для async запроса
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/public/traces",
                    params=params,
                    headers=self._auth_header,
                )

                if response.status_code == 200:
                    data = response.json()
                    struct_logger.info(
                        "langfuse_traces_retrieved",
                        user_id=str(user_id),
                        count=len(data.get("data", [])),
                    )
                    return {
                        "traces": data.get("data", []),
                        "total_count": data.get("total", 0),
                        "limit": limit,
                        "offset": offset,
                    }
                else:
                    struct_logger.error(
                        "langfuse_traces_api_error",
                        status_code=response.status_code,
                        error=response.text,
                    )
                    return {
                        "traces": [],
                        "total_count": 0,
                        "limit": limit,
                        "offset": offset,
                        "error": f"API error: {response.status_code}",
                    }

        except httpx.TimeoutException:
            struct_logger.error(
                "langfuse_traces_timeout",
                user_id=str(user_id),
                timeout=self.timeout,
            )
            return {
                "traces": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "error": "Request timeout",
            }
        except Exception as e:
            struct_logger.error(
                "langfuse_traces_failed",
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

    async def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        """
        Получить детали trace по ID.

        Args:
            trace_id: ID trace

        Returns:
            Словарь с информацией о trace или None при ошибке
        """
        if not self.public_key or not self.secret_key:
            struct_logger.warning("langfuse_rest_client_credentials_missing")
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/public/traces/{trace_id}",
                    headers=self._auth_header,
                )

                if response.status_code == 200:
                    data = response.json()
                    struct_logger.info(
                        "langfuse_trace_retrieved",
                        trace_id=trace_id,
                    )
                    return data.get("data")
                elif response.status_code == 404:
                    struct_logger.warning(
                        "langfuse_trace_not_found",
                        trace_id=trace_id,
                    )
                    return None
                else:
                    struct_logger.error(
                        "langfuse_trace_api_error",
                        trace_id=trace_id,
                        status_code=response.status_code,
                        error=response.text,
                    )
                    return None

        except httpx.TimeoutException:
            struct_logger.error(
                "langfuse_trace_timeout",
                trace_id=trace_id,
                timeout=self.timeout,
            )
            return None
        except Exception as e:
            struct_logger.error(
                "langfuse_trace_failed",
                error=str(e),
                trace_id=trace_id,
            )
            return None

    async def get_spans(self, trace_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """
        Получить spans для trace.

        Args:
            trace_id: ID trace
            limit: Максимальное количество spans для возврата

        Returns:
            Список spans или пустой список при ошибке
        """
        if not self.public_key or not self.secret_key:
            struct_logger.warning("langfuse_rest_client_credentials_missing")
            return []

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/public/spans",
                    params={"trace_id": trace_id, "limit": limit},
                    headers=self._auth_header,
                )

                if response.status_code == 200:
                    data = response.json()
                    struct_logger.info(
                        "langfuse_spans_retrieved",
                        trace_id=trace_id,
                        count=len(data.get("data", [])),
                    )
                    return data.get("data", [])
                else:
                    struct_logger.error(
                        "langfuse_spans_api_error",
                        trace_id=trace_id,
                        status_code=response.status_code,
                        error=response.text,
                    )
                    return []

        except httpx.TimeoutException:
            struct_logger.error(
                "langfuse_spans_timeout",
                trace_id=trace_id,
                timeout=self.timeout,
            )
            return []
        except Exception as e:
            struct_logger.error(
                "langfuse_spans_failed",
                error=str(e),
                trace_id=trace_id,
            )
            return []

    async def record_score(
        self,
        trace_id: str,
        score_name: str,
        score_value: float,
        comment: str | None = None,
    ) -> bool:
        """
        Записать score (оценку) для trace.

        Args:
            trace_id: ID trace
            score_name: Имя score (например, user_satisfaction)
            score_value: Значение score (0.0-1.0)
            comment: Опциональный комментарий

        Returns:
            True если успешно, False при ошибке
        """
        if not self.public_key or not self.secret_key:
            struct_logger.warning("langfuse_rest_client_credentials_missing")
            return False

        # Валидировать значение score
        if not 0.0 <= score_value <= 1.0:
            struct_logger.error(
                "langfuse_invalid_score_value",
                trace_id=trace_id,
                score_name=score_name,
                score_value=score_value,
            )
            return False

        try:
            payload = {
                "traceId": trace_id,
                "name": score_name,
                "value": score_value,
            }

            if comment:
                payload["comment"] = comment

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/public/scores",
                    json=payload,
                    headers=self._auth_header,
                )

                if response.status_code in (200, 201):
                    struct_logger.info(
                        "langfuse_score_recorded",
                        trace_id=trace_id,
                        score_name=score_name,
                        score_value=score_value,
                    )
                    return True
                else:
                    struct_logger.error(
                        "langfuse_score_api_error",
                        trace_id=trace_id,
                        score_name=score_name,
                        status_code=response.status_code,
                        error=response.text,
                    )
                    return False

        except httpx.TimeoutException:
            struct_logger.error(
                "langfuse_score_timeout",
                trace_id=trace_id,
                score_name=score_name,
                timeout=self.timeout,
            )
            return False
        except Exception as e:
            struct_logger.error(
                "langfuse_score_failed",
                error=str(e),
                trace_id=trace_id,
                score_name=score_name,
            )
            return False

    async def get_analytics_summary(
        self,
        user_id: UUID,
        workspace_id: UUID | None = None,
        period_days: int = 7,
    ) -> dict[str, Any]:
        """
        Получить аналитику traces за период.

        Args:
            user_id: ID пользователя
            workspace_id: ID workspace (опционально)
            period_days: Количество дней для анализа

        Returns:
            Словарь с аналитикой (trace_count, avg_duration, cost, etc.)
        """
        if not self.public_key or not self.secret_key:
            struct_logger.warning("langfuse_rest_client_credentials_missing")
            return {
                "trace_count": 0,
                "avg_duration": 0,
                "total_cost": 0.0,
            }

        try:
            # Получить traces за период
            from datetime import timedelta

            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=period_days)

            result = await self.get_traces(
                user_id=user_id,
                workspace_id=workspace_id,
                start_date=start_date,
                end_date=end_date,
                limit=1000,
            )

            traces = result.get("traces", [])

            if not traces:
                return {
                    "trace_count": 0,
                    "avg_duration": 0,
                    "total_cost": 0.0,
                }

            # Простая аналитика (более сложная аналитика может быть реализована позже)
            durations = []
            total_cost = 0.0

            for trace in traces:
                # Langfuse traces содержат timing и cost информацию
                if "duration" in trace:
                    durations.append(trace["duration"])

                if "cost" in trace and isinstance(trace["cost"], (int, float)):
                    total_cost += trace["cost"]

            avg_duration = (
                sum(durations) / len(durations) if durations else 0
            )

            struct_logger.info(
                "langfuse_analytics_retrieved",
                user_id=str(user_id),
                trace_count=len(traces),
                period_days=period_days,
            )

            return {
                "trace_count": len(traces),
                "avg_duration": avg_duration,
                "total_cost": total_cost,
                "period_days": period_days,
            }

        except Exception as e:
            struct_logger.error(
                "langfuse_analytics_failed",
                error=str(e),
                user_id=str(user_id),
            )
            return {
                "trace_count": 0,
                "avg_duration": 0,
                "total_cost": 0.0,
                "error": str(e),
            }

    async def check_health(self) -> bool:
        """
        Проверить доступность Langfuse сервиса.

        Returns:
            True если сервис здоров, False если недоступен или ошибка
        """
        if not self.public_key or not self.secret_key:
            struct_logger.warning("langfuse_rest_client_credentials_missing")
            return False

        try:
            # Langfuse имеет endpoint /api/public/health для проверки статуса
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/public/health",
                    headers=self._auth_header,
                )

                if response.status_code == 200:
                    struct_logger.info("langfuse_health_check_success")
                    return True
                else:
                    struct_logger.warning(
                        "langfuse_health_check_failed",
                        status_code=response.status_code,
                    )
                    return False

        except httpx.TimeoutException:
            struct_logger.error(
                "langfuse_health_check_timeout",
                timeout=self.timeout,
            )
            return False
        except Exception as e:
            struct_logger.error(
                "langfuse_health_check_error",
                error=str(e),
            )
            return False


# Глобальный экземпляр REST клиента
_rest_client: LangfuseRestClient | None = None


def get_langfuse_rest_client() -> LangfuseRestClient:
    """
    Получить глобальный экземпляр REST клиента Langfuse.

    Returns:
        Инициализированный LangfuseRestClient
    """
    global _rest_client

    if _rest_client is None:
        _rest_client = LangfuseRestClient(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            base_url=settings.langfuse_host,
        )

    return _rest_client
