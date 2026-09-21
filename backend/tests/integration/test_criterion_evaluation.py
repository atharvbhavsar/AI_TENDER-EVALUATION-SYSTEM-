"""Integration tests for deterministic Criterion Evaluation and OPA policy evaluation lifecycle."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def eval_lifecycle_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_eval_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-EVAL-{uuid.uuid4().hex[:6]}",
        title="Night Vision Device Procurement",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    db_session.add(version)
    db_session.flush()

    # 1. Turnover Criterion (Eligible)
    turnover_crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="FIN-001",
        name="Annual Turnover Requirement",
        description="Minimum annual turnover of 50 Lakhs INR",
        source_clause="Clause 3.1: Minimum turnover of 50 Lakhs",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=5000000.0,
        unit="INR",
        currency="INR",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    db_session.add(turnover_crit)

    # 2. Experience Criterion (Not Eligible)
    exp_crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="EXP-001",
        name="Past CRPF/Defence Experience",
        description="Minimum 3 completed defence contracts in last 5 years",
        source_clause="Clause 3.2: Minimum 3 completed contracts",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=3.0,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    db_session.add(exp_crit)

    # 3. ISO Certificate Criterion (Missing Evidence -> Manual Review)
    iso_crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CERT-001",
        name="ISO 9001 Certification",
        description="Valid ISO 9001 certification required",
        source_clause="Clause 4.1: Valid ISO 9001 certificate",
        category=CriterionCategory.CERTIFICATION,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
    )
    db_session.add(iso_crit)
    db_session.flush()

    # Create Bidder and Submission
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BID-APEX",
        legal_name="Apex Defence Solutions Ltd",
        contact_email="bids@apexdefence.in",
        contact_phone="+919876543210",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        status=SubmissionStatus.READY,
        submission_reference=f"SUB-APEX-{uuid.uuid4().hex[:6]}",
    )
    db_session.add(submission)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="apex_technical_bid.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024 * 100,
        sha256_hash="dummysha256hashapex",
        storage_key="documents/apex_bid.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()

    extraction_run = EvidenceExtractionRun(
        id=uuid.uuid4(),
        bid_submission_id=submission.id,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        extractor_version="v1.0",
        status=ExtractionRunStatus.COMPLETED,
        created_by=officer.id,
    )
    db_session.add(extraction_run)
    db_session.flush()

    # Evidence for Turnover (Eligible: 75 Lakhs)
    ev_turnover = Evidence(
        id=uuid.uuid4(),
        bid_submission_id=submission.id,
        criterion_id=turnover_crit.id,
        document_id=doc.id,
        extraction_run_id=extraction_run.id,
        status=EvidenceStatus.FOUND,
        extracted_text="The average annual turnover of Apex Defence Solutions for the last 3 financial years is Rs. 75,00,000.",
        extracted_value=7500000.0,
        unit="INR",
        currency="INR",
        confidence=0.95,
        extractor_version="v1.0",
    )
    db_session.add(ev_turnover)

    # Evidence for Experience (Not Eligible: 1 contract only)
    ev_exp = Evidence(
        id=uuid.uuid4(),
        bid_submission_id=submission.id,
        criterion_id=exp_crit.id,
        document_id=doc.id,
        extraction_run_id=extraction_run.id,
        status=EvidenceStatus.FOUND,
        extracted_text="Bidder has successfully completed 1 prior contract with CRPF in 2023.",
        extracted_value=1.0,
        experience_data={"completed_contracts": 1},
        confidence=0.92,
        extractor_version="v1.0",
    )
    db_session.add(ev_exp)

    # Evidence for ISO (Missing -> Manual Review)
    ev_iso = Evidence(
        id=uuid.uuid4(),
        bid_submission_id=submission.id,
        criterion_id=iso_crit.id,
        document_id=doc.id,
        extraction_run_id=extraction_run.id,
        status=EvidenceStatus.MISSING,
        extracted_text=None,
        extracted_value=None,
        confidence=0.0,
        extractor_version="v1.0",
    )
    db_session.add(ev_iso)
    db_session.commit()

    officer_token = create_access_token(subject=officer.id)

    return {
        "officer": officer,
        "officer_token": officer_token,
        "tender": tender,
        "version": version,
        "submission": submission,
        "turnover_crit": turnover_crit,
        "exp_crit": exp_crit,
        "iso_crit": iso_crit,
        "ev_turnover": ev_turnover,
        "ev_exp": ev_exp,
        "ev_iso": ev_iso,
    }


def test_evaluate_turnover_criterion_eligible(client: TestClient, eval_lifecycle_fixture):
    """Test deterministic evaluation yields ELIGIBLE for compliant evidence."""
    token = eval_lifecycle_fixture["officer_token"]
    submission_id = eval_lifecycle_fixture["submission"].id
    crit_id = eval_lifecycle_fixture["turnover_crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/submissions/{submission_id}/criteria/{crit_id}/evaluate",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["result"] == "ELIGIBLE"
    assert data["input_snapshot"] is not None
    assert "rule" in data["input_snapshot"]


def test_evaluate_experience_criterion_not_eligible(client: TestClient, eval_lifecycle_fixture):
    """Test deterministic evaluation yields NOT_ELIGIBLE when threshold not satisfied."""
    token = eval_lifecycle_fixture["officer_token"]
    submission_id = eval_lifecycle_fixture["submission"].id
    crit_id = eval_lifecycle_fixture["exp_crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/submissions/{submission_id}/criteria/{crit_id}/evaluate",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["result"] == "NOT_ELIGIBLE"
    assert "explanation" in data


def test_evaluate_missing_evidence_routes_to_manual_review(client: TestClient, eval_lifecycle_fixture):
    """Test deterministic evaluation routes to MANUAL_REVIEW on MISSING evidence."""
    token = eval_lifecycle_fixture["officer_token"]
    submission_id = eval_lifecycle_fixture["submission"].id
    crit_id = eval_lifecycle_fixture["iso_crit"].id

    headers = {"Authorization": f"Bearer {token}"}
    res = client.post(
        f"/api/v1/submissions/{submission_id}/criteria/{crit_id}/evaluate",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["result"] == "MANUAL_REVIEW"
    assert "explanation" in data


def test_list_and_retrieve_submission_evaluations(client: TestClient, eval_lifecycle_fixture):
    """Test fetching all criterion evaluations for a submission."""
    token = eval_lifecycle_fixture["officer_token"]
    submission_id = eval_lifecycle_fixture["submission"].id
    turnover_id = eval_lifecycle_fixture["turnover_crit"].id
    exp_id = eval_lifecycle_fixture["exp_crit"].id

    headers = {"Authorization": f"Bearer {token}"}

    # Run evaluations first
    client.post(f"/api/v1/submissions/{submission_id}/criteria/{turnover_id}/evaluate", headers=headers)
    client.post(f"/api/v1/submissions/{submission_id}/criteria/{exp_id}/evaluate", headers=headers)

    # Fetch list
    res = client.get(f"/api/v1/submissions/{submission_id}/evaluations", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["submission_id"] == str(submission_id)
    assert data["total_evaluations"] == 2
    results = [e["result"] for e in data["evaluations"]]
    assert "ELIGIBLE" in results
    assert "NOT_ELIGIBLE" in results
