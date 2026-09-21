"""Pydantic schemas for deterministic rule configuration and evaluation outputs."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.criterion_rule import RuleStatus, RuleType


class RuleCreateRequest(BaseModel):
    """Optional payload to customize rule template during creation."""

    rule_type: Optional[RuleType] = None
    configuration: Optional[Dict[str, Any]] = None


class CriterionRuleResponse(BaseModel):
    """Response payload representing an approved criterion's deterministic rule."""

    id: uuid.UUID
    criterion_id: uuid.UUID
    tender_version_id: uuid.UUID
    rule_type: RuleType
    rule_version: str
    template_version: str
    rego_policy_reference: str
    configuration: Dict[str, Any]
    status: RuleStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class CriterionEvaluationResponse(BaseModel):
    """Response payload for a deterministic criterion evaluation."""

    id: uuid.UUID
    criterion_id: uuid.UUID
    bidder_id: uuid.UUID
    bid_submission_id: uuid.UUID
    tender_version_id: uuid.UUID
    rule_id: uuid.UUID
    rule_version: str
    policy_version: str
    result: EvaluationResult
    input_snapshot: Dict[str, Any]
    evidence_ids: List[str]
    explanation: Dict[str, Any]
    evaluation_run_id: Optional[uuid.UUID] = None
    evaluated_at: datetime.datetime

    class Config:
        from_attributes = True


class SubmissionEvaluationsListResponse(BaseModel):
    """Response payload listing all criterion evaluations for a bidder submission."""

    submission_id: uuid.UUID
    total_evaluations: int
    evaluations: List[CriterionEvaluationResponse] = Field(default_factory=list)
