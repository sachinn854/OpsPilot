"""
Retriever: embed a query → Qdrant search → top chunks.

Returns a small, typed list of the most relevant chunks, each with its source and
similarity score, ready to be formatted into a grounded LLM prompt.
"""
from pydantic import BaseModel

from backend.config import settings
from backend.rag.embeddings import embed_query, embed_sparse_query
from backend.rag.store import hybrid_search, search


class RetrievedChunk(BaseModel):
    text: str
    source: str
    document_id: str
    chunk_index: int
    score: float


async def retrieve(
    query: str,
    *,
    org_id: str = "default",
    top_k: int | None = None,
) -> list[RetrievedChunk]:
    """Return the top-k most relevant chunks for `query` within one org.

    Uses hybrid (dense + BM25) search when `RAG_HYBRID` is on, else pure dense.
    """
    if not query.strip():
        return []

    k = top_k or settings.RAG_TOP_K
    dense = await embed_query(query)

    if settings.RAG_HYBRID:
        try:
            sparse = await embed_sparse_query(query)
            points = await hybrid_search(
                dense, sparse.indices, sparse.values, k, org_id
            )
        except Exception:
            # Fallback to dense-only if hybrid/sparse fails (e.g. collection pre-dates BM25).
            points = await search(dense, k, org_id)
    else:
        points = await search(dense, k, org_id)

    chunks: list[RetrievedChunk] = []
    for point in points:
        payload = point.payload or {}
        chunks.append(
            RetrievedChunk(
                text=payload.get("text", ""),
                source=payload.get("source", "unknown"),
                document_id=payload.get("document_id", ""),
                chunk_index=payload.get("chunk_index", 0),
                score=point.score,
            )
        )
    return chunks
