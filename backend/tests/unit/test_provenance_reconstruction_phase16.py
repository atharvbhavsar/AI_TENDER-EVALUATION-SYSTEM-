"""Unit tests for Phase 16 Provenance and Lineage Reconstruction."""

import hashlib
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.audit.provenance import ProvenanceService
from app.audit.service import AuditService
from app.db.base import Base
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleType
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
from app.db.models.review_case import HumanDecision, OfficerDecision, ReviewCase, ReviewPriority, ReviewStatus
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import CriterionCategory, RequirementType, TenderCriterion
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User


@pytest.fixture
def db_session() -> Session:
    """In-memory SQLite session fixture for provenance tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_reconstruct_submission_provenance_full_lineage(db_session: Session):
    """Verify full end-to-end provenance reconstruction from Tender down to Officer Decision."""
    # 1. User & Officer
    officer = User(
        id=uuid.uuid4(),
        email="eval_officer@crpf.gov.in",
        password_hash="hash",
        full_name="Commandant Officer",
    )
    db_session.add(officer)

    # 2. Tender & Version
    tender = Tender(
        id=uuid.uuid4(),
        tender_number="CRPF/2026/PROV/001",
        title="Tactical Drone Procurement",
        created_by=officer.id,
        status=TenderStatus.PUBLISHED,
    )
    db_session.add(tender)

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    db_session.add(version)

    # 3. Criterion & Rule
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CRIT-TURNOVER",
        name="Minimum Annual Turnover",
        description="Audited minimum annual turnover of 10 Crore",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        mandatory=True,
        operator=">=",
        threshold_value=10.0,
        unit="CRORE",
        currency="INR",
        source_clause="Financial Thresholds",
        source_page=12,
        source_section="4.1.2",
        source_block_id="blk-99",
        model_name="mock-llm",
        model_version="1.0",
        prompt_version="criterion_extraction_v1",
    )
    db_session.add(crit)

    rule = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="1.0.0",
        template_version="1.0.0",
        rego_policy_reference="crpf.turnover.v1",
        configuration={},
    )
    db_session.add(rule)

    # 4. Bidder & Submission
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BID-001",
        legal_name="AeroDefense India Ltd",
        contact_email="contact@aerodefense.in",
    )
    db_session.add(bidder)

    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-2026-001",
        status=SubmissionStatus.READY,
    )
    db_session.add(sub)

    # 5. Document & Evidence
    doc_hash = hashlib.sha256(b"Financial Audit 2025").hexdigest()
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=sub.id,
        filename="Audited_Accounts_2025.pdf",
        content_type="application/pdf",
        file_extension="pdf",
        file_size=2048,
        sha256_hash=doc_hash,
        storage_key=f"submissions/{sub.id}/doc.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)

    run = EvidenceExtractionRun(
        id=uuid.uuid4(),
        bid_submission_id=sub.id,
        extractor_version="1.0.0",
        model_name="mock-extractor",
        model_version="1.0",
        prompt_version="evidence_extraction_v1",
        created_by=officer.id,
    )
    db_session.add(run)

    ev = Evidence(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        bid_submission_id=sub.id,
        document_id=doc.id,
        extraction_run_id=run.id,
        evidence_type="DOCUMENT",
        extracted_text="Average annual turnover is Rs 14.50 Crore.",
        extracted_value=14.5,
        normalized_value="14.50 CRORE INR",
        unit="CRORE",
        currency="INR",
        source_page=5,
        source_block_id="tbl-row-3",
        bbox=[100.0, 200.0, 500.0, 250.0],
        status=EvidenceStatus.FOUND,
        confidence=0.98,
        extractor_version="1.0.0",
    )
    db_session.add(ev)

    # 6. Criterion Evaluation & Overall Evaluation
    eval_record = CriterionEvaluation(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        tender_version_id=version.id,
        rule_id=rule.id,
        rule_version="1.0.0",
        policy_version="crpf.turnover.v1",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"value": 14.5, "threshold": 10.0},
        evidence_ids=[str(ev.id)],
        explanation={"reason": "Turnover ₹14.5 Cr exceeds required ₹10.0 Cr"},
    )
    db_session.add(eval_record)

    overall_eval = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        result=EvaluationResult.ELIGIBLE,
        criterion_count=1,
        eligible_count=1,
        not_eligible_count=0,
        manual_review_count=0,
        mandatory_criterion_count=1,
        mandatory_eligible_count=1,
    )
    db_session.add(overall_eval)

    # 7. Human Review Case & Officer Decision
    rev_case = ReviewCase(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        criterion_id=crit.id,
        status=ReviewStatus.RESOLVED,
        priority=ReviewPriority.LOW,
        title="Review financial audit certificate",
    )
    db_session.add(rev_case)

    decision = OfficerDecision(
        id=uuid.uuid4(),
        review_case_id=rev_case.id,
        criterion_id=crit.id,
        decision=HumanDecision.CONFIRM,
        system_result=EvaluationResult.ELIGIBLE,
        final_verdict=EvaluationResult.ELIGIBLE,
        reason="Verified against original chartered accountant seal on page 5.",
        officer_id=officer.id,
    )
    db_session.add(decision)

    # 8. Record an audit log
    AuditService.record(
        db_session,
        action="BIDDER_EVALUATED",
        entity_type="BID_SUBMISSION",
        entity_id=str(sub.id),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
    )
    db_session.commit()

    # Reconstruct provenance
    prov = ProvenanceService.reconstruct_submission_provenance(db_session, sub.id)

    assert prov.submission_id == sub.id
    assert prov.submission_number == "SUB-2026-001"
    assert prov.tender_title == "Tactical Drone Procurement"
    assert prov.tender_version_number == 1
    assert prov.bidder_name == "AeroDefense India Ltd"
    assert prov.overall_evaluation_result == "ELIGIBLE"
    assert prov.audit_events_count >= 1

    # Check Document
    assert len(prov.documents) == 1
    assert prov.documents[0].filename == "Audited_Accounts_2025.pdf"
    assert prov.documents[0].sha256_hash == doc_hash

    # Check Criteria & Evidence
    assert len(prov.criteria) == 1
    c = prov.criteria[0]
    assert c.code == "CRIT-TURNOVER"
    assert c.threshold_value == 10.0
    assert c.evaluation_result == "ELIGIBLE"
    assert len(c.evidence_items) == 1
    e = c.evidence_items[0]
    assert e.extracted_value == 14.5
    assert e.source_page == 5
    assert e.document_filename == "Audited_Accounts_2025.pdf"

    # Check Human Decisions
    assert len(prov.human_decisions) == 1
    d = prov.human_decisions[0]
    assert d.decision == "CONFIRM"
    assert d.officer_id == officer.id
    assert "chartered accountant" in d.reason
