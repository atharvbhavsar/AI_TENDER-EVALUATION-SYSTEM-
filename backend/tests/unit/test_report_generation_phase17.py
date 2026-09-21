"""Comprehensive Unit Tests for Phase 17 - Report Generation System."""

import hashlib
import io
import re
import uuid
import pypdf
import pytest
from app.core.exceptions import ConflictException, NotFoundException
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.evaluation_report import EvaluationReport, ReportStatus, ReportType
from app.db.models.review_case import HumanDecision
from app.reports.pdf_generator import PDFReportGenerator
from app.reports.schemas import (
    BidderExplanationResponse,
    CriterionExplanationResponse,
    EvidenceProvenanceItem,
    ReportCreateRequest,
)
from app.reports.service import ReportService, sanitize_filename


@pytest.fixture
def sample_bidder_explanation() -> BidderExplanationResponse:
    """Fixture providing complete data structure for all 7 report sections (A-G)."""
    cid1 = uuid.uuid4()
    ceid1 = uuid.uuid4()
    sub_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    crit1 = CriterionExplanationResponse(
        criterion_evaluation_id=ceid1,
        criterion_id=cid1,
        requirement_name="Annual Financial Turnover",
        category="FINANCIAL",
        requirement_type="MANDATORY",
        source_clause="Clause 3.2.1: Bidder must have minimum average turnover of Rs 50 Crores over last 3 audited financial years.",
        rule_type="NUMERIC_THRESHOLD",
        rule_version="v2.1",
        rule_config={"min_value": 50.0, "currency": "INR"},
        evidence_items=[
            EvidenceProvenanceItem(
                evidence_id=uuid.uuid4(),
                document_id=doc_id,
                document_name="Audited_Balance_Sheet_2023_2025.pdf",
                document_hash="3f79bb7b435b05321651daefd374cdc681dc06faa65e374e38337b88ca1453f0",
                page_number=12,
                block_id="blk-99",
                table_reference="Table 4: Financial Summary",
                bbox=[50, 100, 450, 300],
                extracted_value="62.5 Crore INR",
                normalized_value=62.5,
                evidence_status="FOUND",
                confidence_score=0.99,
                source_clause_quote="Average turnover for FY 2023-2025 is Rs. 62.50 Cr.",
            )
        ],
        primary_document_id=doc_id,
        primary_document_name="Audited_Balance_Sheet_2023_2025.pdf",
        primary_document_hash="3f79bb7b435b05321651daefd374cdc681dc06faa65e374e38337b88ca1453f0",
        primary_page_number=12,
        primary_bbox=[50, 100, 450, 300],
        extracted_value="62.5 Crore INR",
        normalized_value=62.5,
        evidence_status="FOUND",
        extraction_confidence=0.99,
        automated_result=EvaluationResult.ELIGIBLE,
        human_review_required=False,
        final_criterion_decision=EvaluationResult.ELIGIBLE,
    )

    crit2 = CriterionExplanationResponse(
        criterion_evaluation_id=uuid.uuid4(),
        criterion_id=uuid.uuid4(),
        requirement_name="BIS Level 4 Certification for Ballistic Helmets",
        category="TECHNICAL",
        requirement_type="MANDATORY",
        source_clause="Clause 5.4: Test Certificate from TBRL / DRDO / NABL accredited laboratory for NIJ Level III / BIS level 4 compliance.",
        rule_type="CERTIFICATE_VALIDITY",
        rule_version="v1.0",
        rule_config={"cert_type": "BIS_LEVEL_4"},
        evidence_items=[
            EvidenceProvenanceItem(
                evidence_id=uuid.uuid4(),
                document_id=doc_id,
                document_name="TBRL_Ballistic_Test_Report.pdf",
                document_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                page_number=4,
                extracted_value="TBRL/CH/2026/884",
                normalized_value="TBRL/CH/2026/884",
                evidence_status="UNREADABLE",
                confidence_score=0.45,
            )
        ],
        primary_document_id=doc_id,
        primary_document_name="TBRL_Ballistic_Test_Report.pdf",
        primary_page_number=4,
        extracted_value="TBRL/CH/2026/884",
        normalized_value="TBRL/CH/2026/884",
        evidence_status="UNREADABLE",
        extraction_confidence=0.45,
        automated_result=EvaluationResult.MANUAL_REVIEW,
        human_review_required=True,
        review_case_id=uuid.uuid4(),
        human_decision=HumanDecision.OVERRIDE,
        is_overridden=True,
        override_reason="Physical laboratory certificate verified and stamped by Director (Armament) on 18-Sep-2026.",
        officer_id=uuid.uuid4(),
        final_criterion_decision=EvaluationResult.ELIGIBLE,
    )

    return BidderExplanationResponse(
        tender_id=uuid.uuid4(),
        tender_number="CRPF-PROC-2026-NVD-004",
        tender_title="Procurement of High-Grade Night Vision Devices & Ballistic Helmets",
        tender_version_id=uuid.uuid4(),
        tender_version_number=1,
        bidder_id=uuid.uuid4(),
        bidder_name="Bharat Defense Systems Ltd",
        bid_submission_id=sub_id,
        evaluation_run_id=uuid.uuid4(),
        overall_evaluation_id=uuid.uuid4(),
        total_criteria=2,
        mandatory_criteria_count=2,
        optional_criteria_count=0,
        eligible_count=1,
        not_eligible_count=0,
        manual_review_count=1,
        mandatory_eligible_count=1,
        mandatory_not_eligible_count=0,
        mandatory_manual_review_count=1,
        missing_evidence_count=0,
        conflicting_evidence_count=0,
        unreadable_evidence_count=1,
        ambiguous_evidence_count=0,
        invalid_evidence_count=0,
        automated_overall_result=EvaluationResult.MANUAL_REVIEW,
        human_overall_decision=HumanDecision.OVERRIDE,
        final_decision_state=EvaluationResult.ELIGIBLE,
        criteria_explanations=[crit1, crit2],
        review_cases_summary=[
            {
                "id": str(uuid.uuid4()),
                "title": "Review of Unreadable TBRL Test Report Stamp",
                "status": "RESOLVED",
                "priority": "CRITICAL",
                "issue_type": "UNREADABLE_EVIDENCE",
                "decision_count": 1,
                "latest_decision": "OVERRIDE",
            }
        ],
    )


def test_sanitize_filename_utility():
    """Verify filename sanitization prevents directory traversal, control chars, and unsafe symbols."""
    assert sanitize_filename("Tender/2026\\Armor:Special*Check?") == "Tender_2026_Armor_Special_Check"
    assert sanitize_filename("../../../etc/passwd") == "etc_passwd"
    assert sanitize_filename("CRPF Tender #123 (Final)") == "CRPF_Tender_123_Final"
    assert sanitize_filename("") == "unnamed"
    assert sanitize_filename("   ") == "unnamed"


def test_generate_safe_report_filename():
    """Verify standard report naming convention with sanitized inputs."""
    fn1 = ReportService.generate_safe_filename(
        tender_number="CRPF/T-2026/001",
        bidder_name="Alpha & Beta Technologies Ltd",
        report_version=2,
        report_type=ReportType.BIDDER_EVALUATION_REPORT,
    )
    assert fn1 == "CRPF_T-2026_001_Alpha_Beta_Technologies_Ltd_bidder_report_v2.pdf"

    fn2 = ReportService.generate_safe_filename(
        tender_number="CRPF/T-2026/001",
        bidder_name=None,
        report_version=1,
        report_type=ReportType.CONSOLIDATED_TENDER_REPORT,
    )
    assert fn2 == "CRPF_T-2026_001_Consolidated_consolidated_report_v1.pdf"


def test_bidder_report_pdf_complete_sections(sample_bidder_explanation):
    """Verify generated PDF contains all Sections A through G and valid metadata."""
    audit_summary = [
        {
            "timestamp": "2026-09-18T10:00:00.000000Z",
            "action": "EVALUATION_RUN_COMPLETED",
            "entity_type": "EVALUATION_RUN",
            "entity_id": "run-001",
            "actor_id": "SYSTEM",
            "reason": "Automated deterministic evaluation finished",
        },
        {
            "timestamp": "2026-09-18T10:15:30.000000Z",
            "action": "OFFICER_OVERRIDE_RECORDED",
            "entity_type": "OFFICER_DECISION",
            "entity_id": "dec-001",
            "actor_id": "officer-77",
            "reason": "Physical TBRL lab cert verified",
        },
    ]

    report_meta = {
        "report_id": uuid.uuid4(),
        "generated_at": "2026-09-18 12:00:00 UTC",
        "report_version": 1,
    }

    pdf_bytes = PDFReportGenerator.generate_bidder_report(
        explanation=sample_bidder_explanation,
        audit_summary=audit_summary,
        report_meta=report_meta,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF-")

    # Compute and verify SHA-256
    computed_hash = hashlib.sha256(pdf_bytes).hexdigest()
    assert len(computed_hash) == 64

    # Extract text from generated PDF pages
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1

    all_text = " ".join([page.extract_text() for page in reader.pages])
    norm_text = re.sub(r"\s+", " ", all_text)

    # Section A verification
    assert "SECTION A - REPORT INFORMATION" in norm_text
    assert "CRPF-PROC-2026-NVD-004" in norm_text
    assert "Bharat Defense Systems Ltd" in norm_text

    # Section B verification
    assert "SECTION B - EXECUTIVE SUMMARY & VERDICT COMPARISON" in norm_text
    assert "MANUAL_REVIEW" in norm_text
    assert "OVERRIDE" in norm_text
    assert "ELIGIBLE" in norm_text

    # Section C verification
    assert "SECTION C - CRITERION-LEVEL DETAILED EVALUATIONS" in norm_text
    assert "Annual Financial Turnover" in norm_text
    assert "BIS Level 4 Certification" in norm_text

    # Section D verification
    assert "SECTION D - EVIDENCE SUMMARY & PROVENANCE" in norm_text
    assert "Audited_Balance_Sheet" in norm_text

    # Section E verification
    assert "SECTION E - HUMAN MANUAL REVIEW & OFFICER DECISIONS" in norm_text
    assert "Review of Unreadable TBRL Test Report Stamp" in norm_text

    # Section F verification
    assert "SECTION F - EVALUATION LINEAGE & TRACEABILITY" in norm_text
    assert "Traceability Chain" in norm_text

    # Section G verification
    assert "SECTION G - SYSTEM AUDIT & PROVENANCE SUMMARY" in norm_text


def test_consolidated_report_pdf_structure(sample_bidder_explanation):
    """Verify consolidated tender report contains matrix and strictly no ranking or scoring."""
    tender_meta = {
        "tender_number": "CRPF-PROC-2026-NVD-004",
        "title": "Procurement of High-Grade Night Vision Devices",
        "version_number": 1,
    }

    report_meta = {
        "report_id": uuid.uuid4(),
        "generated_at": "2026-09-18 12:00:00 UTC",
        "report_version": 1,
    }

    pdf_bytes = PDFReportGenerator.generate_consolidated_report(
        tender_meta=tender_meta,
        bidders_explanations=[sample_bidder_explanation],
        report_meta=report_meta,
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    all_text = " ".join([page.extract_text() for page in reader.pages])
    norm_text = re.sub(r"\s+", " ", all_text)

    assert "CONSOLIDATED TENDER EVALUATION & BIDDER COMPARISON REPORT" in norm_text
    assert "SECTION A - TENDER SPECIFICATIONS & REPORT INFORMATION" in norm_text
    assert "SECTION B - COMPARATIVE BIDDER ELIGIBILITY MATRIX" in norm_text
    assert "no ranking, scoring, or winner selection is performed" in norm_text.lower()
    assert "Bharat Defense Systems Ltd" in norm_text


def test_multi_page_pdf_generation_with_many_criteria(sample_bidder_explanation):
    """Verify ReportLab handles long tables and multi-page flows gracefully without text overflow."""
    many_criteria = []
    for i in range(1, 26):
        many_criteria.append(
            CriterionExplanationResponse(
                criterion_evaluation_id=uuid.uuid4(),
                criterion_id=uuid.uuid4(),
                requirement_name=f"Technical Specification Requirement #{i} - Extended Spec Details",
                category="TECHNICAL",
                requirement_type="MANDATORY" if i % 2 == 0 else "OPTIONAL",
                source_clause=f"Clause {i}.1: Mandatory technical compliance standard {i} for procurement item.",
                rule_type="NUMERIC_THRESHOLD",
                rule_version="v1.0",
                evidence_items=[
                    EvidenceProvenanceItem(
                        evidence_id=uuid.uuid4(),
                        document_id=uuid.uuid4(),
                        document_name=f"Technical_Datasheet_Spec_{i}.pdf",
                        page_number=i,
                        extracted_value=f"Compliant Spec Value {i} with extended textual commentary",
                        normalized_value=float(i),
                        evidence_status="FOUND",
                        confidence_score=0.95,
                    )
                ],
                primary_document_name=f"Technical_Datasheet_Spec_{i}.pdf",
                primary_page_number=i,
                extracted_value=f"Compliant Spec Value {i}",
                normalized_value=float(i),
                evidence_status="FOUND",
                automated_result=EvaluationResult.ELIGIBLE if i % 3 != 0 else EvaluationResult.NOT_ELIGIBLE,
                human_review_required=False,
                final_criterion_decision=EvaluationResult.ELIGIBLE if i % 3 != 0 else EvaluationResult.NOT_ELIGIBLE,
            )
        )

    sample_bidder_explanation.criteria_explanations = many_criteria
    sample_bidder_explanation.total_criteria = len(many_criteria)

    pdf_bytes = PDFReportGenerator.generate_bidder_report(
        explanation=sample_bidder_explanation,
    )

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 2

    for p in reader.pages:
        txt = p.extract_text()
        assert "CRPF PROCUREMENT EVALUATION PLATFORM" in txt
        assert "Page" in txt


def test_report_service_rejects_unevaluated_submission(db_session):
    """Verify ReportService raises ConflictException when attempting to generate report for unevaluated submission."""
    from app.db.models.bid_submission import BidSubmission, SubmissionStatus
    from app.db.models.bidder import Bidder
    from app.db.models.tender import Tender, TenderStatus
    from app.db.models.tender_version import TenderVersion
    from app.db.models.user import User
    from app.storage.memory import InMemoryObjectStorageService

    user = User(
        id=uuid.uuid4(),
        email=f"officer_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Officer Test",
        is_active=True,
        password_hash="pwd",
    )
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-TEST-{uuid.uuid4().hex[:6]}",
        title="Test Tender",
        status=TenderStatus.PUBLISHED,
        created_by=user.id,
    )
    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=user.id,
    )
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="B01",
        legal_name="Test Bidder",
    )
    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-001",
        status=SubmissionStatus.READY,
    )

    db_session.add_all([user, tender, version, bidder, sub])
    db_session.commit()

    storage = InMemoryObjectStorageService()
    req = ReportCreateRequest(title="Premature Report")

    # Attempt to generate report without criterion evaluations
    with pytest.raises(ConflictException) as exc_info:
        ReportService.generate_bidder_report(
            db=db_session,
            submission_id=sub.id,
            current_user=user,
            request=req,
            storage=storage,
        )

    assert "has not been evaluated" in str(exc_info.value.detail)
