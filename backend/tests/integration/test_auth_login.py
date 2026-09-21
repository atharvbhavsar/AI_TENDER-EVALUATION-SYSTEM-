"""Integration tests for POST /api/v1/auth/login."""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.db.models.user import User


def test_login_success(client: TestClient, admin_user: User) -> None:
    """Verify successful login with valid credentials."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crpf.gov.in", "password": "SecureAdminPassword123!"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify token payload
    payload = decode_access_token(data["access_token"])
    assert payload["sub"] == str(admin_user.id)


def test_login_email_case_insensitivity(client: TestClient, admin_user: User) -> None:
    """Verify login succeeds regardless of email casing."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "ADMIN@CRPF.GOV.IN", "password": "SecureAdminPassword123!"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "access_token" in response.json()


def test_login_invalid_password(client: TestClient, admin_user: User) -> None:
    """Verify login fails with generic 401 on wrong password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crpf.gov.in", "password": "WrongPassword123!"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


def test_login_nonexistent_user(client: TestClient) -> None:
    """Verify login fails with generic 401 on non-existent email without disclosing existence."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@crpf.gov.in", "password": "Password123!"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


def test_login_inactive_user(client: TestClient, inactive_user: User) -> None:
    """Verify inactive users cannot login."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@crpf.gov.in", "password": "SecurePassword123!"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Invalid email or password"


def test_login_updates_last_login_at(
    client: TestClient, db_session: Session, admin_user: User
) -> None:
    """Verify last_login_at timestamp is populated upon successful authentication."""
    assert admin_user.last_login_at is None

    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crpf.gov.in", "password": "SecureAdminPassword123!"},
    )
    assert response.status_code == status.HTTP_200_OK

    db_session.refresh(admin_user)
    assert admin_user.last_login_at is not None
