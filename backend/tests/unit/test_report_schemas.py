"""Unit tests for Phase 14 reporting and explainability Pydantic schemas."""

import uuid
import pytest
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.evaluation_report import ReportStatus, ReportType
from app.db.models.review_case import HumanDecision
from app.reports.schemas import (
    BidderExplanationResponse,
    CriterionExplanationResponse,
    EvaluationReportResponse,
    EvidenceProvenanceItem,
    ReportCreateRequest,
    ReportListResponse,
)


def test_evidence_provenance_item_valid():
    """Verify EvidenceProvenanceItem model parsing."""
    item = EvidenceProvenanceItem(
        evidence_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        document_name="Audit_Report_2023.pdf",
        document_hash="a" * 64,
        page_number=4,
        block_id="b-12",
        table_reference="tbl-1",
        bbox={"x": 10, "y": 20, "w": 100, "h": 50},
        extracted_value=12.5,
        normalized_value=12.5,
        evidence_status="FOUND",
        confidence_score=0.98,
        source_clause_quote="Turnover of bidder in FY23 was 12.5 Cr",
    )
    assert item.page_number == 4
    assert item.confidence_score == 0.98
    assert item.evidence_status == "FOUND"


def test_criterion_explanation_response_valid():
    """Verify CriterionExplanationResponse model parsing."""
    resp = CriterionExplanationResponse(
        criterion_evaluation_id=uuid.uuid4(),
        criterion_id=uuid.uuid4(),
        requirement_name="Annual Turnover Requirement",
        category="FINANCIAL",
        requirement_type="MANDATORY",
        source_clause="Clause 4.1: Minimum turnover 10 Crore",
        rule_type="NUMERIC_THRESHOLD",
        rule_version="v1.0",
        rule_config={"min_value": 10.0, "currency": "INR"},
        primary_document_name="Financial_Statements.pdf",
        evidence_status="FOUND",
        automated_result=EvaluationResult.ELIGIBLE,
        human_review_required=False,
        final_criterion_decision=EvaluationResult.ELIGIBLE,
    )
    assert resp.automated_result == EvaluationResult.ELIGIBLE
    assert resp.final_criterion_decision == EvaluationResult.ELIGIBLE
    assert resp.is_overridden is False


def test_bidder_explanation_response_valid():
    """Verify BidderExplanationResponse schema and counts."""
    resp = BidderExplanationResponse(
        tender_id=uuid.uuid4(),
        tender_number="CRPF-T-2026-001",
        tender_title="Procurement of Body Armor",
        tender_version_id=uuid.uuid4(),
        tender_version_number=1,
        bidder_id=uuid.uuid4(),
        bidder_name="Apex Defense Ltd",
        bid_submission_id=uuid.uuid4(),
        total_criteria=5,
        mandatory_criteria_count=4,
        optional_criteria_count=1,
        eligible_count=4,
        not_eligible_count=1,
        manual_review_count=0,
        mandatory_eligible_count=3,
        mandatory_not_eligible_count=1,
        mandatory_manual_review_count=0,
        automated_overall_result=EvaluationResult.NOT_ELIGIBLE,
        human_overall_decision=HumanDecision.OVERRIDE,
        final_decision_state=EvaluationResult.ELIGIBLE,
    )
    assert resp.total_criteria == 5
    assert resp.automated_overall_result == EvaluationResult.NOT_ELIGIBLE
    assert resp.human_overall_decision == HumanDecision.OVERRIDE
    assert resp.final_decision_state == EvaluationResult.ELIGIBLE


def test_report_create_request_valid():
    """Verify ReportCreateRequest schema."""
    req = ReportCreateRequest(
        title="Custom Bidder Report",
        include_audit_summary=True,
        include_source_snippets=False,
    )
    assert req.title == "Custom Bidder Report"
    assert req.include_source_snippets is False
