"""
Embeddings provider (Phase 2).

Groq does NOT offer an embeddings API, so we generate vectors locally with
`fastembed` (Qdrant's library). It runs *in-process* — no API key, no cost, and
it works the same way locally or on a deployed server (just needs ~1-2 GB RAM).

The model is loaded lazily and cached, and runs on a worker thread so it never
blocks the async event loop.
"""
import asyncio
from functools import lru_cache

from fastembed import TextEmbedding

from backend.config import settings


@lru_cache
def _model() -> TextEmbedding:
    """Load the embedding model once per process (downloaded on first use)."""
    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def _embed_sync(texts: list[str]) -> list[list[float]]:
    # fastembed returns a generator of numpy arrays.
    return [vec.tolist() for vec in _model().embed(texts)]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts → list of float vectors."""
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts)


async def embed_query(text: str) -> list[float]:
    """Embed a single query string → one float vector."""
    vectors = await embed_texts([text])
    return vectors[0]


@lru_cache
def embedding_dim() -> int:
    """Vector size for the configured model (probed once)."""
    return len(_embed_sync(["dimension probe"])[0])
