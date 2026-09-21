"""Groq LLM client adapter for fallback structured criterion extraction."""

import json
import logging
import re
from typing import Optional
import httpx

from app.core.config import get_settings
from app.extraction.chunking import ExtractionChunk
from app.extraction.llm.base import BaseLLMClient
from app.extraction.schemas import RawExtractionResponse

logger = logging.getLogger("app.extraction.llm.groq")


class GroqLLMClient(BaseLLMClient):
    """
    Groq client adapter using Groq's OpenAI-compatible Chat Completions endpoint.
    Serves as an optional high-speed fallback for extraction.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "openai/gpt-oss-120b",
        timeout: int = 60,
    ) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.LLM_FALLBACK_API_KEY or settings.LLM_API_KEY or ""
        self._model_name = model_name
        self._timeout = timeout
        self._endpoint = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "groq"

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
        Send chunk content to Groq and return validated RawExtractionResponse.
        """
        if not self._api_key:
            raise ValueError("GROQ_API_KEY is not configured.")

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        user_content = (
            f"TASK:\n{user_prompt}\n\n"
            f"DOCUMENT CHUNK TEXT (Page {chunk.start_page}):\n{chunk.formatted_text}"
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

        async with httpx.AsyncClient(timeout=float(self._timeout)) as client:
            response = await client.post(self._endpoint, headers=headers, json=payload)
            if response.status_code != 200:
                logger.error("Groq API error status %s: %s", response.status_code, response.text)
                raise RuntimeError(f"Groq API request failed with status {response.status_code}: {response.text}")

            data = response.json()

        try:
            choices = data.get("choices", [])
            if not choices:
                raise ValueError("No choices returned in Groq response.")

            raw_text = choices[0]["message"]["content"]
            # Strip markdown fence if present
            raw_text = re.sub(r"^```json\s*", "", raw_text.strip(), flags=re.MULTILINE)
            raw_text = re.sub(r"\s*```$", "", raw_text.strip(), flags=re.MULTILINE)

            parsed_json = json.loads(raw_text)
            return RawExtractionResponse.model_validate(parsed_json)
        except Exception as exc:
            logger.error("Failed to parse Groq extraction response: %s", str(exc))
            raise ValueError(f"Malformed Groq structured output: {str(exc)}") from exc
