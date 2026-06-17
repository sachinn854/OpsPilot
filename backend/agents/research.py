"""
Research agent (Phase 3).

Gathers the context needed to achieve the goal. For now its knowledge source is
the RAG knowledge base (Phase 2); memory and more sources slot in later. It
retrieves the most relevant chunks and synthesizes grounded notes the rest of
the pipeline can rely on — citing sources, never inventing facts.
"""
from pydantic import BaseModel

from backend.agents.base import BaseAgent
from backend.llm.base import LLMProvider
from backend.rag.retriever import retrieve

RESEARCH_PROMPT = """You are the Research agent in a multi-agent operations copilot.

You are given a goal and numbered context passages retrieved from the knowledge
base. Summarize ONLY the facts in the context that are relevant to the goal, as
concise notes. Cite passages inline as [1], [2], etc. If the context has nothing
relevant, say "No relevant information found in the knowledge base." Never invent
facts beyond the context."""


class ResearchNotes(BaseModel):
    notes: str
    sources: list[str]  # filenames used


class ResearchAgent(BaseAgent):
    def __init__(self, llm: LLMProvider):
        super().__init__(llm, RESEARCH_PROMPT)

    async def run(
        self, goal: str, *, org_id: str = "default", top_k: int | None = None
    ) -> ResearchNotes:
        """Retrieve relevant chunks for `goal` and return grounded notes."""
        chunks = await retrieve(goal, org_id=org_id, top_k=top_k)
        if not chunks:
            return ResearchNotes(
                notes="No relevant information found in the knowledge base.",
                sources=[],
            )

        context = "\n\n".join(
            f"[{i}] (source: {c.source})\n{c.text}"
            for i, c in enumerate(chunks, start=1)
        )
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Goal: {goal}\n\nContext:\n{context}",
            },
        ]
        response = await self.llm.chat(messages)

        # de-duplicate source filenames, preserving order
        seen: dict[str, None] = {}
        for c in chunks:
            seen.setdefault(c.source, None)
        return ResearchNotes(notes=response.content or "", sources=list(seen))
