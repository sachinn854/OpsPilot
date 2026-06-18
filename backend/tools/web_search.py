"""
Web search tool — fetch current information from the internet.

The implementation here is mocked. A production version would call a real
search API (e.g. Brave Search, SerpAPI, or Tavily) using a key from the
environment.
"""
from backend.tools.base import Tool, ToolResult


class WebSearchTool(Tool):
    name = "web_search"
    description = (
        "Search the web for current information. "
        "Use when the knowledge base doesn't have the answer or the data may be stale."
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
                "description": "Maximum number of results to return (default 5).",
                "default": 5,
            },
        },
        "required": ["query"],
    }

    async def run(self, query: str, max_results: int = 5) -> ToolResult:
        # Mocked — no real search API is called.
        return ToolResult(
            ok=True,
            data={
                "query": query,
                "results": [
                    {
                        "title": f"Simulated result {i + 1} for: {query}",
                        "url": f"https://example.com/result-{i + 1}",
                        "snippet": (
                            f"This is a simulated search snippet for '{query}'. "
                            "Wire a real search API (Brave/Tavily/SerpAPI) to activate."
                        ),
                    }
                    for i in range(min(max_results, 3))
                ],
                "note": "simulated (no search API key configured)",
            },
        )
