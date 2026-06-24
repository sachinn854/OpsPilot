"""
RAG search tool.

Wraps the retriever as a standard `Tool` so the Copilot agent can decide, on its
own, to search the organization's uploaded documents when a question looks like
it needs them. Returns the matching chunks (text + source) for the agent to cite.
"""
from backend.rag.retriever import retrieve
from backend.tools.base import Tool, ToolResult


class RagSearchTool(Tool):
    name = "search_documents"
    description = (
        "Search the organization's uploaded documents / knowledge base "
        "(policies, manuals, notes). Use this when the question is about "
        "internal docs rather than live external data. Returns relevant "
        "passages with their source filenames — cite them in your answer."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look for, in natural language.",
            },
        },
        "required": ["query"],
    }

    def __init__(self, org_id: str = "default"):
        self.org_id = org_id

    async def run(self, query: str, top_k: int = 4) -> ToolResult:
        top_k = min(max(top_k, 1), 10)
        try:
            chunks = await retrieve(query, org_id=self.org_id, top_k=top_k)
            data = [
                {
                    "source": c.source,
                    "score": round(c.score, 4),
                    "text": c.text[:2000],  # cap per-chunk to keep total context manageable
                }
                for c in chunks
            ]
            return ToolResult(ok=True, data=data)
        except Exception as exc:  # Qdrant down / collection missing / etc.
            return ToolResult(ok=False, error=str(exc))
