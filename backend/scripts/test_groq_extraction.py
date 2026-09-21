import asyncio
import uuid
from app.extraction.chunking import ExtractionChunk
from app.extraction.llm.groq import GroqLLMClient
from app.extraction.prompts.v1 import CRITERION_EXTRACTION_PROMPT_V1, build_user_prompt

async def test():
    client = GroqLLMClient(
        api_key="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",
        model_name="openai/gpt-oss-120b"
    )
    text = "CRPF TENDER NOTICE\n1. Annual Turnover: Bidder must have minimum average annual turnover of INR 5 Crores in last 3 financial years.\n2. Experience: Must have completed at least 2 similar supply projects of value 2 Crores each."
    user_prompt = build_user_prompt(text, "CRPF NIT Notice")
    chunk = ExtractionChunk(
        chunk_id="c1",
        document_id=uuid.uuid4(),
        start_page=1,
        end_page=1,
        formatted_text=text
    )
    res = await client.extract_structured(CRITERION_EXTRACTION_PROMPT_V1, user_prompt, chunk)
    print("GROQ SUCCESS! Extracted criteria count:", len(res.criteria))
    for c in res.criteria:
        print("- Name:", c.name, "| Category:", c.category, "| Operator:", c.operator, "| Threshold:", c.threshold_value, "| Mandatory:", c.requirement_type)

if __name__ == "__main__":
    asyncio.run(test())
