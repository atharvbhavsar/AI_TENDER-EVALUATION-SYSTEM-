"""Domain service for document chunk indexing and hybrid evidence retrieval."""

import json
import logging
import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.bid_submission import BidSubmission
from app.db.models.document import Document, ProcessingStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.retrieval_chunk import RetrievalChunk
from app.db.models.tender_criterion import ApprovalStatus, TenderCriterion
from app.pipeline.schemas import NormalizedDocument
from app.retrieval.chunking import create_retrieval_chunks
from app.retrieval.embeddings.base import BaseEmbeddingClient
from app.retrieval.embeddings.client import get_embedding_client
from app.retrieval.schemas import (
    HybridSearchResponse,
    IndexDocumentResponse,
)
from app.retrieval.search import (
    combine_and_rank_results,
    execute_lexical_search,
    execute_semantic_search,
)
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

logger = logging.getLogger("app.retrieval.service")


def index_document_chunks(
    db: Session,
    document_id: uuid.UUID,
    storage: Optional[ObjectStorageService] = None,
    embedding_client: Optional[BaseEmbeddingClient] = None,
) -> IndexDocumentResponse:
    """
    Index a successfully processed document into searchable retrieval chunks:
    1. Loads document entity and verifies COMPLETED processing status.
    2. Downloads NORMALIZED_CONTENT processing artifact from object storage.
    3. Breaks document layout into structure-aware retrieval chunks preserving tables & bounding boxes.
    4. Computes deterministic embeddings in batch.
    5. Persists chunks idempotently to PostgreSQL/pgvector.
    """
    settings = get_settings()
    storage = storage or get_storage_service()
    embedding_client = embedding_client or get_embedding_client()

    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    if doc.processing_status != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot index document {document_id} with status '{doc.processing_status}'. Document must be COMPLETED.",
        )

    # Fetch normalized document artifact
    art_stmt = select(ProcessingArtifact).where(
        ProcessingArtifact.document_id == document_id,
        ProcessingArtifact.artifact_type == ArtifactType.NORMALIZED_CONTENT,
    )
    artifact_record = db.execute(art_stmt).scalar_one_or_none()
    if not artifact_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No NORMALIZED_CONTENT artifact found for document {document_id}. Reprocess document first.",
        )

    try:
        # Download and deserialize artifact
        stream = storage.download(artifact_record.storage_key)
        raw_bytes = stream.read()
        norm_dict = json.loads(raw_bytes.decode("utf-8"))
        normalized_doc = NormalizedDocument.model_validate(norm_dict)

        # Generate structure-aware chunks
        chunks_data = create_retrieval_chunks(
            normalized_doc=normalized_doc,
            max_chunk_chars=settings.MAX_RETRIEVAL_CHUNK_CHARS,
        )

        if not chunks_data:
            return IndexDocumentResponse(
                document_id=document_id,
                status="COMPLETED",
                chunks_indexed=0,
                embedding_model=embedding_client.model_name,
                embedding_model_version=embedding_client.model_version,
                indexer_version=settings.INDEXER_VERSION,
                message="Document has no text content to index.",
            )

        # Batch embed chunk texts
        texts_to_embed = [c.content for c in chunks_data]
        import asyncio
        embeddings = asyncio.run(embedding_client.embed_batch(texts_to_embed))

        # Idempotently delete existing chunks for this document and model
        db.execute(
            delete(RetrievalChunk).where(
                RetrievalChunk.document_id == document_id,
                RetrievalChunk.embedding_model == embedding_client.model_name,
            )
        )

        # Persist new chunks
        for chunk_item, emb in zip(chunks_data, embeddings):
            chunk_record = RetrievalChunk(
                id=uuid.uuid4(),
                document_id=doc.id,
                bid_submission_id=doc.bid_submission_id,
                bidder_id=None,  # Inherited via submission if present
                tender_version_id=doc.tender_version_id,
                tender_id=doc.tender_id,
                chunk_index=chunk_item.chunk_index,
                page_number=chunk_item.page_number,
                section=chunk_item.section,
                block_id=chunk_item.block_id,
                table_reference=chunk_item.table_reference,
                content=chunk_item.content,
                content_type=chunk_item.content_type,
                content_hash=chunk_item.content_hash,
                bbox=chunk_item.bbox,
                source_reference=chunk_item.source_reference,
                embedding=emb,
                embedding_model=embedding_client.model_name,
                embedding_model_version=embedding_client.model_version,
                indexer_version=settings.INDEXER_VERSION,
            )
            # If document is linked to submission, also inherit bidder_id
            if doc.bid_submission_id:
                sub = db.get(BidSubmission, doc.bid_submission_id)
                if sub:
                    chunk_record.bidder_id = sub.bidder_id

            db.add(chunk_record)

        db.commit()
        logger.info(
            "Indexed %d chunks for document %s using model %s",
            len(chunks_data),
            document_id,
            embedding_client.model_name,
        )

        return IndexDocumentResponse(
            document_id=document_id,
            status="COMPLETED",
            chunks_indexed=len(chunks_data),
            embedding_model=embedding_client.model_name,
            embedding_model_version=embedding_client.model_version,
            indexer_version=settings.INDEXER_VERSION,
            message=f"Successfully indexed {len(chunks_data)} chunks for retrieval.",
        )

    except Exception as exc:
        db.rollback()
        logger.error("Indexing failed for document %s: %s", document_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Document indexing failed: {str(exc)}",
        )


def search_submission_by_criterion(
    db: Session,
    submission_id: uuid.UUID,
    criterion_id: uuid.UUID,
    top_k: int = 10,
    lexical_weight: Optional[float] = None,
    semantic_weight: Optional[float] = None,
    embedding_client: Optional[BaseEmbeddingClient] = None,
) -> HybridSearchResponse:
    """
    Search submission documents for relevant evidence chunks targeting an APPROVED criterion:
    1. Validates submission existence.
    2. Verifies criterion is strictly APPROVED and belongs to the submission's tender version.
    3. Builds composite retrieval query from criterion fields.
    4. Executes Lexical FTS and Semantic pgvector search.
    5. Normalizes and ranks hybrid results.
    """
    settings = get_settings()
    embedding_client = embedding_client or get_embedding_client()

    sub = db.get(BidSubmission, submission_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )

    crit = db.get(TenderCriterion, criterion_id)
    if not crit or crit.tender_version_id != sub.tender_version_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Criterion {criterion_id} not found for tender version {sub.tender_version_id}.",
        )

    # Strict Rule: Only APPROVED criteria can serve as search queries
    if crit.approval_status != ApprovalStatus.APPROVED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Criterion {criterion_id} is in status '{crit.approval_status}'. Only APPROVED criteria are authoritative for retrieval.",
        )

    # Construct comprehensive query text from approved criterion
    query_parts = [crit.name]
    if crit.description:
        query_parts.append(crit.description)
    if crit.required_evidence:
        query_parts.append(f"Required evidence: {crit.required_evidence}")
    if crit.threshold_text:
        query_parts.append(f"Threshold: {crit.threshold_text}")
    elif crit.threshold_value is not None:
        query_parts.append(f"Threshold: {crit.threshold_value} {crit.unit or ''}")
    if crit.source_clause:
        query_parts.append(f"Clause: {crit.source_clause}")

    query_text = " ".join(query_parts)

    w_lex = lexical_weight if lexical_weight is not None else settings.LEXICAL_WEIGHT
    w_sem = semantic_weight if semantic_weight is not None else settings.SEMANTIC_WEIGHT
    bounded_top_k = min(max(1, top_k), settings.MAX_TOP_K)

    # 1. Lexical search
    lex_candidates = execute_lexical_search(
        db=db,
        submission_id=submission_id,
        query_text=query_text,
        candidate_limit=50,
    )

    # 2. Semantic search
    import asyncio
    query_vector = asyncio.run(embedding_client.embed_text(query_text))
    sem_candidates = execute_semantic_search(
        db=db,
        submission_id=submission_id,
        query_vector=query_vector,
        candidate_limit=50,
    )

    # 3. Hybrid ranking & score fusion
    ranked_results = combine_and_rank_results(
        lexical_candidates=lex_candidates,
        semantic_candidates=sem_candidates,
        lexical_weight=w_lex,
        semantic_weight=w_sem,
        top_k=bounded_top_k,
    )

    total_candidates = len(set(lex_candidates.keys()).union(set(sem_candidates.keys())))

    return HybridSearchResponse(
        submission_id=submission_id,
        criterion_id=criterion_id,
        query_text=query_text,
        total_candidates=total_candidates,
        returned_count=len(ranked_results),
        lexical_weight=w_lex,
        semantic_weight=w_sem,
        results=ranked_results,
    )


def search_submission_by_text(
    db: Session,
    submission_id: uuid.UUID,
    query_text: str,
    top_k: int = 10,
    lexical_weight: Optional[float] = None,
    semantic_weight: Optional[float] = None,
    embedding_client: Optional[BaseEmbeddingClient] = None,
) -> HybridSearchResponse:
    """
    Execute controlled hybrid search across a bidder submission using an arbitrary text query.
    """
    settings = get_settings()
    embedding_client = embedding_client or get_embedding_client()

    sub = db.get(BidSubmission, submission_id)
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )

    w_lex = lexical_weight if lexical_weight is not None else settings.LEXICAL_WEIGHT
    w_sem = semantic_weight if semantic_weight is not None else settings.SEMANTIC_WEIGHT
    bounded_top_k = min(max(1, top_k), settings.MAX_TOP_K)

    # 1. Lexical search
    lex_candidates = execute_lexical_search(
        db=db,
        submission_id=submission_id,
        query_text=query_text,
        candidate_limit=50,
    )

    # 2. Semantic search
    import asyncio
    query_vector = asyncio.run(embedding_client.embed_text(query_text))
    sem_candidates = execute_semantic_search(
        db=db,
        submission_id=submission_id,
        query_vector=query_vector,
        candidate_limit=50,
    )

    # 3. Hybrid ranking & score fusion
    ranked_results = combine_and_rank_results(
        lexical_candidates=lex_candidates,
        semantic_candidates=sem_candidates,
        lexical_weight=w_lex,
        semantic_weight=w_sem,
        top_k=bounded_top_k,
    )

    total_candidates = len(set(lex_candidates.keys()).union(set(sem_candidates.keys())))

    return HybridSearchResponse(
        submission_id=submission_id,
        criterion_id=None,
        query_text=query_text,
        total_candidates=total_candidates,
        returned_count=len(ranked_results),
        lexical_weight=w_lex,
        semantic_weight=w_sem,
        results=ranked_results,
    )


def list_document_chunks(
    db: Session,
    document_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
) -> Tuple[List[RetrievalChunk], int]:
    """Retrieve paginated indexed chunks for a document."""
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found.",
        )

    total = db.execute(
        select(func.count(RetrievalChunk.id)).where(RetrievalChunk.document_id == document_id)
    ).scalar_one()

    stmt = (
        select(RetrievalChunk)
        .where(RetrievalChunk.document_id == document_id)
        .order_by(RetrievalChunk.chunk_index.asc())
        .offset(skip)
        .limit(limit)
    )
    items = db.execute(stmt).scalars().all()
    return items, total
