"""
Tool Router (ARCHITECTURE.md §5.3).

A small registry that:
  - holds the available tools,
  - exposes their schemas to the LLM,
  - dispatches a tool call by name to the right tool.

Agents talk to this, never to a concrete tool. In Phase 5 an MCP adapter plugs
in here so tools can be discovered over the protocol — no agent changes needed.
"""
from backend.tools.base import Tool, ToolResult


class ToolRouter:
    def __init__(self, tools: list[Tool] | None = None):
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        """All tool schemas in OpenAI/Groq function-calling format."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    async def execute(self, name: str, arguments: dict) -> ToolResult:
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(ok=False, error=f"Unknown tool: {name}")
        try:
            return await tool.run(**arguments)
        except TypeError as exc:
            # Wrong/missing arguments from the model.
            return ToolResult(ok=False, error=f"Bad arguments for '{name}': {exc}")


def build_default_router() -> "ToolRouter":
    """The standard tool set used by the Copilot and the multi-agent runs.

    Kept in one place so every entrypoint exposes the same tools. As tools move
    to MCP (Phase 5), only this factory changes.
    """
    from backend.tools.github import GitHubCommitsTool, GitHubIssuesTool
    from backend.tools.rag import RagSearchTool

    return ToolRouter([GitHubIssuesTool(), GitHubCommitsTool(), RagSearchTool()])
