"""Exhaustive integration tests for Phase 13 Human Review, Officer Override & Decision Audit."""

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
from app.db.models.review_case import (
    HumanDecision,
    OfficerDecision,
    ReviewAuditLog,
    ReviewCase,
    ReviewIssueType,
    ReviewItem,
    ReviewNote,
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
def exhaustive_review_fixture(db_session):
    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()
    reviewer_role = db_session.query(Role).filter_by(name="REVIEWER").first()

    officer1 = User(
        id=uuid.uuid4(),
        email=f"officer1_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Senior Procurement Officer 1",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer1.roles.append(officer_role)

    officer2 = User(
        id=uuid.uuid4(),
        email=f"officer2_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Senior Procurement Officer 2",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer2.roles.append(officer_role)

    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer_ex_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Technical Reviewer",
        is_active=True,
        password_hash="dummy_hash",
    )
    if reviewer_role:
        reviewer.roles.append(reviewer_role)

    db_session.add_all([officer1, officer2, reviewer])

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-EX-REV-{uuid.uuid4().hex[:6]}",
        title="Tactical Missile Defense Ingestion",
        status=TenderStatus.PUBLISHED,
        created_by=officer1.id,
    )
    db_session.add(tender)
    db_session.flush()

    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer1.id)
    v2 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=2, created_by=officer1.id)
    db_session.add_all([v1, v2])
    db_session.flush()

    # Create 3 Criteria for V1: C1 (ELIGIBLE), C2 (NOT_ELIGIBLE), C3 (MANUAL_REVIEW)
    c1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
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
        approved_by=officer1.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    c2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="CRIT-EXPERIENCE",
        name="Past Experience >= 3 Projects",
        description="Minimum past completed contracts",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        operator=">=",
        threshold_value=3.0,
        unit="projects",
        source_clause="Clause 5.1",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer1.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    c3 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="CRIT-ISO-CERT",
        name="ISO 9001:2015 Certificate",
        description="Valid quality management certification",
        category=CriterionCategory.CERTIFICATION,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        source_clause="Clause 7.2",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=officer1.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add_all([c1, c2, c3])
    db_session.flush()

    # Rules
    r1 = CriterionRule(id=uuid.uuid4(), criterion_id=c1.id, tender_version_id=v1.id, rule_type=RuleType.NUMERIC_THRESHOLD, rule_version="v1.0", configuration={"operator": ">=", "threshold": 100000000.0, "currency": "INR"}, status=RuleStatus.ACTIVE)
    r2 = CriterionRule(id=uuid.uuid4(), criterion_id=c2.id, tender_version_id=v1.id, rule_type=RuleType.EXPERIENCE_COUNT, rule_version="v1.0", configuration={"min_count": 3}, status=RuleStatus.ACTIVE)
    r3 = CriterionRule(id=uuid.uuid4(), criterion_id=c3.id, tender_version_id=v1.id, rule_type=RuleType.CERTIFICATE_EXISTENCE, rule_version="v1.0", configuration={"certificate_type": "ISO_9001"}, status=RuleStatus.ACTIVE)
    db_session.add_all([r1, r2, r3])

    # Bidder and Submissions
    bidder = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="REG-DYNAMIC-01", legal_name="Dynamic Defense Ltd", contact_email="dynamic@crpf.gov.in")
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder.id, submission_reference="SUB-DYNAMIC-001", status=SubmissionStatus.READY)
    db_session.add(submission)
    db_session.flush()

    # Documents and Evidence
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bid_submission_id=submission.id,
        filename="technical_proposal.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=2048,
        sha256_hash="shatest123",
        storage_key="docs/proposal.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer1.id,
    )
    db_session.add(doc)
    db_session.flush()

    run = EvidenceExtractionRun(id=uuid.uuid4(), bid_submission_id=submission.id, model_name="mock-llm", model_version="v1.0", prompt_version="v1.0", extractor_version="v1.0", created_by=officer1.id)
    db_session.add(run)
    db_session.flush()

    ev1 = Evidence(
        id=uuid.uuid4(),
        criterion_id=c1.id,
        bid_submission_id=submission.id,
        document_id=doc.id,
        extraction_run_id=run.id,
        status=EvidenceStatus.FOUND,
        extracted_value=150000000.0,
        currency="INR",
        unit="INR",
        confidence=0.95,
        source_page=2,
        source_block_id="block-1",
        bbox=[100.0, 150.0, 450.0, 200.0],
        extractor_version="v1.0",
    )
    ev2 = Evidence(
        id=uuid.uuid4(),
        criterion_id=c2.id,
        bid_submission_id=submission.id,
        document_id=doc.id,
        extraction_run_id=run.id,
        status=EvidenceStatus.FOUND,
        extracted_value=1.0,
        unit="projects",
        confidence=0.90,
        source_page=4,
        source_block_id="block-8",
        bbox=[120.0, 300.0, 480.0, 380.0],
        extractor_version="v1.0",
    )
    ev3 = Evidence(
        id=uuid.uuid4(),
        criterion_id=c3.id,
        bid_submission_id=submission.id,
        document_id=doc.id,
        extraction_run_id=run.id,
        status=EvidenceStatus.CONFLICTING,
        raw_extracted_data={"conflict": "Certificate validity contradicts registrar record"},
        confidence=0.60,
        source_page=6,
        source_block_id="block-15",
        source_table_reference="Table 3.1",
        bbox=[80.0, 400.0, 520.0, 580.0],
        extractor_version="v1.0",
    )
    db_session.add_all([ev1, ev2, ev3])
    db_session.flush()

    eval1 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=c1.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        tender_version_id=v1.id,
        rule_id=r1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"evidence": {"value": 150000000.0}},
        evidence_ids=[str(ev1.id)],
        explanation={"status": "ELIGIBLE", "reason": "Turnover ₹15 Cr satisfies >= ₹10 Cr requirement."},
    )
    eval2 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=c2.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        tender_version_id=v1.id,
        rule_id=r2.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.NOT_ELIGIBLE,
        input_snapshot={"evidence": {"count": 1}},
        evidence_ids=[str(ev2.id)],
        explanation={"status": "NOT_ELIGIBLE", "reason": "1 project completed is less than 3 required."},
    )
    eval3 = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=c3.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        tender_version_id=v1.id,
        rule_id=r3.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.MANUAL_REVIEW,
        input_snapshot={"evidence": {"status": "CONFLICTING"}},
        evidence_ids=[str(ev3.id)],
        explanation={"status": "MANUAL_REVIEW", "reason": "Conflicting validity dates require officer verification."},
    )
    db_session.add_all([eval1, eval2, eval3])
    db_session.flush()

    overall_eval = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        result=EvaluationResult.NOT_ELIGIBLE,
        aggregation_policy_version="v1.0",
        criterion_count=3,
        eligible_count=1,
        not_eligible_count=1,
        manual_review_count=1,
        mandatory_criterion_count=3,
        mandatory_eligible_count=1,
        mandatory_not_eligible_count=1,
        mandatory_manual_review_count=1,
        rule_version_snapshot={"criteria": []},
        explanation={"summary": "1 mandatory criterion failed (CRIT-EXPERIENCE)."},
    )
    db_session.add(overall_eval)
    db_session.commit()

    token1 = create_access_token(subject=officer1.id)
    token2 = create_access_token(subject=officer2.id)
    rev_token = create_access_token(subject=reviewer.id)

    return {
        "officer1": officer1,
        "officer2": officer2,
        "reviewer": reviewer,
        "tender": tender,
        "v1": v1,
        "v2": v2,
        "c1": c1,
        "c2": c2,
        "c3": c3,
        "eval1": eval1,
        "eval2": eval2,
        "eval3": eval3,
        "ev1": ev1,
        "ev2": ev2,
        "ev3": ev3,
        "bidder": bidder,
        "submission": submission,
        "overall_eval": overall_eval,
        "officer1_headers": {"Authorization": f"Bearer {token1}"},
        "officer2_headers": {"Authorization": f"Bearer {token2}"},
        "reviewer_headers": {"Authorization": f"Bearer {rev_token}"},
    }


def test_auto_generate_only_targets_manual_review_criteria(client: TestClient, exhaustive_review_fixture):
    """Verify auto-generation targets only MANUAL_REVIEW (C3) and skips ELIGIBLE (C1) and NOT_ELIGIBLE (C2)."""
    fix = exhaustive_review_fixture
    sub_id = fix["submission"].id

    resp = client.post(
        f"/api/v1/reviews/generate?submission_id={sub_id}",
        headers=fix["officer1_headers"],
    )
    assert resp.status_code == 200
    cases = resp.json()
    assert len(cases) == 1
    assert cases[0]["criterion_id"] == str(fix["c3"].id)
    assert cases[0]["issue_type"] == "MANUAL_REVIEW_REQUIRED"


def test_source_traceability_and_evidence_inspection(client: TestClient, db_session, exhaustive_review_fixture):
    """Verify full source traceability (page, block_id, table_ref, bbox) is accessible without credential leaks."""
    fix = exhaustive_review_fixture
    sub_id = fix["submission"].id

    # Generate review case for C3
    resp_gen = client.post(f"/api/v1/reviews/generate?submission_id={sub_id}", headers=fix["officer1_headers"])
    review_id = resp_gen.json()[0]["id"]

    resp_detail = client.get(f"/api/v1/reviews/{review_id}", headers=fix["officer1_headers"])
    assert resp_detail.status_code == 200
    data = resp_detail.json()

    assert data["criterion_code"] == "CRIT-ISO-CERT"
    assert len(data["evidence_items"]) == 1
    ev_item = data["evidence_items"][0]
    assert ev_item["source_page"] == 6
    assert ev_item["source_block_id"] == "block-15"
    assert ev_item["source_table_reference"] == "Table 3.1"
    assert ev_item["bounding_box"] == [80.0, 400.0, 520.0, 580.0]

    # Verify no raw storage credentials leaked in response
    assert "access_key" not in str(data).lower()
    assert "secret_key" not in str(data).lower()


def test_client_officer_id_spoofing_attack_prevented(client: TestClient, db_session, exhaustive_review_fixture):
    """Client cannot spoof officer identity by injecting arbitrary officer_id in payload."""
    fix = exhaustive_review_fixture
    sub_id = fix["submission"].id

    resp_gen = client.post(f"/api/v1/reviews/generate?submission_id={sub_id}", headers=fix["officer1_headers"])
    review_id = resp_gen.json()[0]["id"]

    fake_officer_id = str(uuid.uuid4())
    resp_decide = client.post(
        f"/api/v1/reviews/{review_id}/decide",
        json={
            "decision": "OVERRIDE",
            "final_verdict": "ELIGIBLE",
            "reason": "Officer physically inspected genuine registrar endorsement.",
            "officer_id": fake_officer_id,  # Spoofed identity
        },
        headers=fix["officer1_headers"],  # Authenticated as officer1
    )
    assert resp_decide.status_code == 201
    decision_data = resp_decide.json()

    # Must match authenticated user (officer1), NOT spoofed id
    assert decision_data["officer_id"] == str(fix["officer1"].id)
    assert decision_data["officer_id"] != fake_officer_id


def test_rule_and_evidence_immutability_during_review(client: TestClient, db_session, exhaustive_review_fixture):
    """Review decisions cannot mutate underlying Phase 9 evidence or Phase 11 rules."""
    fix = exhaustive_review_fixture
    sub_id = fix["submission"].id

    resp_gen = client.post(f"/api/v1/reviews/generate?submission_id={sub_id}", headers=fix["officer1_headers"])
    review_id = resp_gen.json()[0]["id"]

    client.post(
        f"/api/v1/reviews/{review_id}/decide",
        json={
            "decision": "OVERRIDE",
            "final_verdict": "ELIGIBLE",
            "reason": "Technical committee override following in-person verification.",
        },
        headers=fix["officer1_headers"],
    )

    db_session.expire_all()
    # Check Phase 9 Evidence record unchanged
    ev = db_session.get(Evidence, fix["ev3"].id)
    assert ev.status == EvidenceStatus.CONFLICTING
    assert ev.confidence == 0.60

    # Check Phase 11 CriterionEvaluation unchanged
    ce = db_session.get(CriterionEvaluation, fix["eval3"].id)
    assert ce.result == EvaluationResult.MANUAL_REVIEW

    # Check Phase 11 Rule configuration unchanged
    rule = db_session.get(CriterionRule, fix["c3"].id) or db_session.query(CriterionRule).filter_by(criterion_id=fix["c3"].id).first()
    assert rule.configuration == {"certificate_type": "ISO_9001"}


def test_multiple_review_items_support(client: TestClient, db_session, exhaustive_review_fixture):
    """Test creating granular review items within a review case."""
    fix = exhaustive_review_fixture
    sub_id = fix["submission"].id

    resp_gen = client.post(f"/api/v1/reviews/generate?submission_id={sub_id}", headers=fix["officer1_headers"])
    review_id = uuid.UUID(resp_gen.json()[0]["id"])

    # Add 2 items
    item1 = ReviewItem(
        review_case_id=review_id,
        criterion_id=fix["c3"].id,
        evidence_id=fix["ev3"].id,
        issue_type=ReviewIssueType.CONFLICTING_EVIDENCE,
        description="Validity date conflict on registrar stamp",
    )
    item2 = ReviewItem(
        review_case_id=review_id,
        criterion_id=fix["c3"].id,
        evidence_id=fix["ev3"].id,
        issue_type=ReviewIssueType.AMBIGUOUS_EVIDENCE,
        description="Issuing authority stamp blurred",
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    case = db_session.get(ReviewCase, review_id)
    assert len(case.items) == 2


def test_version_isolation_across_tender_amendments(client: TestClient, db_session, exhaustive_review_fixture):
    """Verify Version 1 review cannot be accessed through Version 2 relationships."""
    fix = exhaustive_review_fixture
    sub_id = fix["submission"].id

    resp_gen = client.post(f"/api/v1/reviews/generate?submission_id={sub_id}", headers=fix["officer1_headers"])
    review_id = resp_gen.json()[0]["id"]

    # Filter by v2 returns zero cases
    resp_v2 = client.get(f"/api/v1/reviews?tender_version_id={fix['v2'].id}", headers=fix["officer1_headers"])
    assert resp_v2.status_code == 200
    assert resp_v2.json()["total"] == 0

    # Filter by v1 returns the case
    resp_v1 = client.get(f"/api/v1/reviews?tender_version_id={fix['v1'].id}", headers=fix["officer1_headers"])
    assert resp_v1.status_code == 200
    assert resp_v1.json()["total"] == 1
    assert resp_v1.json()["items"][0]["id"] == review_id
