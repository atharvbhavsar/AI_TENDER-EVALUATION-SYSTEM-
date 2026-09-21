"""Unified Multi-Pass OCR Engine powered by PaddleOCR, OpenCV, Quality Assessment, and Visual Fallback."""

import base64
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import cv2
import httpx
import numpy as np
from PIL import Image

from app.core.config import get_settings
from app.pipeline.ocr.preprocessing import ImagePreprocessor, ImageQualityProfile, PreprocessingResult
from app.pipeline.ocr.quality import OCRQualityAssessment, OCRQualityScore
from app.pipeline.ocr.tables import TableExtractor
from app.pipeline.schemas import BlockType, DocumentBlock

logger = logging.getLogger("app.pipeline.ocr.engine")

VISION_FALLBACK_SYSTEM_PROMPT = """You are a document-reading verifier.

Read ONLY information visibly present in the supplied document image.

Do not infer missing information.
Do not guess unclear characters.
Do not invent numbers, dates, IDs, names or values.

Return structured JSON containing:
- detected_text: list of strings (in top-to-bottom reading order)
- uncertain_fields: list of strings
- exact_numeric_values: list of strings
- exact_dates: list of strings
- exact_identifiers: list of strings
- table_values: list of lists representing rows if tables exist

If a field is unreadable, return:
UNREADABLE

If a value is ambiguous, return:
AMBIGUOUS

Do not make eligibility decisions.
Do not decide whether a bidder is qualified.
Do not override OPA.
"""


@dataclass
class OCRResult:
    """Comprehensive container for OCR execution output, quality metrics, and provenance."""

    blocks: List[DocumentBlock]
    quality_score: OCRQualityScore
    selected_variant: str
    ocr_engine: str
    skew_angle: float
    orientation_angle: int
    is_upscaled: bool
    scale_factor: float
    total_characters: int
    applied_transforms: List[str] = field(default_factory=list)
    fallback_used: bool = False
    secondary_used: bool = False
    disagreement_detected: bool = False


class OCREngine:
    """Production OCR Engine with multi-pass preprocessing, quality scoring, table preservation, and vision fallback."""

    _instance: Optional["OCREngine"] = None
    _paddle_ocr = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCREngine, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._init_ocr()
            self._initialized = True

    def _init_ocr(self):
        """Safely initialize PaddleOCR with oneDNN safety and language configurations."""
        os.environ["FLAGS_use_onednn"] = "0"
        os.environ["FLAGS_enable_pir_api"] = "0"

        # Add torch/paddle DLL directory on Windows if available
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            venv_path = os.path.dirname(sys.executable)
            torch_lib = os.path.join(venv_path, "Lib", "site-packages", "torch", "lib")
            if os.path.exists(torch_lib):
                try:
                    os.add_dll_directory(torch_lib)
                    os.environ["PATH"] = torch_lib + ";" + os.environ.get("PATH", "")
                except Exception as e:
                    logger.debug("Could not add torch lib dll dir: %s", e)

        try:
            import pytesseract
            cfg = get_settings()
            tess_path = cfg.TESSERACT_CMD or r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if os.path.exists(tess_path):
                pytesseract.pytesseract.tesseract_cmd = tess_path
                logger.info("Configured pytesseract command path: %s", tess_path)
        except Exception as tess_init_err:
            logger.debug("Pytesseract config check: %s", tess_init_err)

        try:
            from paddleocr import PaddleOCR
            self._paddle_ocr = PaddleOCR(use_textline_orientation=True, lang="en", enable_mkldnn=False)
            logger.info("PaddleOCR engine initialized successfully.")
        except Exception as exc:
            logger.warning("PaddleOCR engine initialization notice: %s. Using pytesseract fallback.", exc)
            self._paddle_ocr = None

    def _run_raw_ocr(self, img_np: np.ndarray) -> List[Dict[str, Any]]:
        """Run raw OCR on a single image numpy array and return standardized block dictionaries."""
        # Fast exit for blank images
        if np.std(img_np) < 2.0:
            return []

        # Ensure 3-channel BGR for PaddleOCR if needed
        if len(img_np.shape) == 2:
            input_bgr = cv2.cvtColor(img_np, cv2.COLOR_GRAY2BGR)
        else:
            input_bgr = img_np

        results: List[Dict[str, Any]] = []

        # Fast path: try pytesseract first if configured (sub-second on CPU)
        try:
            import pytesseract
            pil_img = Image.fromarray(cv2.cvtColor(input_bgr, cv2.COLOR_BGR2RGB))
            data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
            n_boxes = len(data.get("text", []))
            tess_results = []
            for i in range(n_boxes):
                txt = data["text"][i].strip()
                conf = float(data["conf"][i])
                if txt and conf > 0:
                    x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                    tess_results.append({
                        "text": txt,
                        "bbox": [float(y), float(x), float(y + h), float(x + w)],
                        "confidence": max(0.5, conf / 100.0),
                    })
            if len(tess_results) > 0 and sum(len(r["text"]) for r in tess_results) >= 20:
                return tess_results
        except Exception as exc:
            logger.debug("Pytesseract fast path skipped: %s", exc)

        if self._paddle_ocr is not None:
            try:
                preds = self._paddle_ocr.predict(input_bgr)
                for item in preds:
                    if isinstance(item, dict):
                        rec_texts = item.get("rec_texts", [])
                        rec_scores = item.get("rec_scores", [])
                        rec_boxes = item.get("rec_boxes", [])
                        rec_polys = item.get("rec_polys", [])

                        for idx, text in enumerate(rec_texts):
                            if not text or not text.strip():
                                continue
                            conf = float(rec_scores[idx]) if idx < len(rec_scores) else 0.90

                            if idx < len(rec_boxes):
                                box = rec_boxes[idx]
                                xmin, ymin, xmax, ymax = float(box[0]), float(box[1]), float(box[2]), float(box[3])
                            elif idx < len(rec_polys):
                                poly = rec_polys[idx]
                                xs = [pt[0] for pt in poly]
                                ys = [pt[1] for pt in poly]
                                xmin, xmax = min(xs), max(xs)
                                ymin, ymax = min(ys), max(ys)
                            else:
                                xmin, ymin, xmax, ymax = 0.0, 0.0, 0.0, 0.0

                            results.append({
                                "text": text.strip(),
                                "bbox": [ymin, xmin, ymax, xmax],
                                "confidence": conf,
                            })
                return results
            except Exception as exc:
                logger.warning("PaddleOCR prediction error: %s", exc)

        return results

    def _run_vision_fallback(
        self, img_np: np.ndarray, page_num: int = 1
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute vision-model fallback (Cohere command-a-vision or Groq qwen/qwen3.8-27b)."""
        settings = get_settings()

        # Prepare base64 image data URI
        try:
            h, w = img_np.shape[:2]
            # Resize if overly large to prevent API payload limit
            max_side = 1600
            if max(h, w) > max_side:
                scale = max_side / float(max(h, w))
                img_to_send = cv2.resize(img_np, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                img_to_send = img_np

            _, buf = cv2.imencode(".jpg", img_to_send, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            b64_str = base64.b64encode(buf).decode("utf-8")
            data_uri = f"data:image/jpeg;base64,{b64_str}"
        except Exception as enc_err:
            logger.warning("Failed to encode image for vision fallback: %s", enc_err)
            return None

        # 1. Try Cohere Vision
        cohere_key = settings.LLM_API_KEY
        if cohere_key:
            try:
                cohere_model = "command-a-vision-07-2025"
                url = "https://api.cohere.com/v2/chat"
                headers = {
                    "Authorization": f"Bearer {cohere_key}",
                    "Content-Type": "application/json",
                }
                body = {
                    "model": cohere_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": VISION_FALLBACK_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Extract all visible information from document page {page_num} into JSON.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_uri},
                                },
                            ],
                        },
                    ],
                }
                with httpx.Client(timeout=25.0) as client:
                    resp = client.post(url, headers=headers, json=body)
                    if resp.status_code == 200:
                        content_list = resp.json().get("message", {}).get("content", [])
                        raw_text = ""
                        for part in content_list:
                            if part.get("type") == "text":
                                raw_text += part.get("text", "")

                        parsed_blocks = self._parse_vision_response(raw_text)
                        if parsed_blocks:
                            logger.info("Vision fallback (Cohere %s) succeeded on page %d", cohere_model, page_num)
                            return parsed_blocks
            except Exception as cohere_err:
                logger.warning("Cohere vision fallback error: %s. Trying Groq vision.", cohere_err)

        # 2. Try Groq Vision Fallback
        groq_key = settings.LLM_FALLBACK_API_KEY
        if groq_key:
            try:
                groq_model = "qwen/qwen3.8-27b"
                url = "https://api.groq.com/openai/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {groq_key}",
                    "Content-Type": "application/json",
                }
                body = {
                    "model": groq_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": VISION_FALLBACK_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Extract all visible text from document page {page_num} into structured JSON.",
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": data_uri},
                                },
                            ],
                        },
                    ],
                    "temperature": 0.1,
                }
                with httpx.Client(timeout=20.0) as client:
                    resp = client.post(url, headers=headers, json=body)
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"]
                        parsed_blocks = self._parse_vision_response(content)
                        if parsed_blocks:
                            logger.info("Vision fallback (Groq %s) succeeded on page %d", groq_model, page_num)
                            return parsed_blocks
            except Exception as groq_err:
                logger.warning("Groq vision fallback error: %s", groq_err)

        return None

    def _parse_vision_response(self, raw_content: str) -> Optional[List[Dict[str, Any]]]:
        """Extract lines and structured fields from vision model JSON response."""
        try:
            clean_str = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content.strip(), flags=re.MULTILINE).strip()
            data = json.loads(clean_str)
            blocks: List[Dict[str, Any]] = []

            # Process detected_text
            detected = data.get("detected_text", [])
            if isinstance(detected, str):
                lines = [line.strip() for line in detected.splitlines() if line.strip()]
            elif isinstance(detected, list):
                lines = [str(item).strip() for item in detected if str(item).strip()]
            else:
                lines = []

            for idx, line in enumerate(lines):
                blocks.append({
                    "text": line,
                    "bbox": [float(idx * 40), 10.0, float((idx + 1) * 40), 800.0],
                    "confidence": 0.95,
                })

            # Process table_values if available
            table_values = data.get("table_values", [])
            if isinstance(table_values, list) and len(table_values) >= 2:
                for row in table_values:
                    if isinstance(row, list) and row:
                        row_text = " | ".join(str(cell) for cell in row)
                        blocks.append({
                            "text": row_text,
                            "bbox": [500.0, 10.0, 540.0, 800.0],
                            "confidence": 0.95,
                        })

            return blocks if blocks else None
        except Exception as parse_err:
            logger.warning("Could not parse structured vision fallback JSON: %s", parse_err)
            return None

    def process_image(
        self,
        raw_image: np.ndarray,
        page_num: int = 1,
        document_id: Optional[str] = None,
    ) -> OCRResult:
        """Execute multi-pass OCR strategy with adaptive quality profiling, table preservation, and vision fallback."""
        h, w = raw_image.shape[:2]

        # 1. Pre-OCR Image Quality Analysis (orientation, rotation, skew, sharpness, contrast, noise, resolution)
        quality_profile = ImagePreprocessor.analyze_image_quality(raw_image)

        # 2. Adaptive Preprocessing based on Quality Profile
        adaptive_prep = ImagePreprocessor.preprocess_adaptive(raw_image, quality_profile)
        primary_blocks_raw = self._run_raw_ocr(adaptive_prep.image)
        primary_quality = OCRQualityAssessment.calculate_quality_score(
            primary_blocks_raw, img_width=w, img_height=h
        )

        selected_prep = adaptive_prep
        selected_blocks_raw = primary_blocks_raw
        selected_quality = primary_quality
        engine_name = "paddleocr" if self._paddle_ocr else "tesseract"
        fallback_used = False
        secondary_used = False
        disagreement_detected = False

        # 3. Secondary Local OCR Escalation (Surya if available, or alternate adaptive binarization)
        # Triggered when primary quality is POOR, empty, or has uncertain critical fields
        if selected_quality.status != "GOOD" or not selected_quality.is_acceptable or not primary_blocks_raw:
            secondary_used = True
            sec_prep = ImagePreprocessor.preprocess_alternate(raw_image)
            sec_blocks_raw = self._run_raw_ocr(sec_prep.image)
            sec_quality = OCRQualityAssessment.calculate_quality_score(
                sec_blocks_raw, img_width=w, img_height=h
            )

            # Reconcile primary and secondary
            crit_primary = set(primary_quality.critical_fields_found)
            crit_sec = set(sec_quality.critical_fields_found)

            if crit_primary and crit_sec:
                if crit_primary == crit_sec:
                    # Both agree on critical fields -> elevate confidence
                    selected_quality.is_acceptable = True
                    selected_quality.status = "GOOD"
                else:
                    # Disagreement on critical fields -> flag conflict
                    disagreement_detected = True

            # If secondary produced superior results
            if (sec_quality.overall_score > primary_quality.overall_score and len(sec_blocks_raw) >= len(primary_blocks_raw)) or not primary_blocks_raw:
                selected_prep = sec_prep
                selected_blocks_raw = sec_blocks_raw
                selected_quality = sec_quality
                engine_name = "secondary_ocr"

            # 4. Vision Model Fallback (Cohere / Groq)
            # Escalates only if results remain POOR/unreadable or critical fields conflict
            if selected_quality.status == "POOR" or disagreement_detected or not selected_blocks_raw:
                vision_blocks = self._run_vision_fallback(raw_image, page_num=page_num)
                if vision_blocks:
                    selected_blocks_raw = vision_blocks
                    selected_quality = OCRQualityAssessment.calculate_quality_score(
                        vision_blocks, img_width=w, img_height=h
                    )
                    engine_name = "vision_fallback"
                    fallback_used = True

        # 5. Table Extraction and Structure Preservation
        final_blocks: List[DocumentBlock] = []
        used_raw_indices = set()
        table_idx = 1
        if len(selected_blocks_raw) >= 5:
            gray_for_tables = ImagePreprocessor.to_grayscale(selected_prep.image)
            table_regions = TableExtractor.detect_table_regions(gray_for_tables)
            for region in table_regions:
                table_block = TableExtractor.reconstruct_table_from_blocks(
                    region, selected_blocks_raw, page_num=page_num, table_idx=table_idx
                )
                if table_block:
                    table_block.page = page_num
                    table_block.ocr_engine = engine_name
                    table_block.processing_version = "ocr-v1.0"
                    table_block.orientation = selected_prep.orientation_angle
                    table_block.preprocessing = selected_prep.applied_transforms
                    table_block.metadata = {
                        "skew_angle": selected_prep.skew_angle,
                        "quality_status": selected_quality.status,
                    }
                    final_blocks.append(table_block)
                    table_idx += 1
                    rx, ry, rw, rh = region
                    for idx, b in enumerate(selected_blocks_raw):
                        by_min, bx_min, by_max, bx_max = b["bbox"]
                        if bx_min >= rx - 10 and bx_max <= rx + rw + 10 and by_min >= ry - 10 and by_max <= ry + rh + 10:
                            used_raw_indices.add(idx)

        # 6. Standard Text and Heading Blocks with Full Provenance Contract
        for idx, b in enumerate(selected_blocks_raw):
            if idx in used_raw_indices:
                continue
            text = b["text"].strip()
            if not text:
                continue

            is_heading = text.isupper() and len(text) < 80
            b_type = BlockType.HEADING if is_heading else BlockType.TEXT

            final_blocks.append(
                DocumentBlock(
                    block_id=f"p{page_num}_b{len(final_blocks)+1}",
                    type=b_type,
                    text=text,
                    bbox=b["bbox"],
                    confidence=b["confidence"],
                    page=page_num,
                    ocr_engine=engine_name,
                    processing_version="ocr-v1.0",
                    orientation=selected_prep.orientation_angle,
                    preprocessing=selected_prep.applied_transforms,
                    metadata={
                        "skew_angle": selected_prep.skew_angle,
                        "is_upscaled": selected_prep.is_upscaled,
                        "scale_factor": selected_prep.scale_factor,
                        "quality_status": selected_quality.status,
                    },
                )
            )

        if not final_blocks:
            final_blocks.append(
                DocumentBlock(
                    block_id=f"p{page_num}_unreadable",
                    type=BlockType.IMAGE,
                    text="[Unreadable or Blank Page]",
                    confidence=0.0,
                    page=page_num,
                    ocr_engine=engine_name,
                    processing_version="ocr-v1.0",
                    orientation=selected_prep.orientation_angle,
                    preprocessing=selected_prep.applied_transforms,
                )
            )

        total_chars = sum(len(b.text) for b in final_blocks)

        return OCRResult(
            blocks=final_blocks,
            quality_score=selected_quality,
            selected_variant=selected_prep.variant_name,
            ocr_engine=engine_name,
            skew_angle=selected_prep.skew_angle,
            orientation_angle=selected_prep.orientation_angle,
            is_upscaled=selected_prep.is_upscaled,
            scale_factor=selected_prep.scale_factor,
            total_characters=total_chars,
            applied_transforms=selected_prep.applied_transforms,
            fallback_used=fallback_used,
            secondary_used=secondary_used,
            disagreement_detected=disagreement_detected,
        )
