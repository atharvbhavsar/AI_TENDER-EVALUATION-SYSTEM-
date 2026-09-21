"""Unit tests for Criterion Rule schemas and input validation."""

import pytest
from pydantic import ValidationError

from app.db.models.criterion_rule import RuleType
from app.rules.schemas import RuleCreateRequest


def test_valid_numeric_threshold_rule_schema():
    req = RuleCreateRequest(
        rule_type=RuleType.NUMERIC_THRESHOLD,
        configuration={
            "field": "amount",
            "operator": ">=",
            "threshold": 50000000.0,
            "unit": "INR",
        },
    )
    assert req.rule_type == RuleType.NUMERIC_THRESHOLD
    assert req.configuration["operator"] == ">="
    assert req.configuration["threshold"] == 50000000.0


def test_invalid_rule_type():
    with pytest.raises(ValidationError):
        RuleCreateRequest(
            rule_type="INVALID_RULE_TYPE",
            configuration={},
        )
