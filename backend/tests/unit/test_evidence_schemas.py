"""Unit tests for Phase 9 schemas and validation."""

import pytest
from pydantic import ValidationError
from app.db.models.evidence import EvidenceStatus
from app.evidence.schemas import (
    BidderCreate,
    BidSubmissionCreate,
    RawEvidenceItem,
    RawEvidenceExtractionResponse,
    CertificateDetailsRaw,
    ExperienceDetailsRaw,
)


def test_bidder_create_schema_valid():
    """Test valid BidderCreate payload."""
    payload = BidderCreate(
        bidder_code="BIDDER-101",
        legal_name="Bharat Heavy Dynamics Private Limited",
        contact_email="procurement@bhdynamics.in",
        contact_phone="+91-9876543210",
    )
    assert payload.bidder_code == "BIDDER-101"
    assert payload.legal_name == "Bharat Heavy Dynamics Private Limited"


def test_bidder_create_schema_short_name_rejected():
    """Test invalid short bidder legal name rejected."""
    with pytest.raises(ValidationError):
        BidderCreate(
            bidder_code="B1",
            legal_name="X",
        )


def test_bid_submission_create_schema():
    """Test valid BidSubmissionCreate payload."""
    payload = BidSubmissionCreate(submission_reference="SUB-2026-CRPF-001")
    assert payload.submission_reference == "SUB-2026-CRPF-001"


def test_raw_evidence_item_schema_and_status_bounds():
    """Test RawEvidenceItem validation and confidence bounds."""
    item = RawEvidenceItem(
        criterion_code="FIN-001",
        evidence_found=True,
        evidence_type="FINANCIAL",
        extracted_text="Average annual turnover is Rs. 15 Crore",
        extracted_value=15.0,
        unit="Crore",
        currency="INR",
        status=EvidenceStatus.FOUND,
        confidence=0.95,
        source_page=1,
    )
    assert item.extracted_value == 15.0
    assert item.status == EvidenceStatus.FOUND

    # Confidence out of bounds
    with pytest.raises(ValidationError):
        RawEvidenceItem(
            criterion_code="FIN-001",
            evidence_found=True,
            confidence=1.5,
        )


def test_raw_evidence_extraction_response_serialization():
    """Test full RawEvidenceExtractionResponse parsing."""
    resp = RawEvidenceExtractionResponse(
        extracted_items=[
            RawEvidenceItem(
                criterion_code="CERT-001",
                evidence_found=True,
                evidence_type="CERTIFICATE",
                certificate_data=CertificateDetailsRaw(
                    certificate_name="ISO 9001:2015",
                    certificate_number="ISO-CRPF-991",
                    issuing_authority="BIS",
                ),
                confidence=0.9,
            )
        ]
    )
    assert len(resp.extracted_items) == 1
    assert resp.extracted_items[0].certificate_data.certificate_name == "ISO 9001:2015"
