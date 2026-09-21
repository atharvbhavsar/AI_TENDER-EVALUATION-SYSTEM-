"""Integration tests for Phase 12 Bidder-Level Aggregation & Overall Eligibility REST APIs."""

import datetime
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
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
def aggregation_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_agg_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer Aggregation",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-AGG-{uuid.uuid4().hex[:6]}",
        title="Helicopter Surveillance Procurement",
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

    # Create 3 Approved criteria (2 Mandatory, 1 Optional)
    c1_turnover = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CRIT-TURNOVER",
        name="Annual Turnover >= 10 Cr",
        description="Minimum annual turnover requirement",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        operator=">=",
        threshold_value=10.0,
        currency="INR",
        unit="crore",
        source_clause="Clause 4.1",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    c2_experience = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CRIT-EXP",
        name="Completed Projects >= 3",
        description="Minimum completed past projects",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        operator=">=",
        threshold_value=3.0,
        unit="projects",
        source_clause="Clause 5.2",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    c3_cert = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CRIT-OPT-CERT",
        name="Optional Green Certification",
        description="Optional sustainability certificate",
        category=CriterionCategory.CERTIFICATION,
        requirement_type=RequirementType.OPTIONAL,
        mandatory=False,
        source_clause="Clause 9.1",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add_all([c1_turnover, c2_experience, c3_cert])

    # Rules for criteria
    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=c1_turnover.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"operator": ">=", "threshold": 100000000.0, "currency": "INR"},
        status=RuleStatus.ACTIVE,
        created_by=officer.id,
    )
    rule2 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=c2_experience.id,
        tender_version_id=version.id,
        rule_type=RuleType.EXPERIENCE_COUNT,
        rule_version="v1.0",
        configuration={"min_count": 3},
        status=RuleStatus.ACTIVE,
        created_by=officer.id,
    )
    rule3 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=c3_cert.id,
        tender_version_id=version.id,
        rule_type=RuleType.CERTIFICATE_EXISTENCE,
        rule_version="v1.0",
        configuration={"certificate_type": "GREEN_CERT"},
        status=RuleStatus.ACTIVE,
        created_by=officer.id,
    )
    db_session.add_all([rule1, rule2, rule3])

    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="REG-TATA-99",
        legal_name="Tata Advanced Aerospace Ltd",
        contact_email="tata@crpf.gov.in",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-TATA-001",
        status=SubmissionStatus.READY,
    )
    db_session.add(submission)
    db_session.commit()

    token = create_access_token(
        subject=officer.id,
    )
    headers = {"Authorization": f"Bearer {token}"}

    return {
        "officer": officer,
        "tender": tender,
        "version": version,
        "c1": c1_turnover,
        "c2": c2_experience,
        "c3": c3_cert,
        "rule1": rule1,
        "rule2": rule2,
        "rule3": rule3,
        "bidder": bidder,
        "submission": submission,
        "headers": headers,
    }


def test_evaluate_submission_all_mandatory_pass_with_optional_fail(client: TestClient, db_session, aggregation_fixture):
    """
    Mandatory C1 (ELIGIBLE), Mandatory C2 (ELIGIBLE), Optional C3 (NOT_ELIGIBLE).
    Overall result must be ELIGIBLE.
    """
    fix = aggregation_fixture
    sub_id = fix["submission"].id

    # Create CriterionEvaluations
    eval1 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c1"].id,
        bidder_id=fix["bidder"].id,
        bid_submission_id=sub_id,
        tender_version_id=fix["version"].id,
        rule_id=fix["rule1"].id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"value": 140000000.0}},
        evidence_ids=["ev-turnover"],
        explanation={"status": "ELIGIBLE"},
    )
    eval2 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c2"].id,
        bidder_id=fix["bidder"].id,
        bid_submission_id=sub_id,
        tender_version_id=fix["version"].id,
        rule_id=fix["rule2"].id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"count": 4}},
        evidence_ids=["ev-exp"],
        explanation={"status": "ELIGIBLE"},
    )
    eval3 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c3"].id,
        bidder_id=fix["bidder"].id,
        bid_submission_id=sub_id,
        tender_version_id=fix["version"].id,
        rule_id=fix["rule3"].id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.NOT_ELIGIBLE,
        input_snapshot={"evidence": {"found": False}},
        evidence_ids=["ev-cert"],
        explanation={"status": "NOT_ELIGIBLE"},
    )
    db_session.add_all([eval1, eval2, eval3])
    db_session.commit()

    resp = client.post(
        f"/api/v1/submissions/{sub_id}/evaluate",
        headers=fix["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["result"] == "ELIGIBLE"
    assert data["criterion_count"] == 3
    assert data["eligible_count"] == 2
    assert data["not_eligible_count"] == 1
    assert data["mandatory_criterion_count"] == 2
    assert data["mandatory_eligible_count"] == 2
    assert data["mandatory_not_eligible_count"] == 0
    assert data["optional_criterion_count"] == 1
    assert data["optional_not_eligible_count"] == 1


def test_evaluate_submission_mandatory_fail_produces_not_eligible(client: TestClient, db_session, aggregation_fixture):
    """
    Mandatory C1 (ELIGIBLE), Mandatory C2 (NOT_ELIGIBLE).
    Overall result must be NOT_ELIGIBLE.
    """
    fix = aggregation_fixture
    sub_id = fix["submission"].id

    eval1 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c1"].id,
        bidder_id=fix["bidder"].id,
        bid_submission_id=sub_id,
        tender_version_id=fix["version"].id,
        rule_id=fix["rule1"].id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"value": 140000000.0}},
        evidence_ids=["ev-turnover"],
        explanation={"status": "ELIGIBLE"},
    )
    eval2 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c2"].id,
        bidder_id=fix["bidder"].id,
        bid_submission_id=sub_id,
        tender_version_id=fix["version"].id,
        rule_id=fix["rule2"].id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.NOT_ELIGIBLE,
        input_snapshot={"evidence": {"count": 1}},
        evidence_ids=["ev-exp"],
        explanation={"status": "NOT_ELIGIBLE"},
    )
    db_session.add_all([eval1, eval2])
    db_session.commit()

    resp = client.post(
        f"/api/v1/submissions/{sub_id}/evaluate",
        headers=fix["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["result"] == "NOT_ELIGIBLE"
    assert data["mandatory_not_eligible_count"] == 1


def test_get_submission_evaluation_endpoints_and_history(client: TestClient, db_session, aggregation_fixture):
    """Test GET /evaluation, GET /evaluation/criteria, and GET /evaluations/history."""
    fix = aggregation_fixture
    sub_id = fix["submission"].id

    eval1 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=fix["c1"].id,
        bidder_id=fix["bidder"].id,
        bid_submission_id=sub_id,
        tender_version_id=fix["version"].id,
        rule_id=fix["rule1"].id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"value": 140000000.0}},
        evidence_ids=["ev-turnover"],
        explanation={"status": "ELIGIBLE"},
    )
    db_session.add(eval1)
    db_session.commit()

    # Trigger evaluation Run 1
    resp1 = client.post(f"/api/v1/submissions/{sub_id}/evaluate", headers=fix["headers"])
    assert resp1.status_code == 200

    # Get latest evaluation
    resp_get = client.get(f"/api/v1/submissions/{sub_id}/evaluation", headers=fix["headers"])
    assert resp_get.status_code == 200
    data_get = resp_get.json()
    assert "criteria_breakdown" in data_get
    assert len(data_get["criteria_breakdown"]) == 3

    # Get criteria breakdown endpoint
    resp_crit = client.get(f"/api/v1/submissions/{sub_id}/evaluation/criteria", headers=fix["headers"])
    assert resp_crit.status_code == 200
    data_crit = resp_crit.json()
    assert len(data_crit["criteria"]) == 3

    # Trigger evaluation Run 2
    resp2 = client.post(f"/api/v1/submissions/{sub_id}/evaluate", headers=fix["headers"])
    assert resp2.status_code == 200

    # List history
    resp_hist = client.get(f"/api/v1/submissions/{sub_id}/evaluations/history", headers=fix["headers"])
    assert resp_hist.status_code == 200
    data_hist = resp_hist.json()
    assert data_hist["total_runs"] == 2
    assert len(data_hist["evaluations"]) == 2


def test_nonexistent_submission_returns_404(client: TestClient, aggregation_fixture):
    """Accessing non-existent submission returns 404."""
    fix = aggregation_fixture
    fake_id = uuid.uuid4()
    resp = client.post(f"/api/v1/submissions/{fake_id}/evaluate", headers=fix["headers"])
    assert resp.status_code == 404
