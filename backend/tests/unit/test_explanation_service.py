"""Unit tests for ExplanationService in Phase 14."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.db.base import Base
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.review_case import (
    HumanDecision,
    OfficerDecision,
    ReviewCase,
    ReviewIssueType,
    ReviewPriority,
    ReviewStatus,
)
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.reports.explanation_service import ExplanationService


@pytest.fixture
def db_session():
    """In-memory SQLite session for testing explanation service."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def test_explanation_service_criterion_and_bidder_full_provenance(db_session: Session):
    """Test full 20-point criterion and aggregated bidder explanation retrieval."""
    # 1. User / Officer
    officer = User(
        id=uuid.uuid4(),
        email="officer@crpf.gov.in",
        password_hash="hash",
        full_name="Procurement Officer A",
        is_active=True,
    )

    db_session.add(officer)

    # 2. Tender & Version
    tender = Tender(
        id=uuid.uuid4(),
        tender_number="CRPF-T-2026-999",
        title="Procurement of Tactical Radios",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    db_session.add(version)

    # 3. Criterion
    criterion = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C01",
        name="Experience in Military Radio Deployments",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 4.1: Experience requirement for radios",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extraction_status=ExtractionStatus.EXTRACTED,
        approval_status=ApprovalStatus.APPROVED,
        description="Minimum 3 completed military radio deployment projects",
    )
    db_session.add(criterion)

    # 4. Criterion Rule
    rule = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=criterion.id,
        tender_version_id=version.id,
        rule_type=RuleType.EXPERIENCE_COUNT,
        rule_version="v1.0",
        configuration={"min_count": 3},
        status=RuleStatus.ACTIVE,
    )
    db_session.add(rule)



    # 5. Bidder & Submission
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="WAVE01",
        legal_name="Tactical Wave Ltd",
        contact_email="bidder@wave.com",
    )
    db_session.add(bidder)

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-001",
        status=SubmissionStatus.READY,
    )
    db_session.add(submission)



    # 6. Document & Evidence
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="Past_Experience_Certificates.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="f" * 64,
        storage_key="docs/wave/past_exp.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()


    evidence = Evidence(
        id=uuid.uuid4(),
        document_id=doc.id,
        criterion_id=criterion.id,
        bid_submission_id=submission.id,
        extraction_run_id=uuid.uuid4(),
        extractor_version="1.0.0",
        status=EvidenceStatus.FOUND,
        source_page=2,
        extracted_value=2,  # Extracted 2 projects, needed 3
        normalized_value="2",
        confidence=0.95,
        extracted_text="Completed 2 tactical radio deployment projects with state police",
        raw_extracted_data={"extracted_value": 2, "normalized_value": 2},
    )
    db_session.add(evidence)

    # 7. Criterion Evaluation (Automated NOT_ELIGIBLE)
    ce = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=criterion.id,
        rule_id=rule.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.NOT_ELIGIBLE,
        input_snapshot={"extracted": 2, "required": 3},
        evidence_ids=[str(evidence.id)],
        explanation={"extracted": 2, "required": 3, "met": False},
    )
    db_session.add(ce)

    # 8. Overall Bidder Evaluation
    be = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        result=EvaluationResult.NOT_ELIGIBLE,
        criterion_count=1,
        eligible_count=0,
        not_eligible_count=1,
        manual_review_count=0,
        mandatory_criterion_count=1,
        mandatory_eligible_count=0,
        mandatory_not_eligible_count=1,
        mandatory_manual_review_count=0,
    )
    db_session.add(be)

    # 9. Review Case & Officer Override
    rc = ReviewCase(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=criterion.id,
        criterion_evaluation_id=ce.id,
        status=ReviewStatus.RESOLVED,
        priority=ReviewPriority.HIGH,
        issue_type=ReviewIssueType.OFFICER_FLAGGED,
        title="Experience Shortfall Review",
    )
    db_session.add(rc)

    decision = OfficerDecision(
        id=uuid.uuid4(),
        review_case_id=rc.id,
        criterion_id=criterion.id,
        criterion_evaluation_id=ce.id,
        decision=HumanDecision.OVERRIDE,
        system_result=EvaluationResult.NOT_ELIGIBLE,
        final_verdict=EvaluationResult.ELIGIBLE,
        reason="Vendor submitted supplementary annexure proving 2 additional military contracts in FY22.",
        officer_id=officer.id,
    )
    db_session.add(decision)
    db_session.commit()

    # Test Criterion Explanation
    crit_expl = ExplanationService.get_criterion_explanation(db_session, ce.id)
    assert crit_expl.requirement_name == "Experience in Military Radio Deployments"
    assert crit_expl.automated_result == EvaluationResult.NOT_ELIGIBLE
    assert crit_expl.human_decision == HumanDecision.OVERRIDE
    assert crit_expl.is_overridden is True
    assert "supplementary annexure" in crit_expl.override_reason
    assert crit_expl.final_criterion_decision == EvaluationResult.ELIGIBLE
    assert crit_expl.primary_document_name == "Past_Experience_Certificates.pdf"
    assert crit_expl.primary_page_number == 2

    # Test Bidder Explanation
    bidder_expl = ExplanationService.get_bidder_explanation(db_session, submission.id)
    assert bidder_expl.bidder_name == "Tactical Wave Ltd"
    assert bidder_expl.automated_overall_result == EvaluationResult.NOT_ELIGIBLE
    assert bidder_expl.human_overall_decision == HumanDecision.OVERRIDE
    assert bidder_expl.final_decision_state == EvaluationResult.ELIGIBLE
    assert len(bidder_expl.criteria_explanations) == 1
