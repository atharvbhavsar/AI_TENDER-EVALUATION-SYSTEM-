"""Unit tests for PDF document parser."""

import uuid
import pytest
from app.pipeline.pdf import PDFDocumentParser
from app.pipeline.schemas import BlockType


def make_sample_pdf(text: str = "CRPF TENDER SPECIFICATIONS\nAnnual turnover must be at least Rs 5 Crore.\n1. Bidder must have valid GST registration.") -> bytes:
    content = f"BT /F1 12 Tf 50 750 Td ({text}) Tj ET".encode("latin-1")
    stream_len = len(content)
    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length {stream_len} >>
stream
{content.decode('latin-1')}
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000234 00000 n 
0000000300 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
370
%%EOF
"""
    return pdf.encode("latin-1")


def test_pdf_parser_can_parse():
    parser = PDFDocumentParser()
    assert parser.can_parse(".pdf") is True
    assert parser.can_parse(".PDF") is True
    assert parser.can_parse(".docx") is False


def test_pdf_parser_digital_pdf_success():
    parser = PDFDocumentParser()
    doc_id = uuid.uuid4()
    pdf_bytes = make_sample_pdf()

    result = parser.parse(document_id=doc_id, content=pdf_bytes, filename="tender_specs.pdf")

    assert result.document_id == doc_id
    assert result.page_count == 1
    assert result.document_type == "DIGITAL_PDF"
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].width == 595.0
    assert result.pages[0].height == 842.0
    assert len(result.pages[0].blocks) >= 1


def test_pdf_parser_empty_content_raises():
    parser = PDFDocumentParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=b"", filename="empty.pdf")
    assert "Empty PDF" in str(exc_info.value)


def test_pdf_parser_corrupted_pdf_raises():
    parser = PDFDocumentParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=b"%PDF-1.4 garbage truncated corrupted bytes", filename="bad.pdf")
    assert "Corrupted or invalid" in str(exc_info.value) or "Invalid PDF" in str(exc_info.value)


def test_pdf_parser_page_limit_enforced(monkeypatch):
    parser = PDFDocumentParser()
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_DOCUMENT_PAGES", 0)

    pdf_bytes = make_sample_pdf()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=pdf_bytes, filename="large.pdf")
    assert "exceeds maximum allowed limit" in str(exc_info.value)
