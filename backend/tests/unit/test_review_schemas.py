"""Unit tests for Phase 13 Review schemas and validations."""

import uuid
import pytest
from pydantic import ValidationError

from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.review_case import (
    HumanDecision,
    ReviewIssueType,
    ReviewPriority,
    ReviewStatus,
)
from app.reviews.schemas import (
    OfficerDecisionCreateRequest,
    ReviewCaseCreateRequest,
    ReviewNoteCreateRequest,
)


def test_officer_decision_create_valid():
    """Valid officer override request passes schema validation."""
    req = OfficerDecisionCreateRequest(
        decision=HumanDecision.OVERRIDE,
        final_verdict=EvaluationResult.ELIGIBLE,
        reason="Officer inspected original physical bank guarantee certifying ₹12 crore turnover.",
    )
    assert req.decision == HumanDecision.OVERRIDE
    assert req.final_verdict == EvaluationResult.ELIGIBLE
    assert "₹12 crore turnover" in req.reason


def test_officer_decision_empty_reason_rejected():
    """Empty or whitespace-only reason is rejected."""
    with pytest.raises(ValidationError):
        OfficerDecisionCreateRequest(
            decision=HumanDecision.OVERRIDE,
            final_verdict=EvaluationResult.ELIGIBLE,
            reason="   ",
        )


def test_officer_decision_too_short_reason_rejected():
    """Reason with fewer than 3 chars is rejected."""
    with pytest.raises(ValidationError):
        OfficerDecisionCreateRequest(
            decision=HumanDecision.CONFIRM,
            reason="ok",
        )


def test_review_note_empty_rejected():
    """Empty note is rejected."""
    with pytest.raises(ValidationError):
        ReviewNoteCreateRequest(note="   ")


def test_review_case_create_valid():
    """Valid review case creation schema passes."""
    req = ReviewCaseCreateRequest(
        bid_submission_id=uuid.uuid4(),
        issue_type=ReviewIssueType.CONFLICTING_EVIDENCE,
        priority=ReviewPriority.HIGH,
        title="Conflicting audited financial statements",
        description="Page 4 shows ₹14 Cr while Page 8 shows ₹8 Cr.",
    )
    assert req.issue_type == ReviewIssueType.CONFLICTING_EVIDENCE
    assert req.priority == ReviewPriority.HIGH
