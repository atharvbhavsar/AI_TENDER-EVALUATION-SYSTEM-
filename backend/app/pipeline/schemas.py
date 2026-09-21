"""Normalized document representation schemas for structured processing artifacts."""

import enum
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class BlockType(str, enum.Enum):
    """Controlled block classification for extracted document elements."""

    HEADING = "HEADING"
    TEXT = "TEXT"
    TABLE = "TABLE"
    LIST = "LIST"
    IMAGE = "IMAGE"


class TableData(BaseModel):
    """Structured table cell representation."""

    headers: List[str] = Field(default_factory=list)
    rows: List[List[str]] = Field(default_factory=list)


class DocumentBlock(BaseModel):
    """A distinct structural block of extracted content with source references and provenance."""

    block_id: str
    type: BlockType = BlockType.TEXT
    text: str = ""
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1] normalized or points
    confidence: float = 1.0
    table_data: Optional[TableData] = None
    page: Optional[int] = None
    ocr_engine: Optional[str] = None
    processing_version: Optional[str] = None
    orientation: Optional[int] = None
    preprocessing: Optional[List[str]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentPage(BaseModel):
    """A page within a multi-page document container."""

    page_number: int
    width: Optional[float] = None
    height: Optional[float] = None
    blocks: List[DocumentBlock] = Field(default_factory=list)


class NormalizedDocument(BaseModel):
    """Normalized document payload representing parsed layout, text, and tables."""

    document_id: uuid.UUID
    document_type: str
    processor_version: str
    page_count: int = 0
    total_characters: int = 0
    total_tables: int = 0
    pages: List[DocumentPage] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentProcessingStatusResponse(BaseModel):
    """Safe processing status response."""

    document_id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    status: str
    processor_version: str
    attempt_count: int
    max_attempts: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_code: Optional[str] = None
    worker_id: Optional[str] = None


class ProcessDocumentResponse(BaseModel):
    """Response when a document processing job is triggered or enqueued."""

    message: str
    job_id: uuid.UUID
    status: str
    document_id: Optional[uuid.UUID] = None


class DocumentBatchItemStatus(BaseModel):
    """Status details for an individual document within a batch."""

    document_id: uuid.UUID
    job_id: Optional[uuid.UUID] = None
    filename: str
    file_extension: str
    document_type: str
    status: str
    job_type: str = "DOCUMENT_PROCESSING"
    attempt_count: int = 0
    max_attempts: int = 3
    worker_id: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    failed_at: Optional[str] = None
    error_code: Optional[str] = None


class DocumentBatchStatusResponse(BaseModel):
    """Aggregated batch processing status for documents in a tender or submission."""

    total: int
    completed: int
    processing: int
    queued: int
    failed: int
    retrying: int
    is_complete: bool
    batch_type: Optional[str] = None
    tender_id: Optional[uuid.UUID] = None
    tender_version_id: Optional[uuid.UUID] = None
    submission_id: Optional[uuid.UUID] = None
    items: List[DocumentBatchItemStatus] = Field(default_factory=list)

