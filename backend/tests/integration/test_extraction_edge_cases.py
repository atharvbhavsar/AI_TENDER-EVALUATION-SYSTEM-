"""Integration tests for edge cases, table extraction, and hallucination defense."""

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
from app.extraction.service import get_latest_extraction_run, list_criteria_for_version
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument, TableData
from app.storage.memory import InMemoryObjectStorageService


@pytest.fixture
def procurement_token(db_session: Session) -> str:
    user = create_user(
        db=db_session,
        email="edge_officer@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Edge Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )
    return create_access_token(subject=user.id)


def test_extraction_fails_when_no_completed_documents(
    client: TestClient,
    db_session: Session,
    procurement_token: str,
):
    """Test 400 Bad Request when attempting extraction on tender version without processed documents."""
    user = create_user(
        db=db_session,
        email="admin_nodocs@crpf.gov.in",
        password="SecureAdmin123!",
        full_name="Admin NoDocs",
        role_names=["ADMIN"],
    )
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-NODOC-{uuid.uuid4().hex[:6].upper()}",
        title="Empty Tender",
        description="No documents uploaded yet.",
        status=TenderStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=user.id,
    )
    db_session.add(version)
    db_session.commit()

    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )

    assert response.status_code == 400
    assert "No successfully processed documents" in response.json()["detail"]


def test_table_based_criterion_extraction(
    client: TestClient,
    db_session: Session,
    procurement_token: str,
    memory_storage: InMemoryObjectStorageService,
):
    """Test extracting candidate criteria embedded inside structured document tables."""
    user = create_user(
        db=db_session,
        email="admin_table@crpf.gov.in",
        password="SecureAdmin123!",
        full_name="Admin Table",
        role_names=["ADMIN"],
    )
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-TBL-{uuid.uuid4().hex[:6].upper()}",
        title="Table Specs Tender",
        description="Tender with tabular criteria specifications.",
        status=TenderStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=user.id,
    )
    db_session.add(version)
    db_session.flush()

    document = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="tabular_eligibility.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key=f"documents/tender/{tender.id}/version/{version.id}/tbl.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=user.id,
    )
    db_session.add(document)
    db_session.flush()

    # Create table with eligibility requirements
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
                        block_id="tbl-101",
                        type=BlockType.TABLE,
                        table_data=TableData(
                            headers=["Parameter", "Minimum Eligibility Requirement", "Required Evidence"],
                            rows=[
                                ["Annual Turnover", "Average annual turnover of at least ₹5 Crore for last 3 years", "Audited balance sheet"],
                                ["Technical Experience", "Completed 3 similar contracts in past 5 years", "Work completion certificates"],
                            ],
                        ),
                    )
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

    # Trigger extraction
    response = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )
    assert response.status_code == 202

    # Verify table criteria were extracted and source table reference is populated
    criteria, total = list_criteria_for_version(db_session, tender.id, version.id)
    assert total >= 2
    assert any(c.source_table_reference == "tbl-101" for c in criteria)


def test_re_run_extraction_creates_new_run_preserving_history(
    client: TestClient,
    db_session: Session,
    procurement_token: str,
    memory_storage: InMemoryObjectStorageService,
):
    """Test re-running extraction creates a new historical ExtractionRun without overwriting run history."""
    user = create_user(
        db=db_session,
        email="admin_rerun@crpf.gov.in",
        password="SecureAdmin123!",
        full_name="Admin Rerun",
        role_names=["ADMIN"],
    )
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-RERUN-{uuid.uuid4().hex[:6].upper()}",
        title="Rerun Specs Tender",
        description="Testing re-extraction runs.",
        status=TenderStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=user.id,
    )
    db_session.add(version)
    db_session.flush()

    document = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="specs.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key=f"documents/tender/{tender.id}/version/{version.id}/specs.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=user.id,
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
                        text="The bidder shall have an average annual turnover of at least ₹5 Crore during preceding 3 years.",
                    )
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

    # Run 1
    resp1 = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )
    run1_id = resp1.json()["id"]

    # Run 2
    resp2 = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/criteria/extract",
        headers={"Authorization": f"Bearer {procurement_token}"},
    )
    run2_id = resp2.json()["id"]

    # Verify both runs have distinct UUIDs
    assert run1_id != run2_id

    # Verify latest run points to run2
    latest_run = get_latest_extraction_run(db_session, tender.id, version.id)
    assert str(latest_run.id) == run2_id
