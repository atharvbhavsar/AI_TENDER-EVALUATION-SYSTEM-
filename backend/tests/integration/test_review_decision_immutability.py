"""Integration tests for Phase 13 Decision Immutability and Validation."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
from app.db.models.review_case import (
    HumanDecision,
    OfficerDecision,
    ReviewCase,
    ReviewIssueType,
    ReviewPriority,
    ReviewStatus,
)
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
def decision_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_dec_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer Decision",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-DEC-{uuid.uuid4().hex[:6]}",
        title="Tactical Radio Procurement",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    db_session.add(version)
    db_session.flush()

    criterion = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CRIT-RADIO-CERT",
        name="MIL-STD-810G Certificate",
        description="Military environmental test certificate",
        category=CriterionCategory.CERTIFICATION,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        source_clause="Clause 6.1",
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
        rule_type=RuleType.CERTIFICATE_EXISTENCE,
        rule_version="v1.0",
        configuration={"certificate_type": "MIL_STD_810G"},
        status=RuleStatus.ACTIVE,
        created_by=officer.id,
    )
    db_session.add(rule)

    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="REG-COMM-01",
        legal_name="National Telecom Ltd",
        contact_email="radio@crpf.gov.in",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-COMM-001",
        status=SubmissionStatus.READY,
    )
    db_session.add(submission)
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
        result=EvaluationResult.NOT_ELIGIBLE,
        input_snapshot={"evidence": {"found": False}},
        evidence_ids=[],
        explanation={"reason": "Certificate was missing in uploaded scans."},
    )
    db_session.add(crit_eval)
    db_session.flush()

    review_case = ReviewCase(
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=criterion.id,
        criterion_evaluation_id=crit_eval.id,
        status=ReviewStatus.OPEN,
        priority=ReviewPriority.HIGH,
        issue_type=ReviewIssueType.MISSING_EVIDENCE,
        title="Missing MIL-STD certificate",
        description="Scanned documents lacked page 12 lab endorsement.",
        created_by=officer.id,
    )
    db_session.add(review_case)
    db_session.commit()

    token = create_access_token(subject=officer.id)

    return {
        "officer": officer,
        "review_case": review_case,
        "crit_eval": crit_eval,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def test_system_result_immutability_on_officer_override(client: TestClient, db_session, decision_fixture):
    """An officer override must NOT overwrite the automated system evaluation record in the database."""
    fix = decision_fixture
    review_id = fix["review_case"].id
    eval_id = fix["crit_eval"].id

    resp = client.post(
        f"/api/v1/reviews/{review_id}/decide",
        json={
            "decision": "OVERRIDE",
            "final_verdict": "ELIGIBLE",
            "reason": "Officer verified valid defense lab certificate produced under sealed envelope.",
        },
        headers=fix["headers"],
    )
    assert resp.status_code == 201

    # Check underlying CriterionEvaluation is still NOT_ELIGIBLE
    db_session.expire_all()
    eval_record = db_session.get(CriterionEvaluation, eval_id)
    assert eval_record.result == EvaluationResult.NOT_ELIGIBLE

    # Check OfficerDecision record has both
    dec_record = db_session.query(OfficerDecision).filter_by(review_case_id=review_id).first()
    assert dec_record.system_result == EvaluationResult.NOT_ELIGIBLE
    assert dec_record.decision == HumanDecision.OVERRIDE
    assert dec_record.final_verdict == EvaluationResult.ELIGIBLE


def test_override_requires_non_empty_reason(client: TestClient, decision_fixture):
    """Submitting an override with empty reason is rejected."""
    fix = decision_fixture
    review_id = fix["review_case"].id

    resp = client.post(
        f"/api/v1/reviews/{review_id}/decide",
        json={
            "decision": "OVERRIDE",
            "final_verdict": "ELIGIBLE",
            "reason": "   ",
        },
        headers=fix["headers"],
    )
    assert resp.status_code in (400, 422)


def test_cannot_resolve_review_case_without_decision(client: TestClient, decision_fixture):
    """Resolving a review case without any officer decision is rejected."""
    fix = decision_fixture
    review_id = fix["review_case"].id

    resp = client.post(
        f"/api/v1/reviews/{review_id}/resolve",
        headers=fix["headers"],
    )
    assert resp.status_code == 400
    assert "without an explicit officer decision" in resp.json()["detail"]
