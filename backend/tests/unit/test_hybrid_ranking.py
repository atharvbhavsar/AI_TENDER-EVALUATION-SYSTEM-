"""Unit tests for hybrid score normalization and fusion ranking algorithms."""

import uuid
import pytest
from app.db.models.retrieval_chunk import RetrievalChunk
from app.retrieval.search import (
    combine_and_rank_results,
    compute_lexical_token_score,
    normalize_scores,
)


def test_normalize_scores():
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    id3 = uuid.uuid4()

    scores = {id1: 10.0, id2: 20.0, id3: 30.0}
    norm = normalize_scores(scores)

    assert norm[id1] == 0.0
    assert norm[id2] == 0.5
    assert norm[id3] == 1.0


def test_normalize_scores_identical():
    id1 = uuid.uuid4()
    id2 = uuid.uuid4()

    scores = {id1: 15.0, id2: 15.0}
    norm = normalize_scores(scores)

    assert norm[id1] == 1.0
    assert norm[id2] == 1.0


def test_compute_lexical_token_score():
    query = "ISO 9001 certification"
    text1 = "The company holds valid ISO 9001 certification issued in 2023."
    text2 = "Turnover was 12 crore in 2024 with GST registration."

    score1 = compute_lexical_token_score(query, text1)
    score2 = compute_lexical_token_score(query, text2)

    assert score1 > score2
    assert score1 >= 0.8
    assert score2 == 0.0


def test_combine_and_rank_hybrid_fusion():
    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()
    c3_id = uuid.uuid4()

    chunk1 = RetrievalChunk(id=c1_id, document_id=uuid.uuid4(), content="High lexical, high semantic", content_type="TEXT", page_number=1)
    chunk2 = RetrievalChunk(id=c2_id, document_id=uuid.uuid4(), content="Low lexical, high semantic", content_type="TEXT", page_number=2)
    chunk3 = RetrievalChunk(id=c3_id, document_id=uuid.uuid4(), content="High lexical, low semantic", content_type="TEXT", page_number=3)

    lex_candidates = {
        c1_id: (chunk1, "doc1.pdf", 0.9),
        c3_id: (chunk3, "doc3.pdf", 0.85),
    }

    sem_candidates = {
        c1_id: (chunk1, "doc1.pdf", 0.95),
        c2_id: (chunk2, "doc2.pdf", 0.90),
    }

    # Weight: 0.4 Lexical + 0.6 Semantic
    ranked = combine_and_rank_results(
        lexical_candidates=lex_candidates,
        semantic_candidates=sem_candidates,
        lexical_weight=0.4,
        semantic_weight=0.6,
        top_k=5,
    )

    assert len(ranked) == 3
    # Chunk 1 has both high lexical and high semantic -> should be rank 1
    assert ranked[0].chunk_id == c1_id
    assert ranked[0].rank == 1
    assert ranked[0].hybrid_score > 0.8
