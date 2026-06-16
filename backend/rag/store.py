"""
Qdrant vector store (Phase 2).

Thin async wrapper around the Qdrant client: ensure the collection exists, upsert
chunk vectors, and run similarity search filtered by `org_id` (multi-tenant).

Vectors live here; the chunk text + metadata also live in Postgres
(`document_chunks`). We additionally stash the text in the Qdrant payload so a
search result is self-contained for answering.
"""
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from backend.config import settings

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    """Shared async Qdrant client (created once)."""
    global _client
    if _client is None:
        _client = AsyncQdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY or None,
        )
    return _client


async def ensure_collection(dim: int) -> None:
    """Create the documents collection if it doesn't exist yet."""
    client = get_client()
    if not await client.collection_exists(settings.QDRANT_COLLECTION):
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )


async def upsert_points(points: list[PointStruct]) -> None:
    """Insert/update chunk vectors."""
    if not points:
        return
    client = get_client()
    await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)


async def search(vector: list[float], top_k: int, org_id: str) -> list:
    """Similarity search within one org. Returns scored points with payloads."""
    client = get_client()
    org_filter = Filter(
        must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))]
    )
    result = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=vector,
        limit=top_k,
        query_filter=org_filter,
        with_payload=True,
    )
    return result.points
