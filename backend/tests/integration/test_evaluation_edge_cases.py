"""Integration tests covering edge cases, failure modes, audit preservation, and security (Sections 18-32)."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
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
from app.rules.opa.base import BaseOPAClient


@pytest.fixture
def edge_case_fixture(db_session: Session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    reviewer_role = db_session.query(Role).filter_by(name="REVIEWER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_edge_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer_edge_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Reviewer User",
        is_active=True,
        password_hash="dummy_hash",
    )
    if reviewer_role:
        reviewer.roles.append(reviewer_role)
    db_session.add(reviewer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-EDGE-{uuid.uuid4().hex[:6]}",
        title="Tactical Radios",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    # Version 1
    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    # Version 2
    v2 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=2, created_by=officer.id)
    db_session.add_all([v1, v2])
    db_session.flush()

    # Criteria on V1
    c1_v1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="FIN-001",
        name="Turnover v1",
        description="Turnover >= 5 Cr",
        source_clause="Clause 1: 5 Cr",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=50000000.0,
        unit="INR",
        currency="INR",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    # Criteria on V2 (Higher threshold 10 Cr)
    c1_v2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v2.id,
        criterion_code="FIN-001",
        name="Turnover v2",
        description="Turnover >= 10 Cr",
        source_clause="Clause 1: 10 Cr",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=100000000.0,
        unit="INR",
        currency="INR",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    db_session.add_all([c1_v1, c1_v2])

    bidder_a = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="BID-A", legal_name="Alpha Tech")
    bidder_b = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="BID-B", legal_name="Beta Comms")
    db_session.add_all([bidder_a, bidder_b])
    db_session.flush()

    sub_a_v1 = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        status=SubmissionStatus.READY,
        submission_reference=f"SUB-A-V1-{uuid.uuid4().hex[:4]}",
    )
    sub_b_v1 = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder_b.id,
        status=SubmissionStatus.READY,
        submission_reference=f"SUB-B-V1-{uuid.uuid4().hex[:4]}",
    )
    db_session.add_all([sub_a_v1, sub_b_v1])
    db_session.flush()

    doc_a = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bid_submission_id=sub_a_v1.id,
        filename="alpha_turnover.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="hashalpha",
        storage_key="path/alpha.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc_a)
    db_session.flush()

    run_a = EvidenceExtractionRun(
        id=uuid.uuid4(),
        bid_submission_id=sub_a_v1.id,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        extractor_version="v1.0",
        status=ExtractionRunStatus.COMPLETED,
        created_by=officer.id,
    )
    db_session.add(run_a)
    db_session.flush()

    # Alpha has 7 Cr (Eligible for V1 >= 5 Cr, but NOT_ELIGIBLE for V2 >= 10 Cr)
    ev_a = Evidence(
        id=uuid.uuid4(),
        bid_submission_id=sub_a_v1.id,
        criterion_id=c1_v1.id,
        document_id=doc_a.id,
        extraction_run_id=run_a.id,
        status=EvidenceStatus.FOUND,
        extracted_text="Alpha turnover is 7 Cr",
        extracted_value=70000000.0,
        unit="INR",
        currency="INR",
        confidence=0.95,
        extractor_version="v1.0",
    )
    db_session.add(ev_a)
    db_session.commit()

    officer_token = create_access_token(subject=officer.id)
    reviewer_token = create_access_token(subject=reviewer.id)

    return {
        "officer": officer,
        "reviewer": reviewer,
        "officer_token": officer_token,
        "reviewer_token": reviewer_token,
        "tender": tender,
        "v1": v1,
        "v2": v2,
        "c1_v1": c1_v1,
        "c1_v2": c1_v2,
        "bidder_a": bidder_a,
        "bidder_b": bidder_b,
        "sub_a_v1": sub_a_v1,
        "sub_b_v1": sub_b_v1,
    }


def test_version_isolation_in_evaluations(client: TestClient, edge_case_fixture):
    """Section 19: Version 1 evaluation evaluates strictly against Version 1 rule."""
    token = edge_case_fixture["officer_token"]
    sub_id = edge_case_fixture["sub_a_v1"].id
    c1_v1_id = edge_case_fixture["c1_v1"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/submissions/{sub_id}/criteria/{c1_v1_id}/evaluate",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["result"] == "ELIGIBLE"
    assert data["tender_version_id"] == str(edge_case_fixture["v1"].id)


def test_bidder_and_submission_isolation(client: TestClient, edge_case_fixture):
    """Section 20 & 21: Evaluating Submission B does not pull evidence from Submission A."""
    token = edge_case_fixture["officer_token"]
    sub_b_id = edge_case_fixture["sub_b_v1"].id
    c1_v1_id = edge_case_fixture["c1_v1"].id

    headers = {"Authorization": f"Bearer {token}"}
    # Submission B has no uploaded evidence for this criterion -> Must route to MANUAL_REVIEW
    res = client.post(
        f"/api/v1/submissions/{sub_b_id}/criteria/{c1_v1_id}/evaluate",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["result"] == "MANUAL_REVIEW"
    assert len(data["evidence_ids"]) == 0


def test_rule_tampering_unauthorized(client: TestClient, edge_case_fixture):
    """Section 25: Reviewer lacking TENDER_UPDATE cannot modify rule configuration."""
    token = edge_case_fixture["reviewer_token"]
    crit_id = edge_case_fixture["c1_v1"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/criteria/{crit_id}/rule",
        json={"rule_type": "NUMERIC_THRESHOLD", "configuration": {"threshold": 1.0}},
        headers=headers,
    )
    assert res.status_code == 403


def test_audit_record_preservation(client: TestClient, edge_case_fixture, db_session: Session):
    """Section 26: Verify complete snapshot and audit fields stored in CriterionEvaluation."""
    token = edge_case_fixture["officer_token"]
    sub_id = edge_case_fixture["sub_a_v1"].id
    c1_v1_id = edge_case_fixture["c1_v1"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/submissions/{sub_id}/criteria/{c1_v1_id}/evaluate",
        headers=headers,
    )
    assert res.status_code == 200
    eval_data = res.json()

    # Check DB record directly
    db_eval = db_session.get(CriterionEvaluation, uuid.UUID(eval_data["id"]))
    assert db_eval is not None
    assert db_eval.bidder_id == edge_case_fixture["bidder_a"].id
    assert db_eval.bid_submission_id == sub_id
    assert db_eval.tender_version_id == edge_case_fixture["v1"].id
    assert db_eval.criterion_id == c1_v1_id
    assert db_eval.input_snapshot is not None
    assert "rule" in db_eval.input_snapshot
    assert db_eval.evaluated_at is not None


def test_invalid_opa_response_sanitization(client: TestClient, edge_case_fixture, monkeypatch):
    """Section 29: Invalid or unknown OPA response is safely sanitized to MANUAL_REVIEW."""
    class MalfunctioningOPAClient(BaseOPAClient):
        async def evaluate_policy(self, policy_path: str, input_data: dict) -> dict:
            return {"result": "CORRUPT_UNKNOWN_VERDICT", "explanation": {}}

        async def health_check(self) -> bool:
            return True

    from app.rules import service
    monkeypatch.setattr(service, "get_opa_client", lambda: MalfunctioningOPAClient())

    token = edge_case_fixture["officer_token"]
    sub_id = edge_case_fixture["sub_a_v1"].id
    c1_v1_id = edge_case_fixture["c1_v1"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/submissions/{sub_id}/criteria/{c1_v1_id}/evaluate",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["result"] == "MANUAL_REVIEW"


def test_api_nonexistent_and_invalid_inputs(client: TestClient, edge_case_fixture):
    """Section 31: API validation for nonexistent criterion, submission, and invalid IDs."""
    token = edge_case_fixture["officer_token"]
    headers = {"Authorization": f"Bearer {token}"}
    fake_id = uuid.uuid4()

    # Nonexistent criterion
    res_crit_404 = client.get(f"/api/v1/criteria/{fake_id}/rule", headers=headers)
    assert res_crit_404.status_code == 404

    # Nonexistent submission evaluation
    res_sub_404 = client.post(
        f"/api/v1/submissions/{fake_id}/criteria/{edge_case_fixture['c1_v1'].id}/evaluate",
        headers=headers,
    )
    assert res_sub_404.status_code == 404

    # Invalid UUID string
    res_bad_uuid = client.get("/api/v1/criteria/not-a-uuid/rule", headers=headers)
    assert res_bad_uuid.status_code == 422
