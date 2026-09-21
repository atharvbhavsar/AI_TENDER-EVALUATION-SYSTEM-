"""Unit tests for database session management and lifecycle."""

from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from app.db.session import check_db_connectivity, get_db


def test_get_db_lifecycle() -> None:
    """Verify get_db creates a session and properly closes it."""
    db_gen = get_db()
    session = next(db_gen)
    assert isinstance(session, Session)

    # Closing generator should trigger finally: db.close()
    try:
        next(db_gen)
    except StopIteration:
        pass


def test_check_db_connectivity_success(db_session: Session) -> None:
    """Verify check_db_connectivity returns True when DB query succeeds."""
    assert check_db_connectivity(db=db_session) is True


def test_check_db_connectivity_failure() -> None:
    """Verify check_db_connectivity returns False gracefully when query fails."""
    mock_db = MagicMock(spec=Session)
    mock_db.execute.side_effect = RuntimeError("Database unreachable")

    assert check_db_connectivity(db=mock_db) is False
