"""Hybrid search execution and score fusion algorithms."""

import math
import re
import uuid
from typing import Dict, List, Optional, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.document import Document
from app.db.models.retrieval_chunk import RetrievalChunk
from app.retrieval.schemas import HybridSearchResultItem


class ScoredChunk:
    """Internal container for an intermediate scored chunk."""

    def __init__(
        self,
        chunk: RetrievalChunk,
        document_filename: Optional[str] = None,
        lexical_score: float = 0.0,
        semantic_score: float = 0.0,
    ) -> None:
        self.chunk = chunk
        self.document_filename = document_filename
        self.lexical_score = lexical_score
        self.semantic_score = semantic_score


def normalize_scores(scores: Dict[uuid.UUID, float]) -> Dict[uuid.UUID, float]:
    """
    Min-Max normalize scores to [0.0, 1.0] range.
    If all scores are equal and non-zero, sets them to 1.0.
    """
    if not scores:
        return {}
    vals = list(scores.values())
    min_val = min(vals)
    max_val = max(vals)

    if max_val == min_val:
        if max_val > 0.0:
            return {cid: 1.0 for cid in scores}
        return {cid: 0.0 for cid in scores}

    denom = max_val - min_val
    return {cid: round((val - min_val) / denom, 4) for cid, val in scores.items()}


def calculate_cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(dot / (norm_a * norm_b))


def compute_lexical_token_score(query: str, text: str) -> float:
    """
    Calculate normalized lexical relevance score for text based on query terms,
    exact phrase matching, and token overlap.
    """
    if not query or not text:
        return 0.0

    q_clean = query.lower().strip()
    t_clean = text.lower().strip()

    # Exact full query match
    if q_clean in t_clean:
        phrase_boost = 1.0
    else:
        phrase_boost = 0.0

    q_tokens = [t for t in re.findall(r"\w+", q_clean) if len(t) > 1]
    if not q_tokens:
        return 0.5 if phrase_boost else 0.0

    t_tokens = set(re.findall(r"\w+", t_clean))
    overlap_count = sum(1 for tok in q_tokens if tok in t_tokens)
    overlap_ratio = overlap_count / len(q_tokens)

    # Frequency boost
    term_freq = 0
    for tok in q_tokens:
        term_freq += t_clean.count(tok)
    freq_score = min(1.0, term_freq / (len(q_tokens) * 3))

    score = (0.4 * phrase_boost) + (0.4 * overlap_ratio) + (0.2 * freq_score)
    return round(min(1.0, score), 4)


def execute_lexical_search(
    db: Session,
    submission_id: uuid.UUID,
    query_text: str,
    candidate_limit: int = 50,
) -> Dict[uuid.UUID, Tuple[RetrievalChunk, Optional[str], float]]:
    """
    Execute lexical full-text search scoped to the given submission.
    Returns mapping of chunk_id -> (chunk, document_filename, lexical_score).
    """
    bind = db.get_bind()
    is_postgres = bind and bind.dialect.name == "postgresql"

    # Base query joined with Document to get filename
    stmt = (
        select(RetrievalChunk, Document.filename)
        .outerjoin(Document, RetrievalChunk.document_id == Document.id)
        .where(RetrievalChunk.bid_submission_id == submission_id)
    )

    results: Dict[uuid.UUID, Tuple[RetrievalChunk, Optional[str], float]] = {}

    if is_postgres:
        try:
            # Native PostgreSQL FTS query
            tsquery = func.plainto_tsquery("english", query_text)
            rank_col = func.ts_rank_cd(RetrievalChunk.tsv_content, tsquery).label("rank")
            pg_stmt = (
                select(RetrievalChunk, Document.filename, rank_col)
                .outerjoin(Document, RetrievalChunk.document_id == Document.id)
                .where(
                    RetrievalChunk.bid_submission_id == submission_id,
                    RetrievalChunk.tsv_content.op("@@")(tsquery),
                )
                .order_by(rank_col.desc())
                .limit(candidate_limit)
            )
            rows = db.execute(pg_stmt).all()
            for chunk, filename, rank in rows:
                results[chunk.id] = (chunk, filename, float(rank))
            return results
        except Exception:
            # Fall back to text matching if FTS column isn't populated
            pass

    # Dialect-independent fallback
    rows = db.execute(stmt).all()
    scored: List[Tuple[RetrievalChunk, Optional[str], float]] = []
    for chunk, filename in rows:
        score = compute_lexical_token_score(query_text, chunk.content)
        if score > 0.05:
            scored.append((chunk, filename, score))

    scored.sort(key=lambda x: x[2], reverse=True)
    for chunk, filename, score in scored[:candidate_limit]:
        results[chunk.id] = (chunk, filename, score)

    return results


def execute_semantic_search(
    db: Session,
    submission_id: uuid.UUID,
    query_vector: List[float],
    candidate_limit: int = 50,
) -> Dict[uuid.UUID, Tuple[RetrievalChunk, Optional[str], float]]:
    """
    Execute semantic cosine similarity search scoped to the given submission.
    Returns mapping of chunk_id -> (chunk, document_filename, semantic_score).
    """
    stmt = (
        select(RetrievalChunk, Document.filename)
        .outerjoin(Document, RetrievalChunk.document_id == Document.id)
        .where(
            RetrievalChunk.bid_submission_id == submission_id,
            RetrievalChunk.embedding.isnot(None),
        )
    )

    rows = db.execute(stmt).all()
    results: Dict[uuid.UUID, Tuple[RetrievalChunk, Optional[str], float]] = {}
    scored: List[Tuple[RetrievalChunk, Optional[str], float]] = []

    for chunk, filename in rows:
        if not chunk.embedding:
            continue
        sim = calculate_cosine_similarity(query_vector, chunk.embedding)
        # Shift [-1, 1] to [0, 1]
        norm_sim = max(0.0, (sim + 1.0) / 2.0) if sim >= 0 else 0.0
        scored.append((chunk, filename, norm_sim))

    scored.sort(key=lambda x: x[2], reverse=True)
    for chunk, filename, score in scored[:candidate_limit]:
        results[chunk.id] = (chunk, filename, score)

    return results


def combine_and_rank_results(
    lexical_candidates: Dict[uuid.UUID, Tuple[RetrievalChunk, Optional[str], float]],
    semantic_candidates: Dict[uuid.UUID, Tuple[RetrievalChunk, Optional[str], float]],
    lexical_weight: float = 0.4,
    semantic_weight: float = 0.6,
    top_k: int = 10,
) -> List[HybridSearchResultItem]:
    """
    Combines lexical and semantic search results using normalized scores:
    hybrid_score = (w_lex * lex_norm) + (w_sem * sem_norm)
    """
    all_chunk_ids = set(lexical_candidates.keys()).union(set(semantic_candidates.keys()))
    if not all_chunk_ids:
        return []

    # 1. Normalize scores independently
    raw_lex = {cid: lexical_candidates[cid][2] for cid in lexical_candidates}
    raw_sem = {cid: semantic_candidates[cid][2] for cid in semantic_candidates}

    norm_lex = normalize_scores(raw_lex)
    norm_sem = normalize_scores(raw_sem)

    # 2. Combine scores
    combined_items: List[Tuple[RetrievalChunk, Optional[str], float, float, float]] = []

    for cid in all_chunk_ids:
        chunk = None
        filename = None
        if cid in lexical_candidates:
            chunk, filename, _ = lexical_candidates[cid]
        elif cid in semantic_candidates:
            chunk, filename, _ = semantic_candidates[cid]

        if not chunk:
            continue

        l_score = norm_lex.get(cid, 0.0)
        s_score = norm_sem.get(cid, 0.0)
        h_score = round((lexical_weight * l_score) + (semantic_weight * s_score), 4)

        combined_items.append((chunk, filename, l_score, s_score, h_score))

    # 3. Sort descending by hybrid_score
    combined_items.sort(key=lambda x: x[4], reverse=True)

    # 4. Format top-K items
    ranked_results: List[HybridSearchResultItem] = []
    for rank, (chunk, filename, l_score, s_score, h_score) in enumerate(combined_items[:top_k], start=1):
        ranked_results.append(
            HybridSearchResultItem(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                document_name=filename,
                page=chunk.page_number,
                section=chunk.section,
                block_id=chunk.block_id,
                table_reference=chunk.table_reference,
                content=chunk.content,
                content_type=chunk.content_type or "TEXT",
                bbox=chunk.bbox,
                source_reference=chunk.source_reference,
                lexical_score=l_score,
                semantic_score=s_score,
                hybrid_score=h_score,
                rank=rank,
            )
        )

    return ranked_results
