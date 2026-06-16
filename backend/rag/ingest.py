"""
Document ingestion (Phase 2): load → chunk → embed → store.

Given raw text, this:
  1. splits it into overlapping chunks,
  2. embeds each chunk locally (fastembed),
  3. upserts the vectors into Qdrant (payload carries text + metadata),
  4. records the Document + DocumentChunk rows in Postgres for citations.

Everything is scoped by `org_id` for multi-tenancy.
"""
import uuid

from qdrant_client.models import PointStruct, SparseVector
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Document, DocumentChunk
from backend.rag.chunker import chunk_text
from backend.rag.embeddings import embed_sparse_docs, embed_texts, embedding_dim
from backend.rag.store import DENSE, SPARSE, ensure_collection, upsert_points


async def ingest_text(
    session: AsyncSession,
    *,
    text: str,
    filename: str,
    org_id: str = "default",
    source: str = "upload",
) -> Document:
    """Ingest one document's text and return the persisted Document."""
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("Document has no extractable text.")

    dense_vecs = await embed_texts(chunks)
    sparse_vecs = await embed_sparse_docs(chunks)
    await ensure_collection(embedding_dim())

    doc = Document(
        org_id=org_id,
        filename=filename,
        source=source,
        num_chunks=len(chunks),
    )
    session.add(doc)
    await session.flush()  # assigns doc.id

    points: list[PointStruct] = []
    for index, (content, dense, sparse) in enumerate(
        zip(chunks, dense_vecs, sparse_vecs)
    ):
        point_id = str(uuid.uuid4())
        session.add(
            DocumentChunk(
                document_id=doc.id,
                org_id=org_id,
                chunk_index=index,
                content=content,
                point_id=point_id,
            )
        )
        points.append(
            PointStruct(
                id=point_id,
                vector={
                    DENSE: dense,
                    SPARSE: SparseVector(
                        indices=sparse.indices, values=sparse.values
                    ),
                },
                payload={
                    "org_id": org_id,
                    "document_id": doc.id,
                    "chunk_index": index,
                    "source": filename,
                    "text": content,
                },
            )
        )

    await upsert_points(points)
    await session.commit()
    return doc
