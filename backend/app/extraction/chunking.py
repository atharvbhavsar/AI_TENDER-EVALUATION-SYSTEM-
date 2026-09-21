"""Context preparation and chunking for normalized document artifacts."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.pipeline.schemas import BlockType, DocumentBlock, NormalizedDocument


class BlockContext(BaseModel):
    """Metadata context for a single block in a chunk."""

    block_id: str
    page_number: int
    block_type: BlockType
    text: str
    bbox: Optional[List[float]] = None
    table_reference: Optional[str] = None


class ExtractionChunk(BaseModel):
    """A semantic document chunk prepared for LLM extraction while retaining source traces."""

    chunk_id: str
    document_id: uuid.UUID
    start_page: int
    end_page: int
    formatted_text: str
    blocks: List[BlockContext] = Field(default_factory=list)
    block_map: Dict[str, BlockContext] = Field(default_factory=dict)


def format_table_as_markdown(block: DocumentBlock) -> str:
    """Format structured table cells into markdown for LLM comprehension."""
    if not block.table_data or not block.table_data.rows:
        return block.text or ""

    lines = []
    headers = block.table_data.headers or [f"Column_{i+1}" for i in range(len(block.table_data.rows[0]))]
    lines.append("| " + " | ".join(str(h).strip() for h in headers) + " |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")

    for row in block.table_data.rows:
        lines.append("| " + " | ".join(str(cell).strip() for cell in row) + " |")

    return "\n".join(lines)


def create_extraction_chunks(
    normalized_doc: NormalizedDocument,
    max_chunk_chars: int = 4000,
) -> List[ExtractionChunk]:
    """
    Split normalized document pages and blocks into coherent extraction chunks.
    Ensures table representations and source metadata are preserved.
    """
    chunks: List[ExtractionChunk] = []
    current_blocks: List[BlockContext] = []
    current_block_map: Dict[str, BlockContext] = {}
    current_text_parts: List[str] = []
    current_char_count = 0
    start_page = 1
    end_page = 1
    chunk_index = 1

    for page in normalized_doc.pages:
        page_num = page.page_number

        for block in page.blocks:
            if block.type == BlockType.TABLE:
                block_content = format_table_as_markdown(block)
                formatted_block_text = f"[Page {page_num} | Table {block.block_id}]\n{block_content}\n"
            elif block.type == BlockType.HEADING:
                block_content = block.text.strip()
                formatted_block_text = f"\n### [Page {page_num} | Heading {block.block_id}] {block_content}\n"
            else:
                block_content = block.text.strip()
                formatted_block_text = f"[Page {page_num} | Block {block.block_id}] {block_content}\n"

            if not block_content:
                continue

            block_ctx = BlockContext(
                block_id=block.block_id,
                page_number=page_num,
                block_type=block.type,
                text=block_content,
                bbox=block.bbox,
                table_reference=block.block_id if block.type == BlockType.TABLE else None,
            )

            # Check if adding this block exceeds max_chunk_chars
            if current_char_count + len(formatted_block_text) > max_chunk_chars and current_blocks:
                # Flush current chunk
                chunks.append(
                    ExtractionChunk(
                        chunk_id=f"chunk_{chunk_index}",
                        document_id=normalized_doc.document_id,
                        start_page=start_page,
                        end_page=end_page,
                        formatted_text="".join(current_text_parts),
                        blocks=current_blocks,
                        block_map=current_block_map,
                    )
                )
                chunk_index += 1
                current_blocks = []
                current_block_map = {}
                current_text_parts = []
                current_char_count = 0
                start_page = page_num

            if not current_blocks:
                start_page = page_num

            end_page = page_num
            current_blocks.append(block_ctx)
            current_block_map[block.block_id] = block_ctx
            current_text_parts.append(formatted_block_text)
            current_char_count += len(formatted_block_text)

    # Flush remaining chunk
    if current_blocks:
        chunks.append(
            ExtractionChunk(
                chunk_id=f"chunk_{chunk_index}",
                document_id=normalized_doc.document_id,
                start_page=start_page,
                end_page=end_page,
                formatted_text="".join(current_text_parts),
                blocks=current_blocks,
                block_map=current_block_map,
            )
        )

    return chunks
