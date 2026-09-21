"""Integration tests for OpenAPI documentation endpoints."""

from fastapi import status
from fastapi.testclient import TestClient


def test_openapi_schema(client: TestClient) -> None:
    """Verify GET /openapi.json returns valid OpenAPI JSON schema."""
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "openapi" in data
    assert "info" in data
    assert data["info"]["title"] == "CRPF Tender Evaluation API"
    assert "/api/v1/health" in data["paths"]


def test_swagger_docs(client: TestClient) -> None:
    """Verify GET /docs serves Swagger UI HTML."""
    response = client.get("/docs")
    assert response.status_code == status.HTTP_200_OK
    assert "swagger-ui" in response.text.lower()


def test_redoc(client: TestClient) -> None:
    """Verify GET /redoc serves Redoc HTML."""
    response = client.get("/redoc")
    assert response.status_code == status.HTTP_200_OK
    assert "redoc" in response.text.lower()
