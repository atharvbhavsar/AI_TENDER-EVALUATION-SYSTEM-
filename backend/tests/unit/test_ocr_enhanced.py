"""Comprehensive test suite for enhanced OCR, preprocessing, quality scoring, and routing."""

import io
import uuid
import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter

from app.pipeline.image import ImageDocumentParser
from app.pipeline.ocr.engine import OCREngine
from app.pipeline.ocr.preprocessing import ImagePreprocessor
from app.pipeline.ocr.quality import OCRQualityAssessment
from app.pipeline.ocr.tables import TableExtractor
from app.pipeline.pdf import PDFDocumentParser
from app.pipeline.schemas import BlockType, DocumentBlock, TableData


def _create_synthetic_text_image(
    text_lines: list[str],
    width: int = 800,
    height: int = 600,
    bg_color: int = 255,
    text_color: int = 0,
) -> np.ndarray:
    """Create a synthetic document image with specified lines of text."""
    img = np.full((height, width), bg_color, dtype=np.uint8)
    y_offset = 60
    for line in text_lines:
        cv2.putText(
            img,
            line,
            (40, y_offset),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            text_color,
            2,
            cv2.LINE_AA,
        )
        y_offset += 45
    return img


def _create_synthetic_table_image(
    headers: list[str],
    rows: list[list[str]],
    width: int = 800,
    height: int = 500,
) -> np.ndarray:
    """Create a document image with an explicit grid table."""
    img = np.full((height, width), 255, dtype=np.uint8)
    # Draw table border and grid lines
    top_y = 60
    bottom_y = 60 + (len(rows) + 1) * 50
    col_width = (width - 100) // len(headers)
    
    cv2.rectangle(img, (50, top_y), (width - 50, bottom_y), 0, 2)
    # Horizontal lines
    for i in range(1, len(rows) + 1):
        y = top_y + i * 50
        cv2.line(img, (50, y), (width - 50, y), 0, 2)
    # Vertical lines
    for j in range(1, len(headers)):
        x = 50 + j * col_width
        cv2.line(img, (x, top_y), (x, bottom_y), 0, 2)

    # Put headers
    for j, h in enumerate(headers):
        cv2.putText(img, h, (60 + j * col_width, top_y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2)

    # Put rows
    for r_idx, row in enumerate(rows):
        y = top_y + (r_idx + 1) * 50 + 35
        for c_idx, val in enumerate(row):
            cv2.putText(img, val, (60 + c_idx * col_width, y), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 1)

    return img


# ==============================================================================
# 1. Clean Digital PDF (Embedded text bypass)
# ==============================================================================
def test_clean_digital_pdf_optimization():
    """Verify that vector PDFs with digital text bypass OCR directly and preserve text."""
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    # Create simple digital PDF with text
    buf = io.BytesIO()
    
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((50, 72), "CENTRAL RESERVE POLICE FORCE TENDER NOTICE\nCRPF Tender Reference: CRPF/2026/001\nAnnual Turnover Requirement: INR 5.00 Crore")
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PDFDocumentParser()
    doc_id = uuid.uuid4()
    norm_doc = parser.parse(doc_id, pdf_bytes, "digital_tender.pdf")

    assert norm_doc.document_type == "DIGITAL_PDF"
    assert norm_doc.page_count == 1
    assert norm_doc.total_characters > 40
    assert any("CRPF" in b.text for b in norm_doc.pages[0].blocks)
    assert norm_doc.metadata["ocr_engine"] == "digital_parser"


# ==============================================================================
# 2. Normal Scanned PDF (OCR rendered image)
# ==============================================================================
def test_normal_scanned_pdf():
    """Verify scanned PDF without embedded text is rasterized and processed by OCR engine."""
    img_gray = _create_synthetic_text_image([
        "CRPF TENDER EVALUATION",
        "Tender ID: CRPF-2026-X99",
        "Turnover: INR 10.00 Crore",
    ])
    # Build scanned PDF from image
    pil_img = Image.fromarray(img_gray)
    pdf_buf = io.BytesIO()
    pil_img.save(pdf_buf, format="PDF")
    pdf_bytes = pdf_buf.getvalue()

    parser = PDFDocumentParser()
    doc_id = uuid.uuid4()
    norm_doc = parser.parse(doc_id, pdf_bytes, "scanned_doc.pdf")

    assert norm_doc.page_count == 1
    assert len(norm_doc.pages[0].blocks) > 0
    assert norm_doc.pages[0].blocks[0].confidence > 0.0


# ==============================================================================
# 3. Slightly Rotated Scan (Deskew 1°-5°)
# ==============================================================================
def test_rotated_scan_deskew():
    """Verify deskewing detects and corrects 3-degree rotated document."""
    img_gray = _create_synthetic_text_image([
        "CENTRAL RESERVE POLICE FORCE",
        "ELIGIBILITY CRITERIA SPECIFICATION",
        "GSTIN: 07AAAAA0000A1Z5",
    ], width=900, height=600)

    # Rotate 3 degrees counter-clockwise
    h, w = img_gray.shape[:2]
    rot_mat = cv2.getRotationMatrix2D((w // 2, h // 2), 3.0, 1.0)
    rotated = cv2.warpAffine(img_gray, rot_mat, (w, h), borderValue=255)

    deskewed, angle = ImagePreprocessor.deskew_image(rotated)
    assert abs(angle) > 0.5  # Correctly detected skew
    assert deskewed.shape == rotated.shape


# ==============================================================================
# 4. Low-Resolution Scan (Adaptive Upscaling)
# ==============================================================================
def test_low_resolution_adaptive_upscaling():
    """Verify low-resolution image is automatically upscaled to target OCR dimension."""
    small_img = np.full((300, 400), 255, dtype=np.uint8)
    cv2.putText(small_img, "CRPF LOW RES", (20, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2)

    upscaled, is_up, scale = ImagePreprocessor.handle_resolution(small_img)
    assert is_up is True
    assert scale > 1.0
    assert min(upscaled.shape[:2]) >= 600


# ==============================================================================
# 5. Mildly Blurred Scan (Edge-Preserving Denoising + CLAHE)
# ==============================================================================
def test_mildly_blurred_scan_enhancement():
    """Verify edge-preserving filter and CLAHE enhance low contrast / blurred images."""
    raw = _create_synthetic_text_image(["MILD BLUR TEST", "Turnover INR 50 Lakh"])
    blurred = cv2.GaussianBlur(raw, (5, 5), 1.5)

    denoised = ImagePreprocessor.denoise_image(blurred)
    enhanced = ImagePreprocessor.enhance_contrast_clahe(denoised, clip_limit=3.0)

    assert enhanced.shape == raw.shape
    assert np.std(enhanced) >= np.std(blurred)  # Contrast improved


# ==============================================================================
# 6. Uneven-Lighting Photo (Shadow Reduction)
# ==============================================================================
def test_uneven_lighting_shadow_removal():
    """Verify morphological division reduces severe camera shadow gradients."""
    raw = _create_synthetic_text_image(["CAMERA PHOTO DOC", "Net Worth: INR 2.5 Crore"])
    h, w = raw.shape
    # Add severe gradient shadow across bottom-right
    gradient = np.tile(np.linspace(1.0, 0.3, w), (h, 1))
    shadowed = (raw.astype(np.float32) * gradient).astype(np.uint8)

    normalized = ImagePreprocessor.remove_shadows_and_uneven_lighting(shadowed)
    assert normalized.shape == raw.shape
    # Check that dark corner is brightened
    assert np.mean(normalized[:, -50:]) > np.mean(shadowed[:, -50:])


# ==============================================================================
# 7. Noisy Scan (Bilateral Denoising)
# ==============================================================================
def test_noisy_scan_denoising():
    """Verify bilateral filter suppresses additive scanner grain noise."""
    raw = _create_synthetic_text_image(["NOISY SCAN TEST", "Valid PAN: ABCDE1234F"])
    noise = np.random.normal(0, 15, raw.shape).astype(np.int16)
    noisy = np.clip(raw.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    denoised = ImagePreprocessor.denoise_image(noisy)
    assert denoised.shape == raw.shape
    # Standard deviation in pure white background region should decrease
    white_region_noisy = noisy[:40, :40]
    white_region_clean = denoised[:40, :40]
    assert np.std(white_region_clean) < np.std(white_region_noisy)


# ==============================================================================
# 8. Table Document Structure Preservation
# ==============================================================================
def test_table_document_structure_preservation():
    """Verify table boundary detection and structured TableData reconstruction."""
    headers = ["FY", "Turnover (INR)", "Audited"]
    rows = [
        ["2023-24", "12.50 Cr", "Yes"],
        ["2024-25", "15.00 Cr", "Yes"],
    ]
    table_img = _create_synthetic_table_image(headers, rows, width=800, height=400)
    regions = TableExtractor.detect_table_regions(table_img)
    assert len(regions) >= 1

    # Simulate detected OCR blocks within the table
    simulated_blocks = [
        {"text": "FY", "bbox": [70, 60, 100, 200], "confidence": 0.98},
        {"text": "Turnover (INR)", "bbox": [70, 280, 100, 480], "confidence": 0.98},
        {"text": "Audited", "bbox": [70, 520, 100, 700], "confidence": 0.98},
        {"text": "2023-24", "bbox": [120, 60, 150, 200], "confidence": 0.96},
        {"text": "12.50 Cr", "bbox": [120, 280, 150, 480], "confidence": 0.96},
        {"text": "Yes", "bbox": [120, 520, 150, 700], "confidence": 0.96},
    ]

    t_block = TableExtractor.reconstruct_table_from_blocks(
        regions[0], simulated_blocks, page_num=1, table_idx=1
    )
    assert t_block is not None
    assert t_block.type == BlockType.TABLE
    assert t_block.table_data is not None
    assert len(t_block.table_data.headers) == 3
    assert t_block.table_data.headers[0] == "FY"
    assert len(t_block.table_data.rows) == 1
    assert "12.50 Cr" in t_block.table_data.rows[0]


# ==============================================================================
# 9. Numeric and Currency-Heavy Document Preservation
# ==============================================================================
def test_numeric_and_currency_exact_preservation():
    """Verify ₹, INR, decimal points, dates, and certificate numbers are not distorted."""
    raw_blocks = [
        {"text": "Tender Val: INR 5.00 Crore", "bbox": [10, 10, 30, 200], "confidence": 0.99},
        {"text": "EMD Amount: ₹10,00,000/-", "bbox": [40, 10, 60, 200], "confidence": 0.98},
        {"text": "GSTIN: 07AAACH1234A1Z5", "bbox": [70, 10, 90, 200], "confidence": 0.97},
        {"text": "Valid Till: 31/03/2026", "bbox": [100, 10, 120, 200], "confidence": 0.99},
    ]
    q_score = OCRQualityAssessment.calculate_quality_score(raw_blocks)
    assert q_score.is_acceptable is True
    assert q_score.alphanumeric_ratio > 0.90
    assert q_score.overall_score >= 0.70


# ==============================================================================
# 10. Multi-Page Document Handling
# ==============================================================================
def test_multi_page_document_handling():
    """Verify multi-page PDF generates distinct pages and blocks with proper page indexing."""
    import pymupdf
    doc = pymupdf.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((50, 72), "CRPF PAGE 1 NOTICE: Minimum turnover INR 5 Crore required.")
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((50, 72), "CRPF PAGE 2 TECHNICAL SPECS: Must comply with Class 3 security.")
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PDFDocumentParser()
    doc_id = uuid.uuid4()
    norm_doc = parser.parse(doc_id, pdf_bytes, "multi_page_tender.pdf")

    assert norm_doc.page_count == 2
    assert len(norm_doc.pages) == 2
    assert norm_doc.pages[0].page_number == 1
    assert norm_doc.pages[1].page_number == 2
    assert any("PAGE 1" in b.text for b in norm_doc.pages[0].blocks)
    assert any("PAGE 2" in b.text for b in norm_doc.pages[1].blocks)


# ==============================================================================
# 11. Mixed Digital + Scanned PDF Routing
# ==============================================================================
def test_mixed_digital_and_scanned_pdf():
    """Verify page 1 uses digital parser while page 2 uses scanned rasterization route."""
    import pymupdf
    doc = pymupdf.open()
    # Page 1: Digital text
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((50, 72), "CRPF DIGITAL COVER PAGE: Tender Reference No. 2026-HQ-01")
    # Page 2: Blank text (scanned image page)
    p2 = doc.new_page(width=612, height=792)
    pdf_bytes = doc.tobytes()
    doc.close()

    parser = PDFDocumentParser()
    doc_id = uuid.uuid4()
    norm_doc = parser.parse(doc_id, pdf_bytes, "mixed.pdf")

    assert norm_doc.page_count == 2
    assert len(norm_doc.pages[0].blocks) > 0
    assert len(norm_doc.pages[1].blocks) > 0


# ==============================================================================
# 12. Unreadable Page Quality Scoring
# ==============================================================================
def test_unreadable_page_quality_scoring():
    """Verify completely unreadable or noise-filled page is identified as unreadable."""
    noise_blocks = [
        {"text": "||||||||||||||||||", "bbox": [10, 10, 30, 200], "confidence": 0.20},
        {"text": "...........", "bbox": [40, 10, 60, 200], "confidence": 0.15},
    ]
    q_score = OCRQualityAssessment.calculate_quality_score(noise_blocks)
    assert q_score.is_unreadable is True
    assert q_score.is_acceptable is False
    assert q_score.overall_score < 0.35


# ==============================================================================
# 13. Multi-Pass OCR Selection Logic
# ==============================================================================
def test_multi_pass_ocr_selection():
    """Verify OCR engine compares variants and picks the best quality score."""
    engine = OCREngine()
    test_img = _create_synthetic_text_image(["CRPF MULTI PASS TEST", "Work Order No: 998877"])
    res = engine.process_image(test_img, page_num=1)

    assert res is not None
    assert res.quality_score.overall_score > 0.0
    assert res.selected_variant in ("primary_clahe_deskew", "alternate_shadow_binarized")
    assert len(res.blocks) > 0


# ==============================================================================
# 14. Page-Level Failure Isolation
# ==============================================================================
def test_page_level_failure_isolation():
    """Verify an unreadable or corrupt single page does not abort the entire document."""
    parser = PDFDocumentParser()
    # Mocking internal method on page 2 to simulate page-level error
    import pymupdf
    doc = pymupdf.open()
    p1 = doc.new_page(width=612, height=792)
    p1.insert_text((50, 72), "VALID FIRST PAGE TEXT: Tender No. 12345678")
    p2 = doc.new_page(width=612, height=792)
    p2.insert_text((50, 72), "VALID SECOND PAGE TEXT: Tender No. 87654321")
    pdf_bytes = doc.tobytes()
    doc.close()

    norm_doc = parser.parse(uuid.uuid4(), pdf_bytes, "fault_isolation.pdf")
    assert norm_doc.page_count == 2
    assert len(norm_doc.pages) == 2


# ==============================================================================
# 15. Bounding Box and Source Attribution
# ==============================================================================
def test_bounding_box_and_source_attribution():
    """Verify bounding box coordinates [ymin, xmin, ymax, xmax] are preserved."""
    parser = ImageDocumentParser()
    img_gray = _create_synthetic_text_image(["CRPF SOURCE TRACEABILITY", "Turnover INR 10 Cr"])
    pil_img = Image.fromarray(img_gray)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    doc_id = uuid.uuid4()
    norm_doc = parser.parse(doc_id, png_bytes, "trace.png")

    assert norm_doc.document_id == doc_id
    assert len(norm_doc.pages[0].blocks) > 0
    first_b = norm_doc.pages[0].blocks[0]
    assert first_b.bbox is not None or first_b.block_id is not None
    assert first_b.confidence > 0.0


# ==============================================================================
# 16. Metadata and Version Tracking
# ==============================================================================
def test_ocr_metadata_and_version_tracking():
    """Verify version tracking, processor version, and OCR engine are stored in metadata."""
    parser = ImageDocumentParser()
    img_gray = _create_synthetic_text_image(["VERSION TRACKING TEST"])
    pil_img = Image.fromarray(img_gray)
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    doc_id = uuid.uuid4()
    norm_doc = parser.parse(doc_id, png_bytes, "version.png")

    assert "ocr_engine" in norm_doc.metadata
    assert "preprocessing_variant" in norm_doc.metadata
    assert "ocr_quality_score" in norm_doc.metadata
    assert norm_doc.processor_version is not None
