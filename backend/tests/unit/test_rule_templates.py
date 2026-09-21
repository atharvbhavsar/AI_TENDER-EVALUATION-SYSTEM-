"""Unit tests for Phase 11 rule template inference engine."""

import uuid
import pytest
from app.db.models.criterion_rule import RuleType
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    RequirementType,
    TenderCriterion,
)
from app.rules.templates import infer_rule_template_from_criterion


def test_infer_numeric_threshold_rule():
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=uuid.uuid4(),
        criterion_code="FIN-001",
        name="Average Annual Financial Turnover",
        description="Average annual turnover must exceed Rs 10 Crore",
        source_clause="Clause 3.1",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=10.0,
        unit="CRORE",
        currency="INR",
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
    )

    rule_type, config = infer_rule_template_from_criterion(crit)
    assert rule_type == RuleType.NUMERIC_THRESHOLD
    assert config["operator"] == ">="
    assert config["threshold"] == 10.0
    assert config["unit"] == "CRORE"
    assert config["currency"] == "INR"


def test_infer_experience_count_rule():
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=uuid.uuid4(),
        criterion_code="EXP-001",
        name="Past Technical Experience Projects",
        description="Bidder must have completed at least 3 major projects",
        source_clause="Clause 4.2",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        threshold_value=3.0,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
    )

    rule_type, config = infer_rule_template_from_criterion(crit)
    assert rule_type == RuleType.EXPERIENCE_COUNT
    assert config["min_count"] == 3


def test_infer_certificate_existence_rule():
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=uuid.uuid4(),
        criterion_code="CERT-001",
        name="ISO 9001:2015 Quality Management Certification",
        description="Must hold valid ISO 9001:2015 certification",
        source_clause="Clause 5.1",
        category=CriterionCategory.CERTIFICATION,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
    )

    rule_type, config = infer_rule_template_from_criterion(crit)
    assert rule_type == RuleType.CERTIFICATE_EXISTENCE
    assert "ISO 9001" in config["certificate_type"]


def test_infer_unsupported_rule():
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=uuid.uuid4(),
        criterion_code="MISC-001",
        name="Reputation and Stakeholder Standing",
        description="Bidder should enjoy positive market standing and good goodwill",
        source_clause="Clause 9.0",
        category=CriterionCategory.DOCUMENT_REQUIREMENT,
        requirement_type=RequirementType.OPTIONAL,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
    )

    rule_type, config = infer_rule_template_from_criterion(crit)
    assert rule_type == RuleType.UNSUPPORTED
    assert "manual human review" in config["reason"].lower()
