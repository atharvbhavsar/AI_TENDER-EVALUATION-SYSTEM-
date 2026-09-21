"""Integration tests for Alembic database migrations."""

import os
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config


@pytest.fixture
def alembic_config(tmp_path: Path) -> Config:
    """Create a test Alembic config targeting an isolated SQLite database file."""
    db_file = tmp_path / "test_migration.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    ini_path = Path(__file__).resolve().parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", db_url)
    cfg.set_main_option("script_location", str(ini_path.parent / "alembic"))
    return cfg


def test_alembic_migration_lifecycle(alembic_config: Config) -> None:
    """Verify applying migrations (upgrade), rolling back (downgrade), and re-applying."""
    # 1. Upgrade to head
    command.upgrade(alembic_config, "head")

    # 2. Downgrade to base
    command.downgrade(alembic_config, "base")

    # 3. Re-apply upgrade to head
    command.upgrade(alembic_config, "head")
