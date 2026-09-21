"""Unit tests for Security Headers, Correlation ID, and Rate Limiting Middleware."""

import pytest
from fastapi.testclient import TestClient
from app.core.middleware import RateLimiterMiddleware


def test_security_headers_present(client: TestClient):
    """Verify security headers are attached to responses."""
    response = client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert response.headers.get("X-XSS-Protection") == "1; mode=block"


def test_correlation_id_propagation(client: TestClient):
    """Verify X-Request-ID is generated and returned, or echoed if provided."""
    # 1. Generated if missing
    res1 = client.get("/api/v1/health/live")
    assert "X-Request-ID" in res1.headers
    assert len(res1.headers["X-Request-ID"]) > 0

    # 2. Echoed if passed
    custom_id = "custom-test-request-id-12345"
    res2 = client.get("/api/v1/health/live", headers={"X-Request-ID": custom_id})
    assert res2.headers.get("X-Request-ID") == custom_id


def test_rate_limiter_triggers_429_on_excessive_requests(client: TestClient):
    """Verify rate limiter triggers HTTP 429 when threshold is reached on login."""
    RateLimiterMiddleware.reset()
    # Login rate limit is 10/min
    for i in range(10):
        res = client.post(
            "/api/v1/auth/login",
            json={"email": f"test{i}@crpf.gov.in", "password": "Password123!"},
        )
        assert res.status_code in [400, 401, 404, 422]  # Non-429 request

    # 11th request should trigger 429
    res_exceeded = client.post(
        "/api/v1/auth/login",
        json={"email": "overflow@crpf.gov.in", "password": "Password123!"},
    )
    assert res_exceeded.status_code == 429
    assert res_exceeded.headers.get("Retry-After") == "60"
    data = res_exceeded.json()
    assert "Rate limit exceeded" in data["detail"]
