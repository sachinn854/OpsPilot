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

from fastembed import SparseTextEmbedding, TextEmbedding
from pydantic import BaseModel

from backend.config import settings


class SparseVec(BaseModel):
    """A sparse (keyword/BM25) embedding: parallel indices + weights."""
    indices: list[int]
    values: list[float]


# --------------------------- Dense (semantic) ------------------------------
@lru_cache
def _model() -> TextEmbedding:
    """Load the dense embedding model once per process (downloaded on first use)."""
    return TextEmbedding(model_name=settings.EMBEDDING_MODEL)


def _embed_sync(texts: list[str]) -> list[list[float]]:
    # fastembed returns a generator of numpy arrays.
    return [vec.tolist() for vec in _model().embed(texts)]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts → list of dense float vectors."""
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sync, texts)


async def embed_query(text: str) -> list[float]:
    """Embed a single query string → one dense float vector."""
    vectors = await embed_texts([text])
    return vectors[0]


@lru_cache
def embedding_dim() -> int:
    """Dense vector size for the configured model (probed once)."""
    return len(_embed_sync(["dimension probe"])[0])


# --------------------------- Sparse (keyword/BM25) -------------------------
@lru_cache
def _sparse_model() -> SparseTextEmbedding:
    """Load the sparse BM25 model once per process."""
    return SparseTextEmbedding(model_name=settings.SPARSE_MODEL)


def _to_sparse(emb) -> SparseVec:
    return SparseVec(
        indices=emb.indices.tolist(),
        values=emb.values.tolist(),
    )


def _embed_sparse_docs_sync(texts: list[str]) -> list[SparseVec]:
    return [_to_sparse(e) for e in _sparse_model().embed(texts)]


def _embed_sparse_query_sync(text: str) -> SparseVec:
    return _to_sparse(next(iter(_sparse_model().query_embed([text]))))


async def embed_sparse_docs(texts: list[str]) -> list[SparseVec]:
    """Sparse-embed a batch of documents (BM25 term weights)."""
    if not texts:
        return []
    return await asyncio.to_thread(_embed_sparse_docs_sync, texts)


async def embed_sparse_query(text: str) -> SparseVec:
    """Sparse-embed a single query (BM25)."""
    return await asyncio.to_thread(_embed_sparse_query_sync, text)
