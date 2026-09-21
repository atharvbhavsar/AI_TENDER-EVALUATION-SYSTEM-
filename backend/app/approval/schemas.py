"""Pydantic schemas for officer review, criterion corrections, approvals, and history."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.db.models.criterion_approval_history import ApprovalAction
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    RequirementType,
)


class CriterionCorrectionRequest(BaseModel):
    """Payload submitted by a procurement officer to correct candidate criterion fields."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = Field(None, min_length=1)
    category: Optional[CriterionCategory] = None
    requirement_type: Optional[RequirementType] = None
    condition_text: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[float] = None
    threshold_text: Optional[str] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    mandatory: Optional[bool] = None
    required_evidence: Optional[List[str]] = None
    source_clause: Optional[str] = None
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    reason: Optional[str] = Field(None, description="Optional explanation for correction")


class CriterionApprovalRequest(BaseModel):
    """Payload to approve a candidate criterion."""

    reason: Optional[str] = Field(None, description="Optional officer approval notes")


class CriterionRejectionRequest(BaseModel):
    """Payload to reject a candidate criterion (reason is mandatory)."""

    reason: str = Field(..., min_length=3, max_length=1000, description="Mandatory justification for rejecting criterion")


class CriterionApprovalHistoryResponse(BaseModel):
    """API schema for a single audit history event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    criterion_id: uuid.UUID
    action: ApprovalAction
    previous_status: ApprovalStatus
    new_status: ApprovalStatus
    changed_fields: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    officer_id: uuid.UUID
    created_at: datetime.datetime
