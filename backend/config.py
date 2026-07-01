"""
Central application configuration.

All settings are loaded from environment variables (see `.env`). Nothing is
hardcoded — secrets live only in the environment. Import the singleton `settings`
anywhere in the app:

    from backend.config import settings
    print(settings.OPENROUTER_MODEL)
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "info"
    # Comma-separated allowed CORS origins (add your Railway frontend URL here)
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # --- LLM provider selection ---
    # "openrouter" → cloud via OpenRouter API
    # "ollama"     → local models via Ollama (no API key needed)
    LLM_PROVIDER: str = "openrouter"

    # --- OpenRouter ---
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-haiku-4-5"
    # Small free model for prompt-section classification + chat title generation.
    CLASSIFIER_MODEL: str = "google/gemma-4-31b-it:free"

    # --- Ollama (local LLM) ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"

    # --- JWT auth ---
    JWT_SECRET: str = "change-me-in-production-use-a-long-random-string"
    JWT_EXPIRE_DAYS: int = 30

    # --- API authentication (legacy Bearer gate) ---
    API_KEY: str = ""

    # --- GitHub tool ---
    GITHUB_TOKEN: str = ""
    # Slack Bot OAuth token (xoxb-...). Can also be set per-org via Settings page.
    SLACK_TOKEN: str = ""
    # Slack App-Level Token (xapp-...) — required for Socket Mode (bidirectional bot).
    SLACK_APP_TOKEN: str = ""
    # Slack Signing Secret — used to verify interactive payloads (from Slack app Basic Info).
    SLACK_SIGNING_SECRET: str = ""
    # Secret for verifying GitHub webhook signatures (X-Hub-Signature-256).
    # Generate any strong random string and paste it into the GitHub webhook settings.
    GITHUB_WEBHOOK_SECRET: str = ""

    # --- Integration token encryption ---
    # Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    ENCRYPTION_KEY: str = ""

    # --- PostgreSQL ---
    DATABASE_URL: str = "postgresql+asyncpg://copilot:copilot_pass@localhost:5432/copilot"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Qdrant ---
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # --- RAG / embeddings ---
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # dense, local, 384-dim (fastembed)
    SPARSE_MODEL: str = "Qdrant/bm25"                # sparse/keyword, local (fastembed)
    QDRANT_COLLECTION: str = "documents"
    RAG_CHUNK_SIZE: int = 800       # characters per chunk
    RAG_CHUNK_OVERLAP: int = 150    # overlap between consecutive chunks
    RAG_TOP_K: int = 4              # chunks returned per query
    RAG_HYBRID: bool = True         # fuse semantic + BM25 keyword (cheap, accuracy↑)
    # RAG_RERANK: future toggle — cross-encoder rerank. Kept OFF for now because it
    # adds latency and isn't needed on a small KB. Turn on when the KB grows.
    RAG_RERANK: bool = False

    # --- Multi-agent runs ---
    CRITIC_CONFIDENCE_THRESHOLD: float = 0.7
    RUN_MAX_RETRIES: int = 2

    @field_validator("CRITIC_CONFIDENCE_THRESHOLD")
    @classmethod
    def _clamp_threshold(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("CRITIC_CONFIDENCE_THRESHOLD must be between 0.0 and 1.0")
        return v

    # --- Rate limiting (slowapi, per-IP) ---
    RATE_LIMIT_CHAT: str = "30/minute"
    RATE_LIMIT_RUNS: str = "10/minute"
    RATE_LIMIT_APPROVALS: str = "20/minute"

    # --- MCP tool registry ---
    # Comma-separated server names to enable, or "all" for everything.
    TOOLS_ENABLED: str = "github,rag,ops,slack,search,monitoring,jira,linear,google"

    # --- Email (SMTP) ---
    SMTP_HOST: str = ""            # e.g. smtp.gmail.com
    SMTP_PORT: int = 587
    SMTP_USER: str = ""            # sender address
    SMTP_PASSWORD: str = ""        # app password (Gmail) or API key (SendGrid)
    SMTP_FROM_NAME: str = "OpsPilot"

    # --- Google OAuth2 ---
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/v1/integrations/google/callback"

    # --- LangSmith tracing (optional) ---
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "ai-operations-copilot"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance (loaded once per process)."""
    return Settings()


settings = get_settings()
