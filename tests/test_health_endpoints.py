"""Тесты для health check endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from httpx import TimeoutException

from app.main import app


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


class TestHealthCheckEndpoints:
    """Тесты для health check endpoints."""

    def test_health_check_endpoint(self, client):
        """Тест базового health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_readiness_check_endpoint(self, client):
        """Тест readiness check endpoint."""
        response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


class TestLangfuseHealthCheckEndpoint:
    """Тесты для Langfuse health check endpoint."""

    @patch("app.routes.health.settings.langfuse_enabled", False)
    def test_langfuse_health_check_when_disabled(self, client):
        """Тест health check когда Langfuse отключен."""
        response = client.get("/health/langfuse")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "disabled"
        assert "message" in data

    @patch("app.routes.health.settings.langfuse_enabled", True)
    @patch("app.routes.health.LangfuseRestClient.check_health")
    async def test_langfuse_health_check_when_healthy(self, mock_check_health, client):
        """Тест health check когда Langfuse здоров."""
        mock_check_health.return_value = True

        with patch("app.routes.health.LangfuseRestClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.check_health = AsyncMock(return_value=True)
            MockClient.return_value = mock_instance

            response = client.get("/health/langfuse")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"

    @patch("app.routes.health.settings.langfuse_enabled", True)
    def test_langfuse_health_check_when_unavailable(self, client):
        """Тест health check когда Langfuse недоступен."""
        with patch("app.routes.health.LangfuseRestClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.check_health = AsyncMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.get("/health/langfuse")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data

    @patch("app.routes.health.settings.langfuse_enabled", True)
    def test_langfuse_health_check_timeout(self, client):
        """Тест health check при timeout."""
        with patch("app.routes.health.LangfuseRestClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.check_health = AsyncMock(side_effect=TimeoutException("Timeout"))
            MockClient.return_value = mock_instance

            response = client.get("/health/langfuse")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data

    @patch("app.routes.health.settings.langfuse_enabled", True)
    def test_langfuse_health_check_error(self, client):
        """Тест health check при ошибке подключения."""
        with patch("app.routes.health.LangfuseRestClient") as MockClient:
            mock_instance = AsyncMock()
            mock_instance.check_health = AsyncMock(
                side_effect=Exception("Connection error")
            )
            MockClient.return_value = mock_instance

            response = client.get("/health/langfuse")
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert "error" in data
            assert "Connection error" in data["error"]
