"""
LLM provider management endpoints.

GET   /v1/llm/config                  — user's current provider + model
PATCH /v1/llm/config                  — save user's provider + model preference
DELETE /v1/llm/config                 — reset to system default
GET   /v1/llm/openrouter/models       — fetch available models from OpenRouter (uses user's key)
GET   /v1/llm/ollama/models           — models installed in local Ollama
GET   /v1/llm/ollama/supported        — full list of models known to support tool-calling
"""
import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.deps import get_current_user
from backend.config import settings
from backend.db.models import User
from backend.db.session import get_session
from backend.llm.factory import OLLAMA_TOOL_CALLING_MODELS

router = APIRouter(prefix="/v1/llm", tags=["llm"])


# ── User LLM config ───────────────────────────────────────────────────────────

class LLMConfigIn(BaseModel):
    provider: str   # "openrouter" | "ollama"
    model: str      # model name


@router.get("/config")
async def get_llm_config(current_user: User = Depends(get_current_user)):
    """Return the user's active LLM config (user pref → env fallback)."""
    saved_model = current_user.llm_model or ""
    # Sanitize: if model looks like an email it's a bad DB value — ignore it
    if "@" in saved_model:
        saved_model = ""
    provider = current_user.llm_provider or settings.LLM_PROVIDER
    model    = saved_model or (
        settings.OLLAMA_MODEL if provider == "ollama" else settings.OPENROUTER_MODEL
    )
    return {
        "provider":       provider,
        "model":          model,
        "is_custom":      bool(current_user.llm_provider),
        "env_provider":   settings.LLM_PROVIDER,
        "env_model":      settings.OLLAMA_MODEL if settings.LLM_PROVIDER == "ollama" else settings.OPENROUTER_MODEL,
    }


@router.patch("/config")
async def set_llm_config(
    body: LLMConfigIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Save the user's LLM provider + model preference."""
    if body.provider not in ("openrouter", "ollama"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="provider must be 'openrouter' or 'ollama'")

    current_user.llm_provider = body.provider
    current_user.llm_model    = body.model.strip()
    await session.commit()
    return {"ok": True, "provider": body.provider, "model": body.model}


@router.delete("/config")
async def reset_llm_config(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Reset to system default (remove user override)."""
    current_user.llm_provider = ""
    current_user.llm_model    = ""
    await session.commit()
    return {"ok": True, "message": "Reset to system default"}


@router.get("/openrouter/models")
async def list_openrouter_models(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Fetch available OpenRouter models using the user's own API key."""
    # Try user's saved key first, fall back to env
    from backend.integrations.store import get_token
    api_key = await get_token(session, org_id="default", service="openrouter")
    api_key = api_key or settings.OPENROUTER_API_KEY

    if not api_key:
        return {"ok": False, "error": "No OpenRouter API key. Add your key in Settings → Integrations."}

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        resp.raise_for_status()
        raw = resp.json().get("data", [])

        models = []
        for m in raw:
            ctx    = m.get("context_length", 0)
            pricing = m.get("pricing", {})
            models.append({
                "id":             m.get("id", ""),
                "name":           m.get("name", ""),
                "context_length": ctx,
                "prompt_price":   pricing.get("prompt", "0"),
                "completion_price": pricing.get("completion", "0"),
                "supports_tools": bool(m.get("supported_parameters", {}).get("tools")),
            })

        # Sort: tool-supporting first, then by name
        models.sort(key=lambda m: (not m["supports_tools"], m["name"].lower()))
        return {"ok": True, "models": models, "total": len(models)}

    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            return {"ok": False, "error": "Invalid API key. Check your OpenRouter key in Settings."}
        return {"ok": False, "error": f"OpenRouter error: {exc.response.status_code}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


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
