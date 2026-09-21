"""Base abstract class and interfaces for embedding providers."""

from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddingClient(ABC):
    """Abstract interface for text embedding providers."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier (e.g. BAAI/bge-m3)."""
        pass

    @property
    @abstractmethod
    def model_version(self) -> str:
        """Return the model version string."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the output embedding vector dimensionality."""
        pass

    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """Generate a normalized embedding vector for a single text input."""
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate normalized embedding vectors for a batch of text inputs."""
        pass
