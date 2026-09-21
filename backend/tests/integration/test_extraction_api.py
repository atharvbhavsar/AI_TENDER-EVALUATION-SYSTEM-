"""Integration tests for AI Criterion Extraction API endpoints."""

import json
import pytest
import uuid
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.service import create_user
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import CriterionCategory, ExtractionStatus, RequirementType
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument
from app.storage.memory import InMemoryObjectStorageService


@pytest.fixture
def procurement_token(db_session: Session) -> str:
    user = create_user(
        db=db_session,
        email="api_officer@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Procurement Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )
    return create_access_token(subject=user.id)


@pytest.fixture
def reviewer_token(db_session: Session) -> str:
    user = create_user(
        db=db_session,
        email="api_reviewer@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Technical Reviewer",
        role_names=["REVIEWER"],
    )
    return create_access_token(subject=user.id)


@pytest.fixture
def setup_tender_and_artifact(
    db_session: Session,
    memory_storage: InMemoryObjectStorageService,
):
    admin_user = create_user(
        db=db_session,
        email="admin_setup@crpf.gov.in",
        password="SecureAdminPassword123!",
        full_name="Admin Setup",
        role_names=["ADMIN"],
    )

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-API-{uuid.uuid4().hex[:6].upper()}",
        title="High Altitude Winter Combat Gear",
        description="Procurement of specialized sub-zero combat uniforms.",
        status=TenderStatus.DRAFT,
        created_by=admin_user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=admin_user.id,
    )
    db_session.add(version)
    db_session.flush()

    document = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="winter_gear_specs.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=2048,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key=f"documents/tender/{tender.id}/version/{version.id}/doc.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=admin_user.id,
    )
    db_session.add(document)
    db_session.flush()

    norm_doc = NormalizedDocument(
        document_id=document.id,
        document_type="DIGITAL_PDF",
        processor_version="1.0.0",
        page_count=1,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="b1",
                        type=BlockType.TEXT,
                        text="The bidder shall have an average annual turnover of at least ₹5 Crore during the preceding three financial years. Audited balance sheets must be submitted.",
                    ),
                    DocumentBlock(
                        block_id="b2",
                        type=BlockType.TEXT,
                        text="The bidder must be registered under GST and submit valid GSTIN certificate.",
                    ),
                ],
            )
        ],
    )

    artifact_key = f"documents/tender/{tender.id}/version/{version.id}/{document.id}/artifacts/normalized_content.json"
    json_bytes = norm_doc.model_dump_json(indent=2).encode("utf-8")
    memory_storage.upload(artifact_key, json_bytes, content_type="application/json")

    artifact = ProcessingArtifact(
        id=uuid.uuid4(),
        document_id=document.id,
        artifact_type=ArtifactType.NORMALIZED_CONTENT,
        storage_key=artifact_key,
        file_size=len(json_bytes),
        mime_type="application/json",
    )
    db_session.add(artifact)
    db_session.commit()

    return tender, version, document


def test_trigger_criteria_extraction_success(
    client: TestClient,
    procurement_token: str,
    setup_tender_and_artifact,
):
    """Test POST /tenders/{tender_id}/versions/{version_id}/criteria/extract."""
    tender, version, _ = setup_tender_and_artifact

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["criteria_count"] >= 2
    assert "id" in data
    assert data["tender_version_id"] == str(version.id)


def test_trigger_criteria_extraction_reviewer_forbidden(
    client: TestClient,
    reviewer_token: str,
    setup_tender_and_artifact,
):
    """Test RBAC: Reviewer lacks TENDER_UPDATE permission and is rejected with 403."""
    tender, version, _ = setup_tender_and_artifact

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    assert response.status_code == 403


def test_get_extraction_status(
    client: TestClient,
    procurement_token: str,
    setup_tender_and_artifact,
):
    """Test GET /tenders/{tender_id}/versions/{version_id}/criteria/extraction-status."""
    tender, version, _ = setup_tender_and_artifact

    # First trigger extraction
    client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    # Check status
    response = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extraction-status",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["criteria_count"] >= 2
    assert "model_name" in data


def test_list_and_filter_criteria(
    client: TestClient,
    procurement_token: str,
    reviewer_token: str,
    setup_tender_and_artifact,
):
    """Test GET /tenders/{tender_id}/versions/{version_id}/criteria with filtering."""
    tender, version, _ = setup_tender_and_artifact

    # Trigger extraction
    client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    # Reviewer has TENDER_READ, can view criteria list
    response = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2

    # Filter by category = FINANCIAL
    fin_resp = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria?category=FINANCIAL",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert fin_resp.status_code == 200
    fin_data = fin_resp.json()
    assert all(item["category"] == "FINANCIAL" for item in fin_data["items"])


def test_get_criterion_detail_with_source_traceability(
    client: TestClient,
    procurement_token: str,
    reviewer_token: str,
    setup_tender_and_artifact,
):
    """Test GET /tenders/{tender_id}/versions/{version_id}/criteria/{criterion_id}."""
    tender, version, document = setup_tender_and_artifact

    # Trigger extraction
    client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    # List criteria to grab ID
    list_resp = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    crit_id = list_resp.json()["items"][0]["id"]

    # Get details
    detail_resp = client.get(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/{crit_id}",
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )

    assert detail_resp.status_code == 200
    crit = detail_resp.json()
    assert crit["id"] == crit_id
    assert "source_clause" in crit
    assert len(crit["source_references"]) >= 1
    assert crit["source_references"][0]["document_id"] == str(document.id)


def test_unauthenticated_request_rejected(
    client: TestClient,
    setup_tender_and_artifact,
):
    """Test 401 Unauthorized for missing bearer token."""
    tender, version, _ = setup_tender_and_artifact

    response = client.get(f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria")
    assert response.status_code == 401
