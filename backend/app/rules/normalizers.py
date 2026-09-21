"""Deterministic unit and value normalizers for Phase 11 rule evaluation."""

import re
from typing import Optional, Tuple

UNIT_SCALES = {
    "CRORE": 10_000_000.0,
    "CR": 10_000_000.0,
    "LAKH": 100_000.0,
    "LAC": 100_000.0,
    "MILLION": 1_000_000.0,
    "BILLION": 1_000_000_000.0,
    "THOUSAND": 1_000.0,
    "K": 1_000.0,
    "INR": 1.0,
    "RUPEE": 1.0,
    "RUPEES": 1.0,
    "RS": 1.0,
}


def normalize_numeric_amount_to_base(
    value: float,
    unit: Optional[str] = None,
) -> float:
    """Normalize amounts expressed in Crore, Lakh, etc. to absolute base units."""
    if not unit:
        return value
    clean_unit = unit.upper().strip()
    multiplier = UNIT_SCALES.get(clean_unit, 1.0)
    return value * multiplier


def standardize_currency_code(currency: Optional[str]) -> Optional[str]:
    """Standardize currency codes to ISO-4217 representations."""
    if not currency:
        return None
    c = currency.upper().strip()
    if c in ("INR", "RS", "RUPEE", "RUPEES", "₹"):
        return "INR"
    if c in ("USD", "$", "DOLLAR", "DOLLARS"):
        return "USD"
    if c in ("EUR", "€", "EURO", "EUROS"):
        return "EUR"
    if c in ("GBP", "£", "POUND", "POUNDS"):
        return "GBP"
    return c
