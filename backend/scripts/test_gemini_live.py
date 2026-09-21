"""Test live Gemini API with available model."""

import asyncio
import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.core.config import get_settings
from app.extraction.chunking import ExtractionChunk
from app.extraction.llm.gemini import GeminiLLMClient
from app.extraction.prompts.v1 import CRITERION_EXTRACTION_PROMPT_V1, build_user_prompt

async def main():
    settings = get_settings()
    sample_chunk = ExtractionChunk(
        chunk_id="chunk-real-test-1",
        document_id=uuid.uuid4(),
        start_page=1,
        end_page=1,
        sections=["Section 3: Eligibility Criteria"],
        formatted_text=(
            "Clause 3.1: The bidder must have an average annual turnover of at least INR 5,00,00,000 "
            "(Rupees Five Crore) over the last 3 financial years (2020-21, 2021-22, 2022-23). "
            "Evidence Required: CA Audited balance sheet and turnover certificate."
        ),
    )
    user_prompt = build_user_prompt(sample_chunk.formatted_text, "tender_notice_crpf.pdf")

    for model in ["gemini-3.6-flash", "gemini-flash-latest", "gemini-3.5-flash"]:
        print(f"\nCalling live Gemini API with model: {model}...")
        client = GeminiLLMClient(api_key=settings.LLM_API_KEY, model_name=model, timeout=30)
        try:
            resp = await client.extract_structured(
                system_prompt=CRITERION_EXTRACTION_PROMPT_V1,
                user_prompt=user_prompt,
                chunk=sample_chunk,
            )
            print(f" SUCCESS with {model}! Extracted {len(resp.criteria)} criteria:")
            for c in resp.criteria:
                print(f"  - Name: {c.name}")
                print(f"    Category: {c.category}, Value: {c.threshold_value} {c.currency}, Mandatory: {c.mandatory}")
                print(f"    Evidence: {c.required_evidence}")
                print(f"    Clause: {c.source_clause}")
            break
        except Exception as e:
            print(f"  Error with {model}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
