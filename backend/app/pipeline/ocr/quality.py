"""OCR Quality Assessment module for measurable extraction confidence, critical field protection, and robustness."""

import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Tuple


@dataclass
class OCRQualityScore:
    """Detailed breakdown of OCR quality metrics, classification status, and critical field signals."""

    overall_score: float  # 0.0 to 1.0
    avg_confidence: float
    status: Literal["GOOD", "REVIEW", "POOR"]
    total_characters: int
    num_blocks: int
    alphanumeric_ratio: float
    repeated_char_ratio: float
    is_acceptable: bool
    is_unreadable: bool
    has_uncertain_critical_fields: bool = False
    critical_fields_found: List[str] = field(default_factory=list)
    critical_fields_min_confidence: float = 1.0
    diagnostics: Dict[str, Any] = field(default_factory=dict)


class OCRQualityAssessment:
    """Evaluates measurable OCR signals to drive multi-pass retries, critical field checks, and fallback decisions."""

    CRITICAL_PATTERNS = [
        re.compile(r"(?:₹|INR|Rs\.?)\s*[\d,]+(?:\.\d+)?\s*(?:Crore|Lakh|Cr|L)?", re.IGNORECASE),
        re.compile(r"\b\d+(?:\.\d+)?\s*%", re.IGNORECASE),
        re.compile(r"\b20\d\d[-/]\d\d(?:\d\d)?\b"),
        re.compile(r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"),
        re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b"),  # PAN
        re.compile(r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b"),  # GSTIN
        re.compile(r"\bISO\s*(?:9001|27001|14001|45001|50001)\b", re.IGNORECASE),  # ISO
        re.compile(r"\b(?:NIT|Tender|PO|WO|Ref|Certificate)[\s#.:/-]*[A-Z0-9/-]{4,}\b", re.IGNORECASE),
    ]

    @classmethod
    def get_thresholds(cls) -> Dict[str, float]:
        """Return configurable OCR quality and confidence thresholds."""
        return {
            "conf_accept": float(os.getenv("OCR_CONFIDENCE_ACCEPT", "0.85")),
            "conf_review": float(os.getenv("OCR_CONFIDENCE_REVIEW", "0.65")),
            "qual_accept": float(os.getenv("OCR_QUALITY_ACCEPT", "0.60")),
            "qual_review": float(os.getenv("OCR_QUALITY_REVIEW", "0.35")),
        }

    @classmethod
    def detect_critical_fields(cls, blocks_data: List[Dict[str, Any]]) -> Tuple[List[str], float]:
        """Scan text blocks for procurement-critical identifiers and evaluate minimum confidence."""
        found_fields: List[str] = []
        min_conf = 1.0
        has_critical = False

        for b in blocks_data:
            text = b.get("text", "")
            conf = float(b.get("confidence", 1.0))
            for pat in cls.CRITICAL_PATTERNS:
                for match in pat.finditer(text):
                    has_critical = True
                    matched_str = match.group(0).strip()
                    if matched_str not in found_fields:
                        found_fields.append(matched_str)
                    if conf < min_conf:
                        min_conf = conf

        min_conf = min_conf if has_critical else 1.0
        return found_fields, min_conf

    @classmethod
    def calculate_quality_score(
        cls,
        blocks_data: List[Dict[str, Any]],
        img_width: int = 1000,
        img_height: int = 1000,
    ) -> OCRQualityScore:
        """Calculate composite quality score, critical field confidence, and GOOD/REVIEW/POOR status."""
        thresholds = cls.get_thresholds()

        if not blocks_data:
            return OCRQualityScore(
                overall_score=0.0,
                avg_confidence=0.0,
                status="POOR",
                total_characters=0,
                num_blocks=0,
                alphanumeric_ratio=0.0,
                repeated_char_ratio=0.0,
                is_acceptable=False,
                is_unreadable=True,
                has_uncertain_critical_fields=False,
                critical_fields_found=[],
                critical_fields_min_confidence=0.0,
                diagnostics={"reason": "No text blocks detected"},
            )

        confidences = [float(b.get("confidence", 0.0)) for b in blocks_data if "confidence" in b]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0.0

        all_text = " ".join(b.get("text", "") for b in blocks_data).strip()
        total_chars = len(all_text)

        if total_chars == 0:
            return OCRQualityScore(
                overall_score=0.0,
                avg_confidence=avg_conf,
                status="POOR",
                total_characters=0,
                num_blocks=len(blocks_data),
                alphanumeric_ratio=0.0,
                repeated_char_ratio=0.0,
                is_acceptable=False,
                is_unreadable=True,
                has_uncertain_critical_fields=False,
                critical_fields_found=[],
                critical_fields_min_confidence=0.0,
                diagnostics={"reason": "Extracted text is empty"},
            )

        # 1. Alphanumeric Ratio (words, numbers, spaces, valid document punctuation)
        valid_chars = sum(1 for c in all_text if c.isalnum() or c in " ₹,.%/-:()[]'\"\n\t")
        alnum_ratio = valid_chars / float(total_chars)

        # 2. Repeated character penalty (e.g. '||||||||' or '......' or 'xxxxxxxx')
        repeated_patterns = len(re.findall(r"(.)\1{3,}", all_text))
        repeated_char_ratio = min(1.0, (repeated_patterns * 4) / float(max(total_chars, 1)))

        # 3. Minimum meaningful length
        length_factor = min(1.0, total_chars / 30.0)

        # 4. Composite Quality Formula
        raw_score = (0.40 * avg_conf) + (0.35 * alnum_ratio) + (0.15 * length_factor) - (0.10 * repeated_char_ratio)
        overall_score = max(0.0, min(1.0, raw_score))

        # 5. Critical Fields Assessment
        found_fields, min_crit_conf = cls.detect_critical_fields(blocks_data)
        has_uncertain_critical = bool(found_fields and min_crit_conf < thresholds["conf_review"])

        is_unreadable = (
            overall_score <= thresholds["qual_review"]
            or (total_chars < 15 and avg_conf < 0.5)
            or avg_conf < 0.30
            or alnum_ratio < 0.50
        )

        # 6. Status Classification: GOOD, REVIEW, POOR
        if is_unreadable:
            status = "POOR"
            is_acceptable = False
        elif (
            overall_score >= thresholds["qual_accept"]
            and avg_conf >= thresholds["conf_accept"]
            and not has_uncertain_critical
        ):
            status = "GOOD"
            is_acceptable = True
        elif overall_score >= thresholds["qual_review"] and avg_conf >= thresholds["conf_review"]:
            status = "REVIEW"
            is_acceptable = True
        else:
            status = "POOR"
            is_acceptable = False

        diagnostics = {
            "avg_conf": round(avg_conf, 3),
            "alnum_ratio": round(alnum_ratio, 3),
            "repeated_char_ratio": round(repeated_char_ratio, 3),
            "total_chars": total_chars,
            "block_count": len(blocks_data),
            "status": status,
            "has_uncertain_critical": has_uncertain_critical,
        }

        return OCRQualityScore(
            overall_score=round(overall_score, 3),
            avg_confidence=round(avg_conf, 3),
            status=status,
            total_characters=total_chars,
            num_blocks=len(blocks_data),
            alphanumeric_ratio=round(alnum_ratio, 3),
            repeated_char_ratio=round(repeated_char_ratio, 3),
            is_acceptable=is_acceptable,
            is_unreadable=is_unreadable,
            has_uncertain_critical_fields=has_uncertain_critical,
            critical_fields_found=found_fields,
            critical_fields_min_confidence=round(min_crit_conf, 3),
            diagnostics=diagnostics,
        )
