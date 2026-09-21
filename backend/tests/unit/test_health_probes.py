"""Unit tests for Liveness and Readiness Probes."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import create_application


@pytest.fixture
def client():
    app = create_application()
    return TestClient(app)


def test_liveness_probe_returns_200_alive(client: TestClient):
    """Verify /health/live returns HTTP 200 alive."""
    res = client.get("/api/v1/health/live")
    assert res.status_code == 200
    assert res.json() == {"status": "alive"}


def test_readiness_probe_success(client: TestClient):
    """Verify /health/ready returns 200 ready when DB connectivity succeeds."""
    with patch("app.health.router.check_db_connectivity", return_value=True):
        res = client.get("/api/v1/health/ready")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ready"
        assert data["components"]["database"]["status"] == "connected"


def test_readiness_probe_degraded_when_db_down(client: TestClient):
    """Verify /health/ready returns 503 not_ready when DB connectivity fails."""
    with patch("app.health.router.check_db_connectivity", return_value=False):
        res = client.get("/api/v1/health/ready")
        assert res.status_code == 503
        data = res.json()
        assert data["status"] == "not_ready"
        assert data["components"]["database"]["status"] == "unreachable"


def test_backward_compatible_health_endpoint(client: TestClient):
    """Verify legacy /health endpoint returns expected structure."""
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "database" in data
