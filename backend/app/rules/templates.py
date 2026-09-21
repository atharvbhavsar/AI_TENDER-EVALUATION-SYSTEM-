"""Rule template builders and inference engine for approved tender criteria."""

import re
from typing import Any, Dict, Optional, Tuple
from app.db.models.criterion_rule import RuleType
from app.db.models.tender_criterion import CriterionCategory, TenderCriterion
from app.rules.normalizers import standardize_currency_code


def infer_rule_template_from_criterion(criterion: TenderCriterion) -> Tuple[RuleType, Dict[str, Any]]:
    """
    Infer deterministic rule template and configuration from an approved tender criterion.
    Never invents arbitrary logic; if criteria cannot be deterministically mapped, returns UNSUPPORTED.
    """
    name_upper = (criterion.name or "").upper()
    desc_upper = (criterion.description or "").upper()
    clause_upper = (criterion.source_clause or "").upper()

    # 1. Financial or numeric threshold
    if criterion.threshold_value is not None and (
        criterion.category == CriterionCategory.FINANCIAL
        or criterion.currency is not None
        or any(w in name_upper for w in ["TURNOVER", "REVENUE", "NET WORTH", "NETWORTH", "SOLVENCY"])
    ):
        return (
            RuleType.NUMERIC_THRESHOLD,
            {
                "operator": criterion.operator or ">=",
                "threshold": float(criterion.threshold_value),
                "unit": criterion.unit or "CRORE",
                "currency": standardize_currency_code(criterion.currency) or "INR",
                "min_confidence": 0.70,
            },
        )

    # 2. Experience count
    if (
        any(w in name_upper for w in ["EXPERIENCE", "ASSIGNMENT", "PROJECT", "CONTRACT"])
        and criterion.threshold_value is not None
    ):
        return (
            RuleType.EXPERIENCE_COUNT,
            {
                "min_count": int(criterion.threshold_value),
                "min_confidence": 0.70,
            },
        )

    # 3. Certifications (e.g. ISO 9001, ISO 27001)
    if criterion.category == CriterionCategory.CERTIFICATION or "ISO" in name_upper or "CERTIF" in name_upper:
        cert_match = re.search(r"(ISO\s*\d+(?::\d+)?)", name_upper + " " + desc_upper)
        cert_name = cert_match.group(1) if cert_match else criterion.name
        return (
            RuleType.CERTIFICATE_EXISTENCE,
            {
                "certificate_type": cert_name,
                "min_confidence": 0.70,
            },
        )

    # 4. Statutory Registration
    if any(w in name_upper for w in ["REGISTRATION", "GST", "PAN", "EPFO", "ESIC"]):
        return (
            RuleType.REGISTRATION_VALIDITY,
            {
                "reference_date": "2026-01-01",  # Configured tender reference date
                "min_confidence": 0.70,
            },
        )

    # 5. General Boolean Compliance
    if criterion.category == CriterionCategory.COMPLIANCE or "DECLARATION" in name_upper or "UNDERTAKING" in name_upper:
        return (
            RuleType.BOOLEAN_COMPLIANCE,
            {
                "required_value": True,
                "min_confidence": 0.70,
            },
        )

    # 6. Fallback if threshold is specified
    if criterion.threshold_value is not None and criterion.operator:
        return (
            RuleType.NUMERIC_THRESHOLD,
            {
                "operator": criterion.operator,
                "threshold": float(criterion.threshold_value),
                "unit": criterion.unit,
                "currency": standardize_currency_code(criterion.currency),
                "min_confidence": 0.70,
            },
        )

    # 7. Unsupported template fallback -> routes safely to MANUAL_REVIEW
    return (
        RuleType.UNSUPPORTED,
        {
            "reason": "Criterion requires manual human review and discretionary evaluation",
        },
    )
