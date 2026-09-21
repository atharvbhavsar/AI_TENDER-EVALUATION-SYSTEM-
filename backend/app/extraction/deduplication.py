"""Deduplication and criterion code generation logic for tender versions."""

from typing import Dict, List
from app.db.models.tender_criterion import CriterionCategory
from app.extraction.schemas import ExtractedCriterionRaw

CATEGORY_PREFIX_MAP: Dict[CriterionCategory, str] = {
    CriterionCategory.FINANCIAL: "FIN",
    CriterionCategory.TECHNICAL: "TECH",
    CriterionCategory.COMPLIANCE: "COMP",
    CriterionCategory.CERTIFICATION: "CERT",
    CriterionCategory.DOCUMENT_REQUIREMENT: "DOC",
}


def generate_criterion_code(category: CriterionCategory, index: int) -> str:
    """Generate standardized, human-readable criterion code e.g. FIN-001."""
    prefix = CATEGORY_PREFIX_MAP.get(category, "CRIT")
    return f"{prefix}-{index:03d}"


def consolidate_candidate_criteria(
    raw_candidates: List[ExtractedCriterionRaw],
) -> List[ExtractedCriterionRaw]:
    """
    Consolidate candidate criteria extracted across multiple chunks.
    If the exact same criterion (name + category + threshold + source_clause) appears across chunks,
    consolidate its source references while preserving distinct requirements.
    """
    consolidated: List[ExtractedCriterionRaw] = []
    seen_signatures: Dict[str, ExtractedCriterionRaw] = {}

    for cand in raw_candidates:
        sig = f"{cand.category}:{cand.name.strip().lower()}:{cand.threshold_value}:{cand.source_clause.strip().lower()}"
        
        if sig in seen_signatures:
            existing = seen_signatures[sig]
            # Consolidate evidence lists if complementary
            if cand.required_evidence and existing.required_evidence:
                merged_evidence = list(dict.fromkeys(existing.required_evidence + cand.required_evidence))
                existing.required_evidence = merged_evidence
            elif cand.required_evidence and not existing.required_evidence:
                existing.required_evidence = cand.required_evidence
        else:
            seen_signatures[sig] = cand
            consolidated.append(cand)

    return consolidated
