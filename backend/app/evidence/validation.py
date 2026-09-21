"""Evidence-level validation, source attribution checking, and conflict detection."""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple
from app.db.models.evidence import EvidenceStatus
from app.evidence.schemas import RawEvidenceItem
from app.pipeline.schemas import NormalizedDocument

logger = logging.getLogger("app.evidence.validation")


def normalize_bidder_legal_name(name: Optional[str]) -> Optional[str]:
    """
    Standardize bidder company name for comparative matching:
    - Normalizes whitespace and casing
    - Standardizes legal entity suffixes (e.g. 'Pvt. Ltd.' -> 'Private Limited')
    """
    if not name:
        return None
    cleaned = re.sub(r"[^\w\s.]", "", name.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)

    # Standardize common legal suffixes
    cleaned = re.sub(r"\bpvt\.?\s*ltd\.?\b", "Private Limited", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpvt\s+limited\b", "Private Limited", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bltd\.?\b", "Limited", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bllp\b", "LLP", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def validate_evidence_source_citations(
    item: RawEvidenceItem,
    normalized_doc: Optional[NormalizedDocument],
) -> Tuple[EvidenceStatus, Optional[str]]:
    """
    Verify that cited source_page and source_block_id actually exist in the processed document artifact.
    If hallucinated or non-existent, transitions status to INVALID.
    """
    if item.status in (EvidenceStatus.MISSING, EvidenceStatus.UNREADABLE):
        return item.status, item.ambiguity_reason

    if not normalized_doc:
        return item.status, None

    # Check page existence
    if item.source_page is not None:
        if item.source_page < 1 or item.source_page > normalized_doc.page_count:
            return EvidenceStatus.INVALID, f"Cited source_page {item.source_page} exceeds document page count {normalized_doc.page_count}."

    # Check block_id existence if provided
    if item.source_block_id is not None:
        valid_block_ids: Set[str] = {
            block.block_id
            for page in normalized_doc.pages
            for block in page.blocks
        }
        if item.source_block_id not in valid_block_ids:
            return EvidenceStatus.INVALID, f"Cited source_block_id '{item.source_block_id}' does not exist in processed document artifact."

    return item.status, None


def detect_evidence_conflicts(
    evidence_items: List[RawEvidenceItem],
) -> List[RawEvidenceItem]:
    """
    Detect conflicting numeric values or certificates across multiple evidence items targeting the same criterion.
    Does not pick a winner; updates conflicting items to status CONFLICTING with notes.
    """
    # Group items by criterion_code
    grouped: Dict[str, List[RawEvidenceItem]] = {}
    for it in evidence_items:
        grouped.setdefault(it.criterion_code, []).append(it)

    for code, items in grouped.items():
        # Check numeric conflicts
        numeric_items = [
            it for it in items
            if it.extracted_value is not None and it.status == EvidenceStatus.FOUND
        ]
        if len(numeric_items) > 1:
            values = {it.extracted_value for it in numeric_items}
            if len(values) > 1:
                val_list_str = ", ".join(str(v) for v in values)
                for it in numeric_items:
                    it.status = EvidenceStatus.CONFLICTING
                    it.ambiguity_reason = (
                        f"Conflicting numeric evidence detected across documents: [{val_list_str}]."
                    )

    return evidence_items
