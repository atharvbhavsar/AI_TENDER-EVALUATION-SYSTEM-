"""Integration tests for error handling and edge cases."""

from unittest.mock import patch
from fastapi import status
from fastapi.testclient import TestClient


def test_not_found_error(client: TestClient) -> None:
    """Verify 404 Not Found response format for undefined routes."""
    response = client.get("/api/v1/unknown-endpoint")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": "Not Found"}


def test_method_not_allowed(client: TestClient) -> None:
    """Verify 405 Method Not Allowed when calling an endpoint with an invalid HTTP method."""
    response = client.post("/api/v1/health")
    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response.json() == {"detail": "Method Not Allowed"}


def test_unhandled_exception_sanitized() -> None:
    """Verify unhandled exceptions return 500 with sanitized message and no stack trace."""
    from app.main import app

    @app.get("/api/v1/test-unhandled-error")
    def trigger_error() -> None:
        raise RuntimeError("Simulated critical error")

    with TestClient(app, raise_server_exceptions=False) as error_client:
        response = error_client.get("/api/v1/test-unhandled-error")
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert response.json() == {"detail": "Internal server error"}
        # Ensure internal exception details are NOT leaked in the response
        assert "Simulated critical error" not in response.text
        assert "Traceback" not in response.text
