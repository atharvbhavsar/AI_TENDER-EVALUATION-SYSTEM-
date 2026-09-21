"""Pydantic schemas for Hybrid Retrieval and Document Indexing."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChunkSourceMetadata(BaseModel):
    """Source traceability information for a retrieved chunk."""

    document_id: uuid.UUID
    document_name: Optional[str] = None
    page_number: int
    section: Optional[str] = None
    block_id: Optional[str] = None
    table_reference: Optional[str] = None
    bbox: Optional[List[float]] = None
    source_reference: Optional[str] = None


class RetrievalChunkResponse(BaseModel):
    """Full detail of an indexed retrieval chunk."""

    id: uuid.UUID
    document_id: uuid.UUID
    bid_submission_id: Optional[uuid.UUID] = None
    bidder_id: Optional[uuid.UUID] = None
    tender_version_id: uuid.UUID
    tender_id: uuid.UUID
    chunk_index: int
    page_number: int
    section: Optional[str] = None
    block_id: Optional[str] = None
    table_reference: Optional[str] = None
    content: str
    content_type: str
    content_hash: str
    bbox: Optional[List[float]] = None
    source_reference: Optional[str] = None
    embedding_model: str
    embedding_model_version: str
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class HybridSearchResultItem(BaseModel):
    """A ranked search result item combining lexical and semantic scores."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_name: Optional[str] = None
    page: int
    section: Optional[str] = None
    block_id: Optional[str] = None
    table_reference: Optional[str] = None
    content: str
    content_type: str = "TEXT"
    bbox: Optional[List[float]] = None
    source_reference: Optional[str] = None
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    hybrid_score: float = 0.0
    rank: int


class HybridSearchResponse(BaseModel):
    """Response payload for hybrid search queries."""

    submission_id: uuid.UUID
    criterion_id: Optional[uuid.UUID] = None
    query_text: str
    total_candidates: int
    returned_count: int
    lexical_weight: float
    semantic_weight: float
    results: List[HybridSearchResultItem] = Field(default_factory=list)


class CriterionSearchRequest(BaseModel):
    """Request to retrieve submission evidence chunks matching an approved criterion."""

    criterion_id: uuid.UUID
    top_k: Optional[int] = Field(default=10, ge=1, le=50)
    lexical_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    semantic_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class TextSearchRequest(BaseModel):
    """Request to perform hybrid retrieval using an arbitrary text query."""

    query: str = Field(..., min_length=1, max_length=1000)
    top_k: Optional[int] = Field(default=10, ge=1, le=50)
    lexical_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    semantic_weight: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class IndexDocumentResponse(BaseModel):
    """Response payload for document indexing operation."""

    document_id: uuid.UUID
    status: str
    chunks_indexed: int
    embedding_model: str
    embedding_model_version: str
    indexer_version: str
    message: str


class DocumentChunksResponse(BaseModel):
    """Response payload listing chunks of a document."""

    document_id: uuid.UUID
    total_chunks: int
    chunks: List[RetrievalChunkResponse] = Field(default_factory=list)
