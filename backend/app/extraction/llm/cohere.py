"""Cohere LLM client adapter for structured criterion extraction."""

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

logger = logging.getLogger("app.extraction.llm.cohere")

_RETRYABLE_STATUS_CODES = {429, 503, 502, 500}
_MAX_RETRIES = 5
_BACKOFF_BASE_SECONDS = 5


class CohereLLMClient(BaseLLMClient):
    """
    Cohere client adapter using the v2 Chat API.
    Extracts structured tender evaluation criteria from document chunks.
    Includes exponential-backoff retry on 429/503 before delegating to fallback.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "command-r-plus-08-2024",
        timeout: int = 120,
        fallback_client: Optional[BaseLLMClient] = None,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.LLM_API_KEY or ""
        self._model_name = model_name
        self._timeout = timeout
        self._fallback_client = fallback_client
        self._endpoint = "https://api.cohere.com/v2/chat"

    @property
    def provider_name(self) -> str:
        return "cohere"

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
        Send chunk content to Cohere v2 Chat API and return validated RawExtractionResponse.
        Retries up to _MAX_RETRIES times with exponential backoff on transient errors.
        """
        if not self._api_key:
            if self._fallback_client:
                logger.info("No Cohere API key — routing to fallback client...")
                return await self._fallback_client.extract_structured(system_prompt, user_prompt, chunk)
            raise ValueError("LLM_API_KEY is not configured for Cohere.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        user_content = (
            f"TASK:\n{user_prompt}\n\n"
            f"DOCUMENT CHUNK TEXT (Page {chunk.start_page}):\n{chunk.formatted_text}\n\n"
            "IMPORTANT: Respond ONLY with valid JSON matching the required schema. "
            "No markdown fences, no explanations — pure JSON only."
        )

        payload = {
            "model": self._model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }

        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
                    response = await client.post(self._endpoint, headers=headers, json=payload)

                if response.status_code == 200:
                    data = response.json()
                    content_parts = data.get("message", {}).get("content", [])
                    if not content_parts:
                        raise ValueError("No content returned in Cohere v2 response.")

                    # Cohere reasoning models (e.g. command-a-plus-05-2026) return thinking part first, then text part
                    raw_text = ""
                    for part in content_parts:
                        if isinstance(part, dict) and part.get("type") == "text":
                            raw_text = part.get("text", "")
                            break
                    if not raw_text:
                        for part in content_parts:
                            if isinstance(part, dict) and "text" in part:
                                raw_text = part["text"]
                                break

                    if not raw_text:
                        raise ValueError(f"No text content found in Cohere response parts: {content_parts}")

                    raw_text = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.MULTILINE)
                    raw_text = re.sub(r"\s*```$", "", raw_text.strip(), flags=re.MULTILINE)

                    parsed_json = json.loads(raw_text)
                    return RawExtractionResponse.model_validate(parsed_json)

                if response.status_code in _RETRYABLE_STATUS_CODES:
                    wait = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                    logger.warning(
                        "Cohere transient error (HTTP %s) attempt %d/%d — retrying in %ds. Body: %s",
                        response.status_code, attempt + 1, _MAX_RETRIES, wait, response.text[:200],
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(wait)
                        continue
                    last_exc = RuntimeError(f"Cohere returned {response.status_code} after {_MAX_RETRIES} retries")
                    break

                logger.warning("Cohere non-retryable error (%s): %s", response.status_code, response.text[:200])
                last_exc = RuntimeError(f"Cohere API failed status {response.status_code}: {response.text}")
                break

            except Exception as exc:
                wait = _BACKOFF_BASE_SECONDS * (2 ** attempt)
                logger.warning("Cohere exception attempt %d/%d (%s) — retrying in %ds...", attempt + 1, _MAX_RETRIES, str(exc), wait)
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(wait)
                    continue
                break

        if self._fallback_client:
            logger.warning("Cohere failed after %d attempts. Delegating to fallback...", _MAX_RETRIES + 1)
            return await self._fallback_client.extract_structured(system_prompt, user_prompt, chunk)

        logger.error("Cohere extraction failed with no fallback: %s", str(last_exc))
        raise ValueError(f"Cohere extraction failed: {str(last_exc)}") from last_exc
