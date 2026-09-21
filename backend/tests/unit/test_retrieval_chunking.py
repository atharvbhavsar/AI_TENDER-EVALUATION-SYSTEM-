"""Unit tests for Phase 10 structure-aware retrieval chunking engine."""

import uuid
import pytest
from app.pipeline.schemas import (
    BlockType,
    DocumentBlock,
    DocumentPage,
    NormalizedDocument,
    TableData,
)
from app.retrieval.chunking import (
    compute_content_hash,
    create_retrieval_chunks,
    format_table_for_search,
    merge_bounding_boxes,
)


def test_compute_content_hash():
    text1 = "Turnover requirement of ₹10 crore."
    text2 = "Turnover   requirement of ₹10   crore. "
    text3 = "Different text content."

    # Normalized whitespace produces identical hash
    assert compute_content_hash(text1) == compute_content_hash(text2)
    assert compute_content_hash(text1) != compute_content_hash(text3)
    assert len(compute_content_hash(text1)) == 64


def test_merge_bounding_boxes():
    box1 = [10.0, 20.0, 100.0, 150.0]
    box2 = [50.0, 10.0, 200.0, 180.0]
    merged = merge_bounding_boxes([box1, box2])
    assert merged == [10.0, 10.0, 200.0, 180.0]

    assert merge_bounding_boxes([]) is None
    assert merge_bounding_boxes([None, []]) is None


def test_format_table_for_search():
    block = DocumentBlock(
        block_id="tbl_1",
        type=BlockType.TABLE,
        table_data=TableData(
            headers=["Financial Year", "Turnover (INR Cr)", "Net Profit (INR Cr)"],
            rows=[
                ["2022-23", "12.5", "1.8"],
                ["2023-24", "18.2", "2.5"],
                ["2024-25", "22.0", "3.1"],
            ],
        ),
    )

    md = format_table_for_search(block)
    assert "| Financial Year | Turnover (INR Cr) | Net Profit (INR Cr) |" in md
    assert "| 2022-23 | 12.5 | 1.8 |" in md
    assert "| 2024-25 | 22.0 | 3.1 |" in md


def test_create_retrieval_chunks_structure_awareness():
    doc_id = uuid.uuid4()
    norm_doc = NormalizedDocument(
        document_id=doc_id,
        document_type="PDF",
        processor_version="1.0.0",
        page_count=2,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="b1",
                        type=BlockType.HEADING,
                        text="1. Technical Experience",
                        bbox=[50.0, 50.0, 300.0, 80.0],
                    ),
                    DocumentBlock(
                        block_id="b2",
                        type=BlockType.TEXT,
                        text="The bidder must have completed at least 3 security infrastructure assignments.",
                        bbox=[50.0, 90.0, 500.0, 150.0],
                    ),
                    DocumentBlock(
                        block_id="b3",
                        type=BlockType.TABLE,
                        table_data=TableData(
                            headers=["Project Name", "Client", "Value (Cr)"],
                            rows=[
                                ["CRPF Camp Perimeter", "CRPF", "15.0"],
                                ["Border Surveillance", "MHA", "22.0"],
                            ],
                        ),
                        bbox=[50.0, 160.0, 500.0, 300.0],
                    ),
                ],
            ),
            DocumentPage(
                page_number=2,
                blocks=[
                    DocumentBlock(
                        block_id="b4",
                        type=BlockType.HEADING,
                        text="2. Financial Standing",
                    ),
                    DocumentBlock(
                        block_id="b5",
                        type=BlockType.TEXT,
                        text="Audited annual turnover for the last 3 financial years must exceed ₹10 crore.",
                    ),
                ],
            ),
        ],
    )

    chunks = create_retrieval_chunks(norm_doc, max_chunk_chars=1000)
    assert len(chunks) == 5

    # Heading 1 chunk
    assert chunks[0].content_type == "HEADING"
    assert chunks[0].section == "1. Technical Experience"
    assert chunks[0].page_number == 1

    # Text block chunk under Heading 1
    assert chunks[1].content_type == "TEXT"
    assert "security infrastructure assignments" in chunks[1].content
    assert chunks[1].section == "1. Technical Experience"
    assert chunks[1].page_number == 1

    # Table chunk
    assert chunks[2].content_type == "TABLE"
    assert chunks[2].table_reference == "b3"
    assert "| Project Name | Client | Value (Cr) |" in chunks[2].content
    assert chunks[2].page_number == 1

    # Heading 2 chunk
    assert chunks[3].content_type == "HEADING"
    assert chunks[3].section == "2. Financial Standing"
    assert chunks[3].page_number == 2

    # Text block chunk under Heading 2
    assert chunks[4].content_type == "TEXT"
    assert "Audited annual turnover" in chunks[4].content
    assert chunks[4].section == "2. Financial Standing"
    assert chunks[4].page_number == 2


def test_empty_document_produces_no_chunks():
    doc_id = uuid.uuid4()
    empty_doc = NormalizedDocument(
        document_id=doc_id,
        document_type="PDF",
        processor_version="1.0.0",
        pages=[],
    )
    chunks = create_retrieval_chunks(empty_doc)
    assert chunks == []
