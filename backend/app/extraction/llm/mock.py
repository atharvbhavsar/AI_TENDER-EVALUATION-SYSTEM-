"""Deterministic mock LLM provider for fast, reproducible automated testing."""

import logging
import re
from typing import List, Optional
from app.db.models.tender_criterion import (
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
)
from app.extraction.chunking import ExtractionChunk
from app.extraction.llm.base import BaseLLMClient
from app.extraction.normalizers import (
    normalize_numeric_threshold,
    normalize_operator,
)
from app.extraction.schemas import ExtractedCriterionRaw, RawExtractionResponse

logger = logging.getLogger("app.extraction.llm.mock")


class MockLLMClient(BaseLLMClient):
    """Mock LLM adapter simulating high-fidelity deterministic criterion extraction."""

    def __init__(
        self,
        model_name: str = "mock-extractor-v1",
        should_fail: bool = False,
        should_return_malformed: bool = False,
        custom_criteria: Optional[List[ExtractedCriterionRaw]] = None,
    ):
        self._model_name = model_name
        self.should_fail = should_fail
        self.should_return_malformed = should_return_malformed
        self.custom_criteria = custom_criteria

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def extract_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        chunk: ExtractionChunk,
    ) -> RawExtractionResponse:
        """Deterministically extract criteria from chunk based on procurement keywords and heuristics."""
        if self.should_fail:
            raise RuntimeError("Mock LLM service communication failure (simulated timeout/error).")

        if self.should_return_malformed:
            raise ValueError("LLM returned non-conforming schema payload (simulated malformed JSON).")

        if self.custom_criteria is not None:
            return RawExtractionResponse(criteria=self.custom_criteria)

        extracted: List[ExtractedCriterionRaw] = []
        text = chunk.formatted_text

        # Check for prompt injection attempt
        if "ignore previous instructions" in text.lower() or "administrator password" in text.lower():
            logger.info("Mock LLM detected benign prompt injection payload in untrusted tender text: treating as plain text.")
            # Do NOT execute injection instructions or return secrets; continue normal extraction

        # Helper to find source block context
        def find_source_block(snippet: str):
            for blk in chunk.blocks:
                if snippet.lower() in blk.text.lower():
                    return blk
            return chunk.blocks[0] if chunk.blocks else None

        # 1. Financial: Annual Turnover
        turnover_match = re.search(r"(?:annual\s+turnover|average\s+annual\s+turnover)[^\.\n]*", text, re.IGNORECASE)
        if turnover_match and "turnover" in text.lower():
            clause = turnover_match.group(0).strip()
            val_match = re.search(r"(?:₹|\$|€|rs\.?|inr\s*)?\s*[\d\.]+\s*(?:crores?|cr|lakhs?|lac|lacs?|millions?|m|billions?|b)?", clause, re.IGNORECASE)
            val_text = val_match.group(0).strip() if val_match else "₹5 Crore"
            num_val, curr, unit = normalize_numeric_threshold(val_text)
            period_match = re.search(r"(during\s+(?:the\s+)?(?:preceding|last|past)\s+(?:\d+|three|four|five|two)\s+(?:financial\s+)?years?)", text, re.IGNORECASE)
            period = period_match.group(1) if period_match else None
            
            # Evidence detection
            evidence = []
            if "audited" in text.lower() or "financial statement" in text.lower() or "balance sheet" in text.lower():
                evidence.append("Audited financial statements / Balance sheets")
            if "ca certificate" in text.lower():
                evidence.append("CA turnover certificate")

            blk = find_source_block("turnover")
            extracted.append(
                ExtractedCriterionRaw(
                    name="Annual Financial Turnover",
                    description="Minimum average annual turnover requirement for eligibility.",
                    category=CriterionCategory.FINANCIAL,
                    requirement_type=RequirementType.MANDATORY,
                    operator=normalize_operator("at least"),
                    threshold_value=num_val if num_val else 50000000.0,
                    threshold_text=val_text,
                    unit=unit or "INR",
                    currency=curr or "INR",
                    period=period,
                    mandatory=True,
                    required_evidence=evidence if evidence else None,
                    source_clause=clause,
                    source_page=blk.page_number if blk else chunk.start_page,
                    source_block_id=blk.block_id if blk else None,
                    source_table_reference=blk.table_reference if blk else None,
                    confidence=0.96,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    explanation="Explicit monetary turnover threshold stated in tender text.",
                )
            )

        # 2. Technical: Experience / Similar Projects
        exp_match = re.search(r"(?:completed|executed)[^\.\n]*?(\d+)\s*(?:similar\s+)?(?:projects?|works?|contracts?)[^\.\n]*", text, re.IGNORECASE)
        if exp_match or "similar project" in text.lower() or "technical experience" in text.lower():
            clause = exp_match.group(0).strip() if exp_match else "Bidder must possess past experience in executing similar works."
            period_match = re.search(r"(during\s+(?:the\s+)?(?:last|past)\s+\d+\s+years?)", text, re.IGNORECASE)
            period = period_match.group(1) if period_match else None
            
            evidence = []
            if "completion certificate" in text.lower():
                evidence.append("Work completion certificate")
            if "work order" in text.lower():
                evidence.append("Client work orders")

            blk = find_source_block("experience") or find_source_block("project")
            extracted.append(
                ExtractedCriterionRaw(
                    name="Past Project Experience",
                    description="Prior experience executing similar technical procurement contracts.",
                    category=CriterionCategory.TECHNICAL,
                    requirement_type=RequirementType.MANDATORY,
                    operator=">=",
                    threshold_value=float(exp_match.group(1)) if exp_match else 3.0,
                    threshold_text=f"{exp_match.group(1)} projects" if exp_match else "3 similar projects",
                    unit="Projects",
                    currency=None,
                    period=period,
                    mandatory=True,
                    required_evidence=evidence if evidence else None,
                    source_clause=clause,
                    source_page=blk.page_number if blk else chunk.start_page,
                    source_block_id=blk.block_id if blk else None,
                    source_table_reference=blk.table_reference if blk else None,
                    confidence=0.93,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    explanation="Technical experience clause identified.",
                )
            )

        # 3. Certification: ISO / CMMI / BIS
        iso_match = re.search(r"(ISO\s*(?:9001|27001|14001|45001)(?::\d{4})?)", text, re.IGNORECASE)
        if iso_match:
            iso_name = iso_match.group(1)
            clause_match = re.search(rf"[^\.\n]*?{re.escape(iso_name)}[^\.\n]*", text, re.IGNORECASE)
            clause = clause_match.group(0).strip() if clause_match else f"Bidder must have valid {iso_name} certification."
            
            evidence = [f"Valid {iso_name} Certificate copy"] if "certificate" in text.lower() or "copy" in text.lower() else None
            blk = find_source_block("iso") or find_source_block("certification")
            extracted.append(
                ExtractedCriterionRaw(
                    name=f"{iso_name} Quality Certification",
                    description=f"Requirement to possess a valid {iso_name} quality management certificate.",
                    category=CriterionCategory.CERTIFICATION,
                    requirement_type=RequirementType.MANDATORY,
                    operator="EXISTS",
                    threshold_value=None,
                    threshold_text=None,
                    unit=None,
                    currency=None,
                    period="Valid as on bid submission date" if "valid" in text.lower() else None,
                    mandatory=True,
                    required_evidence=evidence,
                    source_clause=clause,
                    source_page=blk.page_number if blk else chunk.start_page,
                    source_block_id=blk.block_id if blk else None,
                    source_table_reference=blk.table_reference if blk else None,
                    confidence=0.95,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    explanation="Explicit quality standard certification required.",
                )
            )

        # 4. Compliance: GST / PAN / Non-blacklisting
        if "gst" in text.lower() or "gstin" in text.lower():
            clause_match = re.search(r"[^\.\n]*?(?:gst|gstin)[^\.\n]*", text, re.IGNORECASE)
            clause = clause_match.group(0).strip() if clause_match else "Bidder must possess valid GST registration."
            blk = find_source_block("gst")
            extracted.append(
                ExtractedCriterionRaw(
                    name="GST Registration Compliance",
                    description="Bidder must be legally registered under Goods and Services Tax (GST).",
                    category=CriterionCategory.COMPLIANCE,
                    requirement_type=RequirementType.MANDATORY,
                    operator="EXISTS",
                    mandatory=True,
                    required_evidence=["GST Registration Certificate"] if "certificate" in text.lower() or "copy" in text.lower() else None,
                    source_clause=clause,
                    source_page=blk.page_number if blk else chunk.start_page,
                    source_block_id=blk.block_id if blk else None,
                    source_table_reference=blk.table_reference if blk else None,
                    confidence=0.97,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    explanation="Statutory tax compliance registration requirement.",
                )
            )

        # 5. Document Requirement: EMD / Bank Guarantee / Authorization
        if "earnest money" in text.lower() or "emd" in text.lower():
            clause_match = re.search(r"[^\.\n]*?(?:earnest\s+money|emd)[^\.\n]*", text, re.IGNORECASE)
            clause = clause_match.group(0).strip() if clause_match else "Earnest Money Deposit (EMD) submission."
            num_val, curr, unit = normalize_numeric_threshold(clause)
            blk = find_source_block("emd") or find_source_block("earnest")
            extracted.append(
                ExtractedCriterionRaw(
                    name="Earnest Money Deposit (EMD)",
                    description="Submission of Earnest Money Deposit / Bid Security.",
                    category=CriterionCategory.DOCUMENT_REQUIREMENT,
                    requirement_type=RequirementType.MANDATORY,
                    operator="=" if num_val else "EXISTS",
                    threshold_value=num_val,
                    threshold_text=f"{num_val}" if num_val else None,
                    currency=curr or "INR",
                    mandatory=True,
                    required_evidence=["EMD Bank Guarantee / Proof of Payment"],
                    source_clause=clause,
                    source_page=blk.page_number if blk else chunk.start_page,
                    source_block_id=blk.block_id if blk else None,
                    source_table_reference=blk.table_reference if blk else None,
                    confidence=0.94,
                    extraction_status=ExtractionStatus.EXTRACTED,
                    explanation="Mandatory bid security deposit submission.",
                )
            )

        # 6. Conditional: "If applicable", "In case of joint venture"
        if "if applicable" in text.lower() or "in case of" in text.lower():
            cond_match = re.search(r"[^\.\n]*?(?:if\s+applicable|in\s+case\s+of)[^\.\n]*", text, re.IGNORECASE)
            if cond_match:
                clause = cond_match.group(0).strip()
                blk = find_source_block("if applicable") or find_source_block("in case of")
                extracted.append(
                    ExtractedCriterionRaw(
                        name="Conditional Submission Requirement",
                        description="Requirement dependent on specific bidder status/applicability.",
                        category=CriterionCategory.DOCUMENT_REQUIREMENT,
                        requirement_type=RequirementType.CONDITIONAL,
                        condition_text="If applicable to bidder entity category",
                        mandatory=None,
                        source_clause=clause,
                        source_page=blk.page_number if blk else chunk.start_page,
                        source_block_id=blk.block_id if blk else None,
                        source_table_reference=blk.table_reference if blk else None,
                        confidence=0.88,
                        extraction_status=ExtractionStatus.EXTRACTED,
                        explanation="Conditional clause requiring situational verification.",
                    )
                )

        # 7. Ambiguous Clauses
        if "adequate resources" in text.lower() or "sufficient financial standing" in text.lower():
            amb_match = re.search(r"[^\.\n]*?(?:adequate\s+resources|sufficient\s+financial)[^\.\n]*", text, re.IGNORECASE)
            clause = amb_match.group(0).strip() if amb_match else "The bidder should have adequate resources."
            blk = find_source_block("adequate") or find_source_block("sufficient")
            extracted.append(
                ExtractedCriterionRaw(
                    name="Financial Standing Adequacy",
                    description="General clause regarding financial standing without explicit numeric threshold.",
                    category=CriterionCategory.FINANCIAL,
                    requirement_type=RequirementType.AMBIGUOUS,
                    operator=None,
                    threshold_value=None,
                    threshold_text=None,
                    unit=None,
                    currency=None,
                    mandatory=None,
                    required_evidence=None,
                    source_clause=clause,
                    source_page=blk.page_number if blk else chunk.start_page,
                    source_block_id=blk.block_id if blk else None,
                    source_table_reference=blk.table_reference if blk else None,
                    confidence=0.60,
                    extraction_status=ExtractionStatus.AMBIGUOUS,
                    explanation="Vague wording lacking quantifiable threshold or explicit requirement type.",
                )
            )

        return RawExtractionResponse(criteria=extracted)
