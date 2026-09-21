"""Abstract base parser interface for document format processors."""

import uuid
from abc import ABC, abstractmethod
from app.pipeline.schemas import NormalizedDocument


class BaseDocumentParser(ABC):
    """Abstract interface for format-specific document processors."""

    @abstractmethod
    def can_parse(self, file_extension: str) -> bool:
        """Check if parser handles given file extension."""
        raise NotImplementedError

    @abstractmethod
    def parse(
        self,
        document_id: uuid.UUID,
        content: bytes,
        filename: str,
    ) -> NormalizedDocument:
        """Extract structured text, tables, and page layout from binary document content."""
        raise NotImplementedError
