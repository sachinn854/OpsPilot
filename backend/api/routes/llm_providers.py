"""
LLM provider management endpoints.

GET  /v1/llm/providers          — current provider config + available providers
GET  /v1/llm/ollama/models      — models installed in local Ollama instance
GET  /v1/llm/ollama/supported   — full list of models known to support tool-calling
"""
import httpx
from fastapi import APIRouter

from backend.config import settings
from backend.llm.factory import OLLAMA_TOOL_CALLING_MODELS

router = APIRouter(prefix="/v1/llm", tags=["llm"])


@router.get("/providers")
async def get_providers():
    """Return active provider config and available options."""
    return {
        "active_provider": settings.LLM_PROVIDER,
        "active_model": (
            settings.OLLAMA_MODEL
            if settings.LLM_PROVIDER == "ollama"
            else settings.OPENROUTER_MODEL
        ),
        "providers": {
            "openrouter": {
                "configured": bool(settings.OPENROUTER_API_KEY),
                "model":      settings.OPENROUTER_MODEL,
                "base_url":   "https://openrouter.ai/api/v1",
            },
            "ollama": {
                "configured": True,   # always available if Ollama is running
                "model":      settings.OLLAMA_MODEL,
                "base_url":   settings.OLLAMA_BASE_URL,
            },
        },
    }


@router.get("/ollama/models")
async def list_ollama_models():
    """List models currently installed in the local Ollama instance."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
        resp.raise_for_status()
        raw = resp.json().get("models", [])

        # Mark which ones support tool-calling
        supported_names = {m["name"] for m in OLLAMA_TOOL_CALLING_MODELS}
        models = []
        for m in raw:
            model_name  = m.get("name", "")
            short_name  = model_name.split(":")[0]   # strip :tag
            tools_ok    = short_name in supported_names
            models.append({
                "name":          model_name,
                "size":          _fmt_size(m.get("size", 0)),
                "modified_at":   m.get("modified_at", ""),
                "tools_support": tools_ok,
            })

        return {
            "ok":            True,
            "ollama_url":    settings.OLLAMA_BASE_URL,
            "models":        models,
            "total":         len(models),
        }
    except httpx.ConnectError:
        return {
            "ok":    False,
            "error": f"Ollama is not running at {settings.OLLAMA_BASE_URL}. "
                     "Start it with: ollama serve",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/ollama/supported")
async def supported_models():
    """Full list of Ollama models known to support tool-calling."""
    return {
        "models": OLLAMA_TOOL_CALLING_MODELS,
        "note":   "Pull any model with: ollama pull <name>",
    }


def _fmt_size(size_bytes: int) -> str:
    if not size_bytes:
        return "unknown"
    gb = size_bytes / (1024 ** 3)
    return f"{gb:.1f} GB"
