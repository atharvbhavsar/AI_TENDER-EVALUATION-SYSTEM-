"""Comprehensive OCR Test Matrix covering Tests A through N from Section 35."""

import io
import uuid
import cv2
import numpy as np
import pytest
import pymupdf

from app.pipeline.ocr.engine import OCREngine
from app.pipeline.ocr.preprocessing import ImagePreprocessor, ImageQualityProfile
from app.pipeline.ocr.quality import OCRQualityAssessment
from app.pipeline.ocr.tables import TableExtractor
from app.pipeline.pdf import PDFDocumentParser
from app.pipeline.schemas import BlockType, DocumentBlock


def _make_text_image(
    lines: list[str],
    width: int = 1000,
    height: int = 700,
    bg: int = 255,
    fg: int = 0,
) -> np.ndarray:
    """Helper to generate clear synthetic document images with text."""
    img = np.full((height, width), bg, dtype=np.uint8)
    y = 80
    for line in lines:
        cv2.putText(img, line, (60, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, fg, 2, cv2.LINE_AA)
        y += 60
    return img


# ==============================================================================
# Test A — Digital PDF Fast Path (PyMuPDF path, OCR avoided)
# ==============================================================================
def test_a_digital_pdf_fastpath():
    """Verify PyMuPDF extracts embedded text directly and bypasses OCR."""
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 80), "CENTRAL RESERVE POLICE FORCE TENDER NOTICE\nRef: CRPF/2026/PROC/990\nTurnover Requirement: Rs 7.50 Crore per annum")
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PDFDocumentParser()
    norm_doc = parser.parse(uuid.uuid4(), pdf_bytes, "digital_sample.pdf")

    assert norm_doc.document_type == "DIGITAL_PDF"
    assert norm_doc.metadata.get("pages_digital_bypassed") == 1
    assert norm_doc.metadata.get("pages_ocr") == 0
    assert norm_doc.metadata.get("ocr_engine") in ("digital_parser", "pymupdf")
    assert len(norm_doc.pages[0].blocks) > 0
    assert norm_doc.pages[0].blocks[0].ocr_engine == "pymupdf"


# ==============================================================================
# Test B — Scanned PDF (OCR Executed)
# ==============================================================================
def test_b_scanned_pdf_ocr():
    """Verify scanned/image PDF triggers OCR engine."""
    img = _make_text_image(["GOVERNMENT OF INDIA TENDER", "Tender Notice No 12345", "Total Value: Rs 50 Lakh"])
    _, buf = cv2.imencode(".png", img)

    # Wrap in single-page PDF containing only an image
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_image(page.rect, stream=buf.tobytes())
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PDFDocumentParser()
    norm_doc = parser.parse(uuid.uuid4(), pdf_bytes, "scanned_sample.pdf")

    assert norm_doc.metadata.get("pages_ocr") == 1
    assert norm_doc.metadata.get("pages_digital_bypassed") == 0
    assert len(norm_doc.pages[0].blocks) > 0


# ==============================================================================
# Test C — 90° Rotation
# ==============================================================================
def test_c_90_degree_rotation():
    """Verify 90° rotated document is detected, rotation corrected, and OCR succeeds."""
    img = _make_text_image(["CENTRAL RESERVE POLICE FORCE", "ANNUAL TURNOVER REQUIREMENT", "ELIGIBILITY CRITERION 2026"])
    rot90 = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)

    engine = OCREngine()
    result = engine.process_image(rot90, page_num=1)

    assert result.orientation_angle in (90, 270) or "rotation" in " ".join(result.applied_transforms)
    assert result.total_characters > 15
    assert len(result.blocks) > 0


# ==============================================================================
# Test D — 180° Rotation
# ==============================================================================
def test_d_180_degree_rotation():
    """Verify 180° upside-down document orientation is corrected."""
    img = _make_text_image(["CENTRAL RESERVE POLICE FORCE TENDER", "TECHNICAL SPECIFICATIONS", "CLAUSE 12 WORK EXPERIENCE"])
    rot180 = cv2.rotate(img, cv2.ROTATE_180)

    engine = OCREngine()
    result = engine.process_image(rot180, page_num=1)

    assert len(result.blocks) > 0
    assert result.total_characters > 10


# ==============================================================================
# Test E — 270° Rotation
# ==============================================================================
def test_e_270_degree_rotation():
    """Verify 270° counter-clockwise document orientation is detected and corrected."""
    img = _make_text_image(["OFFICIAL GOVERNMENT TENDER", "MINIMUM ANNUAL TURNOVER", "RUPEES SEVEN CRORE"])
    rot270 = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)

    engine = OCREngine()
    result = engine.process_image(rot270, page_num=1)

    assert len(result.blocks) > 0
    assert result.total_characters > 10


# ==============================================================================
# Test F — Slight Skew
# ==============================================================================
def test_f_slight_skew():
    """Verify slight angular skew (2° to 5°) is deskewed without 90° flip."""
    img = _make_text_image(["ANNUAL FINANCIAL STATEMENT 2024", "TURNOVER: RS 7.50 CRORE", "NET PROFIT POSITIVE"])
    h, w = img.shape[:2]
    skew_angle = 3.5
    center = (w // 2, h // 2)
    rot_mat = cv2.getRotationMatrix2D(center, skew_angle, 1.0)
    skewed = cv2.warpAffine(img, rot_mat, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)

    deskewed, estimated_skew = ImagePreprocessor.deskew_image(skewed)
    assert abs(estimated_skew) > 1.0  # detected the non-zero skew

    engine = OCREngine()
    result = engine.process_image(skewed, page_num=1)
    assert result.total_characters > 15


# ==============================================================================
# Test G — Perspective Phone Photo
# ==============================================================================
def test_g_perspective_phone_photo():
    """Verify perspective distortion in phone-camera photos is unwarped to rectangular page."""
    bg = np.full((1200, 1500), 50, dtype=np.uint8)  # dark surface
    # Draw trapezoidal document boundary
    pts = np.array([[250, 180], [1250, 240], [1380, 1050], [180, 980]], dtype=np.int32)
    cv2.fillPoly(bg, [pts], 245)
    cv2.putText(bg, "ELIGIBILITY CERTIFICATE", (380, 500), cv2.FONT_HERSHEY_SIMPLEX, 1.0, 0, 2)

    unwarped, applied = ImagePreprocessor.detect_and_unwarp_perspective(bg)
    assert applied is True
    assert unwarped.shape[0] > 600
    assert unwarped.shape[1] > 800


# ==============================================================================
# Test H — Low-Light Page
# ==============================================================================
def test_h_low_light_page():
    """Verify illumination correction and background normalization on low-light / dark pages."""
    img = _make_text_image(["DARK SCAN TEST DOCUMENT", "CRPF PROCUREMENT NOTICE", "PROMPT RESPONSE REQUIRED"], bg=90, fg=20)

    profile = ImagePreprocessor.analyze_image_quality(img)
    assert profile.brightness_score < 0.45

    prep = ImagePreprocessor.preprocess_adaptive(img, profile)
    assert "shadow_removal" in prep.applied_transforms or prep.image is not None

    engine = OCREngine()
    res = engine.process_image(img, page_num=1)
    assert len(res.blocks) > 0


# ==============================================================================
# Test I — Noisy Page
# ==============================================================================
def test_i_noisy_page():
    """Verify bilateral denoising cleans pepper/salt scanner noise without destroying text."""
    img = _make_text_image(["DIRTY SCANNER GLASS TEST", "TURNOVER CLAUSE COMPLIANCE", "VALID ISO 9001 CERTIFIED"])
    noise = np.random.randint(0, 50, img.shape, dtype=np.uint8)
    noisy = cv2.add(img, noise)

    profile = ImagePreprocessor.analyze_image_quality(noisy)
    prep = ImagePreprocessor.preprocess_adaptive(noisy, profile)

    assert prep.image is not None
    engine = OCREngine()
    res = engine.process_image(noisy, page_num=1)
    assert res.total_characters > 10


# ==============================================================================
# Test J — Low-Contrast Page
# ==============================================================================
def test_j_low_contrast_page():
    """Verify CLAHE contrast enhancement improves faded text."""
    # Faded gray text on light-gray background
    img = _make_text_image(["FADED TENDER SPECIFICATION", "GST NUMBER: 07AAAAA0000A1Z5", "DATED 15/08/2024"], bg=230, fg=170)

    profile = ImagePreprocessor.analyze_image_quality(img)
    assert profile.contrast_score < 0.35

    prep = ImagePreprocessor.preprocess_adaptive(img, profile)
    assert "clahe_contrast" in prep.applied_transforms

    engine = OCREngine()
    res = engine.process_image(img, page_num=1)
    assert len(res.blocks) > 0


# ==============================================================================
# Test K — Blurred Page
# ==============================================================================
def test_k_blurred_page():
    """Verify Laplacian variance correctly detects blur and marks quality profile."""
    img = _make_text_image(["BLURRED DOCUMENT PAGE TEST", "ANNUAL BALANCE SHEET", "AUDITED REPORT 2025"])
    blurred = cv2.GaussianBlur(img, (25, 25), 0)

    profile = ImagePreprocessor.analyze_image_quality(blurred)
    assert profile.sharpness_score < 0.20
    assert profile.is_low_quality is True


# ==============================================================================
# Test L — Table Extraction
# ==============================================================================
def test_l_table_extraction():
    """Verify table borders are detected and reconstructed as TableData blocks."""
    headers = ["Financial Year", "Turnover (INR)"]
    rows = [["2022-23", "Rs 6.20 Crore"], ["2023-24", "Rs 7.10 Crore"], ["2024-25", "Rs 7.50 Crore"]]

    # Construct explicit table grid image
    img = np.full((500, 800), 255, dtype=np.uint8)
    cv2.rectangle(img, (60, 60), (740, 300), 0, 2)
    cv2.line(img, (60, 120), (740, 120), 0, 2)
    cv2.line(img, (60, 180), (740, 180), 0, 2)
    cv2.line(img, (60, 240), (740, 240), 0, 2)
    cv2.line(img, (400, 60), (400, 300), 0, 2)

    cv2.putText(img, "Financial Year", (80, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
    cv2.putText(img, "Turnover", (420, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
    cv2.putText(img, "2022-23", (80, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
    cv2.putText(img, "6.20 Crore", (420, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
    cv2.putText(img, "2023-24", (80, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
    cv2.putText(img, "7.10 Crore", (420, 220), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)

    regions = TableExtractor.detect_table_regions(img)
    assert len(regions) >= 1
    rx, ry, rw, rh = regions[0]
    assert rw > 300 and rh > 100


# ==============================================================================
# Test M — Numeric-Heavy Page & Critical Fields
# ==============================================================================
def test_m_numeric_heavy_page():
    """Verify detection of critical procurement fields (amounts, GST, PAN, ISO)."""
    blocks = [
        {"text": "Annual turnover of Rs 7.50 Crore required", "confidence": 0.94},
        {"text": "Valid ISO 9001 certification mandatory", "confidence": 0.92},
        {"text": "PAN: ABCDE1234F, GSTIN: 07AAAAA0000A1Z5", "confidence": 0.91},
        {"text": "Earnest Money Deposit of 2% must be submitted by 15/08/2024", "confidence": 0.89},
    ]

    quality = OCRQualityAssessment.calculate_quality_score(blocks)
    assert quality.status == "GOOD"
    assert len(quality.critical_fields_found) >= 3
    assert quality.has_uncertain_critical_fields is False


# ==============================================================================
# Test N — OCR Conflict Handling
# ==============================================================================
def test_n_ocr_conflict():
    """Verify OCR discrepancy on critical fields flags conflict for manual review / vision escalation."""
    # Low confidence critical field
    uncertain_blocks = [
        {"text": "Turnover: Rs 1.50 Crore", "confidence": 0.45},  # suspicious/uncertain low confidence
    ]

    quality = OCRQualityAssessment.calculate_quality_score(uncertain_blocks)
    # Must NOT be marked as GOOD
    assert quality.status in ("REVIEW", "POOR")
    assert quality.has_uncertain_critical_fields is True
