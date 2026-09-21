"""Google Gemini LLM client adapter for structured criterion extraction."""

import asyncio
import json
import logging
import re
from typing import Optional
import httpx

from app.core.config import get_settings
from app.extraction.chunking import ExtractionChunk
from app.extraction.llm.base import BaseLLMClient
from app.extraction.schemas import RawExtractionResponse

logger = logging.getLogger("app.extraction.llm.gemini")

# Statuses that are transient — retry with backoff rather than immediately failing
_RETRYABLE_STATUS_CODES = {429, 503, 502, 500}
# Maximum retry attempts for transient errors before giving up / falling back
_MAX_RETRIES = 5
# Base delay in seconds for exponential backoff (doubles each attempt: 5, 10, 20, 40, 80)
_BACKOFF_BASE_SECONDS = 5


class GeminiLLMClient(BaseLLMClient):
    """
    Google Gemini client adapter using Google's REST API.
    Extracts structured tender evaluation criteria from document chunks.

    Includes exponential-backoff retry for 429 (quota) and 503 (overload) responses
    so that transient API pressure does not immediately fall through to Mock.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        timeout: int = 60,
        fallback_client: Optional[BaseLLMClient] = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.LLM_API_KEY or ""
        self._model_name = model_name
        self._timeout = timeout
        self._fallback_client = fallback_client
        self._endpoint_template = (
            "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        )

    @property
    def provider_name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model_name

    async def extract_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        chunk: ExtractionChunk,
    ) -> RawExtractionResponse:
        """
        Send chunk content to Gemini and return validated RawExtractionResponse.

        Retries up to _MAX_RETRIES times with exponential backoff on transient
        errors (429 / 503) before delegating to the fallback client.
        """
        if not self._api_key:
            if self._fallback_client:
                logger.info("No Gemini API key, routing to fallback client...")
                return await self._fallback_client.extract_structured(system_prompt, user_prompt, chunk)
            raise ValueError("GEMINI_API_KEY is not configured.")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model_name}:generateContent?key={self._api_key}"
        )

        prompt_text = (
            f"SYSTEM INSTRUCTIONS:\n{system_prompt}\n\n"
            f"USER TASK:\n{user_prompt}\n\n"
            f"DOCUMENT CHUNK TEXT (Page {chunk.start_page}):\n{chunk.formatted_text}"
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt_text}],
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                    response = await client.post(url, json=payload)

                if response.status_code == 200:
                    # Successful response — parse and return
                    data = response.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise ValueError("No candidate completions returned by Gemini.")

                    content_text = candidates[0]["content"]["parts"][0]["text"]
                    content_text = re.sub(r"^```json\s*", "", content_text.strip(), flags=re.MULTILINE)
                    content_text = re.sub(r"\s*```$", "", content_text.strip(), flags=re.MULTILINE)

                    parsed_json = json.loads(content_text)
                    return RawExtractionResponse.model_validate(parsed_json)

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    wait = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                    logger.warning(
                        "Gemini transient error (HTTP %s) on attempt %d/%d — "
                        "retrying in %ds. Body: %s",
                        response.status_code,
                        attempt + 1,
                        _MAX_RETRIES,
                        wait,
                        response.text[:200],
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(wait)
                        continue
                    # Exhausted retries
                    last_exc = RuntimeError(
                        f"Gemini API returned {response.status_code} after "
                        f"{_MAX_RETRIES} retries: {response.text[:200]}"
                    )
                    break

                # Non-retryable error (4xx other than 429)
                logger.warning(
                    "Gemini API non-retryable error (%s): %s. Triggering fallback...",
                    response.status_code,
                    response.text[:200],
                )
                last_exc = RuntimeError(
                    f"Gemini API request failed with status {response.status_code}: {response.text}"
                )
                break

            except Exception as exc:
                wait = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning(
                    "Gemini exception on attempt %d/%d (%s) — retrying in %ds...",
                    attempt + 1,
                    _MAX_RETRIES,
                    str(exc),
                    wait,
                )
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(wait)
                    continue
                break

        # All retries exhausted — delegate to fallback or raise
        if self._fallback_client:
            logger.warning(
                "Gemini failed after %d attempts (%s). Delegating to fallback client...",
                _MAX_RETRIES + 1,
                str(last_exc),
            )
            return await self._fallback_client.extract_structured(system_prompt, user_prompt, chunk)

        logger.error("Gemini extraction failed with no fallback available: %s", str(last_exc))
        raise ValueError(f"Gemini extraction failed: {str(last_exc)}") from last_exc
