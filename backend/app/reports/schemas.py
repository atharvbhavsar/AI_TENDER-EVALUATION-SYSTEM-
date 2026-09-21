"""Pydantic schemas for Explainability, Lineage, and Reporting."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.evaluation_report import ReportStatus, ReportType
from app.db.models.review_case import HumanDecision


class EvidenceProvenanceItem(BaseModel):
    """Detailed evidence provenance item within an explanation."""

    evidence_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    document_name: Optional[str] = None
    document_hash: Optional[str] = None
    page_number: Optional[int] = None
    block_id: Optional[str] = None
    table_reference: Optional[str] = None
    bbox: Optional[Any] = None
    extracted_value: Optional[Any] = None
    normalized_value: Optional[Any] = None
    evidence_status: str
    confidence_score: Optional[float] = None
    source_clause_quote: Optional[str] = None


class CriterionExplanationResponse(BaseModel):
    """
    Comprehensive 20-point deterministic explanation answering exact requirement,
    source, evidence, rule, OPA evaluation, and human decision provenance.
    """

    model_config = ConfigDict(from_attributes=True)

    criterion_evaluation_id: uuid.UUID
    criterion_id: uuid.UUID
    requirement_name: str
    category: str
    requirement_type: str
    source_clause: Optional[str] = None

    # Rule Provenance
    rule_id: Optional[uuid.UUID] = None
    rule_type: Optional[str] = None
    rule_version: Optional[str] = None
    rule_config: Dict[str, Any] = Field(default_factory=dict)

    # Evidence Traceability
    evidence_items: List[EvidenceProvenanceItem] = Field(default_factory=list)
    primary_document_id: Optional[uuid.UUID] = None
    primary_document_name: Optional[str] = None
    primary_document_hash: Optional[str] = None
    primary_page_number: Optional[int] = None
    primary_bbox: Optional[Any] = None
    extracted_value: Optional[Any] = None
    normalized_value: Optional[Any] = None
    evidence_status: str
    extraction_confidence: Optional[float] = None

    # Deterministic Evaluation
    rule_evaluation_details: Dict[str, Any] = Field(default_factory=dict)
    automated_result: EvaluationResult

    # Human Review & Officer Decisions
    human_review_required: bool
    review_case_id: Optional[uuid.UUID] = None
    human_decision: Optional[HumanDecision] = None
    is_overridden: bool = False
    override_reason: Optional[str] = None
    officer_id: Optional[uuid.UUID] = None
    final_criterion_decision: EvaluationResult


class BidderExplanationResponse(BaseModel):
    """
    Consolidated bidder-level explanation distinguishing automated results from human officer decisions.
    """

    tender_id: uuid.UUID
    tender_number: str
    tender_title: str
    tender_version_id: uuid.UUID
    tender_version_number: int

    bidder_id: uuid.UUID
    bidder_name: str
    bid_submission_id: uuid.UUID
    evaluation_run_id: Optional[uuid.UUID] = None
    overall_evaluation_id: Optional[uuid.UUID] = None

    # Criterion Counts
    total_criteria: int
    mandatory_criteria_count: int
    optional_criteria_count: int
    eligible_count: int
    not_eligible_count: int
    manual_review_count: int
    mandatory_eligible_count: int
    mandatory_not_eligible_count: int
    mandatory_manual_review_count: int

    # Evidence Health Counts
    missing_evidence_count: int = 0
    conflicting_evidence_count: int = 0
    unreadable_evidence_count: int = 0
    ambiguous_evidence_count: int = 0
    invalid_evidence_count: int = 0

    # Separate Automated Result vs Human Decision
    automated_overall_result: EvaluationResult
    human_overall_decision: Optional[HumanDecision] = None
    final_decision_state: EvaluationResult

    # Granular Explanations & Reviews
    criteria_explanations: List[CriterionExplanationResponse] = Field(default_factory=list)
    review_cases_summary: List[Dict[str, Any]] = Field(default_factory=list)


class EvaluationReportResponse(BaseModel):
    """Formal evaluation report metadata representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_version_id: uuid.UUID
    bidder_id: Optional[uuid.UUID] = None
    bid_submission_id: Optional[uuid.UUID] = None
    evaluation_run_id: Optional[uuid.UUID] = None
    overall_evaluation_id: Optional[uuid.UUID] = None
    report_type: ReportType
    report_version: int
    status: ReportStatus
    title: str
    storage_key: Optional[str] = None
    file_hash: Optional[str] = None
    file_size_bytes: Optional[int] = None
    mime_type: str
    generated_by: Optional[uuid.UUID] = None
    generation_metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class ReportCreateRequest(BaseModel):
    """Request payload to generate an evaluation report."""

    title: Optional[str] = Field(None, max_length=255)
    include_audit_summary: bool = True
    include_source_snippets: bool = True


class ReportListResponse(BaseModel):
    """Paginated list of evaluation reports."""

    items: List[EvaluationReportResponse]
    total: int
    limit: int
    offset: int
