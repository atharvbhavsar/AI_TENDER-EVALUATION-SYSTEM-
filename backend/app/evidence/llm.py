"""LLM client interface and deterministic mock client for evidence extraction."""

import logging
import re
from abc import ABC, abstractmethod
from typing import List, Optional

from app.core.config import get_settings
from app.db.models.evidence import EvidenceStatus
from app.db.models.tender_criterion import TenderCriterion
from app.evidence.schemas import (
    CertificateDetailsRaw,
    ExperienceDetailsRaw,
    RawEvidenceExtractionResponse,
    RawEvidenceItem,
)
from app.extraction.chunking import ExtractionChunk
from app.extraction.normalizers import (
    normalize_currency,
    normalize_numeric_threshold,
)

logger = logging.getLogger("app.evidence.llm")


class BaseEvidenceLLMClient(ABC):
    """Abstract interface for evidence extraction LLM providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name identifier."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Configured model name."""
        pass

    @abstractmethod
    async def extract_evidence(
        self,
        system_prompt: str,
        user_prompt: str,
        chunk: ExtractionChunk,
        approved_criteria: List[TenderCriterion],
        document_id: Optional[str] = None,
    ) -> RawEvidenceExtractionResponse:
        """
        Send chunk content and approved criteria context to LLM, returning structured evidence candidates.
        """
        pass


class MockEvidenceLLMClient(BaseEvidenceLLMClient):
    """
    High-fidelity deterministic Mock LLM for evidence extraction in tests and dev environments.
    Extracts financial metrics, experience records, certificates, ambiguity, and handles unreadable scans.
    """

    def __init__(self, model_name: str = "mock-evidence-extractor-v1") -> None:
        self._model_name = model_name

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def extract_evidence(
        self,
        system_prompt: str,
        user_prompt: str,
        chunk: ExtractionChunk,
        approved_criteria: List[TenderCriterion],
        document_id: Optional[str] = None,
    ) -> RawEvidenceExtractionResponse:
        """Analyze chunk text deterministically and extract evidence matching approved criteria."""
        items: List[RawEvidenceItem] = []
        text = chunk.formatted_text
        page = chunk.start_page
        first_block_id = chunk.blocks[0].block_id if chunk.blocks else None
        table_ref = chunk.blocks[0].table_reference if chunk.blocks else None

        # 1. Check for Degraded / Unreadable OCR text
        if "[GARBLED]" in text or "[UNREADABLE]" in text or "????" in text:
            for crit in approved_criteria:
                items.append(
                    RawEvidenceItem(
                        criterion_code=crit.criterion_code or "CRIT-001",
                        evidence_found=True,
                        evidence_type="DOCUMENT",
                        extracted_text=text[:200],
                        status=EvidenceStatus.UNREADABLE,
                        confidence=0.35,
                        source_page=page,
                        source_block_id=first_block_id,
                        ambiguity_reason="Text contains severely degraded, illegible OCR content.",
                    )
                )
            return RawEvidenceExtractionResponse(extracted_items=items)

        # 2. Iterate through approved criteria to find matching evidence
        for crit in approved_criteria:
            code = crit.criterion_code or "CRIT-001"
            cat = str(crit.category).upper() if crit.category else ""
            crit_name = (crit.name or "").lower()
            desc = (crit.description or "").lower()

            # --- Financial Turnover / Net Worth Extraction ---
            if "FINANCIAL" in cat or "turnover" in crit_name or "turnover" in desc or "net worth" in crit_name:
                # Regex looking for Turnover or Net Worth patterns
                turnover_patterns = [
                    r"(?:annual\s+turnover|turnover|net\s+worth)[^.\n\r]*?(?:(?:rs\.?|inr|₹|\$)\s*([\d,.]+)\s*(crore|cr|lakh|million|billion|inr|rs)?|([\d,.]+)\s*(crore|cr|lakh|million|billion|inr|rs))",
                    r"turnover\s+for\s+(?:fy\s*[\d-]+)?\s*(?:is|was|amounted\s+to|:)?\s*(?:rs\.?|inr|₹|\$)?\s*([\d,.]+)\s*(crore|cr|lakh|million|billion)?",
                ]
                found_match = False
                for pat in turnover_patterns:
                    match = re.search(pat, text, re.IGNORECASE)
                    if match:
                        matched_text = match.group(0).strip()
                        raw_val_float, curr_from_thresh, unit_from_thresh = normalize_numeric_threshold(matched_text)
                        curr_cand = curr_from_thresh or normalize_currency(matched_text) or "INR"
                        unit_cand = unit_from_thresh or "Crore"

                        # Extract FY period if present
                        fy_match = re.search(r"(?:FY|financial\s+year)\s*([\d]{2,4}[-\s/]?[\d]{2,4})", text, re.IGNORECASE)
                        period_val = fy_match.group(0).strip() if fy_match else None

                        # Extract company name if present
                        bidder_match = re.search(r"(?:M/s|Messrs|Company:?)\s*([A-Za-z0-9\s.,&]+(?:Pvt\.?\s*Ltd\.?|Private\s*Limited|Limited|LLP))", text, re.IGNORECASE)
                        extracted_bidder = bidder_match.group(1).strip() if bidder_match else None

                        items.append(
                            RawEvidenceItem(
                                criterion_code=code,
                                evidence_found=True,
                                evidence_type="FINANCIAL",
                                extracted_text=matched_text,
                                extracted_value=raw_val_float,
                                normalized_value=f"{raw_val_float} {unit_cand} {curr_cand}".strip(),
                                unit=unit_cand,
                                currency=curr_cand,
                                period=period_val,
                                extracted_bidder_name=extracted_bidder,
                                status=EvidenceStatus.FOUND,
                                confidence=0.95,
                                source_page=page,
                                source_block_id=first_block_id,
                                source_table_reference=table_ref,
                                bbox=[0.1, 0.2, 0.8, 0.4] if table_ref else None,
                            )
                        )
                        found_match = True
                        break

            # --- Certificate Evidence Extraction (ISO, Registration, BIS) ---
            if "CERTIF" in cat or "certificate" in crit_name or "iso" in crit_name or "iso" in desc or "registration" in crit_name:
                cert_match = re.search(
                    r"(ISO\s*[\d:]+|Registration\s*Certificate|BIS\s*License|Incorporation\s*Certificate)[^.\n\r]*?(?:No\.?\s*[:\s]?([A-Za-z0-9\-/]+))?",
                    text,
                    re.IGNORECASE,
                )
                if cert_match:
                    cert_name = cert_match.group(1).strip()
                    cert_no = cert_match.group(2).strip() if cert_match.group(2) else "CERT-998811"
                    
                    auth_match = re.search(r"(?:issued\s+by|authority:?)\s*([A-Za-z0-9\s.,]+)", text, re.IGNORECASE)
                    issuing_auth = auth_match.group(1).strip() if auth_match else "Bureau of Indian Standards"

                    exp_match = re.search(r"(?:valid\s+till|expiry\s+date:?|valid\s+until)\s*([\d]{1,2}[-/\s][A-Za-z0-9]{3,9}[-/\s][\d]{2,4})", text, re.IGNORECASE)
                    expiry_date = exp_match.group(1).strip() if exp_match else "2027-03-31"

                    items.append(
                        RawEvidenceItem(
                            criterion_code=code,
                            evidence_found=True,
                            evidence_type="CERTIFICATE",
                            extracted_text=cert_match.group(0).strip(),
                            certificate_data=CertificateDetailsRaw(
                                certificate_name=cert_name,
                                certificate_number=cert_no,
                                issuing_authority=issuing_auth,
                                expiry_date=expiry_date,
                            ),
                            date_value=expiry_date,
                            status=EvidenceStatus.FOUND,
                            confidence=0.92,
                            source_page=page,
                            source_block_id=first_block_id,
                            bbox=[0.1, 0.1, 0.9, 0.3],
                        )
                    )

            # --- Technical Experience / Past Projects Extraction ---
            if "TECHNICAL" in cat or "experience" in crit_name or "project" in crit_name or "work order" in desc:
                # Check for Ambiguous claims
                if "substantial experience" in text.lower() or "vast experience" in text.lower() or "years of rich experience" in text.lower():
                    if not re.search(r"\d+\s*(?:years?|projects?|crore)", text, re.IGNORECASE):
                        items.append(
                            RawEvidenceItem(
                                criterion_code=code,
                                evidence_found=True,
                                evidence_type="EXPERIENCE",
                                extracted_text=text[:150],
                                status=EvidenceStatus.AMBIGUOUS,
                                confidence=0.55,
                                source_page=page,
                                source_block_id=first_block_id,
                                ambiguity_reason="Bidder claims experience qualitatively without specific verifiable duration, project count, or work orders.",
                            )
                        )
                        continue

                exp_match = re.search(
                    r"(?:work\s*order|project|supply\s*of)\s*[:\s]?([A-Za-z0-9\s.,-]+?)(?:,\s*client:?\s*([A-Za-z0-9\s.,]+))?(?:,\s*value:?\s*(?:rs\.?|inr)?\s*([\d.]+)\s*(crore|lakh)?)?",
                    text,
                    re.IGNORECASE,
                )
                if exp_match:
                    proj_name = exp_match.group(1).strip()
                    client = exp_match.group(2).strip() if exp_match.group(2) else "Central Reserve Police Force"
                    val_str = exp_match.group(3)
                    val_float = float(val_str) if val_str else None
                    unit_str = exp_match.group(4) or "Crore"

                    items.append(
                        RawEvidenceItem(
                            criterion_code=code,
                            evidence_found=True,
                            evidence_type="EXPERIENCE",
                            extracted_text=exp_match.group(0).strip(),
                            extracted_value=val_float,
                            unit=unit_str,
                            currency="INR",
                            experience_data=ExperienceDetailsRaw(
                                project_name=proj_name,
                                client_name=client,
                                project_value=val_float,
                                currency="INR",
                            ),
                            status=EvidenceStatus.FOUND,
                            confidence=0.90,
                            source_page=page,
                            source_block_id=first_block_id,
                        )
                    )

        return RawEvidenceExtractionResponse(extracted_items=items)


def get_evidence_llm_client() -> BaseEvidenceLLMClient:
    """Factory function returning the configured evidence extraction LLM client."""
    settings = get_settings()
    # Default to mock client in dev/test
    return MockEvidenceLLMClient(model_name=getattr(settings, "LLM_MODEL", "mock-evidence-extractor-v1"))
