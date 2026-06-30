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


def get_llm_provider(provider: str | None = None) -> LLMProvider:
    """
    Return the configured LLM provider.

    provider arg overrides LLM_PROVIDER env — useful for per-request overrides.
    """
    from backend.config import settings

    name = (provider or settings.LLM_PROVIDER).lower().strip()

    if name == "ollama":
        from backend.llm.ollama_provider import OllamaProvider
        return OllamaProvider()

    # Default: openrouter
    from backend.llm.openrouter_provider import OpenRouterProvider
    return OpenRouterProvider()
