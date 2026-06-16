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

    # --- RAG / embeddings (Phase 2) ---
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"  # local, 384-dim, via fastembed
    QDRANT_COLLECTION: str = "documents"
    RAG_CHUNK_SIZE: int = 800       # characters per chunk
    RAG_CHUNK_OVERLAP: int = 150    # overlap between consecutive chunks
    RAG_TOP_K: int = 4              # chunks retrieved per query

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
