"""Unit tests for Phase 15 Production Configuration and Settings Validation."""

import pytest
from app.core.config import Settings


def test_development_settings_defaults():
    """Verify default development configuration settings."""
    settings = Settings(ENVIRONMENT="development", DEBUG=False)
    assert settings.ENVIRONMENT == "development"
    assert settings.SECURITY_HEADERS_ENABLED is True
    assert settings.RATE_LIMIT_ENABLED is True
    assert "http://localhost:8000" in settings.CORS_ORIGINS


def test_production_settings_rejects_debug_true():
    """Verify production environment rejects DEBUG=True."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=True,
        JWT_SECRET_KEY="a" * 64,
        CORS_ORIGINS=["https://tender.crpf.gov.in"],
    )
    with pytest.raises(ValueError, match="DEBUG mode must be disabled"):
        settings.validate_production_readiness()


def test_production_settings_rejects_insecure_jwt_secret():
    """Verify production environment rejects insecure or default JWT secret."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_SECRET_KEY="change-me-in-development-secure-random-secret-key-32chars",
        CORS_ORIGINS=["https://tender.crpf.gov.in"],
    )
    with pytest.raises(ValueError, match="Insecure JWT_SECRET_KEY detected"):
        settings.validate_production_readiness()

    # Short secret
    settings_short = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_SECRET_KEY="too-short",
        CORS_ORIGINS=["https://tender.crpf.gov.in"],
    )
    with pytest.raises(ValueError, match="Insecure JWT_SECRET_KEY detected"):
        settings_short.validate_production_readiness()


def test_production_settings_rejects_wildcard_cors_with_credentials():
    """Verify production environment rejects wildcard CORS when credentials enabled."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_SECRET_KEY="a" * 64,
        CORS_ORIGINS=["*"],
        CORS_ALLOW_CREDENTIALS=True,
    )
    with pytest.raises(ValueError, match="CORS cannot allow wildcard"):
        settings.validate_production_readiness()


def test_production_settings_valid():
    """Verify valid production settings pass readiness validation."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        JWT_SECRET_KEY="x" * 64,
        CORS_ORIGINS=["https://tender.crpf.gov.in"],
        CORS_ALLOW_CREDENTIALS=True,
    )
    # Should not raise
    settings.validate_production_readiness()
