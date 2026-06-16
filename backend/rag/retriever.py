"""
Retriever (Phase 2): embed a query → Qdrant search → top chunks.

Returns a small, typed list of the most relevant chunks, each with its source and
similarity score, ready to be formatted into a grounded LLM prompt.
"""
from pydantic import BaseModel

from backend.config import settings
from backend.rag.embeddings import embed_query
from backend.rag.store import search


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
    """Return the top-k most relevant chunks for `query` within one org."""
    if not query.strip():
        return []

    vector = await embed_query(query)
    points = await search(vector, top_k or settings.RAG_TOP_K, org_id)

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
