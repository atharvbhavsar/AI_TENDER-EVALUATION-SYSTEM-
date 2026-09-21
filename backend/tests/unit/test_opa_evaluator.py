"""Unit tests for deterministic LocalRegoEvaluator engine."""

import pytest
from app.db.models.criterion_evaluation import EvaluationResult
from app.rules.opa.evaluator import LocalRegoEvaluator


def test_numeric_threshold_eligible():
    inp = {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "unit": "CRORE",
            "currency": "INR",
            "min_confidence": 0.70,
        },
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_value": 14.5,
            "unit": "CRORE",
            "currency": "INR",
            "confidence": 0.95,
        }],
    }
    out = LocalRegoEvaluator.evaluate(inp)
    assert out["result"] == EvaluationResult.ELIGIBLE.value
    assert "14.5 >= 10.0" in out["explanation"]["reason"]


def test_numeric_threshold_not_eligible():
    inp = {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "unit": "CRORE",
            "currency": "INR",
            "min_confidence": 0.70,
        },
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_value": 8.5,
            "unit": "CRORE",
            "currency": "INR",
            "confidence": 0.95,
        }],
    }
    out = LocalRegoEvaluator.evaluate(inp)
    assert out["result"] == EvaluationResult.NOT_ELIGIBLE.value


def test_currency_mismatch_routes_to_manual_review():
    inp = {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "unit": "CRORE",
            "currency": "INR",
        },
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_value": 14.5,
            "unit": "CRORE",
            "currency": "USD",  # Mismatched currency
            "confidence": 0.95,
        }],
    }
    out = LocalRegoEvaluator.evaluate(inp)
    assert out["result"] == EvaluationResult.MANUAL_REVIEW.value
    assert "Currency mismatch" in out["explanation"]["reason"]


def test_experience_count_evaluation():
    inp_eligible = {
        "rule": {
            "rule_type": "EXPERIENCE_COUNT",
            "min_count": 3,
            "min_confidence": 0.70,
        },
        "evidence": [
            {"id": "e1", "status": "FOUND", "confidence": 0.9},
            {"id": "e2", "status": "FOUND", "confidence": 0.9},
            {"id": "e3", "status": "FOUND", "confidence": 0.9},
        ],
    }
    assert LocalRegoEvaluator.evaluate(inp_eligible)["result"] == EvaluationResult.ELIGIBLE.value

    inp_not_eligible = {
        "rule": {
            "rule_type": "EXPERIENCE_COUNT",
            "min_count": 3,
            "min_confidence": 0.70,
        },
        "evidence": [
            {"id": "e1", "status": "FOUND", "confidence": 0.9},
            {"id": "e2", "status": "FOUND", "confidence": 0.9},
        ],
    }
    assert LocalRegoEvaluator.evaluate(inp_not_eligible)["result"] == EvaluationResult.NOT_ELIGIBLE.value


def test_date_validity_evaluation():
    # Valid date
    inp_valid = {
        "rule": {
            "rule_type": "DATE_VALIDITY",
            "reference_date": "2026-01-01",
        },
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "certificate_data": {
                "issue_date": "2023-01-01",
                "expiry_date": "2027-01-01",
            },
            "confidence": 0.9,
        }],
    }
    assert LocalRegoEvaluator.evaluate(inp_valid)["result"] == EvaluationResult.ELIGIBLE.value

    # Expired date
    inp_expired = {
        "rule": {
            "rule_type": "DATE_VALIDITY",
            "reference_date": "2026-01-01",
        },
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "certificate_data": {
                "issue_date": "2020-01-01",
                "expiry_date": "2025-01-01",
            },
            "confidence": 0.9,
        }],
    }
    assert LocalRegoEvaluator.evaluate(inp_expired)["result"] == EvaluationResult.NOT_ELIGIBLE.value


def test_conflicting_and_uncertain_evidence_routes_to_manual_review():
    for uncertain_status in ["CONFLICTING", "UNREADABLE", "AMBIGUOUS", "INVALID", "MISSING"]:
        inp = {
            "rule": {
                "rule_type": "NUMERIC_THRESHOLD",
                "operator": ">=",
                "threshold": 10.0,
            },
            "evidence": [{
                "id": "e1",
                "status": uncertain_status,
                "confidence": 0.9,
            }],
        }
        out = LocalRegoEvaluator.evaluate(inp)
        assert out["result"] == EvaluationResult.MANUAL_REVIEW.value


def test_low_confidence_routes_to_manual_review():
    inp = {
        "rule": {
            "rule_type": "NUMERIC_THRESHOLD",
            "operator": ">=",
            "threshold": 10.0,
            "min_confidence": 0.80,
        },
        "evidence": [{
            "id": "e1",
            "status": "FOUND",
            "extracted_value": 15.0,
            "confidence": 0.65,  # Below min_confidence
        }],
    }
    out = LocalRegoEvaluator.evaluate(inp)
    assert out["result"] == EvaluationResult.MANUAL_REVIEW.value
    assert "below minimum threshold" in out["explanation"]["reason"]
