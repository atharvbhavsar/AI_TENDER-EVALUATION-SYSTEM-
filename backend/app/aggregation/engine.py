"""Deterministic aggregation engine for bidder-level overall eligibility.

CRITICAL ARCHITECTURAL RULE:
No LLMs are involved in this aggregation. Aggregation is purely deterministic,
applying prioritized evaluation rules across mandatory and optional tender criteria.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.tender_criterion import RequirementType


@dataclass
class CriterionEvaluationInput:
    """Standardized representation of a single criterion evaluation for aggregation."""

    criterion_id: str
    criterion_code: str
    criterion_name: str
    requirement_type: RequirementType
    is_mandatory: bool
    result: EvaluationResult
    has_evaluation: bool = True
    evaluation_id: Optional[str] = None
    rule_version: Optional[str] = None
    explanation: Dict[str, Any] = field(default_factory=dict)
    evidence_ids: List[str] = field(default_factory=list)


@dataclass
class AggregationResult:
    """Immutable output produced by the deterministic aggregation engine."""

    overall_result: EvaluationResult
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
    rule_version_snapshot: Dict[str, Any]


def aggregate_criteria_results(
    criteria: List[CriterionEvaluationInput],
    policy_version: str = "v1.0",
) -> AggregationResult:
    """
    Deterministically aggregate criterion-level evaluation results into an overall verdict.

    Aggregation Rules:
    1. IF any mandatory criterion = NOT_ELIGIBLE -> overall NOT_ELIGIBLE
    2. ELSE IF any mandatory criterion = MANUAL_REVIEW (or missing evaluation) -> overall MANUAL_REVIEW
    3. ELSE IF all mandatory criteria = ELIGIBLE -> overall ELIGIBLE
    4. Optional criteria do NOT independently disqualify the bidder.
    """
    total_count = len(criteria)

    eligible_count = 0
    not_eligible_count = 0
    manual_review_count = 0

    mandatory_total = 0
    mandatory_eligible = 0
    mandatory_not_eligible = 0
    mandatory_manual_review = 0

    optional_total = 0
    optional_eligible = 0
    optional_not_eligible = 0
    optional_manual_review = 0

    failing_mandatory_codes: List[str] = []
    review_mandatory_codes: List[str] = []
    snapshot_items: List[Dict[str, Any]] = []

    for item in criteria:
        res = item.result
        # Update overall counts
        if res == EvaluationResult.ELIGIBLE:
            eligible_count += 1
        elif res == EvaluationResult.NOT_ELIGIBLE:
            not_eligible_count += 1
        else:
            manual_review_count += 1

        if item.is_mandatory:
            mandatory_total += 1
            if res == EvaluationResult.ELIGIBLE:
                mandatory_eligible += 1
            elif res == EvaluationResult.NOT_ELIGIBLE:
                mandatory_not_eligible += 1
                failing_mandatory_codes.append(item.criterion_code)
            else:
                mandatory_manual_review += 1
                review_mandatory_codes.append(item.criterion_code)
        else:
            optional_total += 1
            if res == EvaluationResult.ELIGIBLE:
                optional_eligible += 1
            elif res == EvaluationResult.NOT_ELIGIBLE:
                optional_not_eligible += 1
            else:
                optional_manual_review += 1

        snapshot_items.append({
            "criterion_id": item.criterion_id,
            "criterion_code": item.criterion_code,
            "criterion_name": item.criterion_name,
            "requirement_type": item.requirement_type.value if hasattr(item.requirement_type, "value") else str(item.requirement_type),
            "is_mandatory": item.is_mandatory,
            "result": res.value,
            "has_evaluation": item.has_evaluation,
            "evaluation_id": item.evaluation_id,
            "rule_version": item.rule_version,
            "evidence_ids": item.evidence_ids,
        })

    # Apply Priority Matrix
    if total_count == 0:
        overall_verdict = EvaluationResult.MANUAL_REVIEW
        summary_text = "No approved criteria were evaluated for this tender version."
        reasons = ["Zero approved criteria available for evaluation."]
    elif mandatory_not_eligible > 0:
        overall_verdict = EvaluationResult.NOT_ELIGIBLE
        summary_text = f"Bidder failed {mandatory_not_eligible} mandatory eligibility criteria: {', '.join(failing_mandatory_codes)}."
        reasons = [
            f"Mandatory criterion {code} evaluated to NOT_ELIGIBLE."
            for code in failing_mandatory_codes
        ]
    elif mandatory_manual_review > 0:
        overall_verdict = EvaluationResult.MANUAL_REVIEW
        summary_text = f"Bidder requires manual review on {mandatory_manual_review} mandatory criteria: {', '.join(review_mandatory_codes)}."
        reasons = [
            f"Mandatory criterion {code} requires manual review / has uncertain or missing evaluation."
            for code in review_mandatory_codes
        ]
    else:
        # All mandatory criteria passed (or no mandatory criteria exist)
        overall_verdict = EvaluationResult.ELIGIBLE
        summary_text = f"All {mandatory_eligible} mandatory criteria successfully satisfied."
        reasons = ["All mandatory criteria evaluated to ELIGIBLE."]
        if optional_not_eligible > 0 or optional_manual_review > 0:
            reasons.append(
                f"Note: {optional_not_eligible} optional criteria failed and {optional_manual_review} optional criteria require review, but do not disqualify the bidder."
            )

    structured_explanation = {
        "verdict": overall_verdict.value,
        "summary": summary_text,
        "reasons": reasons,
        "failing_mandatory_criteria": failing_mandatory_codes,
        "review_mandatory_criteria": review_mandatory_codes,
        "policy_version": policy_version,
    }

    snapshot = {
        "policy_version": policy_version,
        "total_criteria": total_count,
        "criteria": snapshot_items,
    }

    return AggregationResult(
        overall_result=overall_verdict,
        aggregation_policy_version=policy_version,
        criterion_count=total_count,
        eligible_count=eligible_count,
        not_eligible_count=not_eligible_count,
        manual_review_count=manual_review_count,
        mandatory_criterion_count=mandatory_total,
        mandatory_eligible_count=mandatory_eligible,
        mandatory_not_eligible_count=mandatory_not_eligible,
        mandatory_manual_review_count=mandatory_manual_review,
        optional_criterion_count=optional_total,
        optional_eligible_count=optional_eligible,
        optional_not_eligible_count=optional_not_eligible,
        optional_manual_review_count=optional_manual_review,
        explanation=structured_explanation,
        rule_version_snapshot=snapshot,
    )
