"""Deterministic Mock Embedding Provider for fast, reproducible testing."""

import hashlib
import math
import re
from typing import Dict, List, Set
from app.retrieval.embeddings.base import BaseEmbeddingClient


SEMANTIC_CLUSTERS: Dict[str, Set[str]] = {
    "financial": {
        "turnover", "revenue", "financial", "audited", "balance", "sheet",
        "networth", "worth", "crore", "cr", "lakh", "profit", "loss", "fy"
    },
    "experience": {
        "experience", "assignment", "infrastructure", "project", "completion",
        "certificate", "years", "execution", "work", "order", "contract", "client"
    },
    "certification": {
        "iso", "9001", "27001", "14001", "45001", "certification", "compliance",
        "standard", "quality", "management", "accreditation", "certified"
    },
    "statutory": {
        "gst", "gstin", "pan", "registration", "tax", "epfo", "esic", "statutory",
        "incorporation", "mca", "cin"
    },
    "procurement": {
        "crpf", "procurement", "tender", "bidder", "bid", "submission", "eligibility",
        "criterion", "technical", "commercial", "requirement"
    },
}


class MockEmbeddingClient(BaseEmbeddingClient):
    """
    Mock embedding provider generating reproducible, unit-normalized semantic vectors.
    """

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        model_version: str = "v1.0",
        dimension: int = 1024,
    ) -> None:
        self._model_name = model_name
        self._model_version = model_version
        self._dimension = dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def model_version(self) -> str:
        return self._model_version

    @property
    def dimension(self) -> int:
        return self._dimension

    def _generate_vector(self, text: str) -> List[float]:
        """Generate a deterministic 1024-dim unit vector based on text content and semantic clusters."""
        if not text:
            # Return zero vector with slight base
            vec = [0.0] * self._dimension
            vec[0] = 1.0
            return vec

        raw_vec = [0.0] * self._dimension
        tokens = [t.lower() for t in re.findall(r"\w+", text)]
        token_set = set(tokens)

        # 1. Base token hashing
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimension
            sign = 1.0 if (h >> 4) % 2 == 0 else -1.0
            raw_vec[idx] += sign * 1.5

        # 2. Semantic cluster boosting in dedicated orthogonal subspaces
        cluster_names = list(SEMANTIC_CLUSTERS.keys())
        subspace_size = min(50, self._dimension // (len(cluster_names) + 1))

        for c_idx, (cluster_name, keywords) in enumerate(SEMANTIC_CLUSTERS.items()):
            overlap = len(token_set.intersection(keywords))
            if overlap > 0:
                start_slot = 100 + (c_idx * subspace_size)
                boost = 5.0 * overlap
                for offset in range(subspace_size):
                    slot = (start_slot + offset) % self._dimension
                    raw_vec[slot] += boost * (1.0 if offset % 2 == 0 else 0.8)

        # 3. L2 Normalization
        norm = math.sqrt(sum(x * x for x in raw_vec))
        if norm < 1e-9:
            raw_vec[0] = 1.0
            return raw_vec

        return [float(x / norm) for x in raw_vec]

    async def embed_text(self, text: str) -> List[float]:
        """Embed single text string."""
        return self._generate_vector(text)

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text strings."""
        return [self._generate_vector(t) for t in texts]
