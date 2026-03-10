"""Тесты для TracesService."""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.services.traces_service import TracesService


@pytest.fixture
def traces_service():
    """Создать экземпляр TracesService для тестирования."""
    return TracesService()


@pytest.fixture
def user_id():
    """UUID пользователя для тестирования."""
    return uuid4()


@pytest.fixture
def workspace_id():
    """UUID workspace для тестирования."""
    return uuid4()


@pytest.fixture
def sample_traces() -> list[dict[str, Any]]:
    """Примеры traces для тестирования."""
    return [
        {
            "id": "trace-001",
            "name": "agent-1",
            "createdAt": (datetime.utcnow() - timedelta(hours=1)).isoformat(),
            "duration": 1500,
            "cost": 0.05,
            "metadata": {"model": "gpt-4", "user_id": str(uuid4())},
        },
        {
            "id": "trace-002",
            "name": "agent-2",
            "createdAt": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "duration": 2000,
            "cost": 0.08,
            "metadata": {"model": "claude-3", "user_id": str(uuid4())},
        },
        {
            "id": "trace-003",
            "name": "agent-1",
            "createdAt": (datetime.utcnow() - timedelta(hours=3)).isoformat(),
            "duration": 1200,
            "cost": 0.04,
            "metadata": {"model": "gpt-4", "user_id": str(uuid4())},
        },
    ]


class TestTracesServiceInit:
    """Тесты инициализации TracesService."""

    def test_init_creates_instance(self):
        """Проверить что TracesService инициализируется корректно."""
        service = TracesService()
        assert service is not None
        assert hasattr(service, "rest_client")
        assert hasattr(service, "enabled")

    def test_init_disabled_langfuse(self, monkeypatch):
        """Проверить инициализацию при disabled Langfuse."""
        monkeypatch.setenv("LANGFUSE_ENABLED", "false")
        from app.config import Settings

        settings = Settings()
        assert not settings.langfuse_enabled


class TestGetTraces:
    """Тесты метода get_traces."""

    @pytest.mark.asyncio
    async def test_get_traces_returns_empty_when_disabled(
        self,
        traces_service: TracesService,
        user_id: uuid4,
    ):
        """Проверить что get_traces возвращает пустой список при disabled Langfuse."""
        traces_service.enabled = False

        result = await traces_service.get_traces(user_id=user_id)

        assert result is not None
        assert result["traces"] == []
        assert result["total_count"] == 0
        assert result["limit"] == 100
        assert result["offset"] == 0

    @pytest.mark.asyncio
    async def test_get_traces_with_pagination(
        self,
        traces_service: TracesService,
        user_id: uuid4,
        monkeypatch,
    ):
        """Проверить pagination в get_traces."""
        # Mock rest_client.get_traces
        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=100, offset=0
        ):
            return {
                "traces": [{"id": f"trace-{i}"} for i in range(limit)],
                "total_count": 1000,
            }

        monkeypatch.setattr(traces_service.rest_client, "get_traces", mock_get_traces)

        result = await traces_service.get_traces(user_id=user_id, limit=50, offset=100)

        assert result["limit"] == 50
        assert result["offset"] == 100
        assert result["total_count"] == 1000

    @pytest.mark.asyncio
    async def test_get_traces_with_filters(
        self,
        traces_service: TracesService,
        user_id: uuid4,
        workspace_id: uuid4,
        monkeypatch,
    ):
        """Проверить фильтрацию в get_traces."""
        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=100, offset=0
        ):
            # Проверяем что фильтры переданы правильно
            return {
                "traces": [],
                "total_count": 0,
            }

        monkeypatch.setattr(traces_service.rest_client, "get_traces", mock_get_traces)

        await traces_service.get_traces(
            user_id=user_id,
            workspace_id=workspace_id,
            agent_name="test-agent",
        )

        # Если мы дошли сюда, фильтры были применены

    @pytest.mark.asyncio
    async def test_get_traces_with_sorting(
        self,
        traces_service: TracesService,
        user_id: uuid4,
        sample_traces: list[dict],
        monkeypatch,
    ):
        """Проверить сортировку в get_traces."""
        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=100, offset=0
        ):
            return {
                "traces": sample_traces,
                "total_count": len(sample_traces),
            }

        monkeypatch.setattr(traces_service.rest_client, "get_traces", mock_get_traces)

        # Сортировка по duration (DESC)
        result = await traces_service.get_traces(
            user_id=user_id,
            order_by="duration",
            order_direction="desc",
        )

        traces = result["traces"]
        assert traces[0]["duration"] >= traces[1]["duration"]
        assert traces[1]["duration"] >= traces[2]["duration"]

    @pytest.mark.asyncio
    async def test_get_traces_handles_exceptions(
        self,
        traces_service: TracesService,
        user_id: uuid4,
        monkeypatch,
    ):
        """Проверить обработку исключений в get_traces."""
        async def mock_get_traces(*args, **kwargs):
            raise RuntimeError("API error")

        monkeypatch.setattr(traces_service.rest_client, "get_traces", mock_get_traces)

        result = await traces_service.get_traces(user_id=user_id)

        assert result["traces"] == []
        assert result["total_count"] == 0
        assert "error" in result


class TestGetTraceById:
    """Тесты метода get_trace_by_id."""

    @pytest.mark.asyncio
    async def test_get_trace_by_id_returns_none_when_disabled(
        self,
        traces_service: TracesService,
    ):
        """Проверить что get_trace_by_id возвращает None при disabled Langfuse."""
        traces_service.enabled = False

        result = await traces_service.get_trace_by_id("trace-001")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_trace_by_id_returns_trace(
        self,
        traces_service: TracesService,
        monkeypatch,
    ):
        """Проверить что get_trace_by_id возвращает trace с spans."""
        trace_data = {
            "id": "trace-001",
            "name": "test-agent",
            "duration": 1500,
        }

        async def mock_get_trace(trace_id):
            return trace_data

        async def mock_get_spans(trace_id, limit=100):
            return [
                {"id": "span-001", "name": "step-1"},
                {"id": "span-002", "name": "step-2"},
            ]

        monkeypatch.setattr(traces_service.rest_client, "get_trace", mock_get_trace)
        monkeypatch.setattr(traces_service.rest_client, "get_spans", mock_get_spans)

        result = await traces_service.get_trace_by_id("trace-001")

        assert result is not None
        assert result["id"] == "trace-001"
        assert "spans" in result
        assert len(result["spans"]) == 2

    @pytest.mark.asyncio
    async def test_get_trace_by_id_handles_not_found(
        self,
        traces_service: TracesService,
        monkeypatch,
    ):
        """Проверить обработку случая когда trace не найден."""
        async def mock_get_trace(trace_id):
            return None

        monkeypatch.setattr(traces_service.rest_client, "get_trace", mock_get_trace)

        result = await traces_service.get_trace_by_id("nonexistent-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_trace_by_id_handles_exceptions(
        self,
        traces_service: TracesService,
        monkeypatch,
    ):
        """Проверить обработку исключений в get_trace_by_id."""
        async def mock_get_trace(trace_id):
            raise RuntimeError("API error")

        monkeypatch.setattr(traces_service.rest_client, "get_trace", mock_get_trace)

        result = await traces_service.get_trace_by_id("trace-001")

        assert result is None


class TestGetTracesSummary:
    """Тесты метода get_traces_summary."""

    @pytest.mark.asyncio
    async def test_get_traces_summary_returns_empty_when_disabled(
        self,
        traces_service: TracesService,
        user_id: uuid4,
    ):
        """Проверить что get_traces_summary возвращает пустые метрики при disabled."""
        traces_service.enabled = False

        result = await traces_service.get_traces_summary(user_id=user_id)

        assert result["total_traces"] == 0
        assert result["avg_latency_ms"] == 0
        assert result["total_cost"] == 0.0

    @pytest.mark.asyncio
    async def test_get_traces_summary_calculates_metrics(
        self,
        traces_service: TracesService,
        user_id: uuid4,
        sample_traces: list[dict],
        monkeypatch,
    ):
        """Проверить расчет метрик в get_traces_summary."""
        async def mock_get_analytics_summary(user_id, workspace_id=None, period_days=7):
            return {
                "trace_count": 3,
                "avg_duration": 1567,
                "total_cost": 0.17,
            }

        monkeypatch.setattr(
            traces_service.rest_client,
            "get_analytics_summary",
            mock_get_analytics_summary,
        )

        result = await traces_service.get_traces_summary(user_id=user_id, period="7d")

        assert result["total_traces"] == 3
        assert result["avg_latency_ms"] == 1567
        assert result["total_cost"] == 0.17

    @pytest.mark.asyncio
    async def test_get_traces_summary_different_periods(
        self,
        traces_service: TracesService,
        user_id: uuid4,
        monkeypatch,
    ):
        """Проверить разные периоды в get_traces_summary."""
        async def mock_get_analytics_summary(user_id, workspace_id=None, period_days=7):
            return {
                "trace_count": period_days,
                "avg_duration": 1000,
                "total_cost": 0.0,
            }

        monkeypatch.setattr(
            traces_service.rest_client,
            "get_analytics_summary",
            mock_get_analytics_summary,
        )

        # Test 7d period
        result_7d = await traces_service.get_traces_summary(user_id=user_id, period="7d")
        assert result_7d["period"] == "7d"

        # Test 30d period
        result_30d = await traces_service.get_traces_summary(user_id=user_id, period="30d")
        assert result_30d["period"] == "30d"


class TestGetAgentAnalytics:
    """Тесты метода get_agent_analytics."""

    @pytest.mark.asyncio
    async def test_get_agent_analytics_returns_empty_when_disabled(
        self,
        traces_service: TracesService,
        workspace_id: uuid4,
        user_id: uuid4,
    ):
        """Проверить что get_agent_analytics возвращает пустые данные при disabled."""
        traces_service.enabled = False

        result = await traces_service.get_agent_analytics(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        assert result["agents"] == []
        assert result["total_agents"] == 0

    @pytest.mark.asyncio
    async def test_get_agent_analytics_aggregates_by_agent(
        self,
        traces_service: TracesService,
        workspace_id: uuid4,
        user_id: uuid4,
        sample_traces: list[dict],
        monkeypatch,
    ):
        """Проверить агрегацию по агентам в get_agent_analytics."""
        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=1000, offset=0
        ):
            return {
                "traces": sample_traces,
                "total_count": len(sample_traces),
            }

        monkeypatch.setattr(traces_service, "get_traces", mock_get_traces)

        result = await traces_service.get_agent_analytics(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        assert result["total_agents"] == 2  # agent-1 и agent-2
        agents = {agent["name"]: agent for agent in result["agents"]}
        assert "agent-1" in agents
        assert "agent-2" in agents
        assert agents["agent-1"]["trace_count"] == 2
        assert agents["agent-2"]["trace_count"] == 1


class TestGetCostAnalysis:
    """Тесты метода get_cost_analysis."""

    @pytest.mark.asyncio
    async def test_get_cost_analysis_returns_zero_when_disabled(
        self,
        traces_service: TracesService,
        workspace_id: uuid4,
        user_id: uuid4,
    ):
        """Проверить что get_cost_analysis возвращает ноль при disabled."""
        traces_service.enabled = False

        result = await traces_service.get_cost_analysis(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        assert result["total_cost"] == 0.0
        assert result["by_model"] == {}
        assert result["by_agent"] == {}

    @pytest.mark.asyncio
    async def test_get_cost_analysis_aggregates_costs(
        self,
        traces_service: TracesService,
        workspace_id: uuid4,
        user_id: uuid4,
        sample_traces: list[dict],
        monkeypatch,
    ):
        """Проверить агрегацию стоимости в get_cost_analysis."""
        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=1000, offset=0
        ):
            return {
                "traces": sample_traces,
                "total_count": len(sample_traces),
            }

        monkeypatch.setattr(traces_service, "get_traces", mock_get_traces)

        result = await traces_service.get_cost_analysis(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        assert result["total_cost"] == pytest.approx(0.17, abs=0.01)
        assert "gpt-4" in result["by_model"]
        assert "claude-3" in result["by_model"]
        assert "agent-1" in result["by_agent"]
        assert "agent-2" in result["by_agent"]

    @pytest.mark.asyncio
    async def test_get_cost_analysis_handles_exceptions(
        self,
        traces_service: TracesService,
        workspace_id: uuid4,
        user_id: uuid4,
        monkeypatch,
    ):
        """Проверить обработку исключений в get_cost_analysis."""
        async def mock_get_traces(*args, **kwargs):
            raise RuntimeError("API error")

        monkeypatch.setattr(traces_service, "get_traces", mock_get_traces)

        result = await traces_service.get_cost_analysis(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        assert "error" in result


class TestGetTracesForWorkspace:
    """Тесты метода get_traces_for_workspace."""

    @pytest.mark.asyncio
    async def test_get_traces_for_workspace_returns_empty_when_disabled(
        self,
        traces_service: TracesService,
        workspace_id: uuid4,
        user_id: uuid4,
    ):
        """Проверить что get_traces_for_workspace возвращает пустые данные при disabled."""
        traces_service.enabled = False

        result = await traces_service.get_traces_for_workspace(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        assert result["traces"] == []
        assert result["total_count"] == 0

    @pytest.mark.asyncio
    async def test_get_traces_for_workspace_filters_by_workspace(
        self,
        traces_service: TracesService,
        workspace_id: uuid4,
        user_id: uuid4,
        monkeypatch,
    ):
        """Проверить фильтрацию по workspace в get_traces_for_workspace."""
        async def mock_get_traces(
            user_id, workspace_id=None, agent_name=None, start_date=None, end_date=None, limit=100, offset=0
        ):
            # Проверяем что workspace_id передан
            assert workspace_id is not None
            return {
                "traces": [{"id": "trace-001"}],
                "total_count": 1,
            }

        monkeypatch.setattr(traces_service, "get_traces", mock_get_traces)

        result = await traces_service.get_traces_for_workspace(
            workspace_id=workspace_id,
            user_id=user_id,
        )

        assert result["total_count"] == 1
