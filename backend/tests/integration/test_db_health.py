"""Integration tests for database health check behavior."""

from unittest.mock import patch
from fastapi import status
from fastapi.testclient import TestClient


def test_health_check_with_healthy_db(client: TestClient) -> None:
    """Verify health endpoint reports healthy database status when DB is connected."""
    with patch("app.health.router.check_db_connectivity", return_value=True):
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "healthy"


def test_health_check_with_unhealthy_db(client: TestClient) -> None:
    """Verify health endpoint reports degraded status when DB is unreachable."""
    with patch("app.health.router.check_db_connectivity", return_value=False):
        response = client.get("/api/v1/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "unhealthy"
        # Ensure no sensitive database credentials or URLs are leaked
        assert "password" not in response.text.lower()
        assert "postgresql://" not in response.text.lower()
