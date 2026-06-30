"""
Web search tool — DuckDuckGo (free, no API key required).
"""
from backend.tools.base import Tool, ToolResult


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web for current information using DuckDuckGo. "
        "Use when the user asks about recent news, live data, or anything "
        "not available in the knowledge base."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query.",
            },
            "max_results": {
                "type": "integer",
                "description": "Number of results to return (default 5, max 10).",
            },
        },
        "required": ["query"],
    }

    async def run(self, query: str, max_results: int = 5, **_) -> ToolResult:
        try:
            from duckduckgo_search import DDGS
            max_results = min(int(max_results), 10)
            results = []
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url":   r.get("href", ""),
                        "body":  (r.get("body") or "")[:400],
                    })
            if not results:
                return ToolResult(ok=False, error="No results found.")
            return ToolResult(ok=True, data={"query": query, "results": results})
        except Exception as exc:
            return ToolResult(ok=False, error=f"Search failed: {exc}")
