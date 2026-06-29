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

    # --- OpenRouter (LLM) ---
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_MODEL: str = "anthropic/claude-haiku-4-5"

    # --- API authentication ---
    # Set a strong random string. When set, all requests must carry:
    #   Authorization: Bearer <API_KEY>
    # Leave empty in development to skip validation.
    API_KEY: str = ""

    # --- GitHub tool ---
    GITHUB_TOKEN: str = ""
    # Slack Bot OAuth token (xoxb-...). Can also be set per-org via Settings page.
    SLACK_TOKEN: str = ""
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
    TOOLS_ENABLED: str = "github,rag,ops,slack,search,monitoring"

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
