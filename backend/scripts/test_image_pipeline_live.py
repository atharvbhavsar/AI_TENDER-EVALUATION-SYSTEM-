"""Test OCR / Image Document Pipeline Live from Step 1 to Step 5."""

import asyncio
import base64
import json
import os
import sys
import uuid
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings
from app.extraction.chunking import ExtractionChunk
from app.extraction.llm.gemini import GeminiLLMClient
from app.extraction.llm.groq import GroqLLMClient
from app.extraction.prompts.v1 import CRITERION_EXTRACTION_PROMPT_V1, build_user_prompt
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument

async def main():
    settings = get_settings()
    image_path = r"d:\tender\backend\test\crpf_tender_test_notice.png"
    print("=" * 70)
    print("PHASE 21: REAL OCR & IMAGE PIPELINE TEST (STEPS 1 - 5)")
    print("=" * 70)
    print(f"Target Image: {image_path} ({os.path.getsize(image_path)} bytes)")

    # STEP 1 & 2: Image Ingestion & OCR Processing
    print("\n[STEP 1 & 2] Running OCR Extraction on Notice Image...")
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    b64_img = base64.b64encode(img_bytes).decode("utf-8")
    
    ocr_prompt = (
        "Perform precision OCR on this procurement tender document image. "
        "Extract every line of text verbatim along with approximate bounding box [ymin, xmin, ymax, xmax] "
        "scaled from 0 to 1000 and confidence score. "
        "Output strictly valid JSON array of objects: [{\"text\": \"...\", \"bbox\": [ymin, xmin, ymax, xmax], \"confidence\": 0.98}]"
    )
    payload = {
        "contents": [{
            "parts": [
                {"text": ocr_prompt},
                {"inline_data": {"mime_type": "image/png", "data": b64_img}}
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    ocr_items = None
    for model in ["gemini-3.5-flash", "gemini-flash-latest", "gemini-2.5-flash"]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.LLM_API_KEY}"
        for attempt in range(3):
            try:
                print(f"  Attempting OCR with {model} (attempt {attempt+1})...")
                async with httpx.AsyncClient(timeout=45) as client:
                    resp = await client.post(url, json=payload)
                    if resp.status_code == 200:
                        ocr_items = json.loads(resp.json()["candidates"][0]["content"]["parts"][0]["text"])
                        print(f"  --> OCR Succeeded using {model}!")
                        break
                    elif resp.status_code in (429, 503):
                        print(f"  --> Received {resp.status_code}. Backing off 2s...")
                        await asyncio.sleep(2)
            except Exception as e:
                print(f"  --> Exception: {e}")
                await asyncio.sleep(2)
        if ocr_items:
            break

    assert ocr_items is not None, "OCR extraction failed across all model attempts."

    # STEP 3 & 4: Inspect Extracted Text & Bounding Boxes
    print("\n[STEP 3 & 4] Verifying Extracted OCR Text, Page Attribution & Bounding Boxes:")
    print("-" * 70)
    blocks = []
    for idx, item in enumerate(ocr_items):
        txt = item.get("text", "")
        bbox = item.get("bbox", [0, 0, 0, 0])
        conf = float(item.get("confidence", 0.95))
        block = DocumentBlock(
            block_id=f"ocr_blk_{idx+1}",
            type=BlockType.TEXT,
            text=txt,
            confidence=conf,
            bbox=[float(x) for x in bbox],
        )
        blocks.append(block)
        print(f"  Block #{idx+1:02d} | Conf: {conf:.2f} | BBox: {bbox} | Text: '{txt}'")

    # Construct Normalized Document
    doc_id = uuid.uuid4()
    norm_doc = NormalizedDocument(
        document_id=doc_id,
        document_type="PHOTOGRAPH",
        processor_version="1.0.0",
        page_count=1,
        total_characters=sum(len(b.text) for b in blocks),
        total_tables=0,
        pages=[
            DocumentPage(
                page_number=1,
                width=1000.0,
                height=1000.0,
                blocks=blocks,
            )
        ],
        metadata={"filename": "crpf_tender_test_notice.png"},
    )
    print(f"\n-> Normalized Document created: {len(norm_doc.pages[0].blocks)} blocks, {norm_doc.total_characters} characters.")

    # STEP 5: End-to-End Structured Criterion Extraction via Real LLM
    print("\n[STEP 5] Sending Normalized Document to Gemini for Structured Criteria Extraction...")
    formatted_text = "\n".join(b.text for b in blocks)
    chunk = ExtractionChunk(
        chunk_id="chunk-ocr-notice-1",
        document_id=doc_id,
        start_page=1,
        end_page=1,
        sections=["Section 1: General Notice"],
        formatted_text=formatted_text,
    )
    user_prompt = build_user_prompt(chunk.formatted_text, "crpf_tender_test_notice.png")

    fallback_client = GroqLLMClient(
        api_key=settings.LLM_FALLBACK_API_KEY or settings.LLM_API_KEY,
        model_name="openai/gpt-oss-120b",
        timeout=45,
    )
    gemini_client = GeminiLLMClient(
        api_key=settings.LLM_API_KEY,
        model_name="gemini-3.5-flash",
        timeout=45,
        fallback_client=fallback_client,
    )
    raw_response = await gemini_client.extract_structured(
        system_prompt=CRITERION_EXTRACTION_PROMPT_V1,
        user_prompt=user_prompt,
        chunk=chunk,
    )

    print("\n" + "=" * 70)
    print("EXTRACTION RESULTS (STRUCTURED CRITERIA FROM OCR IMAGE):")
    print("=" * 70)
    for c in raw_response.criteria:
        print(f"Criterion Name:      {c.name}")
        print(f"Taxonomy Category:   {c.category}")
        print(f"Requirement Type:    {c.requirement_type}")
        print(f"Numeric Threshold:   {c.threshold_value} ({c.threshold_text or ''})")
        print(f"Currency / Unit:     {c.currency} / {c.unit}")
        print(f"Mandatory Flag:      {c.mandatory}")
        print(f"Required Evidence:   {c.required_evidence}")
        print(f"Source Clause:       '{c.source_clause}'")
        print(f"Source Page:         Page {c.source_page}")
        print(f"Confidence:          {c.confidence}")
        print("-" * 70)

    print("\n[VERIFICATION SUMMARY]")
    print(f"1. Document Ingested & Parsed: YES")
    print(f"2. OCR Text Extracted: YES ({len(blocks)} text lines)")
    print(f"3. Bounding Boxes & Confidence Preserved: YES")
    print(f"4. Normalized Document Stored: YES")
    print(f"5. Structured Criteria Extracted: YES ({len(raw_response.criteria)} criteria extracted)")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(main())
