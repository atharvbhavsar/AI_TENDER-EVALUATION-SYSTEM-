"""Unit tests for Phase 11 deterministic unit and currency normalizers."""

import pytest
from app.rules.normalizers import (
    normalize_numeric_amount_to_base,
    standardize_currency_code,
)


def test_normalize_numeric_amount_indian_numbering():
    # 10 Crore = 100,000,000
    assert normalize_numeric_amount_to_base(10.0, "CRORE") == 100_000_000.0
    assert normalize_numeric_amount_to_base(14.5, "Cr") == 145_000_000.0

    # 50 Lakh = 5,000,000
    assert normalize_numeric_amount_to_base(50.0, "LAKH") == 5_000_000.0
    assert normalize_numeric_amount_to_base(25.0, "Lac") == 2_500_000.0


def test_normalize_numeric_amount_western_units():
    # 5 Million = 5,000,000
    assert normalize_numeric_amount_to_base(5.0, "MILLION") == 5_000_000.0
    # 1 Billion = 1,000,000,000
    assert normalize_numeric_amount_to_base(1.0, "BILLION") == 1_000_000_000.0


def test_normalize_numeric_amount_no_unit():
    assert normalize_numeric_amount_to_base(500.0, None) == 500.0
    assert normalize_numeric_amount_to_base(100.0, "UNKNOWN") == 100.0


def test_standardize_currency_code():
    assert standardize_currency_code("INR") == "INR"
    assert standardize_currency_code("₹") == "INR"
    assert standardize_currency_code("Rupees") == "INR"
    assert standardize_currency_code("USD") == "USD"
    assert standardize_currency_code("$") == "USD"
    assert standardize_currency_code("EUR") == "EUR"
    assert standardize_currency_code("€") == "EUR"
    assert standardize_currency_code(None) is None
