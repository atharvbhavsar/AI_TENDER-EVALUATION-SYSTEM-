"""Alembic environment configuration."""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
import sqlalchemy as sa
from sqlalchemy import engine_from_config, pool

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import get_settings
from app.db.base import Base
# Import all model packages here in future phases so metadata is complete
import app.db.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()

# Use application database URL if not explicitly provided in config or -x url
x_args = context.get_x_argument(as_dictionary=True)
custom_url = config.get_main_option("sqlalchemy.url")
if "url" in x_args:
    config.set_main_option("sqlalchemy.url", x_args["url"])
elif not custom_url or custom_url == "driver://user:pass@localhost/dbname":
    config.set_main_option("sqlalchemy.url", settings.database_url_str)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_num_length=128,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section, {})
    url = config.get_main_option("sqlalchemy.url")
    if url:
        configuration["sqlalchemy.url"] = url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_num_length=128,
        )

        with context.begin_transaction():
            # If alembic_version table exists, ensure version_num column can hold longer names
            try:
                connection.execute(sa.text("ALTER TABLE IF EXISTS alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)"))
            except Exception:
                pass
            context.run_migrations()





if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
