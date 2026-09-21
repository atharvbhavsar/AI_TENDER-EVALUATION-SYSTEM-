"""Pytest fixtures and configuration."""

from typing import AsyncGenerator, Generator
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.jwt import create_access_token
from app.auth.service import create_user, seed_roles_and_permissions
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.storage.base import ObjectStorageService

# Isolated SQLite in-memory database for testing
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


import os

os.environ["ENVIRONMENT"] = "test"
get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def test_settings() -> Settings:
    """Return test-specific settings."""
    settings = Settings(
        APP_NAME="CRPF Tender Evaluation API (Test)",
        APP_VERSION="0.1.0-test",
        ENVIRONMENT="test",
        DEBUG=True,
        API_V1_PREFIX="/api/v1",
        LOG_LEVEL="DEBUG",
        DATABASE_URL=TEST_DATABASE_URL,
        JWT_SECRET_KEY="test-secret-key-for-pytest-execution-only",
        JWT_ALGORITHM="HS256",
        ACCESS_TOKEN_EXPIRE_MINUTES=60,
    )
    return settings


from app.core.middleware import RateLimiterMiddleware


@pytest.fixture(autouse=True)
def setup_test_db() -> Generator[None, None, None]:
    """Create all database tables, seed RBAC, reset rate limiter, and drop tables after each test."""
    RateLimiterMiddleware.reset()
    Base.metadata.create_all(bind=test_engine)
    with TestingSessionLocal() as session:
        seed_roles_and_permissions(session)
    yield
    RateLimiterMiddleware.reset()
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Provide an isolated database session for testing."""
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Provide a TestClient with database session override."""
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
async def async_client(db_session: Session) -> AsyncGenerator[AsyncClient, None]:
    """Provide an asynchronous httpx client for API tests."""
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create and return an active administrator user."""
    return create_user(
        db=db_session,
        email="admin@crpf.gov.in",
        password="SecureAdminPassword123!",
        full_name="CRPF Admin Officer",
        role_names=["ADMIN"],
        is_active=True,
    )


@pytest.fixture
def procurement_officer_user(db_session: Session) -> User:
    """Create and return an active procurement officer user."""
    return create_user(
        db=db_session,
        email="officer@crpf.gov.in",
        password="SecureOfficerPassword123!",
        full_name="CRPF Procurement Officer",
        role_names=["PROCUREMENT_OFFICER"],
        is_active=True,
    )


@pytest.fixture
def reviewer_user(db_session: Session) -> User:
    """Create and return an active reviewer user."""
    return create_user(
        db=db_session,
        email="reviewer@crpf.gov.in",
        password="SecureReviewerPassword123!",
        full_name="CRPF Reviewer Officer",
        role_names=["REVIEWER"],
        is_active=True,
    )


@pytest.fixture
def inactive_user(db_session: Session) -> User:
    """Create and return an inactive user."""
    return create_user(
        db=db_session,
        email="inactive@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Inactive User",
        role_names=["REVIEWER"],
        is_active=False,
    )


@pytest.fixture
def admin_token(admin_user: User) -> str:
    """Generate a valid JWT access token for admin."""
    return create_access_token(subject=admin_user.id)


@pytest.fixture
def procurement_officer_token(procurement_officer_user: User) -> str:
    """Generate a valid JWT access token for procurement officer."""
    return create_access_token(subject=procurement_officer_user.id)


@pytest.fixture
def reviewer_token(reviewer_user: User) -> str:
    """Generate a valid JWT access token for reviewer."""
    return create_access_token(subject=reviewer_user.id)


from app.storage.memory import InMemoryObjectStorageService


@pytest.fixture
def memory_storage() -> InMemoryObjectStorageService:
    """Provide an isolated in-memory storage instance."""
    return InMemoryObjectStorageService()


@pytest.fixture(autouse=True)
def setup_test_storage(memory_storage: InMemoryObjectStorageService) -> Generator[None, None, None]:
    """Auto-use fixture to hook memory storage service for tests."""
    from app.storage.service import get_storage_service, set_storage_service_override
    set_storage_service_override(memory_storage)
    app.dependency_overrides[get_storage_service] = lambda: memory_storage
    yield
    set_storage_service_override(None)
    if get_storage_service in app.dependency_overrides:
        del app.dependency_overrides[get_storage_service]
