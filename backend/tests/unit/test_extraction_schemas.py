"""Unit tests for Phase 7 Pydantic schemas and taxonomy validation."""

import pytest
from pydantic import ValidationError

from app.db.models.tender_criterion import (
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
)
from app.extraction.schemas import (
    ExtractedCriterionRaw,
    ExtractedSourceRefRaw,
    RawExtractionResponse,
    TriggerExtractionRequest,
)


def test_extracted_criterion_raw_valid():
    """Test valid instantiation of ExtractedCriterionRaw."""
    raw = ExtractedCriterionRaw(
        name="Annual Turnover",
        description="Minimum average annual turnover for last 3 years.",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=50000000.0,
        threshold_text="₹5 Crore",
        unit="INR",
        currency="INR",
        period="preceding three financial years",
        mandatory=True,
        required_evidence=["Audited financial statements"],
        source_clause="Turnover shall be at least ₹5 Crore.",
        source_page=2,
        source_block_id="blk-5",
        confidence=0.95,
        extraction_status=ExtractionStatus.EXTRACTED,
    )
    assert raw.name == "Annual Turnover"
    assert raw.category == CriterionCategory.FINANCIAL
    assert raw.threshold_value == 50000000.0
    assert raw.confidence == 0.95


def test_extracted_criterion_invalid_category_rejected():
    """Test that arbitrary taxonomy categories are rejected by Pydantic."""
    with pytest.raises(ValidationError):
        ExtractedCriterionRaw(
            name="Custom Requirement",
            description="Arbitrary invalid category test",
            category="ARBITRARY_NON_TAXONOMY",  # type: ignore
            source_clause="Some clause text",
        )


def test_extracted_criterion_confidence_bounds():
    """Test confidence bounds validation [0.0, 1.0]."""
    with pytest.raises(ValidationError):
        ExtractedCriterionRaw(
            name="Turnover",
            description="Test",
            category=CriterionCategory.FINANCIAL,
            source_clause="Turnover clause",
            confidence=1.5,  # > 1.0
        )

    with pytest.raises(ValidationError):
        ExtractedCriterionRaw(
            name="Turnover",
            description="Test",
            category=CriterionCategory.FINANCIAL,
            source_clause="Turnover clause",
            confidence=-0.1,  # < 0.0
        )


def test_raw_extraction_response_serialization():
    """Test RawExtractionResponse serialization and deserialization."""
    resp = RawExtractionResponse(
        criteria=[
            ExtractedCriterionRaw(
                name="ISO 9001",
                description="Quality management certification",
                category=CriterionCategory.CERTIFICATION,
                requirement_type=RequirementType.MANDATORY,
                operator="EXISTS",
                source_clause="Bidder must possess valid ISO 9001.",
                source_page=1,
                confidence=0.92,
            )
        ]
    )
    data = resp.model_dump()
    assert len(data["criteria"]) == 1
    assert data["criteria"][0]["category"] == "CERTIFICATION"
    assert data["criteria"][0]["operator"] == "EXISTS"


def test_extracted_source_ref_raw():
    """Test source reference raw model."""
    ref = ExtractedSourceRefRaw(
        page_number=4,
        section="Section 4 - Technical Specs",
        block_id="blk-99",
        table_reference="tbl-1",
        source_text="Specific sub-clause text",
    )
    assert ref.page_number == 4
    assert ref.table_reference == "tbl-1"
