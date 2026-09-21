"""Unit tests for Phase 12 deterministic bidder aggregation engine."""

import uuid
import pytest
from app.aggregation.engine import (
    CriterionEvaluationInput,
    aggregate_criteria_results,
)
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.tender_criterion import RequirementType


def _make_criterion(
    code: str,
    req_type: RequirementType = RequirementType.MANDATORY,
    is_mandatory: bool = True,
    result: EvaluationResult = EvaluationResult.ELIGIBLE,
    has_evaluation: bool = True,
) -> CriterionEvaluationInput:
    """Helper to create a CriterionEvaluationInput test object."""
    return CriterionEvaluationInput(
        criterion_id=str(uuid.uuid4()),
        criterion_code=code,
        criterion_name=f"Criterion {code}",
        requirement_type=req_type,
        is_mandatory=is_mandatory,
        result=result,
        has_evaluation=has_evaluation,
        evaluation_id=str(uuid.uuid4()) if has_evaluation else None,
        rule_version="v1.0",
        explanation={"status": result.value},
        evidence_ids=["ev-1"],
    )


def test_all_mandatory_eligible_produces_overall_eligible():
    """All mandatory criteria passing produces overall ELIGIBLE."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C2", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C3", RequirementType.OPTIONAL, False, EvaluationResult.ELIGIBLE),
    ]
    res = aggregate_criteria_results(criteria)
    assert res.overall_result == EvaluationResult.ELIGIBLE
    assert res.criterion_count == 3
    assert res.mandatory_criterion_count == 2
    assert res.mandatory_eligible_count == 2
    assert res.mandatory_not_eligible_count == 0
    assert res.mandatory_manual_review_count == 0
    assert "successfully satisfied" in res.explanation["summary"]


def test_any_mandatory_not_eligible_produces_overall_not_eligible():
    """A single failing mandatory criterion produces overall NOT_ELIGIBLE."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C2", RequirementType.MANDATORY, True, EvaluationResult.NOT_ELIGIBLE),
        _make_criterion("C3", RequirementType.OPTIONAL, False, EvaluationResult.ELIGIBLE),
    ]
    res = aggregate_criteria_results(criteria)
    assert res.overall_result == EvaluationResult.NOT_ELIGIBLE
    assert res.mandatory_not_eligible_count == 1
    assert "C2" in res.explanation["failing_mandatory_criteria"]


def test_priority_mandatory_failure_takes_precedence_over_review():
    """NOT_ELIGIBLE takes priority over MANUAL_REVIEW for mandatory criteria."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.MANUAL_REVIEW),
        _make_criterion("C2", RequirementType.MANDATORY, True, EvaluationResult.NOT_ELIGIBLE),
    ]
    res = aggregate_criteria_results(criteria)
    assert res.overall_result == EvaluationResult.NOT_ELIGIBLE
    assert res.mandatory_not_eligible_count == 1
    assert res.mandatory_manual_review_count == 1


def test_mandatory_manual_review_without_failure_produces_manual_review():
    """Mandatory review without mandatory failure produces overall MANUAL_REVIEW."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C2", RequirementType.MANDATORY, True, EvaluationResult.MANUAL_REVIEW),
    ]
    res = aggregate_criteria_results(criteria)
    assert res.overall_result == EvaluationResult.MANUAL_REVIEW
    assert res.mandatory_manual_review_count == 1
    assert "C2" in res.explanation["review_mandatory_criteria"]


def test_optional_failure_does_not_disqualify_bidder():
    """An optional criterion failing does NOT produce NOT_ELIGIBLE overall."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C2", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C3", RequirementType.OPTIONAL, False, EvaluationResult.NOT_ELIGIBLE),
    ]
    res = aggregate_criteria_results(criteria)
    assert res.overall_result == EvaluationResult.ELIGIBLE
    assert res.optional_not_eligible_count == 1
    assert res.optional_eligible_count == 0
    assert res.mandatory_eligible_count == 2


def test_optional_manual_review_does_not_force_overall_review():
    """An optional criterion under review does NOT produce MANUAL_REVIEW overall."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C2", RequirementType.OPTIONAL, False, EvaluationResult.MANUAL_REVIEW),
    ]
    res = aggregate_criteria_results(criteria)
    assert res.overall_result == EvaluationResult.ELIGIBLE
    assert res.optional_manual_review_count == 1
    assert res.mandatory_eligible_count == 1


def test_missing_mandatory_evaluation_routes_to_manual_review():
    """Un-evaluated mandatory criterion safely routes to MANUAL_REVIEW."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C2", RequirementType.MANDATORY, True, EvaluationResult.MANUAL_REVIEW, has_evaluation=False),
    ]
    res = aggregate_criteria_results(criteria)
    assert res.overall_result == EvaluationResult.MANUAL_REVIEW
    assert res.mandatory_manual_review_count == 1


def test_empty_criteria_list_routes_to_manual_review():
    """Zero approved criteria gracefully routes to MANUAL_REVIEW."""
    res = aggregate_criteria_results([])
    assert res.overall_result == EvaluationResult.MANUAL_REVIEW
    assert res.criterion_count == 0


def test_aggregation_determinism_across_100_runs():
    """Verify zero variance in output given identical input criteria."""
    criteria = [
        _make_criterion("C1", RequirementType.MANDATORY, True, EvaluationResult.ELIGIBLE),
        _make_criterion("C2", RequirementType.MANDATORY, True, EvaluationResult.NOT_ELIGIBLE),
        _make_criterion("C3", RequirementType.OPTIONAL, False, EvaluationResult.MANUAL_REVIEW),
    ]
    baseline = aggregate_criteria_results(criteria)

    for _ in range(100):
        run_res = aggregate_criteria_results(criteria)
        assert run_res.overall_result == baseline.overall_result
        assert run_res.criterion_count == baseline.criterion_count
        assert run_res.mandatory_not_eligible_count == baseline.mandatory_not_eligible_count
        assert run_res.explanation == baseline.explanation
