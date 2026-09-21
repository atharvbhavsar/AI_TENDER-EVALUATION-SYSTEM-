"""Integration tests for database connection and transactions."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def test_select_1_query(db_session: Session) -> None:
    """Verify executing a basic SELECT 1 query."""
    result = db_session.execute(text("SELECT 1")).scalar()
    assert result == 1


def test_transaction_rollback() -> None:
    """Verify transaction rollback behavior with SQLAlchemy ORM session."""
    engine = create_engine("sqlite:///:memory:")
    TestingSession = sessionmaker(bind=engine)

    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE test_tx (id INTEGER PRIMARY KEY, val TEXT)"))
        conn.commit()

    # Session: insert and commit initial row
    session = TestingSession()
    session.execute(text("INSERT INTO test_tx (id, val) VALUES (1, 'initial')"))
    session.commit()
    assert session.execute(text("SELECT val FROM test_tx WHERE id = 1")).scalar() == "initial"

    # Session: insert second row and rollback
    session.execute(text("INSERT INTO test_tx (id, val) VALUES (2, 'rollback_me')"))
    session.rollback()

    # Verify second row was rolled back and not committed
    count = session.execute(text("SELECT COUNT(*) FROM test_tx")).scalar()
    assert count == 1
    session.close()
