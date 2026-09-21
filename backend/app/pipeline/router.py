"""Parser routing and document format dispatch."""

import uuid
from typing import List
from app.pipeline.base import BaseDocumentParser
from app.pipeline.docx import DOCXDocumentParser
from app.pipeline.image import ImageDocumentParser
from app.pipeline.pdf import PDFDocumentParser
from app.pipeline.schemas import NormalizedDocument
from app.pipeline.spreadsheet import SpreadsheetDocumentParser

# Registered parsers
PARSERS: List[BaseDocumentParser] = [
    PDFDocumentParser(),
    DOCXDocumentParser(),
    SpreadsheetDocumentParser(),
    ImageDocumentParser(),
]


def parse_document(
    document_id: uuid.UUID,
    content: bytes,
    filename: str,
    file_extension: str,
) -> NormalizedDocument:
    """Route document to appropriate format parser based on file extension."""
    ext_lower = file_extension.lower()
    for parser in PARSERS:
        if parser.can_parse(ext_lower):
            return parser.parse(document_id=document_id, content=content, filename=filename)

    raise ValueError(f"No document parser available for file extension '{file_extension}'")
