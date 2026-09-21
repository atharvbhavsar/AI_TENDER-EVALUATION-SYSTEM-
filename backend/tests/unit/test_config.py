"""Unit tests for application configuration."""

import os
from unittest.mock import patch
from app.core.config import Settings, get_settings


def test_settings_defaults() -> None:
    """Verify that default settings load as expected."""
    settings = Settings(
        APP_NAME="Default App",
        APP_VERSION="0.1.0",
        ENVIRONMENT="development",
        DEBUG=False,
        API_V1_PREFIX="/api/v1",
        LOG_LEVEL="INFO",
    )
    assert settings.APP_NAME == "Default App"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.ENVIRONMENT == "development"
    assert settings.DEBUG is False
    assert settings.API_V1_PREFIX == "/api/v1"
    assert settings.LOG_LEVEL == "INFO"


def test_settings_env_override() -> None:
    """Verify that settings can be loaded from environment variables."""
    with patch.dict(
        os.environ,
        {
            "APP_NAME": "Overridden Name",
            "APP_VERSION": "1.2.3",
            "ENVIRONMENT": "production",
            "DEBUG": "True",
            "API_V1_PREFIX": "/api/v1",
            "LOG_LEVEL": "WARNING",
        },
        clear=False,
    ):
        settings = Settings()
        assert settings.APP_NAME == "Overridden Name"
        assert settings.APP_VERSION == "1.2.3"
        assert settings.ENVIRONMENT == "production"
        assert settings.DEBUG is True
        assert settings.API_V1_PREFIX == "/api/v1"
        assert settings.LOG_LEVEL == "WARNING"


def test_get_settings_caching() -> None:
    """Verify that get_settings returns a cached instance."""
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2
