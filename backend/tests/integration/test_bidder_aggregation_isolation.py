"""Integration tests for Phase 12 Version, Bidder, and Submission Isolation."""

import datetime
import uuid
import pytest

from app.aggregation import service
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
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
        full_name="Procurement Officer Isolation",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-ISO-{uuid.uuid4().hex[:6]}",
        title="Tactical Drone Ingestion",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    v2 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=2, created_by=officer.id)
    db_session.add_all([v1, v2])
    db_session.flush()

    # V1 criteria: C1 (Approved)
    c1_v1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="CRIT-V1",
        name="V1 Requirement",
        description="Version 1 Criterion",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        source_clause="Clause 1.0",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    # V2 criteria: C2 (Approved)
    c2_v2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v2.id,
        criterion_code="CRIT-V2",
        name="V2 Requirement",
        description="Version 2 Criterion",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        source_clause="Clause 2.0",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    # V1 criterion that is REJECTED
    c1_rejected = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="CRIT-V1-REJ",
        name="Rejected Requirement",
        description="Rejected Criterion",
        category=CriterionCategory.COMPLIANCE,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        source_clause="Clause 3.0",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.REJECTED,
    )
    # V1 criterion that is PENDING_REVIEW
    c1_pending = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="CRIT-V1-PEND",
        name="Pending Requirement",
        description="Pending Criterion",
        category=CriterionCategory.COMPLIANCE,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        source_clause="Clause 4.0",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )
    db_session.add_all([c1_v1, c2_v2, c1_rejected, c1_pending])

    # Bidder A and Bidder B
    bidder_a = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="REG-A", legal_name="Bidder Alpha", contact_email="a@crpf.gov.in")
    bidder_b = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="REG-B", legal_name="Bidder Beta", contact_email="b@crpf.gov.in")
    db_session.add_all([bidder_a, bidder_b])
    db_session.flush()

    # Submissions
    sub_a_v1 = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder_a.id, submission_reference="SUB-A-V1", status=SubmissionStatus.READY)
    sub_b_v1 = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder_b.id, submission_reference="SUB-B-V1", status=SubmissionStatus.READY)
    sub_a_v2 = BidSubmission(id=uuid.uuid4(), tender_version_id=v2.id, bidder_id=bidder_a.id, submission_reference="SUB-A-V2", status=SubmissionStatus.READY)
    db_session.add_all([sub_a_v1, sub_b_v1, sub_a_v2])
    db_session.commit()

    return {
        "officer": officer,
        "tender": tender,
        "v1": v1,
        "v2": v2,
        "c1_v1": c1_v1,
        "c2_v2": c2_v2,
        "c1_rejected": c1_rejected,
        "c1_pending": c1_pending,
        "bidder_a": bidder_a,
        "bidder_b": bidder_b,
        "sub_a_v1": sub_a_v1,
        "sub_b_v1": sub_b_v1,
        "sub_a_v2": sub_a_v2,
    }


def test_tender_version_isolation_in_aggregation(db_session, isolation_fixture):
    """Evaluating V1 only aggregates V1 criteria; evaluating V2 only aggregates V2 criteria."""
    fix = isolation_fixture

    # Add evaluation for V1
    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=fix["c1_v1"].id,
        tender_version_id=fix["v1"].id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"operator": ">=", "threshold": 10},
        status=RuleStatus.ACTIVE,
    )
    rule2 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=fix["c2_v2"].id,
        tender_version_id=fix["v2"].id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"operator": ">=", "threshold": 20},
        status=RuleStatus.ACTIVE,
    )
    db_session.add_all([rule1, rule2])
    db_session.flush()

    eval_v1 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c1_v1"].id,
        bidder_id=fix["bidder_a"].id,
        bid_submission_id=fix["sub_a_v1"].id,
        tender_version_id=fix["v1"].id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"value": 15}},
        evidence_ids=["ev-1"],
    )
    eval_v2 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c2_v2"].id,
        bidder_id=fix["bidder_a"].id,
        bid_submission_id=fix["sub_a_v2"].id,
        tender_version_id=fix["v2"].id,
        rule_id=rule2.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.NOT_ELIGIBLE,
        input_snapshot={"evidence": {"value": 15}},
        evidence_ids=["ev-2"],
    )
    db_session.add_all([eval_v1, eval_v2])
    db_session.commit()

    # Aggregate V1
    res_v1 = service.aggregate_submission_evaluation(db_session, fix["sub_a_v1"].id)
    assert res_v1.result == EvaluationResult.ELIGIBLE
    assert res_v1.criterion_count == 1
    assert res_v1.rule_version_snapshot["criteria"][0]["criterion_code"] == "CRIT-V1"

    # Aggregate V2
    res_v2 = service.aggregate_submission_evaluation(db_session, fix["sub_a_v2"].id)
    assert res_v2.result == EvaluationResult.NOT_ELIGIBLE
    assert res_v2.criterion_count == 1
    assert res_v2.rule_version_snapshot["criteria"][0]["criterion_code"] == "CRIT-V2"


def test_bidder_isolation_in_aggregation(db_session, isolation_fixture):
    """Bidder A evaluation must not include Bidder B evaluations."""
    fix = isolation_fixture

    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=fix["c1_v1"].id,
        tender_version_id=fix["v1"].id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"operator": ">=", "threshold": 10},
        status=RuleStatus.ACTIVE,
    )
    db_session.add(rule1)
    db_session.flush()

    # Bidder A is ELIGIBLE
    eval_a = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c1_v1"].id,
        bidder_id=fix["bidder_a"].id,
        bid_submission_id=fix["sub_a_v1"].id,
        tender_version_id=fix["v1"].id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"value": 15}},
        evidence_ids=["ev-a"],
    )
    # Bidder B is NOT_ELIGIBLE
    eval_b = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c1_v1"].id,
        bidder_id=fix["bidder_b"].id,
        bid_submission_id=fix["sub_b_v1"].id,
        tender_version_id=fix["v1"].id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.NOT_ELIGIBLE,
        input_snapshot={"evidence": {"value": 5}},
        evidence_ids=["ev-b"],
    )
    db_session.add_all([eval_a, eval_b])
    db_session.commit()

    res_a = service.aggregate_submission_evaluation(db_session, fix["sub_a_v1"].id)
    assert res_a.result == EvaluationResult.ELIGIBLE

    res_b = service.aggregate_submission_evaluation(db_session, fix["sub_b_v1"].id)
    assert res_b.result == EvaluationResult.NOT_ELIGIBLE


def test_unapproved_criteria_are_excluded_from_aggregation(db_session, isolation_fixture):
    """REJECTED and PENDING_REVIEW criteria are never included in authoritative aggregation."""
    fix = isolation_fixture
    # V1 has c1_v1 (APPROVED), c1_rejected (REJECTED), c1_pending (PENDING_REVIEW)
    res = service.aggregate_submission_evaluation(db_session, fix["sub_a_v1"].id)

    # Only 1 approved criterion should participate
    assert res.criterion_count == 1
    codes = [c["criterion_code"] for c in res.rule_version_snapshot["criteria"]]
    assert "CRIT-V1" in codes
    assert "CRIT-V1-REJ" not in codes
    assert "CRIT-V1-PEND" not in codes


def test_historical_runs_are_preserved(db_session, isolation_fixture):
    """When a new evaluation is run, previous BidderEvaluation records remain completely unchanged."""
    fix = isolation_fixture

    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=fix["c1_v1"].id,
        tender_version_id=fix["v1"].id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"operator": ">=", "threshold": 10},
        status=RuleStatus.ACTIVE,
    )
    db_session.add(rule1)
    db_session.flush()

    # Run 1: Missing evaluation -> MANUAL_REVIEW
    run1 = service.aggregate_submission_evaluation(db_session, fix["sub_a_v1"].id)
    assert run1.result == EvaluationResult.MANUAL_REVIEW
    run1_id = run1.id

    # Now add an evaluation -> Run 2: ELIGIBLE
    eval_a = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c1_v1"].id,
        bidder_id=fix["bidder_a"].id,
        bid_submission_id=fix["sub_a_v1"].id,
        tender_version_id=fix["v1"].id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"value": 15}},
        evidence_ids=["ev-a"],
    )
    db_session.add(eval_a)
    db_session.commit()

    run2 = service.aggregate_submission_evaluation(db_session, fix["sub_a_v1"].id)
    assert run2.result == EvaluationResult.ELIGIBLE
    assert run2.id != run1_id

    # Verify Run 1 and Run 2 are both preserved with their exact verdicts and configurations
    history = service.list_submission_evaluations_history(db_session, fix["sub_a_v1"].id)
    assert len(history) == 2
    history_ids = {h.id for h in history}
    assert run1_id in history_ids
    assert run2.id in history_ids

    run1_record = next(h for h in history if h.id == run1_id)
    run2_record = next(h for h in history if h.id == run2.id)
    assert run1_record.result == EvaluationResult.MANUAL_REVIEW
    assert run2_record.result == EvaluationResult.ELIGIBLE
