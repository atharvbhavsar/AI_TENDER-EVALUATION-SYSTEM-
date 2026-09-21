"""Integration tests for Tender creation and atomic Version 1 initialization."""

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.db.models.tender import Tender, TenderStatus
from app.db.models.user import User


def test_create_tender_success(
    client: TestClient, procurement_officer_user: User, db_session: Session
) -> None:
    """Verify authorized user can create tender with automatic Version 1 initialization."""
    token = create_access_token(subject=procurement_officer_user.id)
    payload = {
        "tender_number": "CRPF/PROC/2026/001",
        "title": "Procurement of Tactical Armor",
        "description": "Level IV body armor sets",
        "issuing_authority": "Central Reserve Police Force",
        "initial_version_label": "Initial Release",
        "initial_change_summary": "Original specification document",
    }

    response = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["tender_number"] == "CRPF/PROC/2026/001"
    assert data["title"] == "Procurement of Tactical Armor"
    assert data["status"] == "DRAFT"
    assert data["created_by"] == str(procurement_officer_user.id)

    # Verify Version 1 was initialized and is active
    assert data["active_version"] is not None
    assert data["active_version"]["version_number"] == 1
    assert data["active_version"]["version_label"] == "Initial Release"
    assert data["active_version"]["is_active"] is True


def test_create_tender_duplicate_number_rejected(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify creating a tender with an existing tender number returns 409 Conflict."""
    token = create_access_token(subject=procurement_officer_user.id)
    payload = {
        "tender_number": "CRPF/PROC/2026/DUPLICATE",
        "title": "First Tender",
    }

    # First creation succeeds
    res1 = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res1.status_code == status.HTTP_201_CREATED

    # Second creation with identical number fails
    res2 = client.post(
        "/api/v1/tenders",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res2.status_code == status.HTTP_409_CONFLICT
    assert "already exists" in res2.json()["detail"]
