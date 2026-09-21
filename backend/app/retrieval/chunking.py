"""Structure-aware chunking engine for Phase 10 Hybrid Retrieval."""

import hashlib
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.pipeline.schemas import BlockType, DocumentBlock, NormalizedDocument


class RetrievalChunkData(BaseModel):
    """In-memory representation of a document retrieval chunk before persistence."""

    chunk_index: int
    page_number: int
    section: Optional[str] = None
    block_id: Optional[str] = None
    table_reference: Optional[str] = None
    content: str
    content_type: str = "TEXT"
    content_hash: str
    bbox: Optional[List[float]] = None
    source_reference: Optional[str] = None


def format_table_for_search(block: DocumentBlock) -> str:
    """
    Format structured table cells into search-friendly markdown preserving
    column headers and row relationships.
    """
    if not block.table_data or not block.table_data.rows:
        return block.text or ""

    lines = []
    headers = block.table_data.headers or [f"Column_{i+1}" for i in range(len(block.table_data.rows[0]))]
    clean_headers = [str(h).strip().replace("\n", " ") for h in headers]
    lines.append("| " + " | ".join(clean_headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(clean_headers)) + " |")

    for row in block.table_data.rows:
        clean_row = [str(cell).strip().replace("\n", " ") for cell in row]
        # Pad or trim if row length doesn't match headers
        if len(clean_row) < len(clean_headers):
            clean_row.extend([""] * (len(clean_headers) - len(clean_row)))
        elif len(clean_row) > len(clean_headers):
            clean_row = clean_row[:len(clean_headers)]
        lines.append("| " + " | ".join(clean_row) + " |")

    return "\n".join(lines)


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of normalized text."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def merge_bounding_boxes(bboxes: List[List[float]]) -> Optional[List[float]]:
    """Merge multiple [x0, y0, x1, y1] bounding boxes into an enclosing box."""
    valid_boxes = [b for b in bboxes if b and len(b) == 4]
    if not valid_boxes:
        return None
    min_x0 = min(b[0] for b in valid_boxes)
    min_y0 = min(b[1] for b in valid_boxes)
    max_x1 = max(b[2] for b in valid_boxes)
    max_y1 = max(b[3] for b in valid_boxes)
    return [round(min_x0, 4), round(min_y0, 4), round(max_x1, 4), round(max_y1, 4)]


def create_retrieval_chunks(
    normalized_doc: NormalizedDocument,
    max_chunk_chars: int = 1500,
) -> List[RetrievalChunkData]:
    """
    Structure-aware chunking of a NormalizedDocument:
    - Preserves headings and applies them as `section` context.
    - Treats tables as distinct, structured units to preserve column-row semantic relationships.
    - Preserves exact page numbers, block IDs, and bounding boxes.
    - Produces clean, deduplicated chunks with SHA-256 hashes.
    """
    chunks: List[RetrievalChunkData] = []
    chunk_index = 0
    current_section: Optional[str] = None

    for page in normalized_doc.pages:
        page_num = page.page_number
        current_text_parts: List[str] = []
        current_block_ids: List[str] = []
        current_bboxes: List[List[float]] = []
        current_char_count = 0

        for block in page.blocks:
            # 1. Heading blocks
            if block.type == BlockType.HEADING:
                heading_text = block.text.strip()
                current_section = heading_text

                # Flush prior text buffer if non-empty
                if current_text_parts:
                    content_str = "\n\n".join(current_text_parts).strip()
                    if content_str:
                        chunks.append(
                            RetrievalChunkData(
                                chunk_index=chunk_index,
                                page_number=page_num,
                                section=current_section,
                                block_id=",".join(current_block_ids),
                                table_reference=None,
                                content=content_str,
                                content_type="TEXT",
                                content_hash=compute_content_hash(content_str),
                                bbox=merge_bounding_boxes(current_bboxes),
                                source_reference=f"Page {page_num} | Blocks {','.join(current_block_ids)}",
                            )
                        )
                        chunk_index += 1
                        current_text_parts = []
                        current_block_ids = []
                        current_bboxes = []
                        current_char_count = 0

                # Also create a distinct HEADING chunk
                if heading_text:
                    chunks.append(
                        RetrievalChunkData(
                            chunk_index=chunk_index,
                            page_number=page_num,
                            section=heading_text,
                            block_id=block.block_id,
                            table_reference=None,
                            content=heading_text,
                            content_type="HEADING",
                            content_hash=compute_content_hash(heading_text),
                            bbox=block.bbox,
                            source_reference=f"Page {page_num} | Heading {block.block_id}",
                        )
                    )
                    chunk_index += 1
                continue

            # 2. Table blocks - keep tables standalone so relational integrity is preserved
            if block.type == BlockType.TABLE:
                # Flush prior text buffer
                if current_text_parts:
                    content_str = "\n\n".join(current_text_parts).strip()
                    if content_str:
                        chunks.append(
                            RetrievalChunkData(
                                chunk_index=chunk_index,
                                page_number=page_num,
                                section=current_section,
                                block_id=",".join(current_block_ids),
                                table_reference=None,
                                content=content_str,
                                content_type="TEXT",
                                content_hash=compute_content_hash(content_str),
                                bbox=merge_bounding_boxes(current_bboxes),
                                source_reference=f"Page {page_num} | Blocks {','.join(current_block_ids)}",
                            )
                        )
                        chunk_index += 1
                        current_text_parts = []
                        current_block_ids = []
                        current_bboxes = []
                        current_char_count = 0

                table_md = format_table_for_search(block)
                if table_md.strip():
                    chunks.append(
                        RetrievalChunkData(
                            chunk_index=chunk_index,
                            page_number=page_num,
                            section=current_section,
                            block_id=block.block_id,
                            table_reference=block.block_id,
                            content=table_md,
                            content_type="TABLE",
                            content_hash=compute_content_hash(table_md),
                            bbox=block.bbox,
                            source_reference=f"Page {page_num} | Table {block.block_id}",
                        )
                    )
                    chunk_index += 1
                continue

            # 3. Standard Text / Paragraph / List blocks
            block_text = block.text.strip()
            if not block_text:
                continue

            # Check if adding this block exceeds max_chunk_chars
            if current_char_count + len(block_text) > max_chunk_chars and current_text_parts:
                content_str = "\n\n".join(current_text_parts).strip()
                if content_str:
                    chunks.append(
                        RetrievalChunkData(
                            chunk_index=chunk_index,
                            page_number=page_num,
                            section=current_section,
                            block_id=",".join(current_block_ids),
                            table_reference=None,
                            content=content_str,
                            content_type="TEXT",
                            content_hash=compute_content_hash(content_str),
                            bbox=merge_bounding_boxes(current_bboxes),
                            source_reference=f"Page {page_num} | Blocks {','.join(current_block_ids)}",
                        )
                    )
                    chunk_index += 1
                    current_text_parts = []
                    current_block_ids = []
                    current_bboxes = []
                    current_char_count = 0

            current_text_parts.append(block_text)
            current_block_ids.append(block.block_id)
            if block.bbox:
                current_bboxes.append(block.bbox)
            current_char_count += len(block_text)

        # Flush any remaining page blocks
        if current_text_parts:
            content_str = "\n\n".join(current_text_parts).strip()
            if content_str:
                chunks.append(
                    RetrievalChunkData(
                        chunk_index=chunk_index,
                        page_number=page_num,
                        section=current_section,
                        block_id=",".join(current_block_ids),
                        table_reference=None,
                        content=content_str,
                        content_type="TEXT",
                        content_hash=compute_content_hash(content_str),
                        bbox=merge_bounding_boxes(current_bboxes),
                        source_reference=f"Page {page_num} | Blocks {','.join(current_block_ids)}",
                    )
                )
                chunk_index += 1

    return chunks
