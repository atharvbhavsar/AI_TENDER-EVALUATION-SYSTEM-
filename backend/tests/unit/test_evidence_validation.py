"""Unit tests for evidence citation validation and conflict detection."""

import uuid
import pytest
from app.db.models.evidence import EvidenceStatus
from app.evidence.schemas import RawEvidenceItem
from app.evidence.validation import (
    detect_evidence_conflicts,
    normalize_bidder_legal_name,
    validate_evidence_source_citations,
)
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument


def test_normalize_bidder_legal_name():
    """Test standardizing company legal names and suffixes."""
    assert normalize_bidder_legal_name("  ABC Corp Pvt Ltd  ") == "ABC Corp Private Limited"
    assert normalize_bidder_legal_name("Tata Advanced Systems Limited") == "Tata Advanced Systems Limited"
    assert normalize_bidder_legal_name("Apex Defense Solutions LLP") == "Apex Defense Solutions LLP"
    assert normalize_bidder_legal_name(None) is None


def test_validate_evidence_source_citations_valid():
    """Test citation validation passes when page and block exist."""
    norm_doc = NormalizedDocument(
        document_id=uuid.uuid4(),
        document_type="DIGITAL_PDF",
        processor_version="v1.0",
        page_count=3,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[DocumentBlock(block_id="b-1", type=BlockType.TEXT, text="Sample")],
            )
        ],
    )
    item = RawEvidenceItem(
        criterion_code="FIN-001",
        evidence_found=True,
        confidence=0.9,
        source_page=1,
        source_block_id="b-1",
    )
    status_out, note = validate_evidence_source_citations(item, norm_doc)
    assert status_out == EvidenceStatus.FOUND
    assert note is None


def test_validate_evidence_source_citations_hallucinated_block_marked_invalid():
    """Test citation validation marks hallucinated block_id as INVALID."""
    norm_doc = NormalizedDocument(
        document_id=uuid.uuid4(),
        document_type="DIGITAL_PDF",
        processor_version="v1.0",
        page_count=2,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[DocumentBlock(block_id="b-1", type=BlockType.TEXT, text="Sample")],
            )
        ],
    )
    # Fabricated block ID
    item = RawEvidenceItem(
        criterion_code="FIN-001",
        evidence_found=True,
        confidence=0.9,
        source_page=1,
        source_block_id="nonexistent-block-999",
    )
    status_out, note = validate_evidence_source_citations(item, norm_doc)
    assert status_out == EvidenceStatus.INVALID
    assert "does not exist" in note


def test_detect_evidence_conflicts():
    """Test conflict detection flags differing numeric values for the same criterion."""
    items = [
        RawEvidenceItem(
            criterion_code="FIN-001",
            evidence_found=True,
            extracted_value=15.0,
            confidence=0.9,
            status=EvidenceStatus.FOUND,
        ),
        RawEvidenceItem(
            criterion_code="FIN-001",
            evidence_found=True,
            extracted_value=10.0,
            confidence=0.9,
            status=EvidenceStatus.FOUND,
        ),
    ]
    resolved = detect_evidence_conflicts(items)
    assert resolved[0].status == EvidenceStatus.CONFLICTING
    assert resolved[1].status == EvidenceStatus.CONFLICTING
    assert "Conflicting numeric evidence" in resolved[0].ambiguity_reason
