"""Unit tests for PDF Report Generator (ReportLab)."""

import hashlib
import uuid
import pypdf
import io
import pytest
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.review_case import HumanDecision
from app.reports.pdf_generator import PDFReportGenerator
from app.reports.schemas import (
    BidderExplanationResponse,
    CriterionExplanationResponse,
    EvidenceProvenanceItem,
)


@pytest.fixture
def mock_bidder_explanation() -> BidderExplanationResponse:
    """Fixture providing rich bidder explanation for PDF generation testing."""
    cid1 = uuid.uuid4()
    ceid1 = uuid.uuid4()
    sub_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    crit1 = CriterionExplanationResponse(
        criterion_evaluation_id=ceid1,
        criterion_id=cid1,
        requirement_name="Annual Turnover Requirement",
        category="FINANCIAL",
        requirement_type="MANDATORY",
        source_clause="Clause 4.1: Minimum 10 Crore turnover in last 3 financial years",
        rule_type="NUMERIC_THRESHOLD",
        rule_version="v1.0",
        rule_config={"min_value": 10.0, "currency": "INR"},
        evidence_items=[
            EvidenceProvenanceItem(
                evidence_id=uuid.uuid4(),
                document_id=doc_id,
                document_name="Audited_Accounts_2023.pdf",
                document_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                page_number=3,
                extracted_value="14.2 Crore",
                normalized_value=14.2,
                evidence_status="FOUND",
                confidence_score=0.98,
            )
        ],
        primary_document_id=doc_id,
        primary_document_name="Audited_Accounts_2023.pdf",
        primary_page_number=3,
        extracted_value="14.2 Crore",
        normalized_value=14.2,
        evidence_status="FOUND",
        extraction_confidence=0.98,
        automated_result=EvaluationResult.ELIGIBLE,
        human_review_required=False,
        final_criterion_decision=EvaluationResult.ELIGIBLE,
    )

    crit2 = CriterionExplanationResponse(
        criterion_evaluation_id=uuid.uuid4(),
        criterion_id=uuid.uuid4(),
        requirement_name="ISO 9001 Certification",
        category="TECHNICAL",
        requirement_type="MANDATORY",
        source_clause="Clause 5.2: Valid ISO 9001:2015 certification required",
        rule_type="CERTIFICATE_VALIDITY",
        rule_version="v1.0",
        rule_config={"cert_type": "ISO 9001"},
        evidence_items=[],
        evidence_status="UNREADABLE",
        automated_result=EvaluationResult.MANUAL_REVIEW,
        human_review_required=True,
        human_decision=HumanDecision.OVERRIDE,
        is_overridden=True,
        override_reason="Original physical certificate verified and stamped by procurement board on 18-Sep-2026.",
        final_criterion_decision=EvaluationResult.ELIGIBLE,
    )

    return BidderExplanationResponse(
        tender_id=uuid.uuid4(),
        tender_number="CRPF-T-2026-ARMOR-001",
        tender_title="Procurement of Ballistic Helmets",
        tender_version_id=uuid.uuid4(),
        tender_version_number=1,
        bidder_id=uuid.uuid4(),
        bidder_name="Apex Tactical Systems Pvt Ltd",
        bid_submission_id=sub_id,
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
                "title": "Review of Unreadable ISO Certificate",
                "status": "RESOLVED",
                "priority": "HIGH",
                "issue_type": "UNREADABLE_EVIDENCE",
                "decision_count": 1,
                "latest_decision": "OVERRIDE",
            }
        ],
    )


def test_generate_bidder_report_pdf_valid(mock_bidder_explanation):
    """Verify that bidder report PDF is generated with valid structure and headers."""
    audit_summary = [
        {
            "timestamp": "2026-09-18T10:00:00Z",
            "action": "EVALUATION_EXECUTED",
            "entity_type": "SUBMISSION",
            "entity_id": str(mock_bidder_explanation.bid_submission_id),
            "actor_id": "SYSTEM",
            "reason": "Automated deterministic OPA evaluation completed",
        },
        {
            "timestamp": "2026-09-18T10:15:00Z",
            "action": "OFFICER_OVERRIDDEN",
            "entity_type": "REVIEW_CASE",
            "entity_id": "rc-001",
            "actor_id": "officer-45",
            "reason": "Physical inspection verified",
        },
    ]

    pdf_bytes = PDFReportGenerator.generate_bidder_report(
        explanation=mock_bidder_explanation,
        audit_summary=audit_summary,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")

    # Verify readable through pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    page_text = reader.pages[0].extract_text()
    assert "CENTRAL RESERVE POLICE FORCE" in page_text
    assert "Apex Tactical Systems Pvt Ltd" in page_text
    assert "CRPF-T-2026-ARMOR-001" in page_text
    assert "MANUAL_REVIEW" in page_text


def test_generate_consolidated_report_pdf_valid(mock_bidder_explanation):
    """Verify that consolidated tender report PDF is generated properly."""
    tender_meta = {
        "tender_number": "CRPF-T-2026-ARMOR-001",
        "title": "Procurement of Ballistic Helmets",
        "version_number": 1,
    }

    pdf_bytes = PDFReportGenerator.generate_consolidated_report(
        tender_meta=tender_meta,
        bidders_explanations=[mock_bidder_explanation],
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 1
    page_text = reader.pages[0].extract_text()
    import re
    norm_text = re.sub(r"\s+", " ", page_text)
    assert "CONSOLIDATED TENDER EVALUATION" in norm_text
    assert "Apex Tactical Systems Pvt Ltd" in norm_text
