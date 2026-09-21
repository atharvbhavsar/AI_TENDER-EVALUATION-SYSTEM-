"""Integration tests for RBAC authorization on Tender endpoints."""

from fastapi import status
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.auth.service import create_user
from app.db.models.user import User
from sqlalchemy.orm import Session


def test_tender_unauthenticated_requests_denied(client: TestClient) -> None:
    """Verify unauthenticated requests return 401 Unauthorized across tender endpoints."""
    assert client.post("/api/v1/tenders", json={}).status_code == status.HTTP_401_UNAUTHORIZED
    assert client.get("/api/v1/tenders").status_code == status.HTTP_401_UNAUTHORIZED


def test_tender_creation_rbac(
    client: TestClient,
    admin_token: str,
    procurement_officer_user: User,
    reviewer_user: User,
    db_session: Session,
) -> None:
    """Verify role permissions for creating tenders."""
    officer_token = create_access_token(subject=procurement_officer_user.id)
    reviewer_token = create_access_token(subject=reviewer_user.id)

    # 1. Admin (has TENDER_CREATE) succeeds
    res_admin = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/RBAC/ADMIN", "title": "Admin Tender"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == status.HTTP_201_CREATED

    # 2. Procurement Officer (has TENDER_CREATE) succeeds
    res_officer = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/RBAC/OFFICER", "title": "Officer Tender"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert res_officer.status_code == status.HTTP_201_CREATED

    # 3. Reviewer (lacks TENDER_CREATE) receives 403 Forbidden
    res_reviewer = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/RBAC/REVIEWER", "title": "Reviewer Tender"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res_reviewer.status_code == status.HTTP_403_FORBIDDEN


def test_tender_update_rbac(
    client: TestClient,
    procurement_officer_user: User,
    reviewer_user: User,
) -> None:
    """Verify role permissions for updating tenders and adding versions."""
    officer_token = create_access_token(subject=procurement_officer_user.id)
    reviewer_token = create_access_token(subject=reviewer_user.id)

    create_res = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/RBAC/UPDATE", "title": "Base Tender"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    tender_id = create_res.json()["id"]

    # Reviewer (lacks TENDER_UPDATE) receives 403 Forbidden on update
    res_patch = client.patch(
        f"/api/v1/tenders/{tender_id}",
        json={"title": "Unauthorized Title"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res_patch.status_code == status.HTTP_403_FORBIDDEN

    # Reviewer receives 403 Forbidden on creating new version
    res_version = client.post(
        f"/api/v1/tenders/{tender_id}/versions",
        json={"version_label": "Unauthorized Corrigendum"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res_version.status_code == status.HTTP_403_FORBIDDEN

    # Officer (has TENDER_UPDATE) succeeds on update and version creation
    res_officer_patch = client.patch(
        f"/api/v1/tenders/{tender_id}",
        json={"title": "Authorized Title"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert res_officer_patch.status_code == status.HTTP_200_OK

    res_officer_version = client.post(
        f"/api/v1/tenders/{tender_id}/versions",
        json={"version_label": "Authorized Corrigendum"},
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert res_officer_version.status_code == status.HTTP_201_CREATED
