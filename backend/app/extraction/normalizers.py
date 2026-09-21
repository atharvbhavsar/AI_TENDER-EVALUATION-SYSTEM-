"""Normalization utilities for tender thresholds, units, currencies, and operators."""

import re
from typing import Optional, Tuple


def normalize_operator(raw_text: str | None) -> Optional[str]:
    """Map natural language relational operators to standardized symbols."""
    if not raw_text:
        return None
    
    clean = raw_text.strip().lower()
    if clean in [">=", "≥", "at least", "minimum", "not less than", "equal to or greater than", "greater than or equal to"]:
        return ">="
    if clean in [">", "greater than", "more than", "strictly greater than"]:
        return ">"
    if clean in ["<=", "≤", "at most", "maximum", "not more than", "not exceeding", "less than or equal to"]:
        return "<="
    if clean in ["<", "less than", "strictly less than"]:
        return "<"
    if clean in ["=", "==", "equal to", "exact", "exactly"]:
        return "="
    if clean in ["exists", "must have", "required", "mandatory", "possess"]:
        return "EXISTS"
    
    return None


def normalize_currency(raw_text: str | None) -> Optional[str]:
    """Detect and normalize standard ISO currency codes with word boundary precision."""
    if not raw_text:
        return None
    
    clean = raw_text.strip()
    if re.search(r"(?:₹|\bINR\b|\bRS\b|\bRS\.\b|\bRUPEES?\b)", clean, re.IGNORECASE):
        return "INR"
    if re.search(r"(?:\$|\bUSD\b|\bDOLLARS?\b)", clean, re.IGNORECASE):
        return "USD"
    if re.search(r"(?:€|\bEUR\b|\bEUROS?\b)", clean, re.IGNORECASE):
        return "EUR"
    if re.search(r"(?:£|\bGBP\b|\bPOUNDS?\b)", clean, re.IGNORECASE):
        return "GBP"
    
    return None


def normalize_numeric_threshold(raw_text: str | None) -> Tuple[Optional[float], Optional[str], Optional[str]]:
    """
    Parse monetary and numeric expressions to (numeric_value, currency, unit).
    Handles Indian numbering (Crore, Lakh) and Western numbering (Million, Billion).
    Preserves exact string format in caller.
    """
    if not raw_text:
        return None, None, None

    text = raw_text.strip()
    currency = normalize_currency(text)

    # Clean text to isolate numbers and units
    # Match patterns like "₹5 Crore", "50 Lakhs", "10,00,000", "5.5 Million", "3 years"
    match = re.search(r"([\d,]+(?:\.\d+)?)\s*(crores?|cr|lakhs?|lac|lacs?|millions?|m|billions?|b|k|thousand|years?|projects?|months?|%)?", text, re.IGNORECASE)
    if not match:
        return None, currency, None

    num_str = match.group(1).replace(",", "")
    unit_str = (match.group(2) or "").lower()

    try:
        val = float(num_str)
    except ValueError:
        return None, currency, None

    detected_unit = None
    if unit_str in ["crore", "crores", "cr"]:
        val = val * 10_000_000
        detected_unit = "INR" if currency == "INR" else "Crore"
    elif unit_str in ["lakh", "lakhs", "lac", "lacs"]:
        val = val * 100_000
        detected_unit = "INR" if currency == "INR" else "Lakh"
    elif unit_str in ["million", "millions", "m"]:
        val = val * 1_000_000
        detected_unit = "Million"
    elif unit_str in ["billion", "billions", "b"]:
        val = val * 1_000_000_000
        detected_unit = "Billion"
    elif unit_str in ["k", "thousand"]:
        val = val * 1_000
        detected_unit = "Thousand"
    elif "year" in unit_str:
        detected_unit = "Years"
    elif "project" in unit_str:
        detected_unit = "Projects"
    elif "month" in unit_str:
        detected_unit = "Months"
    elif "%" in unit_str:
        detected_unit = "Percentage"
    elif currency:
        detected_unit = currency

    return val, currency, detected_unit
