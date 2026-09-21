"""Document Pydantic schemas for API requests and responses."""

import datetime
import uuid
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.document import DocumentType, ProcessingStatus


class DocumentResponse(BaseModel):
    """Document metadata response representation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_version_id: uuid.UUID
    filename: str
    content_type: str
    file_extension: str
    file_size: int
    sha256_hash: str
    storage_key: str
    document_type: DocumentType
    processing_status: ProcessingStatus
    uploaded_by: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    job_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None

    def model_post_init(self, __context: Any) -> None:
        if self.document_id is None and self.id is not None:
            self.document_id = self.id


class DocumentListResponse(BaseModel):
    """Paginated document response."""

    items: List[DocumentResponse]
    total: int
    limit: int
    offset: int
