"""Unit tests for Image document parser."""

import io
import uuid
from PIL import Image
import pytest
from app.pipeline.image import ImageDocumentParser
from app.pipeline.schemas import BlockType


def make_sample_image(format: str = "PNG", size=(200, 100)) -> bytes:
    """Generate sample image in memory."""
    img = Image.new("RGB", size, color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format=format)
    return buf.getvalue()


def test_image_parser_can_parse():
    parser = ImageDocumentParser()
    assert parser.can_parse(".png") is True
    assert parser.can_parse(".jpg") is True
    assert parser.can_parse(".jpeg") is True
    assert parser.can_parse(".pdf") is False


def test_image_parser_png_success():
    parser = ImageDocumentParser()
    doc_id = uuid.uuid4()
    content = make_sample_image("PNG", size=(300, 150))

    result = parser.parse(document_id=doc_id, content=content, filename="site_map.png")

    assert result.document_id == doc_id
    assert result.document_type == "PHOTOGRAPH"
    assert result.page_count == 1
    assert len(result.pages) == 1
    assert result.pages[0].width == 300.0
    assert result.pages[0].height == 150.0
    assert len(result.pages[0].blocks) >= 1


def test_image_parser_jpeg_success():
    parser = ImageDocumentParser()
    doc_id = uuid.uuid4()
    content = make_sample_image("JPEG", size=(400, 200))

    result = parser.parse(document_id=doc_id, content=content, filename="armor_sample.jpg")

    assert result.document_id == doc_id
    assert result.document_type == "PHOTOGRAPH"
    assert result.pages[0].width == 400.0


def test_image_parser_empty_content_raises():
    parser = ImageDocumentParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=b"", filename="empty.png")
    assert "Empty image" in str(exc_info.value)


def test_image_parser_corrupted_raises():
    parser = ImageDocumentParser()
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=b"\x89PNG\r\n\x1a\ncorrupted bytes", filename="bad.png")
    assert "Corrupted or invalid image" in str(exc_info.value)


def test_image_parser_pixel_limit_enforced(monkeypatch):
    parser = ImageDocumentParser()
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "MAX_IMAGE_PIXELS", 100)

    content = make_sample_image("PNG", size=(50, 50))  # 2500 pixels > 100
    with pytest.raises(ValueError) as exc_info:
        parser.parse(document_id=uuid.uuid4(), content=content, filename="large.png")
    assert "exceed limit" in str(exc_info.value)
