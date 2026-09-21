"""Integration tests verifying strict tenant, cross-tender, and cross-submission evaluation isolation."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
from app.db.models.extraction_run import ExtractionRunStatus
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


@pytest.fixture
def isolation_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_iso_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    # Tender A
    tender_a = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-ISO-A-{uuid.uuid4().hex[:6]}",
        title="Tender Alpha",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    # Tender B
    tender_b = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-ISO-B-{uuid.uuid4().hex[:6]}",
        title="Tender Beta",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add_all([tender_a, tender_b])
    db_session.flush()

    v_a = TenderVersion(id=uuid.uuid4(), tender_id=tender_a.id, version_number=1, created_by=officer.id)
    v_b = TenderVersion(id=uuid.uuid4(), tender_id=tender_b.id, version_number=1, created_by=officer.id)
    db_session.add_all([v_a, v_b])
    db_session.flush()

    crit_a = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v_a.id,
        criterion_code="FIN-A",
        name="Alpha Turnover",
        description="Turnover > 1000",
        source_clause="Clause 1: Alpha Turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=1000.0,
        unit="INR",
        currency="INR",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    crit_b = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v_b.id,
        criterion_code="FIN-B",
        name="Beta Turnover",
        description="Turnover > 2000",
        source_clause="Clause 1: Beta Turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=2000.0,
        unit="INR",
        currency="INR",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    db_session.add_all([crit_a, crit_b])

    bidder_1 = Bidder(id=uuid.uuid4(), tender_id=tender_a.id, bidder_code="BID-1", legal_name="Bidder One")
    bidder_2 = Bidder(id=uuid.uuid4(), tender_id=tender_b.id, bidder_code="BID-2", legal_name="Bidder Two")
    db_session.add_all([bidder_1, bidder_2])
    db_session.flush()

    sub_a1 = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v_a.id,
        bidder_id=bidder_1.id,
        status=SubmissionStatus.READY,
        submission_reference=f"SUB-A1-{uuid.uuid4().hex[:4]}",
    )
    sub_b2 = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v_b.id,
        bidder_id=bidder_2.id,
        status=SubmissionStatus.READY,
        submission_reference=f"SUB-B2-{uuid.uuid4().hex[:4]}",
    )
    db_session.add_all([sub_a1, sub_b2])
    db_session.flush()

    doc_a1 = Document(
        id=uuid.uuid4(),
        tender_id=tender_a.id,
        tender_version_id=v_a.id,
        bid_submission_id=sub_a1.id,
        filename="sub_a1.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="hasha1",
        storage_key="path/a1.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc_a1)
    db_session.flush()

    extraction_run = EvidenceExtractionRun(
        id=uuid.uuid4(),
        bid_submission_id=sub_a1.id,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        extractor_version="v1.0",
        status=ExtractionRunStatus.COMPLETED,
        created_by=officer.id,
    )
    db_session.add(extraction_run)
    db_session.flush()

    ev_a1 = Evidence(
        id=uuid.uuid4(),
        bid_submission_id=sub_a1.id,
        criterion_id=crit_a.id,
        document_id=doc_a1.id,
        extraction_run_id=extraction_run.id,
        status=EvidenceStatus.FOUND,
        extracted_text="Turnover is 1500 INR",
        extracted_value=1500.0,
        unit="INR",
        currency="INR",
        confidence=0.90,
        extractor_version="v1.0",
    )
    db_session.add(ev_a1)
    db_session.commit()

    officer_token = create_access_token(subject=officer.id)

    return {
        "officer_token": officer_token,
        "tender_a": tender_a,
        "tender_b": tender_b,
        "crit_a": crit_a,
        "crit_b": crit_b,
        "sub_a1": sub_a1,
        "sub_b2": sub_b2,
    }


def test_cross_tender_criterion_evaluation_isolation(client: TestClient, isolation_fixture):
    """Evaluating a criterion from Tender B on a submission belonging to Tender A must fail."""
    token = isolation_fixture["officer_token"]
    sub_a1_id = isolation_fixture["sub_a1"].id
    crit_b_id = isolation_fixture["crit_b"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/submissions/{sub_a1_id}/criteria/{crit_b_id}/evaluate",
        headers=headers,
    )
    assert res.status_code in (400, 404)
    assert "not found" in res.json()["detail"].lower() or "tender" in res.json()["detail"].lower() or "version" in res.json()["detail"].lower()
