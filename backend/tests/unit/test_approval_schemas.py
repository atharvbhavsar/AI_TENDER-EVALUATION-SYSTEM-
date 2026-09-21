"""Unit tests for Phase 8 approval schemas and validation."""

import pytest
import uuid
from pydantic import ValidationError

from app.approval.schemas import (
    CriterionApprovalHistoryResponse,
    CriterionApprovalRequest,
    CriterionCorrectionRequest,
    CriterionRejectionRequest,
)
from app.db.models.criterion_approval_history import ApprovalAction
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    RequirementType,
)


def test_criterion_correction_request_valid():
    """Test valid instantiation of CriterionCorrectionRequest."""
    req = CriterionCorrectionRequest(
        name="Corrected Annual Turnover",
        threshold_value=60000000.0,
        threshold_text="₹6 Crore",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        reason="Updated based on clarification corrigendum text",
    )
    assert req.name == "Corrected Annual Turnover"
    assert req.threshold_value == 60000000.0
    assert req.reason == "Updated based on clarification corrigendum text"


def test_criterion_rejection_request_requires_reason():
    """Test that CriterionRejectionRequest requires a non-empty reason."""
    with pytest.raises(ValidationError):
        CriterionRejectionRequest(reason="")  # Min length 3

    with pytest.raises(ValidationError):
        CriterionRejectionRequest()  # Missing reason


def test_criterion_approval_history_response():
    """Test CriterionApprovalHistoryResponse serialization."""
    hist = CriterionApprovalHistoryResponse(
        id=uuid.uuid4(),
        criterion_id=uuid.uuid4(),
        action=ApprovalAction.APPROVE,
        previous_status=ApprovalStatus.PENDING_REVIEW,
        new_status=ApprovalStatus.APPROVED,
        changed_fields={"approval_status": {"old": "PENDING_REVIEW", "new": "APPROVED"}},
        reason="All documents and clauses verified against tender guidelines",
        officer_id=uuid.uuid4(),
        created_at="2026-09-18T03:00:00Z",  # type: ignore
    )
    assert hist.action == ApprovalAction.APPROVE
    assert hist.new_status == ApprovalStatus.APPROVED
