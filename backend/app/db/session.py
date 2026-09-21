"""Database engine and session management."""

import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

logger = logging.getLogger("app.db")
settings = get_settings()

# Configure engine kwargs based on database backend
engine_kwargs = {
    "pool_pre_ping": True,
}

if "sqlite" in settings.database_url_str:
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "pool_size": settings.DB_POOL_SIZE,
            "max_overflow": settings.DB_MAX_OVERFLOW,
            "pool_timeout": settings.DB_POOL_TIMEOUT,
            "pool_recycle": settings.DB_POOL_RECYCLE,
        }
    )

engine = create_engine(settings.database_url_str, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    """Provide a transactional database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connectivity(db: Session | None = None) -> bool:
    """Verify active database connectivity by executing a lightweight SELECT 1 query."""
    try:
        if db is not None:
            db.execute(text("SELECT 1"))
            return True

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            return True
    except Exception as exc:
        logger.warning("Database connectivity check failed: %s", str(exc))
        return False
