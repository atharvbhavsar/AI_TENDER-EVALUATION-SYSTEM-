"""Unit tests for FastAPI application creation and initialization."""

from fastapi import FastAPI
from app.main import create_application, app
from app.core.config import get_settings


def test_app_initialization() -> None:
    """Verify that the FastAPI application initializes correctly with metadata and routes."""
    settings = get_settings()
    test_app = create_application()

    assert isinstance(test_app, FastAPI)
    assert test_app.title == settings.APP_NAME
    assert test_app.version == settings.APP_VERSION
    assert test_app.docs_url == "/docs"
    assert test_app.redoc_url == "/redoc"
    assert test_app.openapi_url == "/openapi.json"

    # Verify that the health route is registered under /api/v1/health
    openapi_schema = test_app.openapi()
    assert "/api/v1/health" in openapi_schema["paths"]


def test_global_app_instance() -> None:
    """Verify that the global app instance is properly created."""
    assert isinstance(app, FastAPI)
