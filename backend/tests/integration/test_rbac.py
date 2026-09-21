"""Integration tests for Role-Based Access Control (RBAC) and permissions."""

from fastapi import status
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.user import User


def test_admin_accesses_protected_admin_endpoint(
    client: TestClient, admin_token: str
) -> None:
    """Verify ADMIN role (with USER_MANAGE permission) can access /admin-test."""
    response = client.get(
        "/api/v1/auth/admin-test",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "success"
    assert "Admin authorization verified" in response.json()["message"]


def test_reviewer_denied_on_admin_endpoint(
    client: TestClient, reviewer_token: str
) -> None:
    """Verify REVIEWER role (lacking USER_MANAGE permission) receives 403 Forbidden."""
    response = client.get(
        "/api/v1/auth/admin-test",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_procurement_officer_denied_on_admin_endpoint(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify PROCUREMENT_OFFICER role receives 403 Forbidden on admin endpoint."""
    officer_token = create_access_token(subject=procurement_officer_user.id)
    response = client.get(
        "/api/v1/auth/admin-test",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "insufficient permissions" in response.json()["detail"].lower()


def test_unauthenticated_request_denied_with_401(client: TestClient) -> None:
    """Verify unauthenticated requests to protected endpoints return 401 Unauthorized."""
    response = client.get("/api/v1/auth/admin-test")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
