"""
LLM provider factory — returns the right provider based on LLM_PROVIDER config.
"""
from backend.llm.base import LLMProvider


# Models known to support tool-calling in Ollama
OLLAMA_TOOL_CALLING_MODELS: list[dict] = [
    {"name": "llama3.3",         "size": "70B",  "notes": "Best tool-calling, high RAM"},
    {"name": "llama3.1",         "size": "8B",   "notes": "Recommended — fast + reliable tools"},
    {"name": "llama3.2",         "size": "3B",   "notes": "Fastest, lower accuracy"},
    {"name": "qwen2.5",          "size": "7B",   "notes": "Strong tool-calling, multilingual"},
    {"name": "qwen2.5-coder",    "size": "7B",   "notes": "Code-focused, good at structured output"},
    {"name": "mistral-nemo",     "size": "12B",  "notes": "Balanced speed + quality"},
    {"name": "mistral-small",    "size": "22B",  "notes": "High quality, needs 16GB+ RAM"},
    {"name": "phi4",             "size": "14B",  "notes": "Microsoft, efficient"},
    {"name": "phi3.5",           "size": "3.8B", "notes": "Very fast, low RAM"},
    {"name": "command-r",        "size": "35B",  "notes": "Cohere, best for RAG + tools"},
    {"name": "granite3.1-dense", "size": "8B",   "notes": "IBM, enterprise-grade tool use"},
    {"name": "deepseek-r1",      "size": "7B",   "notes": "Reasoning model, experimental tools"},
]


def get_llm_provider(provider: str | None = None, model: str | None = None) -> LLMProvider:
    """
    Return the configured LLM provider.

    provider + model args override env — pass user's saved preferences here.
    """
    from backend.config import settings

    name = (provider or settings.LLM_PROVIDER).lower().strip()

    if name == "ollama":
        from backend.llm.ollama_provider import OllamaProvider
        return OllamaProvider(model=model or settings.OLLAMA_MODEL)

    # Default: openrouter
    from backend.llm.openrouter_provider import OpenRouterProvider
    return OpenRouterProvider(model=model or settings.OPENROUTER_MODEL)


def get_llm_for_user(user, api_key: str | None = None) -> LLMProvider:
    """
    Return the LLM provider configured for a specific user (with env fallback).
    api_key — caller should pass the user's decrypted OpenRouter key from DB.
    """
    provider = getattr(user, "llm_provider", "") or None
    model    = getattr(user, "llm_model", "") or None

    from backend.config import settings
    name = (provider or settings.LLM_PROVIDER).lower().strip()

    if name == "ollama":
        from backend.llm.ollama_provider import OllamaProvider
        return OllamaProvider(model=model or settings.OLLAMA_MODEL)

    from backend.llm.openrouter_provider import OpenRouterProvider
    # api_key must come from user's DB token — no env fallback here
    # (env fallback allowed only for system tasks like Celery workers)
    return OpenRouterProvider(
        api_key=api_key or "",
        model=model or settings.OPENROUTER_MODEL,
    )
