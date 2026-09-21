"""FastAPI API routes for Phase 10 Hybrid Retrieval & Evidence Search."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.user import User
from app.db.session import get_db
from app.retrieval.schemas import (
    CriterionSearchRequest,
    DocumentChunksResponse,
    HybridSearchResponse,
    IndexDocumentResponse,
    RetrievalChunkResponse,
    TextSearchRequest,
)
from app.retrieval.service import (
    index_document_chunks,
    list_document_chunks,
    search_submission_by_criterion,
    search_submission_by_text,
)

router = APIRouter(tags=["Retrieval & Evidence Search"])


@router.post(
    "/documents/{document_id}/index",
    response_model=IndexDocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Index document into searchable chunks with embeddings",
)
def index_document_endpoint(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_UPLOAD")),
) -> IndexDocumentResponse:
    """
    Break a completed document into structure-aware retrieval chunks,
    generate vector embeddings, and populate PostgreSQL FTS + pgvector.
    """
    return index_document_chunks(db=db, document_id=document_id)


@router.get(
    "/documents/{document_id}/chunks",
    response_model=DocumentChunksResponse,
    status_code=status.HTTP_200_OK,
    summary="List all indexed chunks for a document",
)
def list_document_chunks_endpoint(
    document_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
) -> DocumentChunksResponse:
    """Retrieve all indexed chunks and source bounding box metadata for a document."""
    items, total = list_document_chunks(db=db, document_id=document_id, skip=skip, limit=limit)
    return DocumentChunksResponse(
        document_id=document_id,
        total_chunks=total,
        chunks=[RetrievalChunkResponse.model_validate(c) for c in items],
    )


@router.post(
    "/submissions/{submission_id}/retrieval/search",
    response_model=HybridSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Hybrid evidence search targeting an approved tender criterion",
)
def search_by_criterion_endpoint(
    submission_id: uuid.UUID,
    request: CriterionSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVIDENCE_READ")),
) -> HybridSearchResponse:
    """
    Execute hybrid search (Lexical FTS + Semantic Cosine Similarity) scoped to
    the bidder submission using an officer-approved tender criterion.
    """
    return search_submission_by_criterion(
        db=db,
        submission_id=submission_id,
        criterion_id=request.criterion_id,
        top_k=request.top_k or 10,
        lexical_weight=request.lexical_weight,
        semantic_weight=request.semantic_weight,
    )


@router.post(
    "/submissions/{submission_id}/retrieval/query",
    response_model=HybridSearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Controlled hybrid evidence search using arbitrary text query",
)
def search_by_text_endpoint(
    submission_id: uuid.UUID,
    request: TextSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVIDENCE_READ")),
) -> HybridSearchResponse:
    """
    Execute controlled hybrid search across a bidder's submitted documents using
    a specific query string. Scoped strictly to the specified submission.
    """
    return search_submission_by_text(
        db=db,
        submission_id=submission_id,
        query_text=request.query,
        top_k=request.top_k or 10,
        lexical_weight=request.lexical_weight,
        semantic_weight=request.semantic_weight,
    )
