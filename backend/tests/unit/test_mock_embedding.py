"""Unit tests for deterministic MockEmbeddingClient."""

import math
import pytest
from app.retrieval.embeddings.mock import MockEmbeddingClient
from app.retrieval.search import calculate_cosine_similarity


@pytest.mark.asyncio
async def test_mock_embedding_dimensions_and_norm():
    client = MockEmbeddingClient(dimension=1024)
    vec = await client.embed_text("Average annual financial turnover ₹15 crore")

    assert len(vec) == 1024
    norm = math.sqrt(sum(x * x for x in vec))
    assert pytest.approx(norm, rel=1e-3) == 1.0


@pytest.mark.asyncio
async def test_mock_embedding_batch():
    client = MockEmbeddingClient(dimension=1024)
    texts = [
        "ISO 9001 quality certificate",
        "Audited balance sheet 2024",
        "Experience certificate for perimeter security",
    ]
    vectors = await client.embed_batch(texts)
    assert len(vectors) == 3
    for v in vectors:
        assert len(v) == 1024


@pytest.mark.asyncio
async def test_mock_embedding_semantic_clustering():
    client = MockEmbeddingClient(dimension=1024)

    # 1. Financial cluster query & documents
    query_fin = await client.embed_text("financial turnover requirement of 10 crore")
    doc_fin_match = await client.embed_text("audited annual revenue and balance sheet turnover 14 cr")
    doc_unrelated = await client.embed_text("ISO 9001 quality management standard accreditation")

    sim_match = calculate_cosine_similarity(query_fin, doc_fin_match)
    sim_unrelated = calculate_cosine_similarity(query_fin, doc_unrelated)

    assert sim_match > sim_unrelated
    assert sim_match > 0.5


@pytest.mark.asyncio
async def test_mock_embedding_empty_text():
    client = MockEmbeddingClient(dimension=1024)
    vec = await client.embed_text("")
    assert len(vec) == 1024
    assert vec[0] == 1.0
