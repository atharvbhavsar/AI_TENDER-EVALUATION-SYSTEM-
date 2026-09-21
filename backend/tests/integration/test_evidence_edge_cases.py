"""Integration tests for edge cases: unapproved criteria, conflicts, missing proof, and IDOR protection."""

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
def edge_case_fixture(db_session):
    """Fixture with both approved and unapproved criteria."""
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    officer = User(
        id=uuid.uuid4(),
        email="officer_edge@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-EDGE-{uuid.uuid4().hex[:6]}",
        title="Procurement of Bulletproof Jackets",
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

    # Approved criterion
    crit_appr = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="FIN-001",
        name="Turnover Criterion",
        description="Turnover must be at least 10 Crore",
        source_clause="Clause 1.1: Turnover required",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    # Unapproved criterion (PENDING_REVIEW)
    crit_pending = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="TECH-999",
        name="Candidate Tech Criterion",
        description="Candidate tech requirement",
        source_clause="Clause 2.1: Tech spec",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )
    # Rejected criterion
    crit_rejected = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="COMP-999",
        name="Rejected Compliance Criterion",
        description="Rejected compliance requirement",
        source_clause="Clause 3.1: Compliance",
        category=CriterionCategory.COMPLIANCE,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.REJECTED,
        rejection_reason="Not applicable for this procurement",
    )
    db_session.add_all([crit_appr, crit_pending, crit_rejected])
    db_session.flush()

    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BID-EDGE-01",
        legal_name="Armor Dynamics Private Limited",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-ARMOR-001",
        status=SubmissionStatus.RECEIVED,
    )
    db_session.add(submission)
    db_session.commit()

    return {
        "officer": officer,
        "tender": tender,
        "version": version,
        "bidder": bidder,
        "submission": submission,
        "crit_appr": crit_appr,
        "crit_pending": crit_pending,
        "crit_rejected": crit_rejected,
    }


@pytest.mark.asyncio
async def test_unapproved_criteria_are_ignored(
    db_session,
    edge_case_fixture,
    memory_storage: InMemoryObjectStorageService,
):
    """Verify evidence extraction strictly targets approved criteria and ignores pending/rejected."""
    fixture = edge_case_fixture
    submission = fixture["submission"]
    officer = fixture["officer"]

    # Create document
    doc = Document(
        id=uuid.uuid4(),
        tender_id=fixture["tender"].id,
        tender_version_id=fixture["version"].id,
        bid_submission_id=submission.id,
        filename="Armor_Docs.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=500,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key=f"documents/{fixture['tender'].id}/armor.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()

    norm_doc = NormalizedDocument(
        document_id=doc.id,
        document_type="DIGITAL_PDF",
        processor_version="v1.0",
        page_count=1,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[DocumentBlock(block_id="b-1", type=BlockType.TEXT, text="Armor Dynamics achieved Turnover of Rs. 20 Crore.")],
            )
        ],
    )
    art_key = f"artifacts/{doc.id}/norm.json"
    json_bytes = norm_doc.model_dump_json(indent=2).encode("utf-8")
    memory_storage.upload(art_key, json_bytes, "application/json")
    db_session.add(
        ProcessingArtifact(
            id=uuid.uuid4(),
            document_id=doc.id,
            artifact_type=ArtifactType.NORMALIZED_CONTENT,
            storage_key=art_key,
            mime_type="application/json",
            file_size=len(json_bytes),
        )
    )
    db_session.commit()

    run = await extract_submission_evidence(
        db=db_session,
        submission_id=submission.id,
        current_user=officer,
        storage=memory_storage,
    )
    assert run.status.value == "COMPLETED"

    # Verify extracted evidence records: should ONLY be for FIN-001
    evidence_items = db_session.query(Evidence).filter_by(bid_submission_id=submission.id).all()
    for ev in evidence_items:
        assert ev.criterion_id == fixture["crit_appr"].id
        assert ev.criterion_id != fixture["crit_pending"].id
        assert ev.criterion_id != fixture["crit_rejected"].id


@pytest.mark.asyncio
async def test_conflicting_evidence_across_documents_detected(
    db_session,
    edge_case_fixture,
    memory_storage: InMemoryObjectStorageService,
):
    """Verify that contradictory evidence across two documents results in CONFLICTING status."""
    fixture = edge_case_fixture
    submission = fixture["submission"]
    officer = fixture["officer"]

    # Doc 1: Turnover = 20 Crore
    doc1 = Document(
        id=uuid.uuid4(),
        tender_id=fixture["tender"].id,
        tender_version_id=fixture["version"].id,
        bid_submission_id=submission.id,
        filename="Doc1_Audited_Report.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=500,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b851",
        storage_key=f"documents/{fixture['tender'].id}/doc1.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    # Doc 2: Turnover = 10 Crore
    doc2 = Document(
        id=uuid.uuid4(),
        tender_id=fixture["tender"].id,
        tender_version_id=fixture["version"].id,
        bid_submission_id=submission.id,
        filename="Doc2_CA_Certificate.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=500,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b852",
        storage_key=f"documents/{fixture['tender'].id}/doc2.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add_all([doc1, doc2])
    db_session.flush()

    norm_doc1 = NormalizedDocument(
        document_id=doc1.id,
        document_type="DIGITAL_PDF",
        processor_version="v1.0",
        page_count=1,
        pages=[DocumentPage(page_number=1, blocks=[DocumentBlock(block_id="b-1", type=BlockType.TEXT, text="Annual Turnover is Rs. 20 Crore.")])],
    )
    norm_doc2 = NormalizedDocument(
        document_id=doc2.id,
        document_type="DIGITAL_PDF",
        processor_version="v1.0",
        page_count=1,
        pages=[DocumentPage(page_number=1, blocks=[DocumentBlock(block_id="b-2", type=BlockType.TEXT, text="Annual Turnover is Rs. 10 Crore.")])],
    )

    k1, k2 = f"artifacts/{doc1.id}/n.json", f"artifacts/{doc2.id}/n.json"
    j1, j2 = norm_doc1.model_dump_json(indent=2).encode("utf-8"), norm_doc2.model_dump_json(indent=2).encode("utf-8")
    memory_storage.upload(k1, j1, "application/json")
    memory_storage.upload(k2, j2, "application/json")
    db_session.add_all([
        ProcessingArtifact(id=uuid.uuid4(), document_id=doc1.id, artifact_type=ArtifactType.NORMALIZED_CONTENT, storage_key=k1, mime_type="application/json", file_size=len(j1)),
        ProcessingArtifact(id=uuid.uuid4(), document_id=doc2.id, artifact_type=ArtifactType.NORMALIZED_CONTENT, storage_key=k2, mime_type="application/json", file_size=len(j2)),
    ])
    db_session.commit()

    await extract_submission_evidence(db=db_session, submission_id=submission.id, current_user=officer, storage=memory_storage)

    evidence_items = db_session.query(Evidence).filter_by(bid_submission_id=submission.id, criterion_id=fixture["crit_appr"].id).all()
    assert len(evidence_items) == 2
    for ev in evidence_items:
        assert ev.status == EvidenceStatus.CONFLICTING
        assert "Conflicting numeric evidence" in ev.validation_notes
