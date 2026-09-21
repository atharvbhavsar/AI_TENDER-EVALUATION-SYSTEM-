"""Test real live LLM APIs (Gemini and Groq) using configured keys."""

import asyncio
import os
import sys
import uuid

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings
from app.extraction.chunking import ExtractionChunk
from app.extraction.llm.gemini import GeminiLLMClient
from app.extraction.llm.groq import GroqLLMClient
from app.extraction.prompts.v1 import CRITERION_EXTRACTION_PROMPT_V1, build_user_prompt

async def main():
    settings = get_settings()
    print("=" * 60)
    print("TESTING REAL LIVE LLM APIS")
    print("=" * 60)
    print(f"Gemini Key: {'*' * 10}{settings.LLM_API_KEY[-4:] if settings.LLM_API_KEY else 'NONE'}")
    print(f"Groq Key:   {'*' * 10}{settings.LLM_FALLBACK_API_KEY[-4:] if settings.LLM_FALLBACK_API_KEY else 'NONE'}")
    print("=" * 60)

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

    # 1. Test Real Groq API
    print("\n[1] Invoking Real Live Groq API...")
    groq_client = GroqLLMClient(
        api_key=settings.LLM_FALLBACK_API_KEY or settings.LLM_API_KEY,
        model_name="openai/gpt-oss-120b",
        timeout=30,
    )
    try:
        groq_resp = await groq_client.extract_structured(
            system_prompt=CRITERION_EXTRACTION_PROMPT_V1,
            user_prompt=user_prompt,
            chunk=sample_chunk,
        )
        print(f"  --> Groq Live Extraction Status: SUCCESS ({len(groq_resp.criteria)} criteria extracted)")
        for c in groq_resp.criteria:
            print(f"      - Extracted Criterion: {c.name}")
            print(f"        Category: {c.category}, Value: {c.threshold_value} {c.currency}, Mandatory: {c.mandatory}")
            print(f"        Evidence: {c.required_evidence}")
    except Exception as e:
        print(f"  --> Groq Live API Error: {e}")

    # 2. Test Real Gemini API
    print("\n[2] Invoking Real Live Gemini API...")
    for model in ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
        print(f"  Testing Gemini model '{model}'...")
        gemini_client = GeminiLLMClient(
            api_key=settings.LLM_API_KEY,
            model_name=model,
            timeout=30,
        )
        try:
            gemini_resp = await gemini_client.extract_structured(
                system_prompt=CRITERION_EXTRACTION_PROMPT_V1,
                user_prompt=user_prompt,
                chunk=sample_chunk,
            )
            print(f"    --> Gemini ({model}) Live Extraction: SUCCESS ({len(gemini_resp.criteria)} criteria extracted)")
            for c in gemini_resp.criteria:
                print(f"        - Extracted: {c.name} | Category: {c.category} | Value: {c.threshold_value} {c.currency}")
            break
        except Exception as e:
            print(f"    --> Gemini ({model}) Error: {str(e)[:180]}...")

    print("\n" + "=" * 60)
    print("LIVE REAL API TEST COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
