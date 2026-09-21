"""Test Gemini model identifiers against Google REST API."""

import asyncio
import os
import sys
import uuid
import httpx

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.core.config import get_settings

async def list_gemini_models():
    settings = get_settings()
    api_key = settings.LLM_API_KEY
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url)
        print(f"ListModels Status: {resp.status_code}")
        if resp.status_code == 200:
            models = resp.json().get("models", [])
            print(f"Available models count: {len(models)}")
            for m in models:
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    print(" -", m.get("name"))
        else:
            print("Response:", resp.text)

if __name__ == "__main__":
    asyncio.run(list_gemini_models())
