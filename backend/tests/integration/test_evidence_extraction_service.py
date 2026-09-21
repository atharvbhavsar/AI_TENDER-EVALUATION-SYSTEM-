"""Integration tests for the complete Evidence Extraction & Validation service lifecycle."""

import datetime
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.role import Role
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.evidence.service import extract_submission_evidence
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument
from app.storage.memory import InMemoryObjectStorageService


@pytest.fixture
def evidence_test_fixture(db_session):
    """Create complete fixture with approved criteria and processed bidder submission document."""
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email="officer_evidence_test@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-EVD-TEST-{uuid.uuid4().hex[:6]}",
        title="Procurement of Tactical Communication Systems",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        is_active=True,
        created_by=officer.id,
    )
    db_session.add(version)
    db_session.flush()

    # 1. Add APPROVED criteria (Phase 8 prerequisite)
    crit_fin = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="FIN-001",
        name="Annual Turnover Requirement",
        description="Average annual turnover >= Rs 10 Crore in past 3 years",
        source_clause="Clause 3.1: Minimum turnover of 10 Crore",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    crit_cert = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CERT-001",
        name="Quality Certification",
        description="Valid ISO 9001:2015 certification",
        source_clause="Clause 4.2: Valid ISO 9001:2015 certification",
        category=CriterionCategory.CERTIFICATION,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add_all([crit_fin, crit_cert])
    db_session.flush()

    # 2. Add Bidder & BidSubmission
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BIDDER-ALPHA",
        legal_name="Alpha Tech Comms Private Limited",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-ALPHA-001",
        status=SubmissionStatus.RECEIVED,
    )
    db_session.add(submission)
    db_session.flush()

    # 3. Create a Document with completed processing artifact
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="Alpha_Financial_and_Certificates.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key=f"documents/{tender.id}/submission_doc.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.commit()

    return {
        "officer": officer,
        "tender": tender,
        "version": version,
        "bidder": bidder,
        "submission": submission,
        "document": doc,
        "crit_fin": crit_fin,
        "crit_cert": crit_cert,
    }


@pytest.mark.asyncio
async def test_evidence_extraction_service_and_api_flow(
    client: TestClient,
    db_session,
    evidence_test_fixture,
    memory_storage: InMemoryObjectStorageService,
):
    """Test executing evidence extraction on a submission and verifying extracted items."""
    fixture = evidence_test_fixture
    submission = fixture["submission"]
    doc = fixture["document"]
    officer = fixture["officer"]

    # 1. Create and store NormalizedDocument artifact in storage
    norm_doc = NormalizedDocument(
        document_id=doc.id,
        document_type="DIGITAL_PDF",
        processor_version="v1.0",
        page_count=2,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="b-1",
                        type=BlockType.TEXT,
                        text="M/s Alpha Tech Comms Private Limited has achieved an Annual Turnover of Rs. 14.5 Crore in FY 2023-24.",
                    )
                ],
            ),
            DocumentPage(
                page_number=2,
                blocks=[
                    DocumentBlock(
                        block_id="b-2",
                        type=BlockType.TEXT,
                        text="This is to certify ISO 9001:2015 Registration Certificate No. ISO-ALPHA-2024 issued by BIS valid until 31 March 2027.",
                    )
                ],
            ),
        ],
    )
    artifact_key = f"artifacts/{doc.id}/normalized.json"
    json_bytes = norm_doc.model_dump_json(indent=2).encode("utf-8")
    memory_storage.upload(artifact_key, json_bytes, content_type="application/json")

    art_record = ProcessingArtifact(
        id=uuid.uuid4(),
        document_id=doc.id,
        artifact_type=ArtifactType.NORMALIZED_CONTENT,
        storage_key=artifact_key,
        file_size=len(json_bytes),
        mime_type="application/json",
    )
    db_session.add(art_record)
    db_session.commit()

    # 2. Trigger evidence extraction via service
    run = await extract_submission_evidence(
        db=db_session,
        submission_id=submission.id,
        current_user=officer,
        storage=memory_storage,
    )
    assert run.status.value == "COMPLETED"
    assert run.evidence_count >= 2

    # 3. Query evidence via REST API
    officer_token = create_access_token(subject=officer.id)
    tender_id = str(fixture["tender"].id)
    version_id = str(fixture["version"].id)
    bidder_id = str(fixture["bidder"].id)
    sub_id = str(submission.id)

    resp = client.get(
        f"/api/v1/tenders/{tender_id}/versions/{version_id}/bidders/{bidder_id}/submissions/{sub_id}/evidence",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 2
    
    # Check extracted values
    fin_item = next((item for item in data["items"] if item["criterion_code"] == "FIN-001"), None)
    assert fin_item is not None
    assert fin_item["extracted_value"] == 145000000.0
    assert fin_item["status"] == "FOUND"

    cert_item = next((item for item in data["items"] if item["criterion_code"] == "CERT-001"), None)
    assert cert_item is not None
    assert cert_item["status"] == "FOUND"
    assert cert_item["certificate_data"]["certificate_name"] == "ISO 9001:2015"

    # 4. Query single evidence detail by ID
    ev_id = fin_item["id"]
    detail_resp = client.get(
        f"/api/v1/evidence/{ev_id}",
        headers={"Authorization": f"Bearer {officer_token}"},
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["id"] == ev_id
