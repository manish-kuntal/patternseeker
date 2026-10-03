import httpx
from ..core.config import settings

async def explain(title, description, evidence):
    if not settings.ollama_enabled:
        return None

    prompt = f"""
You are PATTERN, a personal behavior analytics assistant.

Observed pattern:
{title}

Observation:
{description}

Evidence:
{evidence}

Explain the observation in 2-4 concise sentences.
Do not claim causation.
Do not invent facts.
Clearly distinguish observation from possible interpretation.
"""

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                f"{settings.ollama_url}/api/generate",
                json={
                    "model": settings.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                },
            )
            response.raise_for_status()
            return response.json().get("response", "").strip() or None
    except Exception:
        return None
