"""Table-aware extraction module for financial and technical specification tables."""

import logging
from typing import Any, Dict, List, Optional, Tuple
import cv2
import numpy as np

from app.pipeline.schemas import BlockType, DocumentBlock, TableData

logger = logging.getLogger("app.pipeline.ocr.tables")


class TableExtractor:
    """Detects table boundaries, reconstructs row/column matrices, and creates TableData blocks."""

    @classmethod
    def detect_table_regions(cls, gray_image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect rectangular table bounding boxes [x, y, w, h] using morphological line kernels."""
        if gray_image is None or gray_image.size == 0:
            return []

        h, w = gray_image.shape[:2]
        # Binarize
        thresh = cv2.adaptiveThreshold(
            ~gray_image,
            255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            15,
            -2,
        )

        # Horizontal lines kernel
        horizontal = thresh.copy()
        scale_h = max(20, w // 30)
        h_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (scale_h, 1))
        horizontal = cv2.erode(horizontal, h_structure)
        horizontal = cv2.dilate(horizontal, h_structure)

        # Vertical lines kernel
        vertical = thresh.copy()
        scale_v = max(20, h // 30)
        v_structure = cv2.getStructuringElement(cv2.MORPH_RECT, (1, scale_v))
        vertical = cv2.erode(vertical, v_structure)
        vertical = cv2.dilate(vertical, v_structure)

        # Table grid mask
        table_mask = horizontal + vertical

        # Find external contours of table grids
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        table_boxes = []
        for c in contours:
            area = cv2.contourArea(c)
            if area > (w * h * 0.03):  # Must occupy at least 3% of page
                bx, by, bw, bh = cv2.boundingRect(c)
                # Ensure it looks like a table (wide enough)
                if bw > w * 0.3 and bh > 50:
                    table_boxes.append((bx, by, bw, bh))

        return table_boxes

    @classmethod
    def reconstruct_table_from_blocks(
        cls,
        table_box: Tuple[int, int, int, int],
        text_blocks: List[Dict[str, Any]],
        page_num: int,
        table_idx: int = 1,
    ) -> Optional[DocumentBlock]:
        """Group text blocks inside a table bounding box into structured rows and columns."""
        tx, ty, tw, th = table_box
        t_right = tx + tw
        t_bottom = ty + th

        # Filter blocks inside table bounding box
        inside_blocks = []
        for b in text_blocks:
            bbox = b.get("bbox", [0, 0, 0, 0])
            # Handle normalized [0..1000] or absolute coords
            by_min, bx_min, by_max, bx_max = bbox
            if bx_min >= tx - 10 and bx_max <= t_right + 10 and by_min >= ty - 10 and by_max <= t_bottom + 10:
                inside_blocks.append(b)

        if len(inside_blocks) < 2:
            return None

        # Sort blocks top-to-bottom, left-to-right
        inside_blocks.sort(key=lambda b: (b["bbox"][0], b["bbox"][1]))

        # Cluster into rows based on y-coordinate proximity
        rows_data: List[List[Dict[str, Any]]] = []
        current_row: List[Dict[str, Any]] = []
        current_y = inside_blocks[0]["bbox"][0]
        row_threshold = 20  # pixel tolerance for same row

        for b in inside_blocks:
            by = b["bbox"][0]
            if abs(by - current_y) <= row_threshold:
                current_row.append(b)
            else:
                if current_row:
                    current_row.sort(key=lambda item: item["bbox"][1])  # sort left-to-right
                    rows_data.append(current_row)
                current_row = [b]
                current_y = by

        if current_row:
            current_row.sort(key=lambda item: item["bbox"][1])
            rows_data.append(current_row)

        if not rows_data:
            return None

        # Headers from first row, data from subsequent rows
        headers = [b["text"].strip() for b in rows_data[0]]
        extracted_rows: List[List[str]] = []
        for row in rows_data[1:]:
            extracted_rows.append([b["text"].strip() for b in row])

        table_data = TableData(headers=headers, rows=extracted_rows)
        raw_text_repr = f"Table ({len(headers)} cols x {len(extracted_rows)+1} rows):\n"
        raw_text_repr += " | ".join(headers) + "\n"
        for r in extracted_rows:
            raw_text_repr += " | ".join(r) + "\n"

        return DocumentBlock(
            block_id=f"p{page_num}_table_{table_idx}",
            type=BlockType.TABLE,
            text=raw_text_repr.strip(),
            bbox=[float(ty), float(tx), float(t_bottom), float(t_right)],
            confidence=0.95,
            table_data=table_data,
        )
