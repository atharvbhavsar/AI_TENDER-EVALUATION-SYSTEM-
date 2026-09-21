"""Image document parser supporting robust preprocessing, multi-pass OCR, and structured normalization."""

import io
import logging
import uuid
from typing import List
from PIL import Image

from app.core.config import get_settings
from app.pipeline.base import BaseDocumentParser
from app.pipeline.ocr.engine import OCREngine
from app.pipeline.ocr.preprocessing import ImagePreprocessor
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument

logger = logging.getLogger("app.pipeline.image")


class ImageDocumentParser(BaseDocumentParser):
    """Parser for photograph and scanned image documents (.jpg, .jpeg, .png)."""

    def can_parse(self, file_extension: str) -> bool:
        return file_extension.lower() in (".jpg", ".jpeg", ".png")

    def parse(
        self,
        document_id: uuid.UUID,
        content: bytes,
        filename: str,
    ) -> NormalizedDocument:
        settings = get_settings()

        if not content or len(content) == 0:
            raise ValueError("Empty image document content.")

        try:
            img = Image.open(io.BytesIO(content))
            img.verify()  # Verify integrity
            # Reopen after verify
            img = Image.open(io.BytesIO(content))
        except Exception as exc:
            logger.error("Failed to open image '%s': %s", filename, str(exc))
            raise ValueError(f"Corrupted or invalid image: {str(exc)}")

        width, height = img.size
        total_pixels = width * height
        if total_pixels > settings.MAX_IMAGE_PIXELS:
            raise ValueError(
                f"Image dimensions ({width}x{height} = {total_pixels} px) exceed limit of {settings.MAX_IMAGE_PIXELS} pixels."
            )

        # Convert to OpenCV image format for high-performance preprocessing and OCR
        cv2_img = ImagePreprocessor.pil_to_cv2(img)

        # Run multi-pass OCR engine with quality scoring & table extraction
        engine = OCREngine()
        ocr_result = engine.process_image(cv2_img, page_num=1, document_id=str(document_id))

        blocks: List[DocumentBlock] = ocr_result.blocks
        total_tables = sum(1 for b in blocks if b.type == BlockType.TABLE)
        total_chars = sum(len(b.text) for b in blocks)

        pages = [
            DocumentPage(
                page_number=1,
                width=float(width),
                height=float(height),
                blocks=blocks,
            )
        ]

        metadata = {
            "filename": filename,
            "width": width,
            "height": height,
            "format": img.format,
            "ocr_engine": ocr_result.ocr_engine,
            "preprocessing_variant": ocr_result.selected_variant,
            "ocr_quality_score": ocr_result.quality_score.overall_score,
            "avg_confidence": ocr_result.quality_score.avg_confidence,
            "skew_angle": ocr_result.skew_angle,
            "orientation_angle": ocr_result.orientation_angle,
            "is_upscaled": ocr_result.is_upscaled,
            "scale_factor": ocr_result.scale_factor,
        }

        return NormalizedDocument(
            document_id=document_id,
            document_type="PHOTOGRAPH",
            processor_version=settings.PROCESSOR_VERSION,
            page_count=1,
            total_characters=total_chars,
            total_tables=total_tables,
            pages=pages,
            metadata=metadata,
        )
