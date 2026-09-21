"""Integration tests for Tender Versioning, Corrigenda, and historical preservation."""

import uuid
from fastapi import status
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.user import User


def test_sequential_versioning_and_historical_preservation(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify creating sequential versions, active version transitions, and historical preservation."""
    token = create_access_token(subject=procurement_officer_user.id)

    # 1. Create original tender (initializes Version 1)
    tender_res = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/VERSIONS/001", "title": "Multi-Version Tender"},
        headers={"Authorization": f"Bearer {token}"},
    )
    tender_id = tender_res.json()["id"]

    # 2. Create Version 2 (Corrigendum 01)
    v2_res = client.post(
        f"/api/v1/tenders/{tender_id}/versions",
        json={
            "version_label": "Corrigendum 01",
            "change_summary": "Extended EMD submission date",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v2_res.status_code == status.HTTP_201_CREATED
    v2_data = v2_res.json()
    assert v2_data["version_number"] == 2
    assert v2_data["version_label"] == "Corrigendum 01"
    assert v2_data["is_active"] is True

    # 3. Create Version 3 (Corrigendum 02)
    v3_res = client.post(
        f"/api/v1/tenders/{tender_id}/versions",
        json={
            "version_label": "Corrigendum 02",
            "change_summary": "Revised turnover eligibility criteria",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v3_res.status_code == status.HTTP_201_CREATED
    v3_data = v3_res.json()
    assert v3_data["version_number"] == 3
    assert v3_data["is_active"] is True

    # 4. Check main tender detail reports active_version as Version 3
    detail_res = client.get(
        f"/api/v1/tenders/{tender_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_res.status_code == status.HTTP_200_OK
    assert detail_res.json()["active_version"]["version_number"] == 3

    # 5. List all versions for the tender (ordered DESC: 3, 2, 1)
    versions_list_res = client.get(
        f"/api/v1/tenders/{tender_id}/versions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert versions_list_res.status_code == status.HTTP_200_OK
    all_versions = versions_list_res.json()
    assert len(all_versions) == 3
    assert [v["version_number"] for v in all_versions] == [3, 2, 1]

    # Verify Version 1 and Version 2 are now inactive but preserved intact
    v1_listed = next(v for v in all_versions if v["version_number"] == 1)
    v2_listed = next(v for v in all_versions if v["version_number"] == 2)
    v3_listed = next(v for v in all_versions if v["version_number"] == 3)

    assert v1_listed["is_active"] is False
    assert v2_listed["is_active"] is False
    assert v3_listed["is_active"] is True

    # 6. Retrieve specific historical Version 1
    v1_detail_res = client.get(
        f"/api/v1/tenders/{tender_id}/versions/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert v1_detail_res.status_code == status.HTTP_200_OK
    assert v1_detail_res.json()["version_number"] == 1
    assert v1_detail_res.json()["version_label"] == "Initial Release"


def test_get_nonexistent_tender_version(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify 404 response for non-existent version number."""
    token = create_access_token(subject=procurement_officer_user.id)

    tender_res = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/V404/001", "title": "V404 Tender"},
        headers={"Authorization": f"Bearer {token}"},
    )
    tender_id = tender_res.json()["id"]

    res = client.get(
        f"/api/v1/tenders/{tender_id}/versions/99",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
