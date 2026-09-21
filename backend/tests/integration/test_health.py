"""Integration tests for the Health Check API."""

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient


def test_health_check_sync(client: TestClient) -> None:
    """Verify GET /api/v1/health returns HTTP 200 with status and database fields."""
    response = client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "status" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_health_check_async(async_client: AsyncClient) -> None:
    """Verify async GET /api/v1/health returns HTTP 200 with status and database fields."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "status" in data
    assert "database" in data


def test_health_check_unintended_path(client: TestClient) -> None:
    """Verify that /health without the /api/v1 prefix returns 404."""
    response = client.get("/health")
    assert response.status_code == status.HTTP_404_NOT_FOUND
