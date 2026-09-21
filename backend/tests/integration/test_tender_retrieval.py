"""Integration tests for Tender listing, pagination, filtering, and detail views."""

import uuid
from fastapi import status
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.user import User


def test_list_tenders_and_pagination(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify paginated listing of tenders."""
    token = create_access_token(subject=procurement_officer_user.id)

    # Create 5 tenders
    for i in range(1, 6):
        client.post(
            "/api/v1/tenders",
            json={"tender_number": f"CRPF/PAGINATION/{i:03d}", "title": f"Tender {i}"},
            headers={"Authorization": f"Bearer {token}"},
        )

    # Request page 1 with page_size 2
    res_page1 = client.get(
        "/api/v1/tenders?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_page1.status_code == status.HTTP_200_OK
    data1 = res_page1.json()
    assert data1["total"] == 5
    assert len(data1["items"]) == 2
    assert data1["page"] == 1
    assert data1["page_size"] == 2
    assert data1["total_pages"] == 3

    # Request page 3 with page_size 2
    res_page3 = client.get(
        "/api/v1/tenders?page=3&page_size=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res_page3.status_code == status.HTTP_200_OK
    data3 = res_page3.json()
    assert len(data3["items"]) == 1


def test_get_tender_by_id_success(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify retrieving a single tender with its active version."""
    token = create_access_token(subject=procurement_officer_user.id)

    create_res = client.post(
        "/api/v1/tenders",
        json={"tender_number": "CRPF/DETAIL/001", "title": "Detail Tender"},
        headers={"Authorization": f"Bearer {token}"},
    )
    tender_id = create_res.json()["id"]

    res = client.get(
        f"/api/v1/tenders/{tender_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == status.HTTP_200_OK
    data = res.json()
    assert data["id"] == tender_id
    assert data["tender_number"] == "CRPF/DETAIL/001"
    assert data["active_version"]["version_number"] == 1


def test_get_tender_not_found(
    client: TestClient, procurement_officer_user: User
) -> None:
    """Verify 404 response for non-existent tender ID."""
    token = create_access_token(subject=procurement_officer_user.id)
    random_id = uuid.uuid4()

    res = client.get(
        f"/api/v1/tenders/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == status.HTTP_404_NOT_FOUND
