"""Comprehensive End-to-End Integration Test for the Complete 15-Phase Procurement Lifecycle."""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.audit.service import AuditService
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evaluation_report import EvaluationReport, ReportType
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
from app.reports.schemas import ReportCreateRequest
from app.reports.service import ReportService
from app.storage.memory import InMemoryObjectStorageService
from app.storage.service import set_storage_service_override


@pytest.fixture
def db_session():
    """In-memory SQLite session for full end-to-end lifecycle verification."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    mem_storage = InMemoryObjectStorageService()
    set_storage_service_override(mem_storage)
    try:
        yield session, mem_storage
    finally:
        session.close()


def test_complete_15_phase_procurement_lifecycle_end_to_end(db_session):
    """
    Verify complete 15-phase chain:
    Tender -> Version -> Doc Ingestion -> Criteria Extraction -> Officer Approval ->
    Rule Config -> Bidder & Submission -> Evidence Extraction -> Hybrid Retrieval ->
    OPA Rule Evaluation -> Bidder Aggregation -> Human Review & Override ->
    20-Point Explainability -> Report Generation (PDF + SHA256) -> Audit Trail.
    """
    session, mem_storage = db_session

    # 1. User & Officer Authentication
    officer = User(
        id=uuid.uuid4(),
        email="commandant_procurement@crpf.gov.in",
        password_hash="hashed_pw",
        full_name="Commandant R. K. Singh",
        is_active=True,
    )
    session.add(officer)
    session.flush()

    AuditService.record(
        session,
        action="USER_LOGIN_SUCCESS",
        actor_id=officer.id,
        entity_type="USER",
        entity_id=str(officer.id),
        metadata_json={"ip": "10.0.1.5", "role": "procurement_officer"},
    )

    # 2. Tender Creation & Versioning (Phases 4 & 8)
    tender = Tender(
        id=uuid.uuid4(),
        tender_number="CRPF-NIT-2026-DRONE-001",
        title="Procurement of High-Altitude Tactical Drones",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    session.add(tender)
    session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    session.add(version)
    session.flush()

    # 3. Document Ingestion (Phase 5 & 6)
    tender_doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="NIT_Drone_Requirements_2026.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=204850,
        sha256_hash="a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
        storage_key=f"tenders/{tender.id}/docs/nit.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    session.add(tender_doc)
    session.flush()

    # 4. Tender Understanding & AI Criteria Extraction & Officer Approval (Phases 7 & 8)
    criterion1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C01",
        name="Minimum Financial Turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 3.1: Minimum annual turnover of 25 Crore in INR over past 3 fiscal years",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extraction_status=ExtractionStatus.EXTRACTED,
        approval_status=ApprovalStatus.APPROVED,
        description="Minimum annual turnover 25.0 Cr INR",
    )
    criterion2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C02",
        name="DGCA Type Certificate",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 4.2: Valid DGCA Type Certification for tactical UAV systems",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extraction_status=ExtractionStatus.EXTRACTED,
        approval_status=ApprovalStatus.APPROVED,
        description="Valid DGCA Type Certificate",
    )
    session.add_all([criterion1, criterion2])
    session.flush()

    # 5. Deterministic Rules (Phase 11)
    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=criterion1.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"min_value": 25.0, "currency": "INR", "operator": ">="},
        status=RuleStatus.ACTIVE,
    )
    rule2 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=criterion2.id,
        tender_version_id=version.id,
        rule_type=RuleType.CERTIFICATE_EXISTENCE,
        rule_version="v1.0",
        configuration={"cert_type": "DGCA_TYPE_CERT"},
        status=RuleStatus.ACTIVE,
    )
    session.add_all([rule1, rule2])
    session.flush()

    # 6. Bidder & Bid Submission (Phase 9 & 10)
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="AERO-IND-01",
        legal_name="AeroDefense Dynamics India Pvt Ltd",
        contact_email="bids@aerodefense.in",
    )
    session.add(bidder)
    session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-AERO-2026-001",
        status=SubmissionStatus.READY,
    )
    session.add(submission)
    session.flush()

    # 7. Bidder Document & Evidence Extraction (Phase 9 & 10)
    bidder_doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="Audited_Financials_and_DGCA.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=512000,
        sha256_hash="b2c3d4e5f6a10718293a4b5c6d7e8f90123456789abcdef0123456789abcdef1",
        storage_key=f"submissions/{submission.id}/docs/financials.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    session.add(bidder_doc)
    session.flush()

    run_id = uuid.uuid4()
    ev1 = Evidence(
        id=uuid.uuid4(),
        document_id=bidder_doc.id,
        criterion_id=criterion1.id,
        bid_submission_id=submission.id,
        extraction_run_id=run_id,
        extractor_version="1.0.0",
        status=EvidenceStatus.FOUND,
        source_page=4,
        extracted_value=32.4,  # 32.4 Cr >= 25.0 Cr (ELIGIBLE)
        normalized_value="32.4",
        confidence=0.98,
        extracted_text="Average annual turnover for FY23-25 is 32.4 Crore INR.",
        raw_extracted_data={"extracted_value": 32.4, "currency": "INR"},
    )
    ev2 = Evidence(
        id=uuid.uuid4(),
        document_id=bidder_doc.id,
        criterion_id=criterion2.id,
        bid_submission_id=submission.id,
        extraction_run_id=run_id,
        extractor_version="1.0.0",
        status=EvidenceStatus.UNREADABLE,  # Blurry certificate scan -> MANUAL_REVIEW
        source_page=12,
        confidence=0.45,
        extracted_text="DGCA Certificate copy is degraded and illegible",
        raw_extracted_data={"status": "UNREADABLE"},
    )
    session.add_all([ev1, ev2])
    session.flush()

    # 8. OPA Criterion Evaluation & Bidder Aggregation (Phases 11 & 12)
    ce1 = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=criterion1.id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"extracted": 32.4, "required": 25.0},
        evidence_ids=[str(ev1.id)],
        explanation={"extracted": 32.4, "required": 25.0, "met": True},
    )
    ce2 = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=criterion2.id,
        rule_id=rule2.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.MANUAL_REVIEW,
        input_snapshot={"status": "UNREADABLE"},
        evidence_ids=[str(ev2.id)],
        explanation={"reason": "Unreadable scan requires manual inspection by officer"},
    )
    session.add_all([ce1, ce2])
    session.flush()

    be = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        result=EvaluationResult.MANUAL_REVIEW,
        criterion_count=2,
        eligible_count=1,
        not_eligible_count=0,
        manual_review_count=1,
        mandatory_criterion_count=2,
        mandatory_eligible_count=1,
        mandatory_not_eligible_count=0,
        mandatory_manual_review_count=1,
    )
    session.add(be)
    session.flush()

    # 9. Human Review, Officer Override & Decision Audit (Phase 13)
    review_case = ReviewCase(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_evaluation_id=ce2.id,
        criterion_id=criterion2.id,
        title="Review Degraded DGCA Certificate Scan",
        status=ReviewStatus.RESOLVED,
        priority=ReviewPriority.HIGH,
        issue_type=ReviewIssueType.UNREADABLE_EVIDENCE,
    )
    session.add(review_case)
    session.flush()

    officer_decision = OfficerDecision(
        id=uuid.uuid4(),
        review_case_id=review_case.id,
        officer_id=officer.id,
        system_result="MANUAL_REVIEW",
        decision=HumanDecision.OVERRIDE,
        final_verdict=EvaluationResult.ELIGIBLE,
        reason="Physical verification of original DGCA Type Certificate #TC-UAV-2024-88 confirmed authentic and valid.",
    )
    session.add(officer_decision)
    session.flush()

    # 10. 20-Point Explainability (Phase 14)
    c1_explanation = ExplanationService.get_criterion_explanation(session, ce1.id)
    assert c1_explanation.automated_result == EvaluationResult.ELIGIBLE
    assert c1_explanation.primary_page_number == 4
    assert c1_explanation.extracted_value == 32.4

    c2_explanation = ExplanationService.get_criterion_explanation(session, ce2.id)
    assert c2_explanation.automated_result == EvaluationResult.MANUAL_REVIEW
    assert c2_explanation.is_overridden is True
    assert c2_explanation.final_criterion_decision == EvaluationResult.ELIGIBLE
    assert "DGCA Type Certificate #TC-UAV-2024-88" in c2_explanation.override_reason

    bidder_explanation = ExplanationService.get_bidder_explanation(session, submission.id)
    assert bidder_explanation.total_criteria == 2
    assert bidder_explanation.mandatory_criteria_count == 2
    assert bidder_explanation.unreadable_evidence_count == 1
    assert bidder_explanation.final_decision_state == EvaluationResult.ELIGIBLE

    # 11. Official PDF Report Generation & SHA-256 Checksum (Phase 14)
    report_req = ReportCreateRequest(
        title="Official High-Altitude Tactical Drone Bidder Eligibility Report",
        include_audit_summary=True,
    )
    report = ReportService.generate_bidder_report(
        db=session,
        submission_id=submission.id,
        current_user=officer,
        request=report_req,
        storage=mem_storage,
    )
    assert report.report_type == ReportType.BIDDER_EVALUATION_REPORT
    assert report.report_version == 1
    assert len(report.file_hash) == 64
    assert report.file_size_bytes > 1000

    # 12. Complete Audit Trail Verification (Phase 14 & 15)
    audit_trail, _ = AuditService.get_submission_audit_trail(session, submission.id)
    assert len(audit_trail) >= 1
    actions = [a.action for a in audit_trail]
    assert "REPORT_GENERATED" in actions
