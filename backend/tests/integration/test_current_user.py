"""Integration tests for GET /api/v1/auth/me."""

import datetime
from fastapi import status
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.user import User


def test_get_current_user_success(
    client: TestClient, admin_user: User, admin_token: str
) -> None:
    """Verify /api/v1/auth/me returns safe user profile with valid Bearer token."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["id"] == str(admin_user.id)
    assert data["email"] == "admin@crpf.gov.in"
    assert data["full_name"] == "CRPF Admin Officer"
    assert "ADMIN" in data["roles"]
    assert "USER_MANAGE" in data["permissions"]
    # Ensure sensitive credentials are never leaked
    assert "password" not in data
    assert "password_hash" not in data


def test_get_current_user_missing_token(client: TestClient) -> None:
    """Verify /api/v1/auth/me returns 401 when Authorization header is omitted."""
    response = client.get("/api/v1/auth/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_invalid_token(client: TestClient) -> None:
    """Verify /api/v1/auth/me returns 401 on malformed/invalid token."""
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer not-a-valid-jwt-token"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_expired_token(
    client: TestClient, admin_user: User
) -> None:
    """Verify /api/v1/auth/me returns 401 when token has expired."""
    expired_token = create_access_token(
        subject=admin_user.id,
        expires_delta=datetime.timedelta(minutes=-5),
    )
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_user_inactive_account(
    client: TestClient, inactive_user: User
) -> None:
    """Verify /api/v1/auth/me rejects inactive users even with valid signature."""
    token = create_access_token(subject=inactive_user.id)
    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Inactive" in response.json()["detail"]
