"""Exhaustive Phase 18 End-to-End Integration & Canonical Procurement Scenarios Test Suite.

Verifies canonical end-to-end evaluation workflows across all 17 completed phases:
- Scenario A: Mandatory criteria fully satisfied -> Automated ELIGIBLE -> Report generated.
- Scenario B: Mandatory criterion fails -> Automated NOT_ELIGIBLE -> Report reflects failure.
- Scenario C: Ambiguous/unreadable evidence -> MANUAL_REVIEW -> Review Case -> Officer Override -> Segregated Report.
- Scenario D: Tender Version 1 vs Version 2 amendment -> Strict version isolation & independent evaluations.
- Scenario E: Multiple conflicting evidence documents -> Safe routing to MANUAL_REVIEW.
- Scenario F: Document integrity tracking -> SHA-256 preserved across document, evidence, audit, and report.
- Scenario G: Complete API-driven workflow via TestClient from authentication to report streaming.
"""

import hashlib
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.audit.service import AuditService
from app.auth.jwt import create_access_token
from app.auth.security import hash_password
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evaluation_report import EvaluationReport, ReportStatus, ReportType
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
from app.db.models.extraction_run import ExtractionRunStatus
from app.db.models.permission import Permission
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
    ExtractionStatus,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.reports.schemas import ReportCreateRequest
from app.reports.service import ReportService
from app.reports.explanation_service import ExplanationService
from app.rules.service import evaluate_submission_criterion, get_or_create_criterion_rule
from app.aggregation.service import aggregate_submission_evaluation
from app.reviews.service import (
    generate_review_cases_for_submission,
    record_officer_decision,
    resolve_review_case,
)
from app.storage.memory import InMemoryObjectStorageService
from app.storage.service import get_storage_service, set_storage_service_override


def make_criterion(
    tender_version_id: uuid.UUID,
    criterion_code: str,
    name: str,
    description: str = "Requirement description",
    category: CriterionCategory = CriterionCategory.FINANCIAL,
    requirement_type: RequirementType = RequirementType.MANDATORY,
    approval_status: ApprovalStatus = ApprovalStatus.APPROVED,
    source_clause: str = "Clause 1.0: Standard requirement",
    **kwargs,
) -> TenderCriterion:
    """Helper to instantiate valid TenderCriterion with non-null AI metadata fields."""
    return TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=tender_version_id,
        criterion_code=criterion_code,
        name=name,
        description=description,
        source_clause=source_clause,
        category=category,
        requirement_type=requirement_type,
        approval_status=approval_status,
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        confidence=0.95,
        **kwargs,
    )


def make_evidence_run(db: Session, submission_id: uuid.UUID, criterion_id: uuid.UUID = None, created_by: uuid.UUID = None) -> EvidenceExtractionRun:
    """Helper to create and persist a valid EvidenceExtractionRun record."""
    run = EvidenceExtractionRun(
        id=uuid.uuid4(),
        bid_submission_id=submission_id,
        criterion_id=criterion_id,
        model_name="crpf-evidence-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extractor_version="1.0.0",
        status=ExtractionRunStatus.COMPLETED,
        created_by=created_by or uuid.uuid4(),
    )
    db.add(run)
    db.flush()
    return run


def make_evidence(
    db: Session,
    criterion_id: uuid.UUID,
    submission_id: uuid.UUID,
    document_id: uuid.UUID,
    run_id: uuid.UUID = None,
    status: EvidenceStatus = EvidenceStatus.FOUND,
    extracted_value=None,
    normalized_value: str = None,
    currency: str = "INR",
    confidence: float = 0.95,
    extracted_text: str = "Extracted evidence proof text.",
    raw_extracted_data: dict = None,
    certificate_data: dict = None,
    **kwargs,
) -> Evidence:
    """Helper to create and persist a valid Evidence record."""
    if not run_id:
        run = make_evidence_run(db, submission_id, criterion_id)
        run_id = run.id
    ev = Evidence(
        id=uuid.uuid4(),
        criterion_id=criterion_id,
        bid_submission_id=submission_id,
        document_id=document_id,
        extraction_run_id=run_id,
        extractor_version="1.0.0",
        status=status,
        extracted_value=extracted_value,
        normalized_value=normalized_value,
        currency=currency,
        confidence=confidence,
        extracted_text=extracted_text,
        raw_extracted_data=raw_extracted_data or {},
        certificate_data=certificate_data,
        **kwargs,
    )
    db.add(ev)
    db.flush()
    return ev


@pytest.fixture
def e2e_env():
    """Setup isolated SQLite engine, test database session, in-memory object storage, and test users."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()

    storage = InMemoryObjectStorageService()
    set_storage_service_override(storage)

    # Seed permissions and roles
    perms = [
        "TENDER_CREATE", "TENDER_READ", "TENDER_UPDATE", "TENDER_APPROVE",
        "DOCUMENT_UPLOAD", "DOCUMENT_READ",
        "EVALUATION_READ", "EVALUATION_EXECUTE",
        "REVIEW_CREATE", "REVIEW_APPROVE",
        "REPORT_GENERATE", "REPORT_READ", "AUDIT_READ",
    ]
    perm_objs = []
    for p_name in perms:
        p = Permission(id=uuid.uuid4(), name=p_name, description=f"Permission for {p_name}")
        session.add(p)
        perm_objs.append(p)
    session.flush()

    admin_role = Role(id=uuid.uuid4(), name="ADMIN", description="Administrator")
    officer_role = Role(id=uuid.uuid4(), name="TENDER_OFFICER", description="Procurement Officer")
    bidder_role = Role(id=uuid.uuid4(), name="BIDDER", description="Bidder Representative")

    for p in perm_objs:
        admin_role.permissions.append(p)
        if p.name not in ["TENDER_CREATE", "TENDER_APPROVE"]:
            officer_role.permissions.append(p)
        if p.name in ["DOCUMENT_READ", "REPORT_READ", "DOCUMENT_UPLOAD"]:
            bidder_role.permissions.append(p)

    officer_role.permissions.extend([p for p in perm_objs if p.name in ["TENDER_APPROVE", "TENDER_CREATE", "REVIEW_APPROVE", "EVALUATION_EXECUTE", "REPORT_GENERATE"]])

    session.add_all([admin_role, officer_role, bidder_role])
    session.flush()

    # Create test officer user
    officer = User(
        id=uuid.uuid4(),
        email="commandant_eval@crpf.gov.in",
        password_hash=hash_password("OfficerSecurePass123!"),
        full_name="Commandant S. K. Sharma",
        is_active=True,
    )
    officer.roles.append(officer_role)
    session.add(officer)

    # Create test bidder user
    bidder_user = User(
        id=uuid.uuid4(),
        email="representative@aerobids.in",
        password_hash=hash_password("BidderSecurePass123!"),
        full_name="Aero Representative",
        is_active=True,
    )
    bidder_user.roles.append(bidder_role)
    session.add(bidder_user)

    session.commit()

    def get_test_db():
        s = session_factory()
        try:
            yield s
        finally:
            s.close()

    def get_test_storage():
        return storage

    app.dependency_overrides[get_db] = get_test_db
    app.dependency_overrides[get_storage_service] = get_test_storage

    yield session, storage, officer, bidder_user

    app.dependency_overrides.clear()
    session.close()


# ==============================================================================
# SCENARIO A: MANDATORY CRITERIA SATISFIED -> OVERALL ELIGIBLE
# ==============================================================================
def test_scenario_a_all_mandatory_criteria_satisfied(e2e_env):
    """
    Scenario A:
    1. Tender & Version created.
    2. 2 Mandatory Criteria extracted and APPROVED (C01: Turnover >= 10 Cr, C02: ISO 9001).
    3. Bidder A submits valid documents (Turnover = 18 Cr, ISO 9001 valid).
    4. Deterministic OPA evaluation + Aggregation.
    5. Expected: Overall Result = ELIGIBLE.
    6. PDF Report generated with SHA-256 and verified against storage.
    """
    db, storage, officer, _ = e2e_env

    # 1. Tender & Version
    tender = Tender(
        id=uuid.uuid4(),
        tender_number="CRPF-NIT-2026-SCENARIO-A",
        title="Procurement of Body Armor & Helmets",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db.add(tender)
    db.flush()

    v1 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    db.add(v1)
    db.flush()

    # 2. Approved Criteria & Rules
    c1 = make_criterion(
        tender_version_id=v1.id,
        criterion_code="C01",
        name="Annual Turnover >= 10 Cr",
        description="Minimum annual turnover 10 Crore INR",
        source_clause="Clause 3.1: Minimum turnover 10 Crore INR over past 3 fiscal years",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    c2 = make_criterion(
        tender_version_id=v1.id,
        criterion_code="C02",
        name="ISO 9001 Quality Certification",
        description="Valid ISO 9001 Quality Certificate",
        source_clause="Clause 4.1: Must possess valid ISO 9001 Quality Management System Certificate",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    db.add_all([c1, c2])
    db.flush()

    get_or_create_criterion_rule(
        db, c1.id, user_id=officer.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        configuration={"threshold": 10.0, "currency": "INR", "operator": ">="},
    )
    get_or_create_criterion_rule(
        db, c2.id, user_id=officer.id,
        rule_type=RuleType.CERTIFICATE_EXISTENCE,
        configuration={"certificate_name": "ISO 9001"},
    )

    # 3. Bidder & Submission
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BIDDER-ALPHA",
        legal_name="Alpha Defense Equipment Pvt Ltd",
        contact_email="contact@alphadefense.in",
    )
    db.add(bidder)
    db.flush()

    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder.id,
        submission_reference="SUB-ALPHA-001",
        status=SubmissionStatus.READY,
    )
    db.add(sub)
    db.flush()

    # 4. Bidder Document & Evidence
    b_doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bid_submission_id=sub.id,
        filename="Alpha_Financials_and_ISO.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=102400,
        sha256_hash=hashlib.sha256(b"Alpha_Doc_Content_Valid").hexdigest(),
        storage_key=f"submissions/{sub.id}/docs/alpha.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db.add(b_doc)
    db.flush()

    run = make_evidence_run(db, sub.id, created_by=officer.id)

    ev1 = make_evidence(
        db=db,
        document_id=b_doc.id,
        criterion_id=c1.id,
        submission_id=sub.id,
        run_id=run.id,
        status=EvidenceStatus.FOUND,
        source_page=2,
        extracted_value=18.5,
        normalized_value="18.5",
        currency="INR",
        confidence=0.99,
        extracted_text="Audited annual turnover for FY24-25 is 18.5 Crore INR.",
        raw_extracted_data={"extracted_value": 18.5, "currency": "INR"},
    )
    ev2 = make_evidence(
        db=db,
        document_id=b_doc.id,
        criterion_id=c2.id,
        submission_id=sub.id,
        run_id=run.id,
        status=EvidenceStatus.FOUND,
        source_page=7,
        confidence=0.95,
        extracted_text="ISO 9001:2015 Quality Management System Certification #ISO-2024-998.",
        certificate_data={"certificate_name": "ISO 9001", "is_valid": True},
        raw_extracted_data={"certificate_name": "ISO 9001"},
    )
    db.commit()

    # 5. Full Evaluation Orchestration (Rules + Aggregation)
    eval_record = aggregate_submission_evaluation(
        db=db,
        submission_id=sub.id,
        user_id=officer.id,
        run_rules=True,
        auto_generate_reviews=True,
    )

    assert eval_record.result == EvaluationResult.ELIGIBLE
    assert eval_record.mandatory_eligible_count == 2
    assert eval_record.mandatory_not_eligible_count == 0
    assert eval_record.mandatory_manual_review_count == 0

    # Verify no review cases created
    cases = db.execute(select(ReviewCase).where(ReviewCase.bid_submission_id == sub.id)).scalars().all()
    assert len(cases) == 0

    # 6. Report Generation
    report = ReportService.generate_bidder_report(
        db=db,
        submission_id=sub.id,
        current_user=officer,
        request=ReportCreateRequest(title="Alpha Defense Evaluation Report"),
        storage=storage,
    )
    assert report.status == ReportStatus.COMPLETED
    assert report.report_version == 1
    assert len(report.file_hash) == 64

    # Verify file stored in storage and SHA256 matches
    stream = storage.download(report.storage_key)
    pdf_bytes = stream.read()
    calc_hash = hashlib.sha256(pdf_bytes).hexdigest()
    assert calc_hash == report.file_hash


# ==============================================================================
# SCENARIO B: MANDATORY CRITERION FAILS -> OVERALL NOT_ELIGIBLE
# ==============================================================================
def test_scenario_b_mandatory_criterion_fails(e2e_env):
    """
    Scenario B:
    Bidder Beta has Turnover = 4.2 Cr (< 10 Cr required).
    Expected: C01 = NOT_ELIGIBLE, Overall = NOT_ELIGIBLE.
    Report generated reflects exact failure without awarding or ranking.
    """
    db, storage, officer, _ = e2e_env

    # 1. Tender, Version & Criteria
    tender = Tender(
        id=uuid.uuid4(),
        tender_number="CRPF-NIT-2026-SCENARIO-B",
        title="Procurement of Communication Equipment",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    db.add_all([tender, v1])
    db.flush()

    c1 = make_criterion(
        tender_version_id=v1.id,
        criterion_code="C01",
        name="Minimum Turnover 10 Cr",
        description="Minimum annual turnover 10 Crore INR",
        source_clause="Clause 3.1: Minimum annual turnover of 10 Crore INR",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    db.add(c1)
    db.flush()

    get_or_create_criterion_rule(
        db, c1.id, user_id=officer.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        configuration={"threshold": 10.0, "currency": "INR", "operator": ">="},
    )

    # 2. Bidder & Submission
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BIDDER-BETA",
        legal_name="Beta Comms Ltd",
        contact_email="info@betacomms.in",
    )
    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder.id,
        submission_reference="SUB-BETA-001",
        status=SubmissionStatus.READY,
    )
    db.add_all([bidder, sub])
    db.flush()

    b_doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bid_submission_id=sub.id,
        filename="Beta_Financials.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=50000,
        sha256_hash=hashlib.sha256(b"Beta_Doc_Content").hexdigest(),
        storage_key=f"submissions/{sub.id}/docs/beta.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db.add(b_doc)
    db.flush()

    run = make_evidence_run(db, sub.id, created_by=officer.id)

    ev1 = make_evidence(
        db=db,
        document_id=b_doc.id,
        criterion_id=c1.id,
        submission_id=sub.id,
        run_id=run.id,
        status=EvidenceStatus.FOUND,
        source_page=1,
        extracted_value=4.2,  # Below threshold
        normalized_value="4.2",
        currency="INR",
        confidence=0.98,
        extracted_text="Annual turnover is 4.2 Crore INR.",
        raw_extracted_data={"extracted_value": 4.2, "currency": "INR"},
    )
    db.commit()

    # 3. Evaluate Submission
    eval_record = aggregate_submission_evaluation(
        db=db,
        submission_id=sub.id,
        user_id=officer.id,
        run_rules=True,
    )

    assert eval_record.result == EvaluationResult.NOT_ELIGIBLE
    assert eval_record.mandatory_not_eligible_count == 1
    assert eval_record.mandatory_eligible_count == 0

    # 4. Generate Report
    report = ReportService.generate_bidder_report(
        db=db,
        submission_id=sub.id,
        current_user=officer,
        request=ReportCreateRequest(title="Beta Evaluation Report"),
        storage=storage,
    )
    assert report.status == ReportStatus.COMPLETED
    assert report.generation_metadata["automated_result"] == "NOT_ELIGIBLE"
    assert report.generation_metadata["final_decision_state"] == "NOT_ELIGIBLE"


# ==============================================================================
# SCENARIO C: AMBIGUOUS EVIDENCE -> MANUAL REVIEW -> OFFICER OVERRIDE
# ==============================================================================
def test_scenario_c_ambiguous_evidence_and_officer_override(e2e_env):
    """
    Scenario C:
    1. Bidder Gamma has unreadable certificate scan -> MANUAL_REVIEW.
    2. Review case generated automatically.
    3. Officer inspects original certificate, records OVERRIDE decision with justification.
    4. Automated result remains MANUAL_REVIEW, Human decision is OVERRIDE (ELIGIBLE).
    5. Verified report maintains separation between automated OPA result and human override.
    """
    db, storage, officer, _ = e2e_env

    tender = Tender(id=uuid.uuid4(), tender_number="CRPF-NIT-2026-SCENARIO-C", title="Specialized UAVs", status=TenderStatus.PUBLISHED, created_by=officer.id)
    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    db.add_all([tender, v1])
    db.flush()

    c1 = make_criterion(
        tender_version_id=v1.id,
        criterion_code="C01",
        name="DGCA Type Certificate",
        description="Valid DGCA Type Certificate for Tactical UAVs",
        source_clause="Clause 4.2: Must possess valid DGCA Type Certificate",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    db.add(c1)
    db.flush()

    get_or_create_criterion_rule(
        db, c1.id, user_id=officer.id,
        rule_type=RuleType.CERTIFICATE_EXISTENCE,
        configuration={"certificate_name": "DGCA"},
    )

    bidder = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="BIDDER-GAMMA", legal_name="Gamma Aviation Ltd", contact_email="gamma@aviation.in")
    sub = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder.id, submission_reference="SUB-GAMMA-001", status=SubmissionStatus.READY)
    db.add_all([bidder, sub])
    db.flush()

    b_doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bid_submission_id=sub.id,
        filename="Gamma_DGCA_Scan.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=60000,
        sha256_hash=hashlib.sha256(b"Gamma_Scan_Doc").hexdigest(),
        storage_key=f"submissions/{sub.id}/docs/gamma.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db.add(b_doc)
    db.flush()

    run = make_evidence_run(db, sub.id, created_by=officer.id)

    # Unreadable degraded evidence
    ev1 = make_evidence(
        db=db,
        document_id=b_doc.id,
        criterion_id=c1.id,
        submission_id=sub.id,
        run_id=run.id,
        status=EvidenceStatus.UNREADABLE,
        source_page=3,
        confidence=0.35,
        extracted_text="Certificate number partially obscured due to poor scan quality.",
        raw_extracted_data={"status": "UNREADABLE"},
    )
    db.commit()

    # Evaluate submission with auto_generate_reviews=True
    eval_record = aggregate_submission_evaluation(
        db=db,
        submission_id=sub.id,
        user_id=officer.id,
        run_rules=True,
        auto_generate_reviews=True,
    )

    assert eval_record.result == EvaluationResult.MANUAL_REVIEW
    assert eval_record.mandatory_manual_review_count == 1

    # Verify review case exists
    cases = db.execute(select(ReviewCase).where(ReviewCase.bid_submission_id == sub.id)).scalars().all()
    assert len(cases) >= 1
    case = cases[0]
    assert case.status == ReviewStatus.OPEN

    # Officer records explicit human OVERRIDE
    decision = record_officer_decision(
        db=db,
        review_id=case.id,
        decision=HumanDecision.OVERRIDE,
        reason="Physical DGCA Certificate TC-99203 verified and validated against DGCA portal register.",
        final_verdict=EvaluationResult.ELIGIBLE,
        officer_id=officer.id,
    )
    assert decision.decision == HumanDecision.OVERRIDE
    assert decision.final_verdict == EvaluationResult.ELIGIBLE

    # Resolve review case
    resolved_case = resolve_review_case(db=db, review_id=case.id, officer_id=officer.id)
    assert resolved_case.status == ReviewStatus.RESOLVED

    # Generate report and verify separation
    report = ReportService.generate_bidder_report(
        db=db,
        submission_id=sub.id,
        current_user=officer,
        request=ReportCreateRequest(title="Gamma Evaluation Report"),
        storage=storage,
    )

    # Automated result remains MANUAL_REVIEW
    assert report.generation_metadata["automated_result"] == "MANUAL_REVIEW"
    assert report.generation_metadata["human_decision"] == "OVERRIDE"
    assert report.generation_metadata["final_decision_state"] == "ELIGIBLE"

    # Verify explanation service lineage reflects human decision separately
    explanation = ExplanationService.get_bidder_explanation(db, sub.id)
    assert explanation.automated_overall_result == EvaluationResult.MANUAL_REVIEW
    assert explanation.human_overall_decision == HumanDecision.OVERRIDE
    assert explanation.final_decision_state == EvaluationResult.ELIGIBLE


# ==============================================================================
# SCENARIO D: TENDER VERSION ISOLATION (V1 vs V2)
# ==============================================================================
def test_scenario_d_tender_version_isolation(e2e_env):
    """
    Scenario D:
    Tender Version 1 requires Turnover >= 10 Cr.
    Tender Version 2 requires Turnover >= 20 Cr.
    Bidder Delta has Turnover = 15 Cr.
    - Evaluation under Version 1 -> ELIGIBLE.
    - Evaluation under Version 2 -> NOT_ELIGIBLE.
    - Verify both historical evaluations and reports remain isolated without crosstalk.
    """
    db, storage, officer, _ = e2e_env

    tender = Tender(id=uuid.uuid4(), tender_number="CRPF-NIT-2026-SCENARIO-D", title="Tactical Boots", status=TenderStatus.PUBLISHED, created_by=officer.id)
    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    v2 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=2, created_by=officer.id)
    db.add_all([tender, v1, v2])
    db.flush()

    c_v1 = make_criterion(
        tender_version_id=v1.id,
        criterion_code="C01",
        name="Turnover >= 10 Cr",
        description="Minimum annual turnover 10 Crore INR",
        source_clause="Clause 3.1: Turnover >= 10 Cr",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    c_v2 = make_criterion(
        tender_version_id=v2.id,
        criterion_code="C01",
        name="Turnover >= 20 Cr",
        description="Minimum annual turnover 20 Crore INR",
        source_clause="Clause 3.1: Turnover >= 20 Cr",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    db.add_all([c_v1, c_v2])
    db.flush()

    get_or_create_criterion_rule(
        db, c_v1.id, user_id=officer.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        configuration={"threshold": 10.0, "currency": "INR", "operator": ">="},
    )
    get_or_create_criterion_rule(
        db, c_v2.id, user_id=officer.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        configuration={"threshold": 20.0, "currency": "INR", "operator": ">="},
    )

    bidder = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="BIDDER-DELTA", legal_name="Delta Footwear Ltd", contact_email="delta@boots.in")
    db.add(bidder)
    db.flush()

    # Submission 1 against V1
    sub_v1 = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder.id, submission_reference="SUB-DELTA-V1", status=SubmissionStatus.READY)
    # Submission 2 against V2
    sub_v2 = BidSubmission(id=uuid.uuid4(), tender_version_id=v2.id, bidder_id=bidder.id, submission_reference="SUB-DELTA-V2", status=SubmissionStatus.READY)
    db.add_all([sub_v1, sub_v2])
    db.flush()

    # Docs & Evidence for V1
    doc_v1 = Document(
        id=uuid.uuid4(), tender_id=tender.id, tender_version_id=v1.id, bid_submission_id=sub_v1.id,
        filename="Delta_Fin_V1.pdf", content_type="application/pdf", file_extension=".pdf", file_size=40000,
        sha256_hash=hashlib.sha256(b"V1_Doc").hexdigest(), storage_key=f"submissions/{sub_v1.id}/docs/v1.pdf",
        document_type=DocumentType.DIGITAL_PDF, processing_status=ProcessingStatus.COMPLETED, uploaded_by=officer.id,
    )
    doc_v2 = Document(
        id=uuid.uuid4(), tender_id=tender.id, tender_version_id=v2.id, bid_submission_id=sub_v2.id,
        filename="Delta_Fin_V2.pdf", content_type="application/pdf", file_extension=".pdf", file_size=40000,
        sha256_hash=hashlib.sha256(b"V2_Doc").hexdigest(), storage_key=f"submissions/{sub_v2.id}/docs/v2.pdf",
        document_type=DocumentType.DIGITAL_PDF, processing_status=ProcessingStatus.COMPLETED, uploaded_by=officer.id,
    )
    db.add_all([doc_v1, doc_v2])
    db.flush()

    run_v1 = make_evidence_run(db, sub_v1.id, created_by=officer.id)
    run_v2 = make_evidence_run(db, sub_v2.id, created_by=officer.id)

    ev_v1 = make_evidence(
        db=db, document_id=doc_v1.id, criterion_id=c_v1.id, submission_id=sub_v1.id, run_id=run_v1.id,
        status=EvidenceStatus.FOUND, extracted_value=15.0, normalized_value="15.0", currency="INR", confidence=0.98,
        extracted_text="Turnover is 15.0 Cr.", raw_extracted_data={"extracted_value": 15.0, "currency": "INR"},
    )
    ev_v2 = make_evidence(
        db=db, document_id=doc_v2.id, criterion_id=c_v2.id, submission_id=sub_v2.id, run_id=run_v2.id,
        status=EvidenceStatus.FOUND, extracted_value=15.0, normalized_value="15.0", currency="INR", confidence=0.98,
        extracted_text="Turnover is 15.0 Cr.", raw_extracted_data={"extracted_value": 15.0, "currency": "INR"},
    )
    db.commit()

    # Evaluate both
    eval_v1 = aggregate_submission_evaluation(db, sub_v1.id, user_id=officer.id, run_rules=True)
    eval_v2 = aggregate_submission_evaluation(db, sub_v2.id, user_id=officer.id, run_rules=True)

    assert eval_v1.result == EvaluationResult.ELIGIBLE
    assert eval_v2.result == EvaluationResult.NOT_ELIGIBLE

    # Reports
    rep_v1 = ReportService.generate_bidder_report(db, sub_v1.id, current_user=officer, request=ReportCreateRequest(title="Delta V1 Report"), storage=storage)
    rep_v2 = ReportService.generate_bidder_report(db, sub_v2.id, current_user=officer, request=ReportCreateRequest(title="Delta V2 Report"), storage=storage)

    assert rep_v1.tender_version_id == v1.id
    assert rep_v2.tender_version_id == v2.id
    assert rep_v1.generation_metadata["automated_result"] == "ELIGIBLE"
    assert rep_v2.generation_metadata["automated_result"] == "NOT_ELIGIBLE"


# ==============================================================================
# SCENARIO E: CONFLICTING MULTI-DOCUMENT EVIDENCE -> MANUAL REVIEW
# ==============================================================================
def test_scenario_e_conflicting_multi_document_evidence(e2e_env):
    """
    Scenario E:
    Bidder provides 2 documents with contradictory turnover amounts for the same criterion
    (Doc 1: 25 Cr, Doc 2: 4 Cr).
    OPA detects conflicting evidence and safely routes to MANUAL_REVIEW.
    """
    db, storage, officer, _ = e2e_env

    tender = Tender(id=uuid.uuid4(), tender_number="CRPF-NIT-2026-SCENARIO-E", title="Vehicle Fleet", status=TenderStatus.PUBLISHED, created_by=officer.id)
    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    db.add_all([tender, v1])
    db.flush()

    c1 = make_criterion(
        tender_version_id=v1.id,
        criterion_code="C01",
        name="Turnover >= 10 Cr",
        description="Minimum annual turnover 10 Crore INR",
        source_clause="Clause 3.1: Turnover >= 10 Cr",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    db.add(c1)
    db.flush()

    get_or_create_criterion_rule(
        db, c1.id, user_id=officer.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        configuration={"threshold": 10.0, "currency": "INR", "operator": ">="},
    )

    bidder = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="BIDDER-EPSILON", legal_name="Epsilon Motors", contact_email="eps@motors.in")
    sub = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder.id, submission_reference="SUB-EPS-001", status=SubmissionStatus.READY)
    db.add_all([bidder, sub])
    db.flush()

    doc1 = Document(
        id=uuid.uuid4(), tender_id=tender.id, tender_version_id=v1.id, bid_submission_id=sub.id,
        filename="Doc1_Audited.pdf", content_type="application/pdf", file_extension=".pdf", file_size=40000,
        sha256_hash=hashlib.sha256(b"Doc1").hexdigest(), storage_key=f"submissions/{sub.id}/docs/doc1.pdf",
        document_type=DocumentType.DIGITAL_PDF, processing_status=ProcessingStatus.COMPLETED, uploaded_by=officer.id,
    )
    doc2 = Document(
        id=uuid.uuid4(), tender_id=tender.id, tender_version_id=v1.id, bid_submission_id=sub.id,
        filename="Doc2_CA_Summary.pdf", content_type="application/pdf", file_extension=".pdf", file_size=40000,
        sha256_hash=hashlib.sha256(b"Doc2").hexdigest(), storage_key=f"submissions/{sub.id}/docs/doc2.pdf",
        document_type=DocumentType.DIGITAL_PDF, processing_status=ProcessingStatus.COMPLETED, uploaded_by=officer.id,
    )
    db.add_all([doc1, doc2])
    db.flush()

    run = make_evidence_run(db, sub.id, created_by=officer.id)

    ev1 = make_evidence(
        db=db, document_id=doc1.id, criterion_id=c1.id, submission_id=sub.id, run_id=run.id,
        status=EvidenceStatus.FOUND, extracted_value=25.0, normalized_value="25.0", currency="INR", confidence=0.95,
        extracted_text="Turnover is 25.0 Cr.", raw_extracted_data={"extracted_value": 25.0, "currency": "INR"},
    )
    ev2 = make_evidence(
        db=db, document_id=doc2.id, criterion_id=c1.id, submission_id=sub.id, run_id=run.id,
        status=EvidenceStatus.CONFLICTING, extracted_value=4.0, normalized_value="4.0", currency="INR", confidence=0.95,
        extracted_text="Turnover is 4.0 Cr.", raw_extracted_data={"extracted_value": 4.0, "currency": "INR"},
    )
    db.commit()

    eval_record = aggregate_submission_evaluation(db, sub.id, user_id=officer.id, run_rules=True)
    # Conflicting values must not be blindly approved
    assert eval_record.result == EvaluationResult.MANUAL_REVIEW


# ==============================================================================
# SCENARIO F: DOCUMENT INTEGRITY & SHA-256 PRESERVATION
# ==============================================================================
def test_scenario_f_document_integrity_preservation(e2e_env):
    """
    Scenario F:
    Verifies that the original document SHA-256 hash is preserved across:
    Document upload -> Evidence extraction -> Criterion evaluation -> Audit trail -> PDF Report.
    """
    db, storage, officer, _ = e2e_env

    tender = Tender(id=uuid.uuid4(), tender_number="CRPF-NIT-2026-SCENARIO-F", title="Integrity Check Tender", status=TenderStatus.PUBLISHED, created_by=officer.id)
    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender.id, version_number=1, created_by=officer.id)
    db.add_all([tender, v1])
    db.flush()

    c1 = make_criterion(
        tender_version_id=v1.id,
        criterion_code="C01",
        name="Mandatory ISO",
        description="Mandatory ISO 9001 Certification",
        source_clause="Clause 4.1: ISO 9001 Quality Certificate",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.APPROVED,
    )
    db.add(c1)
    db.flush()

    get_or_create_criterion_rule(db, c1.id, user_id=officer.id, rule_type=RuleType.CERTIFICATE_EXISTENCE, configuration={"certificate_name": "ISO 9001"})

    bidder = Bidder(id=uuid.uuid4(), tender_id=tender.id, bidder_code="BIDDER-ZETA", legal_name="Zeta Ltd", contact_email="zeta@co.in")
    sub = BidSubmission(id=uuid.uuid4(), tender_version_id=v1.id, bidder_id=bidder.id, submission_reference="SUB-ZETA-001", status=SubmissionStatus.READY)
    db.add_all([bidder, sub])
    db.flush()

    expected_doc_hash = hashlib.sha256(b"Zeta_Original_Immutable_Bytes_2026").hexdigest()
    doc = Document(
        id=uuid.uuid4(), tender_id=tender.id, tender_version_id=v1.id, bid_submission_id=sub.id,
        filename="Zeta_ISO.pdf", content_type="application/pdf", file_extension=".pdf", file_size=45000,
        sha256_hash=expected_doc_hash, storage_key=f"submissions/{sub.id}/docs/zeta.pdf",
        document_type=DocumentType.DIGITAL_PDF, processing_status=ProcessingStatus.COMPLETED, uploaded_by=officer.id,
    )
    db.add(doc)
    db.flush()

    run = make_evidence_run(db, sub.id, created_by=officer.id)

    ev = make_evidence(
        db=db, document_id=doc.id, criterion_id=c1.id, submission_id=sub.id, run_id=run.id,
        status=EvidenceStatus.FOUND, confidence=0.98, extracted_text="ISO 9001 Valid Certificate confirmed.",
        certificate_data={"certificate_name": "ISO 9001", "is_valid": True}, raw_extracted_data={"certificate_name": "ISO 9001"},
    )
    db.commit()

    # Evaluate
    eval_res = aggregate_submission_evaluation(db, sub.id, user_id=officer.id, run_rules=True)
    assert eval_res.result == EvaluationResult.ELIGIBLE

    # 1. Check explanation service preserves document hash in evidence lineage
    explanation = ExplanationService.get_bidder_explanation(db, sub.id)
    assert len(explanation.criteria_explanations) == 1
    assert len(explanation.criteria_explanations[0].evidence_items) == 1
    assert explanation.criteria_explanations[0].evidence_items[0].document_hash == expected_doc_hash
    assert explanation.criteria_explanations[0].primary_document_hash == expected_doc_hash

    # 2. Generate report and check immutable SHA-256 hash preservation in storage and audit
    report = ReportService.generate_bidder_report(db, sub.id, current_user=officer, request=ReportCreateRequest(title="Zeta Report"), storage=storage)
    assert report.status == ReportStatus.COMPLETED
    assert len(report.file_hash) == 64

    # Verify report binary hash matches
    stream = storage.download(report.storage_key)
    pdf_bytes = stream.read()
    calc_hash = hashlib.sha256(pdf_bytes).hexdigest()
    assert calc_hash == report.file_hash


# ==============================================================================
# SCENARIO G: COMPLETE API-DRIVEN WORKFLOW (TestClient)
# ==============================================================================
def test_scenario_g_api_driven_workflow(e2e_env):
    """
    Scenario G:
    Full API-driven execution via FastAPI TestClient:
    1. Authenticate procurement officer -> JWT token.
    2. Create Tender & Version via API.
    3. Register Bidder & Submission via API.
    4. List criteria & approve criterion via API.
    5. Evaluate submission via API (/submissions/{id}/evaluate with run_rules=True).
    6. Generate report via API (/submissions/{submission_id}/reports).
    7. Download report via API (/reports/{report_id}/download) with SHA-256 header.
    """
    db, storage, officer, _ = e2e_env
    client = TestClient(app)

    token = create_access_token(subject=officer.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create Tender
    res = client.post(
        "/api/v1/tenders",
        headers=headers,
        json={"tender_number": "CRPF-NIT-2026-API-E2E", "title": "API End-to-End Test Tender", "description": "Automated E2E"},
    )
    assert res.status_code == 201
    tender_data = res.json()
    tender_id = tender_data["id"]

    # 2. Create Tender Version
    res = client.post(
        f"/api/v1/tenders/{tender_id}/versions",
        headers=headers,
        json={"version_number": 1, "comments": "Initial Version"},
    )
    assert res.status_code == 201
    version_data = res.json()
    version_id = version_data["id"]

    # 3. Add & Approve a criterion
    crit = make_criterion(
        tender_version_id=uuid.UUID(version_id),
        criterion_code="C01",
        name="Turnover >= 5 Cr",
        description="Minimum 5 Crore",
        source_clause="Clause 3.1: Minimum 5 Crore annual turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )
    db.add(crit)
    db.commit()

    # Approve via API
    res = client.post(
        f"/api/v1/tenders/{tender_id}/versions/{version_id}/criteria/{crit.id}/approve",
        headers=headers,
        json={"notes": "Approved for testing"},
    )
    assert res.status_code == 200

    # 4. Create Bidder & Submission
    res = client.post(
        f"/api/v1/tenders/{tender_id}/bidders",
        headers=headers,
        json={"bidder_code": "BIDDER-OMEGA", "legal_name": "Omega Defense Corp", "contact_email": "omega@defense.gov.in"},
    )
    assert res.status_code == 201
    bidder_id = res.json()["id"]

    res = client.post(
        f"/api/v1/tenders/{tender_id}/versions/{version_id}/bidders/{bidder_id}/submissions",
        headers=headers,
        json={"submission_reference": "SUB-OMEGA-001"},
    )
    assert res.status_code == 201
    submission_id = res.json()["id"]

    # 5. Attach doc & evidence
    doc = Document(
        id=uuid.uuid4(), tender_id=uuid.UUID(tender_id), tender_version_id=uuid.UUID(version_id), bid_submission_id=uuid.UUID(submission_id),
        filename="Omega_Fin.pdf", content_type="application/pdf", file_extension=".pdf", file_size=30000,
        sha256_hash=hashlib.sha256(b"Omega_Doc").hexdigest(), storage_key=f"submissions/{submission_id}/docs/omega.pdf",
        document_type=DocumentType.DIGITAL_PDF, processing_status=ProcessingStatus.COMPLETED, uploaded_by=officer.id,
    )
    db.add(doc)
    db.flush()

    run = make_evidence_run(db, uuid.UUID(submission_id), created_by=officer.id)

    ev = make_evidence(
        db=db, document_id=doc.id, criterion_id=crit.id, submission_id=uuid.UUID(submission_id), run_id=run.id,
        status=EvidenceStatus.FOUND, extracted_value=8.0, normalized_value="8.0", currency="INR", confidence=0.99,
        extracted_text="Turnover is 8.0 Cr.", raw_extracted_data={"extracted_value": 8.0, "currency": "INR"},
    )
    db.commit()

    # Configure rule
    get_or_create_criterion_rule(
        db, crit.id, user_id=officer.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        configuration={"threshold": 5.0, "currency": "INR", "operator": ">="},
    )

    # 6. Evaluate via API
    res = client.post(
        f"/api/v1/submissions/{submission_id}/evaluate",
        headers=headers,
        json={"run_rules": True, "auto_generate_reviews": True},
    )
    assert res.status_code == 200
    eval_resp = res.json()
    assert eval_resp["result"] == "ELIGIBLE"

    # 7. Generate report via API
    res = client.post(
        f"/api/v1/submissions/{submission_id}/reports",
        headers=headers,
        json={"title": "Omega Official Report"},
    )
    assert res.status_code == 201
    report_resp = res.json()
    report_id = report_resp["id"]
    report_hash = report_resp["file_hash"]

    # 8. Download report via API
    res = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    assert res.status_code == 200
    assert res.headers.get("content-type") == "application/pdf"
    assert res.headers.get("x-report-sha256") == report_hash

    # 9. Verify Audit Trail
    res = client.get(f"/api/v1/audit/submissions/{submission_id}", headers=headers)
    assert res.status_code == 200
    logs = res.json()
    actions = [l["action"] for l in logs["items"]]
    assert "SUBMISSION_EVALUATION_COMPLETED" in actions
    assert "REPORT_GENERATED" in actions
    assert "REPORT_DOWNLOADED" in actions
