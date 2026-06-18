"""
Central application configuration.

All settings are loaded from environment variables (see `.env`). Nothing is
hardcoded — secrets live only in the environment. Import the singleton `settings`
anywhere in the app:

    from backend.config import settings
    print(settings.GROQ_MODEL)
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App ---
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "info"

    # --- Groq (LLM) ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # --- GitHub tool ---
    GITHUB_TOKEN: str = ""

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
    CRITIC_CONFIDENCE_THRESHOLD: float = 0.7  # below this → retry the loop
    RUN_MAX_RETRIES: int = 2                   # max Critic-driven retries per run

    # --- Rate limiting (slowapi, per-IP) ---
    RATE_LIMIT_CHAT: str = "30/minute"
    RATE_LIMIT_RUNS: str = "10/minute"
    RATE_LIMIT_APPROVALS: str = "20/minute"

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
