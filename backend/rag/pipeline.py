"""
RAG pipeline: query → retrieve → grounded answer with citations.

The retrieved chunks are formatted as a numbered context block. The LLM is told
to answer ONLY from that context and to cite sources as [1], [2], ... — so every
claim is traceable and hallucination is curbed.
"""
from pydantic import BaseModel

from backend.llm.base import LLMProvider
from backend.rag.retriever import RetrievedChunk, retrieve

RAG_SYSTEM_PROMPT = """You are AI Operations Copilot answering from a knowledge base.

Rules:
- Answer ONLY using the numbered context below. Do not use outside knowledge.
- Cite the sources you used inline as [1], [2], etc. (matching the context numbers).
- If the context does not contain the answer, say "I couldn't find that in the
  documents." Do not guess or invent facts.
- Be concise and clear."""


class Source(BaseModel):
    ref: int          # the [n] citation number
    source: str       # filename
    document_id: str
    chunk_index: int
    score: float


class RagAnswer(BaseModel):
    answer: str
    sources: list[Source]


def _format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(f"[{i}] (source: {c.source})\n{c.text}")
    return "\n\n".join(blocks)


async def answer_question(
    question: str,
    *,
    llm: LLMProvider,
    org_id: str = "default",
    top_k: int | None = None,
) -> RagAnswer:
    """Retrieve relevant chunks and produce a grounded, cited answer."""
    chunks = await retrieve(question, org_id=org_id, top_k=top_k)
    if not chunks:
        return RagAnswer(
            answer="I couldn't find that in the documents.", sources=[]
        )

    context = _format_context(chunks)
    messages = [
        {"role": "system", "content": RAG_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"Context:\n{context}\n\nQuestion: {question}",
        },
    ]
    response = await llm.chat(messages)

    sources = [
        Source(
            ref=i,
            source=c.source,
            document_id=c.document_id,
            chunk_index=c.chunk_index,
            score=c.score,
        )
        for i, c in enumerate(chunks, start=1)
    ]
    return RagAnswer(answer=response.content or "", sources=sources)
