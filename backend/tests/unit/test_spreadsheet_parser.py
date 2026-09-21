"""Unit tests for XLSX spreadsheet parser."""

import io
import uuid
import openpyxl
import pytest
from app.pipeline.schemas import BlockType
from app.pipeline.spreadsheet import SpreadsheetDocumentParser


def make_sample_xlsx() -> bytes:
    """Generate a sample XLSX workbook in memory with tabular data."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ_Schedule"
    
    ws.append(["Schedule No", "Item Description", "Estimated Cost (INR)", "Mandatory"])
    ws.append(["SCH-01", "Bulletproof Jackets Level IV", "50000000", "Yes"])
    ws.append(["SCH-02", "Night Vision Goggles", "25000000", "Yes"])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_spreadsheet_parser_can_parse():
    parser = SpreadsheetDocumentParser()
    assert parser.can_parse(".xlsx") is True
    assert parser.can_parse(".XLSX") is True
    assert parser.can_parse(".pdf") is False


def test_spreadsheet_parser_success():
    parser = SpreadsheetDocumentParser()
    doc_id = uuid.uuid4()
    content = make_sample_xlsx()

    result = parser.parse(document_id=doc_id, content=content, filename="boq.xlsx")

    assert result.document_id == doc_id
    assert result.document_type == "SPREADSHEET"
    assert result.page_count == 1
    assert result.total_tables == 1
    assert len(result.pages) == 1

    blocks = result.pages[0].blocks
    assert len(blocks) >= 2

    heading_blocks = [b for b in blocks if b.type == BlockType.HEADING]
    assert len(heading_blocks) >= 1
    assert "BOQ_Schedule" in heading_blocks[0].text

    table_blocks = [b for b in blocks if b.type == BlockType.TABLE]
    assert len(table_blocks) == 1
    assert table_blocks[0].table_data is not None
    assert "Schedule No" in table_blocks[0].table_data.headers
    assert len(table_blocks[0].table_data.rows) == 2


def test_spreadsheet_parser_empty_content_raises():
    parser = SpreadsheetDocumentParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=b"", filename="empty.xlsx")
    assert "Empty spreadsheet" in str(exc_info.value)


def test_spreadsheet_parser_corrupted_raises():
    parser = SpreadsheetDocumentParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=b"PK\x03\x04corrupted excel payload", filename="bad.xlsx")
    assert "Corrupted or invalid spreadsheet" in str(exc_info.value)
