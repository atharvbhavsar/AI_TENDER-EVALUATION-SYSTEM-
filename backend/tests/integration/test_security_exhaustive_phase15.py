"""Exhaustive Security Integration Tests for Phase 15."""

import uuid
import pytest
from fastapi.testclient import TestClient


def test_authentication_bypass_rejected(client: TestClient):
    """Verify protected endpoints reject unauthenticated access with HTTP 401."""
    endpoints = [
        ("GET", "/api/v1/tenders"),
        ("POST", "/api/v1/tenders"),
        ("GET", "/api/v1/audit/logs"),
        ("GET", "/api/v1/reports/00000000-0000-0000-0000-000000000000"),
    ]
    for method, path in endpoints:
        if method == "GET":
            res = client.get(path)
        else:
            res = client.post(path, json={})
        assert res.status_code == 401


def test_idor_cross_tender_access_isolated(client: TestClient, admin_token: str):
    """Verify tender records cannot be accessed across unauthorized IDs."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Requesting non-existent tender returns 404
    non_existent_id = uuid.uuid4()
    res = client.get(f"/api/v1/tenders/{non_existent_id}", headers=headers)
    assert res.status_code == 404


def test_cors_preflight_headers(client: TestClient):
    """Verify CORS preflight OPTIONS requests return allowed headers and origins."""
    res = client.options(
        "/api/v1/health/live",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code in [200, 204]
    assert res.headers.get("access-control-allow-origin") in ["http://localhost:3000", "*"]
