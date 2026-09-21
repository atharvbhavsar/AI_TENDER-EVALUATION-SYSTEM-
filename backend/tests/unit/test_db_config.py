"""Unit tests for database configuration and connection strings."""

import os
from unittest.mock import patch
from app.core.config import Settings


def test_database_default_settings() -> None:
    """Verify default PostgreSQL settings."""
    settings = Settings(
        POSTGRES_SERVER="localhost",
        POSTGRES_PORT=5432,
        POSTGRES_USER="postgres",
        POSTGRES_PASSWORD="postgres_password",
        POSTGRES_DB="tender_evaluation",
    )
    assert settings.POSTGRES_SERVER == "localhost"
    assert settings.POSTGRES_PORT == 5432
    assert settings.POSTGRES_USER == "postgres"
    assert settings.POSTGRES_DB == "tender_evaluation"
    assert (
        settings.database_url_str
        == "postgresql+psycopg://postgres:postgres_password@localhost:5432/tender_evaluation"
    )


def test_database_url_explicit_override() -> None:
    """Verify that explicit DATABASE_URL takes precedence."""
    settings = Settings(
        DATABASE_URL="postgresql+psycopg://custom_user:custom_pass@dbhost:5433/custom_db"
    )
    assert (
        settings.database_url_str
        == "postgresql+psycopg://custom_user:custom_pass@dbhost:5433/custom_db"
    )


def test_database_pool_settings() -> None:
    """Verify database connection pool parameters."""
    settings = Settings(
        DB_POOL_SIZE=10,
        DB_MAX_OVERFLOW=20,
        DB_POOL_TIMEOUT=45,
        DB_POOL_RECYCLE=3600,
    )
    assert settings.DB_POOL_SIZE == 10
    assert settings.DB_MAX_OVERFLOW == 20
    assert settings.DB_POOL_TIMEOUT == 45
    assert settings.DB_POOL_RECYCLE == 3600
