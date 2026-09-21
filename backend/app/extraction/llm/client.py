"""Factory for instantiating configured LLM provider clients."""

import logging
from app.core.config import Settings, get_settings
from app.extraction.llm.base import BaseLLMClient
from app.extraction.llm.mock import MockLLMClient

logger = logging.getLogger("app.extraction.llm.client")


def get_llm_client(settings: Settings | None = None) -> BaseLLMClient:
    """Instantiate and return the configured LLM client adapter."""
    if settings is None:
        settings = get_settings()

    if settings.ENVIRONMENT in ("test", "testing"):
        return MockLLMClient(model_name=settings.LLM_MODEL)

    provider = settings.LLM_PROVIDER.lower()

    if provider == "cohere":
        fallback_client: BaseLLMClient | None = None
        if settings.LLM_FALLBACK_API_KEY or (settings.LLM_FALLBACK_PROVIDER == "groq" and settings.LLM_FALLBACK_API_KEY):
            try:
                from app.extraction.llm.groq import GroqLLMClient
                fallback_client = GroqLLMClient(
                    api_key=settings.LLM_FALLBACK_API_KEY,
                    model_name=settings.LLM_FALLBACK_MODEL or "openai/gpt-oss-120b",
                    timeout=settings.LLM_TIMEOUT,
                )
            except Exception as exc:
                logger.warning("Could not initialize Groq fallback LLM client: %s.", str(exc))

        if settings.LLM_API_KEY:
            try:
                from app.extraction.llm.cohere import CohereLLMClient
                return CohereLLMClient(
                    api_key=settings.LLM_API_KEY,
                    model_name=settings.LLM_MODEL or "command-r-plus-08-2024",
                    timeout=settings.LLM_TIMEOUT,
                    fallback_client=fallback_client or MockLLMClient(model_name=settings.LLM_MODEL),
                )
            except Exception as exc:
                logger.warning("Could not initialize Cohere LLM client: %s. Trying fallback.", str(exc))

        if fallback_client:
            return fallback_client

        return MockLLMClient(model_name=settings.LLM_MODEL)

    if provider == "gemini":
        fallback_client: BaseLLMClient | None = None
        if settings.LLM_FALLBACK_API_KEY or (settings.LLM_FALLBACK_PROVIDER == "groq" and settings.LLM_API_KEY):
            try:
                from app.extraction.llm.groq import GroqLLMClient
                fallback_client = GroqLLMClient(
                    api_key=settings.LLM_FALLBACK_API_KEY or settings.LLM_API_KEY,
                    model_name=settings.LLM_FALLBACK_MODEL or "openai/gpt-oss-120b",
                    timeout=settings.LLM_TIMEOUT,
                )
            except Exception as exc:
                logger.warning("Could not initialize Groq fallback LLM client: %s.", str(exc))

        if settings.LLM_API_KEY:
            try:
                from app.extraction.llm.gemini import GeminiLLMClient
                return GeminiLLMClient(
                    api_key=settings.LLM_API_KEY,
                    model_name=settings.LLM_MODEL,
                    timeout=settings.LLM_TIMEOUT,
                    fallback_client=fallback_client or MockLLMClient(model_name=settings.LLM_MODEL),
                )
            except Exception as exc:
                logger.warning("Could not initialize Gemini LLM client: %s. Trying fallback.", str(exc))

        if fallback_client:
            return fallback_client

        return MockLLMClient(model_name=settings.LLM_MODEL)

    if provider == "groq":
        if settings.LLM_API_KEY or settings.LLM_FALLBACK_API_KEY:
            try:
                from app.extraction.llm.groq import GroqLLMClient
                return GroqLLMClient(
                    api_key=settings.LLM_API_KEY or settings.LLM_FALLBACK_API_KEY,
                    model_name=settings.LLM_MODEL,
                    timeout=settings.LLM_TIMEOUT,
                )
            except Exception as exc:
                logger.warning("Could not initialize Groq LLM client: %s. Using Mock.", str(exc))

        return MockLLMClient(model_name=settings.LLM_MODEL)

    return MockLLMClient(model_name=settings.LLM_MODEL)

