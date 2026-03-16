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
