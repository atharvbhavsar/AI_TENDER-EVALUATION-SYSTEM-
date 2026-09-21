"""Unit tests for document context chunking and table formatting."""

import uuid
from app.extraction.chunking import create_extraction_chunks, format_table_as_markdown
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument, TableData


def test_format_table_as_markdown():
    """Test converting structured table rows to markdown representation."""
    block = DocumentBlock(
        block_id="tbl-1",
        type=BlockType.TABLE,
        table_data=TableData(
            headers=["Criterion", "Minimum Requirement", "Evidence Required"],
            rows=[
                ["Annual Turnover", "₹5 Crore", "Audited Balance Sheets"],
                ["Past Experience", "3 Projects", "Completion Certificates"],
            ],
        ),
    )
    md = format_table_as_markdown(block)
    assert "| Criterion | Minimum Requirement | Evidence Required |" in md
    assert "| Annual Turnover | ₹5 Crore | Audited Balance Sheets |" in md
    assert "| Past Experience | 3 Projects | Completion Certificates |" in md


def test_create_extraction_chunks_single_page():
    """Test chunking a single page document."""
    doc_id = uuid.uuid4()
    norm_doc = NormalizedDocument(
        document_id=doc_id,
        document_type="DIGITAL_PDF",
        processor_version="1.0.0",
        page_count=1,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(block_id="b1", type=BlockType.HEADING, text="Section 1: Eligibility"),
                    DocumentBlock(block_id="b2", type=BlockType.TEXT, text="Turnover shall be at least ₹5 Crore."),
                ],
            )
        ],
    )

    chunks = create_extraction_chunks(norm_doc, max_chunk_chars=1000)
    assert len(chunks) == 1
    assert chunks[0].document_id == doc_id
    assert chunks[0].start_page == 1
    assert chunks[0].end_page == 1
    assert "Section 1: Eligibility" in chunks[0].formatted_text
    assert "Turnover shall be at least ₹5 Crore." in chunks[0].formatted_text
    assert "b1" in chunks[0].block_map
    assert "b2" in chunks[0].block_map


def test_create_extraction_chunks_multi_page_splitting():
    """Test chunking large multi-page document across size thresholds."""
    doc_id = uuid.uuid4()
    pages = []
    for p in range(1, 6):
        pages.append(
            DocumentPage(
                page_number=p,
                blocks=[
                    DocumentBlock(block_id=f"b_{p}_1", type=BlockType.TEXT, text=f"Page {p} long specification text " * 30),
                ],
            )
        )

    norm_doc = NormalizedDocument(
        document_id=doc_id,
        document_type="DIGITAL_PDF",
        processor_version="1.0.0",
        page_count=5,
        pages=pages,
    )

    chunks = create_extraction_chunks(norm_doc, max_chunk_chars=500)
    assert len(chunks) > 1
    # Verify continuous page tracking
    for chunk in chunks:
        assert chunk.document_id == doc_id
        assert chunk.start_page <= chunk.end_page
        assert len(chunk.blocks) > 0
