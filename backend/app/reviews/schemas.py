"""Pydantic schemas for Phase 13 Human Review, Officer Override & Decision Audit."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.review_case import (
    HumanDecision,
    ReviewIssueType,
    ReviewPriority,
    ReviewStatus,
)


class ReviewCaseCreateRequest(BaseModel):
    """Payload for creating a manual review case."""

    bid_submission_id: uuid.UUID
    criterion_id: Optional[uuid.UUID] = None
    criterion_evaluation_id: Optional[uuid.UUID] = None
    issue_type: ReviewIssueType = Field(default=ReviewIssueType.MANUAL_REVIEW_REQUIRED)
    priority: ReviewPriority = Field(default=ReviewPriority.MEDIUM)
    title: str = Field(min_length=3, max_length=255)
    description: Optional[str] = None


class ReviewAssignRequest(BaseModel):
    """Payload for assigning a review case to an officer."""

    assigned_to: uuid.UUID


class OfficerDecisionCreateRequest(BaseModel):
    """Payload for recording an explicit human officer decision."""

    decision: HumanDecision
    final_verdict: Optional[EvaluationResult] = None
    reason: str = Field(min_length=3, description="Mandatory justification for human review decision")

    @field_validator("reason")
    @classmethod
    def validate_reason_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Decision reason must not be empty or whitespace only.")
        return v.strip()

    @field_validator("final_verdict")
    @classmethod
    def validate_final_verdict_for_override(cls, v: Optional[EvaluationResult], info) -> Optional[EvaluationResult]:
        # If decision is OVERRIDE, final_verdict must be specified
        return v


class OfficerDecisionResponse(BaseModel):
    """Response payload for a recorded human decision."""

    id: uuid.UUID
    review_case_id: uuid.UUID
    criterion_id: Optional[uuid.UUID] = None
    criterion_evaluation_id: Optional[uuid.UUID] = None
    decision: HumanDecision
    system_result: EvaluationResult
    final_verdict: Optional[EvaluationResult] = None
    reason: str
    officer_id: uuid.UUID
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewNoteCreateRequest(BaseModel):
    """Payload for adding a structured review note."""

    note: str = Field(min_length=1)

    @field_validator("note")
    @classmethod
    def validate_note_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Review note cannot be empty.")
        return v.strip()


class ReviewNoteResponse(BaseModel):
    """Response payload for an immutable review note."""

    id: uuid.UUID
    review_case_id: uuid.UUID
    author_id: uuid.UUID
    note: str
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewAuditLogResponse(BaseModel):
    """Response payload for a review audit trail item."""

    id: uuid.UUID
    review_case_id: uuid.UUID
    action: str
    actor_id: Optional[uuid.UUID] = None
    details: Dict[str, Any]
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewCaseResponse(BaseModel):
    """Response payload for a review case summary."""

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_version_id: uuid.UUID
    bidder_id: uuid.UUID
    bid_submission_id: uuid.UUID
    criterion_id: Optional[uuid.UUID] = None
    criterion_evaluation_id: Optional[uuid.UUID] = None
    overall_evaluation_id: Optional[uuid.UUID] = None
    evaluation_run_id: Optional[uuid.UUID] = None
    status: ReviewStatus
    priority: ReviewPriority
    issue_type: ReviewIssueType
    title: str
    description: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None
    created_by: Optional[uuid.UUID] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewCaseListResponse(BaseModel):
    """List response for review cases."""

    total: int
    items: List[ReviewCaseResponse]


class EvidenceDetailItem(BaseModel):
    """Extracted evidence item with source localization for officer review."""

    evidence_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    document_filename: Optional[str] = None
    status: str
    extracted_value: Optional[Any] = None
    confidence: float
    source_page: Optional[int] = None
    source_block_id: Optional[str] = None
    source_table_reference: Optional[str] = None
    bounding_box: Optional[Any] = None
    extractor_version: Optional[str] = None


class ReviewCaseDetailResponse(ReviewCaseResponse):
    """Comprehensive review detail payload including all contextual evidence and evaluations."""

    tender_number: Optional[str] = None
    bidder_name: Optional[str] = None
    submission_reference: Optional[str] = None
    criterion_code: Optional[str] = None
    criterion_name: Optional[str] = None
    criterion_requirement_type: Optional[str] = None

    system_criterion_result: Optional[EvaluationResult] = None
    system_overall_result: Optional[EvaluationResult] = None
    opa_explanation: Dict[str, Any] = Field(default_factory=dict)

    evidence_items: List[EvidenceDetailItem] = Field(default_factory=list)
    decisions: List[OfficerDecisionResponse] = Field(default_factory=list)
    notes: List[ReviewNoteResponse] = Field(default_factory=list)
    audit_logs: List[ReviewAuditLogResponse] = Field(default_factory=list)
