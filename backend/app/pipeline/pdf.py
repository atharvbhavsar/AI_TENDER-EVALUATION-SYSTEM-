"""PDF document parser supporting digital text fast-path bypass, scanned OCR fallback, and page-level isolation."""

import io
import logging
import re
import uuid
from typing import List, Tuple
import cv2
import numpy as np
from PIL import Image

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.core.config import get_settings
from app.pipeline.base import BaseDocumentParser
from app.pipeline.ocr.engine import OCREngine
from app.pipeline.ocr.preprocessing import ImagePreprocessor
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument

logger = logging.getLogger("app.pipeline.pdf")


class PDFDocumentParser(BaseDocumentParser):
    """Parser for digital, scanned, and mixed PDF documents with page-level fault isolation."""

    def can_parse(self, file_extension: str) -> bool:
        return file_extension.lower() == ".pdf"

    def _is_usable_digital_text(self, text: str) -> bool:
        """Evaluate whether page embedded digital text is sufficiently complete and valid to bypass OCR."""
        clean = text.strip()
        if len(clean) < 40:
            return False
        # Valid character ratio (letters, digits, punctuation, currency)
        valid_chars = sum(1 for c in clean if c.isalnum() or c in " ₹,.%/-:()[]'\"\n\t")
        if (valid_chars / float(len(clean))) < 0.70:
            return False
        # Word count check
        words = clean.split()
        if len(words) < 5:
            return False
        # Repeated character run penalty (e.g. ........ or --------)
        if len(re.findall(r"(.)\1{5,}", clean)) > 10:
            return False
        return True

    def parse(
        self,
        document_id: uuid.UUID,
        content: bytes,
        filename: str,
    ) -> NormalizedDocument:
        settings = get_settings()

        if not content or len(content) == 0:
            raise ValueError("Empty PDF content.")

        # Try opening with PyMuPDF first for rich text + rasterization capabilities
        doc_fitz = None
        num_pages = 0
        if fitz is not None:
            try:
                doc_fitz = fitz.open(stream=content, filetype="pdf")
                num_pages = len(doc_fitz)
            except Exception as exc:
                logger.warning("PyMuPDF failed to open '%s': %s. Falling back to PyPDF.", filename, exc)
                doc_fitz = None

        if doc_fitz is None:
            try:
                reader = PdfReader(io.BytesIO(content))
                num_pages = len(reader.pages)
            except PdfReadError as exc:
                logger.error("Failed to read PDF '%s': %s", filename, str(exc))
                raise ValueError(f"Corrupted or invalid PDF structure: {str(exc)}")
            except Exception as exc:
                logger.error("Unexpected error opening PDF '%s': %s", filename, str(exc))
                raise ValueError(f"Invalid PDF file: {str(exc)}")

        if num_pages == 0:
            raise ValueError("PDF contains 0 pages.")

        if num_pages > settings.MAX_DOCUMENT_PAGES:
            raise ValueError(
                f"PDF page count ({num_pages}) exceeds maximum allowed limit of {settings.MAX_DOCUMENT_PAGES} pages."
            )

        pages: List[DocumentPage] = []
        total_chars = 0
        total_tables = 0
        total_text_chars = 0
        pages_ocr_count = 0
        pages_bypassed_count = 0

        engine = OCREngine()

        for page_idx in range(num_pages):
            page_num = page_idx + 1
            page_blocks: List[DocumentBlock] = []
            page_width: float = 612.0
            page_height: float = 792.0

            try:
                # 1. Attempt PyMuPDF extraction if available
                if doc_fitz is not None:
                    fitz_page = doc_fitz[page_idx]
                    rect = fitz_page.rect
                    page_width = float(rect.width)
                    page_height = float(rect.height)
                    raw_text = fitz_page.get_text() or ""

                    # Digital PDF Fast Path: check if page has usable embedded text
                    if self._is_usable_digital_text(raw_text):
                        pages_bypassed_count += 1
                        total_text_chars += len(raw_text.strip())
                        blocks = self._segment_text_into_blocks(raw_text, page_num)
                        page_blocks.extend(blocks)
                    else:
                        # Scanned or image-only page: render to image and route to OCR
                        pages_ocr_count += 1
                        pix = fitz_page.get_pixmap(dpi=96)
                        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n).copy()
                        if pix.n == 4:
                            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2BGR)
                        elif pix.n == 3:
                            img_np = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

                        ocr_res = engine.process_image(img_np, page_num=page_num, document_id=str(document_id))
                        page_blocks.extend(ocr_res.blocks)
                        if ocr_res.total_characters > 20:
                            total_text_chars += ocr_res.total_characters

                else:
                    # Fallback PyPDF processing
                    reader = PdfReader(io.BytesIO(content))
                    pypdf_page = reader.pages[page_idx]
                    if pypdf_page.mediabox:
                        page_width = float(pypdf_page.mediabox.width)
                        page_height = float(pypdf_page.mediabox.height)
                    raw_text = pypdf_page.extract_text() or ""

                    if self._is_usable_digital_text(raw_text):
                        pages_bypassed_count += 1
                        total_text_chars += len(raw_text.strip())
                        blocks = self._segment_text_into_blocks(raw_text, page_num)
                        page_blocks.extend(blocks)
                    else:
                        # Extract embedded images and run OCR
                        pages_ocr_count += 1
                        ocr_blocks, chars = self._ocr_pypdf_images(pypdf_page, page_num, engine)
                        if ocr_blocks:
                            page_blocks.extend(ocr_blocks)
                            total_text_chars += chars
                        elif len(raw_text.strip()) > 0:
                            page_blocks.append(
                                DocumentBlock(
                                    block_id=f"p{page_num}_b1",
                                    type=BlockType.TEXT,
                                    text=raw_text.strip(),
                                    confidence=0.8,
                                    page=page_num,
                                    ocr_engine="pypdf",
                                    processing_version=settings.PROCESSOR_VERSION,
                                    orientation=0,
                                    preprocessing=[],
                                )
                            )

            except Exception as page_exc:
                logger.warning(
                    "Page %d processing encountered error in '%s': %s. Isolating failure to page.",
                    page_num,
                    filename,
                    str(page_exc),
                )
                page_blocks.append(
                    DocumentBlock(
                        block_id=f"p{page_num}_error",
                        type=BlockType.IMAGE,
                        text=f"[Page {page_num} unreadable / processing exception: {str(page_exc)}]",
                        confidence=0.0,
                        page=page_num,
                        ocr_engine="error",
                        processing_version=settings.PROCESSOR_VERSION,
                        orientation=0,
                        preprocessing=[],
                    )
                )

            for b in page_blocks:
                total_chars += len(b.text)
                if b.type == BlockType.TABLE:
                    total_tables += 1

            pages.append(
                DocumentPage(
                    page_number=page_num,
                    width=page_width,
                    height=page_height,
                    blocks=page_blocks,
                )
            )

        if doc_fitz is not None:
            try:
                doc_fitz.close()
            except Exception:
                pass

        is_scanned = pages_ocr_count > 0 and pages_bypassed_count == 0
        doc_type = "SCANNED_PDF" if is_scanned and total_text_chars < 50 else "DIGITAL_PDF"

        return NormalizedDocument(
            document_id=document_id,
            document_type=doc_type,
            processor_version=settings.PROCESSOR_VERSION,
            page_count=num_pages,
            total_characters=total_chars,
            total_tables=total_tables,
            pages=pages,
            metadata={
                "filename": filename,
                "is_scanned": is_scanned,
                "pages_processed": num_pages,
                "pages_ocr": pages_ocr_count,
                "pages_digital_bypassed": pages_bypassed_count,
                "ocr_engine": "paddleocr" if pages_ocr_count > 0 else "digital_parser",
            },
        )

    def _segment_text_into_blocks(self, text: str, page_num: int) -> List[DocumentBlock]:
        """Segment raw extracted page text into structured paragraphs, headings, and lists with provenance."""
        settings = get_settings()
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        blocks: List[DocumentBlock] = []
        current_paragraph: List[str] = []
        block_idx = 1

        def flush_paragraph():
            nonlocal block_idx
            if current_paragraph:
                p_text = " ".join(current_paragraph)
                blocks.append(
                    DocumentBlock(
                        block_id=f"p{page_num}_b{block_idx}",
                        type=BlockType.TEXT,
                        text=p_text,
                        confidence=1.0,
                        page=page_num,
                        ocr_engine="pymupdf",
                        processing_version=settings.PROCESSOR_VERSION,
                        orientation=0,
                        preprocessing=[],
                    )
                )
                block_idx += 1
                current_paragraph.clear()

        for line in lines:
            # Check if line looks like a major heading (e.g. all-caps short line or "SECTION 1", "ANNEXURE A")
            is_heading = (
                (line.isupper() and len(line) < 80)
                or re.match(r"^(SECTION|ANNEXURE|CHAPTER|SCHEDULE|PART|CLAUSE|TENDER NOTICE)\b", line, re.IGNORECASE)
                is not None
            )

            # Check if list item
            is_list = re.match(r"^(\d+[\.\)]|\([a-z\d]+\)|[\*\-\•])\s+", line) is not None

            if is_heading:
                flush_paragraph()
                blocks.append(
                    DocumentBlock(
                        block_id=f"p{page_num}_b{block_idx}",
                        type=BlockType.HEADING,
                        text=line,
                        confidence=1.0,
                        page=page_num,
                        ocr_engine="pymupdf",
                        processing_version=settings.PROCESSOR_VERSION,
                        orientation=0,
                        preprocessing=[],
                    )
                )
                block_idx += 1
            elif is_list:
                flush_paragraph()
                blocks.append(
                    DocumentBlock(
                        block_id=f"p{page_num}_b{block_idx}",
                        type=BlockType.LIST,
                        text=line,
                        confidence=1.0,
                        page=page_num,
                        ocr_engine="pymupdf",
                        processing_version=settings.PROCESSOR_VERSION,
                        orientation=0,
                        preprocessing=[],
                    )
                )
                block_idx += 1
            else:
                current_paragraph.append(line)

        flush_paragraph()
        return blocks

    def _ocr_pypdf_images(self, page, page_num: int, engine: OCREngine) -> Tuple[List[DocumentBlock], int]:
        """Perform OCR on embedded images in PyPDF page fallback."""
        blocks: List[DocumentBlock] = []
        total_chars = 0
        try:
            for img_idx, image_file_object in enumerate(page.images):
                pil_img = Image.open(io.BytesIO(image_file_object.data))
                cv2_img = ImagePreprocessor.pil_to_cv2(pil_img)
                res = engine.process_image(cv2_img, page_num=page_num)
                blocks.extend(res.blocks)
                total_chars += res.total_characters
        except Exception as exc:
            logger.debug("PyPDF image OCR error on page %d: %s", page_num, str(exc))

        return blocks, total_chars
