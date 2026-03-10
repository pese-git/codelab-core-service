"""Integration тесты для Traces API endpoints."""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.main import app
from app.services.traces_service import TracesService


@pytest.fixture
async def async_client():
    """Создать async HTTP клиент для тестирования."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_jwt_token(monkeypatch):
    """Mock JWT token для тестирования."""

    def mock_get_current_user_id():
        return uuid4()

    def mock_get_workspace_id():
        return uuid4()

    monkeypatch.setattr(
        "app.middleware.user_isolation.get_current_user_id",
        lambda: uuid4(),
    )
    monkeypatch.setattr(
        "app.middleware.user_isolation.get_workspace_id",
        lambda: uuid4(),
    )


class TestTracesListEndpoint:
    """Тесты для GET /traces endpoint."""

    @pytest.mark.asyncio
    async def test_list_traces_success(self, async_client, mock_jwt_token, monkeypatch):
        """Проверить успешное получение списка traces."""

        async def mock_get_traces(*args, **kwargs):
            return {
                "traces": [
                    {"id": "trace-1", "name": "agent-1", "duration": 1000},
                    {"id": "trace-2", "name": "agent-2", "duration": 2000},
                ],
                "total_count": 2,
                "limit": 100,
                "offset": 0,
            }

        monkeypatch.setattr(TracesService, "get_traces", mock_get_traces)

        response = await async_client.get("/traces")

        assert response.status_code == 200
        data = response.json()
        assert "traces" in data
        assert len(data["traces"]) == 2

    @pytest.mark.asyncio
    async def test_list_traces_with_pagination(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить pagination в GET /traces."""

        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=100, offset=0, order_by="created_at", order_direction="desc"
        ):
            return {
                "traces": [],
                "total_count": 1000,
                "limit": limit,
                "offset": offset,
            }

        monkeypatch.setattr(TracesService, "get_traces", mock_get_traces)

        response = await async_client.get("/traces?limit=50&offset=100")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 50
        assert data["offset"] == 100

    @pytest.mark.asyncio
    async def test_list_traces_with_filters(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить фильтры в GET /traces."""

        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=100, offset=0, order_by="created_at", order_direction="desc"
        ):
            return {
                "traces": [] if agent_name else [{"id": "trace-1"}],
                "total_count": 0 if agent_name else 1,
                "limit": limit,
                "offset": offset,
            }

        monkeypatch.setattr(TracesService, "get_traces", mock_get_traces)

        response = await async_client.get("/traces?agent_name=test-agent")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_traces_with_sorting(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить сортировку в GET /traces."""

        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=100, offset=0, order_by="created_at", order_direction="desc"
        ):
            return {
                "traces": [],
                "total_count": 0,
                "limit": limit,
                "offset": offset,
                "order_by": order_by,
                "order_direction": order_direction,
            }

        monkeypatch.setattr(TracesService, "get_traces", mock_get_traces)

        response = await async_client.get("/traces?order_by=duration&order_direction=asc")

        assert response.status_code == 200


class TestTraceDetailEndpoint:
    """Тесты для GET /traces/{trace_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_trace_success(self, async_client, mock_jwt_token, monkeypatch):
        """Проверить успешное получение trace по ID."""

        async def mock_get_trace_by_id(trace_id):
            return {
                "id": "trace-001",
                "name": "agent-1",
                "duration": 1500,
                "spans": [
                    {"id": "span-1", "name": "step-1"},
                ],
            }

        monkeypatch.setattr(
            TracesService, "get_trace_by_id", mock_get_trace_by_id
        )

        response = await async_client.get("/traces/trace-001")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "trace-001"
        assert "spans" in data

    @pytest.mark.asyncio
    async def test_get_trace_not_found(self, async_client, mock_jwt_token, monkeypatch):
        """Проверить ошибку 404 для несуществующего trace."""

        async def mock_get_trace_by_id(trace_id):
            return None

        monkeypatch.setattr(
            TracesService, "get_trace_by_id", mock_get_trace_by_id
        )

        response = await async_client.get("/traces/nonexistent-id")

        assert response.status_code == 404


class TestTraceScoresEndpoint:
    """Тесты для POST /traces/{trace_id}/scores endpoint."""

    @pytest.mark.asyncio
    async def test_record_score_success(self, async_client, mock_jwt_token, monkeypatch):
        """Проверить успешную запись score."""

        async def mock_record_score(trace_id, score_name, score_value, comment=None):
            return True

        # Mock rest_client
        from app.services.langfuse_rest_client import LangfuseRestClient

        monkeypatch.setattr(
            LangfuseRestClient, "record_score", mock_record_score
        )

        async def mock_get_trace_by_id(trace_id):
            return {"id": trace_id}

        monkeypatch.setattr(
            TracesService, "get_trace_by_id", mock_get_trace_by_id
        )

        response = await async_client.post(
            "/traces/trace-001/scores?score_name=user_satisfaction&score_value=0.9"
        )

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_record_score_invalid_value(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить валидацию value (должен быть в диапазоне 0-1)."""
        async def mock_get_trace_by_id(trace_id):
            return {"id": trace_id}

        monkeypatch.setattr(
            TracesService, "get_trace_by_id", mock_get_trace_by_id
        )

        # score_value > 1.0
        response = await async_client.post(
            "/traces/trace-001/scores?score_name=test&score_value=1.5"
        )

        # Должна быть валидационная ошибка
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_record_score_trace_not_found(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить ошибку 404 если trace не найден."""
        async def mock_get_trace_by_id(trace_id):
            return None

        monkeypatch.setattr(
            TracesService, "get_trace_by_id", mock_get_trace_by_id
        )

        response = await async_client.post(
            "/traces/nonexistent/scores?score_name=test&score_value=0.5"
        )

        assert response.status_code == 404


class TestAnalyticsEndpoints:
    """Тесты для analytics endpoints."""

    @pytest.mark.asyncio
    async def test_traces_summary_success(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить GET /analytics/summary endpoint."""

        async def mock_get_traces_summary(user_id, workspace_id=None, period="7d"):
            return {
                "period": period,
                "total_traces": 42,
                "avg_latency_ms": 1234,
                "total_cost": 10.5,
            }

        monkeypatch.setattr(
            TracesService, "get_traces_summary", mock_get_traces_summary
        )

        response = await async_client.get("/traces/analytics/summary?period=7d")

        assert response.status_code == 200
        data = response.json()
        assert data["total_traces"] == 42
        assert data["total_cost"] == 10.5

    @pytest.mark.asyncio
    async def test_agents_analytics_success(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить GET /analytics/agents endpoint."""

        async def mock_get_agent_analytics(workspace_id, user_id):
            return {
                "workspace_id": str(workspace_id),
                "agents": [
                    {"name": "agent-1", "trace_count": 10, "total_cost": 5.0},
                    {"name": "agent-2", "trace_count": 8, "total_cost": 3.5},
                ],
                "total_agents": 2,
            }

        monkeypatch.setattr(
            TracesService, "get_agent_analytics", mock_get_agent_analytics
        )

        response = await async_client.get("/traces/analytics/agents")

        assert response.status_code == 200
        data = response.json()
        assert data["total_agents"] == 2
        assert len(data["agents"]) == 2

    @pytest.mark.asyncio
    async def test_cost_analysis_success(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить GET /analytics/cost endpoint."""

        async def mock_get_cost_analysis(
            workspace_id, user_id, start_date=None, end_date=None
        ):
            return {
                "workspace_id": str(workspace_id),
                "total_cost": 123.45,
                "by_model": {"gpt-4": 100.0, "claude-3": 23.45},
                "by_agent": {"agent-1": 70.0, "agent-2": 53.45},
                "currency": "USD",
            }

        monkeypatch.setattr(
            TracesService, "get_cost_analysis", mock_get_cost_analysis
        )

        response = await async_client.get("/traces/analytics/cost")

        assert response.status_code == 200
        data = response.json()
        assert data["total_cost"] == 123.45
        assert "by_model" in data
        assert "by_agent" in data


class TestHealthCheckEndpoint:
    """Тесты для health check endpoint."""

    @pytest.mark.asyncio
    async def test_langfuse_health_check_enabled(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить health check когда Langfuse enabled."""

        async def mock_init():
            pass

        monkeypatch.setattr(
            TracesService,
            "__init__",
            lambda self: (setattr(self, "enabled", True), setattr(self, "rest_client", None)),
        )

        response = await async_client.get("/traces/health/langfuse")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    @pytest.mark.asyncio
    async def test_langfuse_health_check_disabled(
        self, async_client, mock_jwt_token, monkeypatch
    ):
        """Проверить health check когда Langfuse disabled."""

        monkeypatch.setattr(
            TracesService,
            "__init__",
            lambda self: (setattr(self, "enabled", False), setattr(self, "rest_client", None)),
        )

        response = await async_client.get("/traces/health/langfuse")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disabled"
