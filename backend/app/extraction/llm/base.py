"""Base interface for LLM provider adapters."""

from abc import ABC, abstractmethod
from typing import Optional
from app.extraction.chunking import ExtractionChunk
from app.extraction.schemas import RawExtractionResponse


class BaseLLMClient(ABC):
    """Abstract interface for LLM extraction providers."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name identifier."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Configured model name."""
        pass

    @abstractmethod
    async def extract_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        chunk: ExtractionChunk,
    ) -> RawExtractionResponse:
        """
        Send chunk content to LLM and return validated structured extraction response.
        Raises ValueError or RuntimeError on malformed model outputs or failures.
        """
        pass
