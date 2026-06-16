"""
Qdrant vector store (Phase 2) — hybrid (dense + sparse) search.

The collection holds two named vectors per chunk:
  - "dense" : semantic embedding (cosine)
  - "bm25"  : sparse keyword embedding (BM25, IDF-weighted at query time)

`hybrid_search` runs both and fuses the rankings with Reciprocal Rank Fusion
(RRF) — cheap on latency, better on accuracy than either alone. A pure-dense
path is kept for when hybrid is disabled. All searches are filtered by `org_id`.
"""
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    Fusion,
    FusionQuery,
    MatchValue,
    Modifier,
    PointStruct,
    Prefetch,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from backend.config import settings

DENSE = "dense"
SPARSE = "bm25"

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


def _org_filter(org_id: str) -> Filter:
    return Filter(must=[FieldCondition(key="org_id", match=MatchValue(value=org_id))])


async def ensure_collection(dim: int) -> None:
    """Create the collection with dense + sparse vectors if needed.

    If an older collection exists without the sparse "bm25" vector (e.g. created
    before hybrid search), it is recreated so the schema matches.
    """
    client = get_client()
    name = settings.QDRANT_COLLECTION

    if await client.collection_exists(name):
        try:
            info = await client.get_collection(name)
            sparse = info.config.params.sparse_vectors or {}
            if SPARSE in sparse:
                return  # already hybrid-ready
        except Exception:
            pass
        await client.delete_collection(name)

    await client.create_collection(
        collection_name=name,
        vectors_config={DENSE: VectorParams(size=dim, distance=Distance.COSINE)},
        sparse_vectors_config={SPARSE: SparseVectorParams(modifier=Modifier.IDF)},
    )


async def upsert_points(points: list[PointStruct]) -> None:
    """Insert/update chunk vectors."""
    if not points:
        return
    client = get_client()
    await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=points)


async def search(dense: list[float], top_k: int, org_id: str) -> list:
    """Pure semantic (dense-only) search within one org."""
    client = get_client()
    result = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        query=dense,
        using=DENSE,
        limit=top_k,
        query_filter=_org_filter(org_id),
        with_payload=True,
    )
    return result.points


async def hybrid_search(
    dense: list[float],
    sparse_indices: list[int],
    sparse_values: list[float],
    top_k: int,
    org_id: str,
) -> list:
    """Dense + BM25 search fused with RRF. Each branch pulls a wider candidate
    pool, then fusion picks the final top_k."""
    client = get_client()
    org = _org_filter(org_id)
    pool = max(top_k * 5, 20)  # bounded candidate pool keeps latency in check

    result = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        prefetch=[
            Prefetch(query=dense, using=DENSE, limit=pool, filter=org),
            Prefetch(
                query=SparseVector(indices=sparse_indices, values=sparse_values),
                using=SPARSE,
                limit=pool,
                filter=org,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return result.points
