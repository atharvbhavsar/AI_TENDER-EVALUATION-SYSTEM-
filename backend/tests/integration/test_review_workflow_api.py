"""Integration tests for Phase 13 Human Review workflow and REST APIs."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
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
def review_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    reviewer_role = db_session.query(Role).filter_by(name="REVIEWER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_rev_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer Review",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer_rev_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Reviewer Specialist",
        is_active=True,
        password_hash="dummy_hash",
    )
    if reviewer_role:
        reviewer.roles.append(reviewer_role)

    db_session.add_all([officer, reviewer])

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-REV-{uuid.uuid4().hex[:6]}",
        title="Tactical Body Armor Ingestion",
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

    criterion = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CRIT-TURNOVER",
        name="Annual Turnover >= 10 Cr",
        description="Minimum annual turnover requirement",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        source_clause="Clause 4.1",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(criterion)
    db_session.flush()

    rule = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=criterion.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"operator": ">=", "threshold": 100000000.0, "currency": "INR"},
        status=RuleStatus.ACTIVE,
        created_by=officer.id,
    )
    db_session.add(rule)

    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="REG-BHARAT-01",
        legal_name="Bharat Defense Armor Ltd",
        contact_email="defense@crpf.gov.in",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-BHARAT-001",
        status=SubmissionStatus.READY,
    )
    db_session.add(submission)
    db_session.flush()

    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="audited_balance_sheet_2025.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="dummyhash123",
        storage_key="docs/dummy.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()

    run = EvidenceExtractionRun(
        id=uuid.uuid4(),
        bid_submission_id=submission.id,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        extractor_version="v1.0",
        created_by=officer.id,
    )
    db_session.add(run)
    db_session.flush()

    evidence = Evidence(
        id=uuid.uuid4(),
        criterion_id=criterion.id,
        bid_submission_id=submission.id,
        document_id=doc.id,
        extraction_run_id=run.id,
        status=EvidenceStatus.UNREADABLE,
        raw_extracted_data={"unreadable_reason": "Low resolution scan on page 3"},
        confidence=0.45,
        source_page=3,
        source_block_id="block-44",
        bbox=[50.0, 100.0, 500.0, 250.0],
        extractor_version="v1.0",
    )
    db_session.add(evidence)
    db_session.flush()

    crit_eval = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=criterion.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        tender_version_id=version.id,
        rule_id=rule.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.MANUAL_REVIEW,
        input_snapshot={"evidence": {"status": "UNREADABLE", "confidence": 0.45}},
        evidence_ids=[str(evidence.id)],
        explanation={"reason": "Evidence is unreadable and requires officer review."},
    )
    db_session.add(crit_eval)

    overall_eval = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        evaluation_run_id=uuid.uuid4(),
        result=EvaluationResult.MANUAL_REVIEW,
        aggregation_policy_version="v1.0",
        criterion_count=1,
        eligible_count=0,
        not_eligible_count=0,
        manual_review_count=1,
        mandatory_criterion_count=1,
        mandatory_eligible_count=0,
        mandatory_not_eligible_count=0,
        mandatory_manual_review_count=1,
        rule_version_snapshot={"criteria": [{"criterion_code": "CRIT-TURNOVER", "result": "MANUAL_REVIEW"}]},
        explanation={"summary": "1 mandatory criterion requires manual review."},
    )
    db_session.add(overall_eval)
    db_session.commit()

    officer_token = create_access_token(subject=officer.id)
    reviewer_token = create_access_token(subject=reviewer.id)

    return {
        "officer": officer,
        "reviewer": reviewer,
        "tender": tender,
        "version": version,
        "criterion": criterion,
        "bidder": bidder,
        "submission": submission,
        "evidence": evidence,
        "crit_eval": crit_eval,
        "overall_eval": overall_eval,
        "officer_headers": {"Authorization": f"Bearer {officer_token}"},
        "reviewer_headers": {"Authorization": f"Bearer {reviewer_token}"},
    }


def test_complete_human_review_lifecycle(client: TestClient, db_session, review_fixture):
    """
    Test complete review lifecycle:
    1. Auto-generate review case from MANUAL_REVIEW evaluation.
    2. Get full detail with bounding box and OPA explanation.
    3. Assign to officer.
    4. Add review note.
    5. Record human OVERRIDE decision with justification.
    6. Resolve review case.
    7. Reopen case.
    8. Check full audit history.
    """
    fix = review_fixture
    sub_id = fix["submission"].id

    # 1. Auto-generate review case
    resp_gen = client.post(
        f"/api/v1/reviews/generate?submission_id={sub_id}",
        headers=fix["officer_headers"],
    )
    assert resp_gen.status_code == 200
    cases = resp_gen.json()
    assert len(cases) == 1
    review_id = cases[0]["id"]
    assert cases[0]["status"] == "OPEN"
    assert cases[0]["priority"] == "HIGH"

    # 2. Get full detail
    resp_detail = client.get(
        f"/api/v1/reviews/{review_id}",
        headers=fix["officer_headers"],
    )
    assert resp_detail.status_code == 200
    detail = resp_detail.json()
    assert detail["criterion_code"] == "CRIT-TURNOVER"
    assert detail["system_criterion_result"] == "MANUAL_REVIEW"
    assert len(detail["evidence_items"]) == 1
    assert detail["evidence_items"][0]["bounding_box"] == [50.0, 100.0, 500.0, 250.0]

    # 3. Assign to officer
    resp_assign = client.post(
        f"/api/v1/reviews/{review_id}/assign",
        json={"assigned_to": str(fix["officer"].id)},
        headers=fix["officer_headers"],
    )
    assert resp_assign.status_code == 200
    assert resp_assign.json()["status"] == "IN_REVIEW"

    # 4. Add review note
    resp_note = client.post(
        f"/api/v1/reviews/{review_id}/notes",
        json={"note": "Physical attested balance sheet reviewed on site; turnover verified as ₹15.2 Cr."},
        headers=fix["officer_headers"],
    )
    assert resp_note.status_code == 201
    assert "₹15.2 Cr" in resp_note.json()["note"]

    # 5. Record OVERRIDE decision
    resp_decide = client.post(
        f"/api/v1/reviews/{review_id}/decide",
        json={
            "decision": "OVERRIDE",
            "final_verdict": "ELIGIBLE",
            "reason": "Officer verified CA certified original financial statements establishing ₹15.2 crore annual turnover.",
        },
        headers=fix["officer_headers"],
    )
    assert resp_decide.status_code == 201
    dec_data = resp_decide.json()
    assert dec_data["decision"] == "OVERRIDE"
    assert dec_data["system_result"] == "MANUAL_REVIEW"
    assert dec_data["final_verdict"] == "ELIGIBLE"

    # 6. Resolve review case
    resp_resolve = client.post(
        f"/api/v1/reviews/{review_id}/resolve",
        headers=fix["officer_headers"],
    )
    assert resp_resolve.status_code == 200
    assert resp_resolve.json()["status"] == "RESOLVED"
    assert resp_resolve.json()["resolved_at"] is not None

    # 7. Reopen review case
    resp_reopen = client.post(
        f"/api/v1/reviews/{review_id}/reopen",
        headers=fix["officer_headers"],
    )
    assert resp_reopen.status_code == 200
    assert resp_reopen.json()["status"] == "IN_REVIEW"

    # 8. Check audit history
    resp_hist = client.get(
        f"/api/v1/reviews/{review_id}/history",
        headers=fix["officer_headers"],
    )
    assert resp_hist.status_code == 200
    hist = resp_hist.json()
    actions = [h["action"] for h in hist]
    assert "AUTO_GENERATED" in actions
    assert "ASSIGNED" in actions
    assert "NOTE_ADDED" in actions
    assert "DECISION_RECORDED" in actions
    assert "RESOLVED" in actions
    assert "REOPENED" in actions


def test_manual_review_creation_and_listing_with_filters(client: TestClient, db_session, review_fixture):
    """Test manual review case creation and listing API with filters."""
    fix = review_fixture
    sub_id = fix["submission"].id

    resp_create = client.post(
        "/api/v1/reviews",
        json={
            "bid_submission_id": str(sub_id),
            "criterion_id": str(fix["criterion"].id),
            "issue_type": "CONFLICTING_EVIDENCE",
            "priority": "HIGH",
            "title": "Discrepancy in revenue disclosure",
            "description": "Page 2 and Page 14 report different revenue figures.",
        },
        headers=fix["officer_headers"],
    )
    assert resp_create.status_code == 201
    case_data = resp_create.json()
    case_id = case_data["id"]

    # Filter by priority=HIGH
    resp_list = client.get(
        f"/api/v1/reviews?priority=HIGH&submission_id={sub_id}",
        headers=fix["officer_headers"],
    )
    assert resp_list.status_code == 200
    data_list = resp_list.json()
    assert data_list["total"] >= 1
    assert any(c["id"] == case_id for c in data_list["items"])
