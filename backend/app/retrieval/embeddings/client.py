"""Embedding client factory and lifecycle management."""

from functools import lru_cache
from typing import Optional
from app.core.config import get_settings
from app.retrieval.embeddings.base import BaseEmbeddingClient
from app.retrieval.embeddings.mock import MockEmbeddingClient


@lru_cache()
def get_embedding_client(
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
    dimension: Optional[int] = None,
) -> BaseEmbeddingClient:
    """
    Factory function returning the configured embedding provider.
    Defaults to MockEmbeddingClient for fast, deterministic unit/integration testing.
    """
    settings = get_settings()
    prov = (provider or settings.EMBEDDING_PROVIDER).lower()
    model = model_name or settings.EMBEDDING_MODEL
    dim = dimension or settings.EMBEDDING_DIMENSION

    if prov in ("mock", "test", "fake"):
        return MockEmbeddingClient(
            model_name=model,
            model_version=settings.EMBEDDING_MODEL_VERSION,
            dimension=dim,
        )

    # Fallback to mock for unsupported or future provider integrations
    return MockEmbeddingClient(
        model_name=model,
        model_version=settings.EMBEDDING_MODEL_VERSION,
        dimension=dim,
    )
