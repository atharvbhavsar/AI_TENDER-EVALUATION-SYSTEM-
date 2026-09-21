"""Exhaustive unit tests for Phase 13 Human Review, Officer Override & Decision Audit."""

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
    ReviewAssignRequest,
    ReviewCaseCreateRequest,
    ReviewNoteCreateRequest,
)


def test_override_requires_non_empty_meaningful_reason():
    """Verify that override reasons must be non-empty and non-whitespace."""
    # Valid
    req = OfficerDecisionCreateRequest(
        decision=HumanDecision.OVERRIDE,
        final_verdict=EvaluationResult.ELIGIBLE,
        reason="Officer inspected original sealed bank guarantee certifying required turnover.",
    )
    assert req.reason == "Officer inspected original sealed bank guarantee certifying required turnover."

    # Empty string fails
    with pytest.raises(ValidationError):
        OfficerDecisionCreateRequest(
            decision=HumanDecision.OVERRIDE,
            final_verdict=EvaluationResult.ELIGIBLE,
            reason="",
        )

    # Whitespace fails
    with pytest.raises(ValidationError):
        OfficerDecisionCreateRequest(
            decision=HumanDecision.OVERRIDE,
            final_verdict=EvaluationResult.ELIGIBLE,
            reason="     \t\n  ",
        )

    # Short reason (< 3 chars) fails
    with pytest.raises(ValidationError):
        OfficerDecisionCreateRequest(
            decision=HumanDecision.OVERRIDE,
            final_verdict=EvaluationResult.ELIGIBLE,
            reason="no",
        )


def test_confirmation_decision_validation():
    """Confirming a system verdict requires a valid reason and defaults final_verdict."""
    req = OfficerDecisionCreateRequest(
        decision=HumanDecision.CONFIRM,
        reason="Verified and confirmed automated evaluation findings against tender document clause 4.2.",
    )
    assert req.decision == HumanDecision.CONFIRM
    assert req.final_verdict is None


def test_request_review_decision_validation():
    """Requesting secondary review requires an explanation."""
    req = OfficerDecisionCreateRequest(
        decision=HumanDecision.REQUEST_REVIEW,
        reason="Ambiguity in audited statement requires secondary review by financial technical committee.",
    )
    assert req.decision == HumanDecision.REQUEST_REVIEW


def test_review_note_validation():
    """Review notes must not be empty or whitespace."""
    req = ReviewNoteCreateRequest(note="Officer contacted bidder representative for clarification on annexure B.")
    assert req.note == "Officer contacted bidder representative for clarification on annexure B."

    with pytest.raises(ValidationError):
        ReviewNoteCreateRequest(note="")

    with pytest.raises(ValidationError):
        ReviewNoteCreateRequest(note="   \n ")


def test_review_assign_schema():
    """Review assignment schema requires a valid UUID."""
    u_id = uuid.uuid4()
    req = ReviewAssignRequest(assigned_to=u_id)
    assert req.assigned_to == u_id


def test_review_case_create_schema():
    """ReviewCaseCreateRequest validation and defaults."""
    sub_id = uuid.uuid4()
    req = ReviewCaseCreateRequest(
        bid_submission_id=sub_id,
        issue_type=ReviewIssueType.UNREADABLE_EVIDENCE,
        priority=ReviewPriority.CRITICAL,
        title="Unreadable ISO 9001 Certificate scan",
        description="Page 3 blur prevents OCR extraction of validity dates.",
    )
    assert req.bid_submission_id == sub_id
    assert req.issue_type == ReviewIssueType.UNREADABLE_EVIDENCE
    assert req.priority == ReviewPriority.CRITICAL
    assert req.title == "Unreadable ISO 9001 Certificate scan"
