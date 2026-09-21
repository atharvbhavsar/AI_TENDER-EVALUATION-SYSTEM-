"""Pydantic schemas for bidder-level overall eligibility aggregation."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.tender_criterion import RequirementType


class CriterionBreakdownItem(BaseModel):
    """Evaluation summary for an individual approved criterion."""

    criterion_id: uuid.UUID
    criterion_code: str
    criterion_name: str
    requirement_type: RequirementType
    is_mandatory: bool
    result: EvaluationResult
    has_evaluation: bool = True
    evaluation_id: Optional[uuid.UUID] = None
    rule_version: Optional[str] = None
    explanation: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class EvaluateSubmissionRequest(BaseModel):
    """Optional configuration for triggering an overall submission aggregation."""

    aggregation_policy_version: str = Field(default="v1.0", description="Aggregation policy version")
    evaluation_run_id: Optional[uuid.UUID] = Field(default=None, description="Optional evaluation run group ID")
    run_rules: bool = Field(default=False, description="Whether to evaluate all approved criteria in OPA before aggregating")
    auto_generate_reviews: bool = Field(default=False, description="Whether to auto-generate review cases for MANUAL_REVIEW results")


class BidderEvaluationResponse(BaseModel):
    """Response payload representing an aggregated overall bidder evaluation."""

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_version_id: uuid.UUID
    bidder_id: uuid.UUID
    bid_submission_id: uuid.UUID
    evaluation_run_id: uuid.UUID
    result: EvaluationResult
    aggregation_policy_version: str

    criterion_count: int
    eligible_count: int
    not_eligible_count: int
    manual_review_count: int

    mandatory_criterion_count: int
    mandatory_eligible_count: int
    mandatory_not_eligible_count: int
    mandatory_manual_review_count: int

    optional_criterion_count: int
    optional_eligible_count: int
    optional_not_eligible_count: int
    optional_manual_review_count: int

    explanation: Dict[str, Any]
    evaluated_by: Optional[uuid.UUID] = None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class BidderEvaluationDetailResponse(BidderEvaluationResponse):
    """Detailed response payload including criterion-by-criterion breakdown."""

    criteria_breakdown: List[CriterionBreakdownItem] = Field(default_factory=list)
    rule_version_snapshot: Dict[str, Any] = Field(default_factory=dict)


class SubmissionCriteriaBreakdownResponse(BaseModel):
    """Response payload listing criterion evaluations for a submission."""

    bid_submission_id: uuid.UUID
    evaluation_id: Optional[uuid.UUID] = None
    evaluation_run_id: Optional[uuid.UUID] = None
    overall_result: Optional[EvaluationResult] = None
    criteria: List[CriterionBreakdownItem] = Field(default_factory=list)


class EvaluationHistoryListResponse(BaseModel):
    """Response payload listing historical overall evaluation runs."""

    bid_submission_id: uuid.UUID
    total_runs: int
    evaluations: List[BidderEvaluationResponse] = Field(default_factory=list)
