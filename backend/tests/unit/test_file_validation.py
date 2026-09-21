"""Unit tests for document validation, security checks, and magic byte verification."""

import io
import zipfile
import pytest
from fastapi import HTTPException

from app.documents.validators import (
    ALLOWED_EXTENSIONS_MAP,
    generate_storage_key,
    sanitize_filename,
    validate_file_signature,
)


def create_dummy_docx_bytes() -> bytes:
    """Create a minimal valid DOCX/XLSX zip container with [Content_Types].xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types></Types>')
        zf.writestr("word/document.xml", "<document>Sample CRPF Tender Specifications</document>")
    return buf.getvalue()


def create_dummy_xlsx_bytes() -> bytes:
    """Create a minimal valid XLSX zip container with [Content_Types].xml."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8"?><Types></Types>')
        zf.writestr("xl/workbook.xml", "<workbook>Sample CRPF BOQ Sheet</workbook>")
    return buf.getvalue()


def test_sanitize_filename_valid():
    safe_name, ext = sanitize_filename("Tender_Notice_2026.pdf")
    assert safe_name == "Tender_Notice_2026.pdf"
    assert ext == ".pdf"


def test_sanitize_filename_path_traversal():
    with pytest.raises(HTTPException) as exc_info:
        sanitize_filename("../../etc/passwd.pdf")
    assert exc_info.value.status_code == 400
    assert "path traversal" in exc_info.value.detail.lower()

    with pytest.raises(HTTPException) as exc_info:
        sanitize_filename("..\\..\\windows\\system32\\calc.exe")
    assert exc_info.value.status_code == 400


def test_sanitize_filename_null_byte():
    with pytest.raises(HTTPException) as exc_info:
        sanitize_filename("innocent.pdf\x00malicious.exe")
    assert exc_info.value.status_code == 400


def test_sanitize_filename_empty():
    with pytest.raises(HTTPException) as exc_info:
        sanitize_filename("   ")
    assert exc_info.value.status_code == 400


def test_validate_file_signature_pdf_valid():
    valid_pdf = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    # Should not raise
    validate_file_signature(valid_pdf, ".pdf")


def test_validate_file_signature_pdf_invalid():
    invalid_pdf = b"This is just plain text masquerading as a PDF document."
    with pytest.raises(HTTPException) as exc_info:
        validate_file_signature(invalid_pdf, ".pdf")
    assert exc_info.value.status_code == 400
    assert "Invalid file signature" in exc_info.value.detail


def test_validate_file_signature_jpeg_valid():
    valid_jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
    validate_file_signature(valid_jpeg, ".jpg")
    validate_file_signature(valid_jpeg, ".jpeg")


def test_validate_file_signature_png_valid():
    valid_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    validate_file_signature(valid_png, ".png")


def test_validate_file_signature_ole_doc_valid():
    valid_doc = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 50
    validate_file_signature(valid_doc, ".doc")


def test_validate_file_signature_docx_and_xlsx_valid():
    docx_bytes = create_dummy_docx_bytes()
    validate_file_signature(docx_bytes, ".docx")

    xlsx_bytes = create_dummy_xlsx_bytes()
    validate_file_signature(xlsx_bytes, ".xlsx")


def test_validate_file_signature_docx_missing_manifest():
    # Zip without [Content_Types].xml
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("test.txt", "hello")
    bad_zip = buf.getvalue()

    with pytest.raises(HTTPException) as exc_info:
        validate_file_signature(bad_zip, ".docx")
    assert exc_info.value.status_code == 400
    assert "Missing Open Packaging Convention manifest" in exc_info.value.detail


def test_validate_file_signature_rejects_executable():
    pe_executable = b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 100
    with pytest.raises(HTTPException) as exc_info:
        validate_file_signature(pe_executable, ".pdf")
    assert exc_info.value.status_code == 400
    assert "Executable binaries are strictly prohibited" in exc_info.value.detail


def test_validate_file_signature_rejects_html_injection():
    html_spoof = b"<!DOCTYPE html><html><script>alert('xss')</script></html>"
    with pytest.raises(HTTPException) as exc_info:
        validate_file_signature(html_spoof, ".pdf")
    assert exc_info.value.status_code == 400
    assert "HTML or script content detected" in exc_info.value.detail


def test_archive_safety_rejects_internal_path_traversal():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
        zf.writestr("../evil.txt", "payload")
    malicious_docx = buf.getvalue()

    with pytest.raises(HTTPException) as exc_info:
        validate_file_signature(malicious_docx, ".docx")
    assert exc_info.value.status_code == 400
    assert "Archive safety violation" in exc_info.value.detail


def test_generate_storage_key():
    import uuid
    t_id = uuid.uuid4()
    v_id = uuid.uuid4()
    d_id = uuid.uuid4()
    key = generate_storage_key(t_id, v_id, d_id, "safe_tender.pdf")
    assert key == f"documents/tender/{t_id}/version/{v_id}/{d_id}/safe_tender.pdf"
