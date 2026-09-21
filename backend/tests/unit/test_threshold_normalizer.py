"""Unit tests for threshold, unit, currency, and operator normalizers."""

from app.extraction.normalizers import (
    normalize_currency,
    normalize_numeric_threshold,
    normalize_operator,
)


def test_normalize_operator():
    """Test standard relational operator mappings."""
    assert normalize_operator("at least") == ">="
    assert normalize_operator("minimum") == ">="
    assert normalize_operator("not less than") == ">="
    assert normalize_operator("≥") == ">="
    assert normalize_operator(">=") == ">="
    
    assert normalize_operator("at most") == "<="
    assert normalize_operator("maximum") == "<="
    assert normalize_operator("not exceeding") == "<="
    assert normalize_operator("≤") == "<="
    
    assert normalize_operator("greater than") == ">"
    assert normalize_operator("less than") == "<"
    assert normalize_operator("exact") == "="
    assert normalize_operator("must have") == "EXISTS"
    assert normalize_operator(None) is None
    assert normalize_operator("arbitrary words") is None


def test_normalize_currency():
    """Test ISO currency normalization."""
    assert normalize_currency("₹5 Crore") == "INR"
    assert normalize_currency("INR 50,00,000") == "INR"
    assert normalize_currency("Rs. 10 Lakh") == "INR"
    assert normalize_currency("$ 2 Million") == "USD"
    assert normalize_currency("USD 100,000") == "USD"
    assert normalize_currency("€ 50,000") == "EUR"
    assert normalize_currency("£ 10,000") == "GBP"
    assert normalize_currency("No currency mentioned") is None


def test_normalize_numeric_threshold_indian_numbering():
    """Test parsing Indian numbering system (Crores, Lakhs)."""
    # ₹5 Crore -> 50,000,000
    val, curr, unit = normalize_numeric_threshold("₹5 Crore")
    assert val == 50000000.0
    assert curr == "INR"
    assert unit == "INR"

    # 50 Lakhs -> 5,000,000
    val, curr, unit = normalize_numeric_threshold("50 Lakhs")
    assert val == 5000000.0

    # 2.5 Cr -> 25,000,000
    val, curr, unit = normalize_numeric_threshold("₹ 2.5 Cr")
    assert val == 25000000.0
    assert curr == "INR"


def test_normalize_numeric_threshold_western_numbering():
    """Test parsing Western numbering system (Millions, Billions, Thousands)."""
    val, curr, unit = normalize_numeric_threshold("$ 2 Million")
    assert val == 2000000.0
    assert curr == "USD"
    assert unit == "Million"

    val, curr, unit = normalize_numeric_threshold("100 Thousand")
    assert val == 100000.0


def test_normalize_numeric_threshold_units_and_counts():
    """Test non-currency numeric units (Years, Projects, Percentages)."""
    val, curr, unit = normalize_numeric_threshold("3 years")
    assert val == 3.0
    assert curr is None
    assert unit == "Years"

    val, curr, unit = normalize_numeric_threshold("5 projects")
    assert val == 5.0
    assert unit == "Projects"

    val, curr, unit = normalize_numeric_threshold("25 %")
    assert val == 25.0
    assert unit == "Percentage"
