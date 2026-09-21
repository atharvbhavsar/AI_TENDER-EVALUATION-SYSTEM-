"""Integration tests for Tender metadata updates and lifecycle transitions."""

import uuid
from fastapi import status
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.user import User


def test_update_tender_metadata_and_status(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify updating title, description, issuing_authority, and status."""
    token = create_access_token(subject=procurement_officer_user.id)

    create_res = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/UPDATE/001", "title": "Original Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    tender_id = create_res.json()["id"]

    patch_payload = {
        "title": "Amended Tender Title",
        "description": "Added requirements",
        "issuing_authority": "Directorate General CRPF",
        "status": "PUBLISHED",
    }

    patch_res = client.patch(
        f"/api/v1/tenders/{tender_id}",
        json=patch_payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    data = patch_res.json()
    assert data["title"] == "Amended Tender Title"
    assert data["description"] == "Added requirements"
    assert data["issuing_authority"] == "Directorate General CRPF"
    assert data["status"] == "PUBLISHED"
    # Verify tender_number remains unchanged
    assert data["tender_number"] == "CRPF/UPDATE/001"


def test_update_tender_not_found(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify updating a non-existent tender returns 404."""
    token = create_access_token(subject=procurement_officer_user.id)
    random_id = uuid.uuid4()

    patch_res = client.patch(
        f"/api/v1/tenders/{random_id}",
        json={"title": "New Title"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_res.status_code == status.HTTP_404_NOT_FOUND
