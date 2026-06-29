"""
Tool Router.

A small registry that:
  - holds the available tools,
  - exposes their schemas to the LLM,
  - dispatches a tool call by name to the right tool.

Agents talk to this, never to a concrete tool. Later an MCP adapter plugs
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
    to MCP, only this factory changes.
    """
    from backend.tools.github import (
        GitHubBranchesTool,
        GitHubCloseIssueTool,
        GitHubCommentOnIssueTool,
        GitHubCommentOnPRTool,
        GitHubCommitsTool,
        GitHubContributorsTool,
        GitHubCreateIssueTool,
        GitHubFileContentTool,
        GitHubFileTreeTool,
        GitHubIssuesTool,
        GitHubPRsTool,
        GitHubReadmeTool,
        GitHubReleasesTool,
        GitHubRepoInfoTool,
        GitHubRepoLanguagesTool,
        GitHubSearchCodeTool,
        GitHubUserReposTool,
    )
    from backend.tools.ops import RestartServiceTool, RollbackDeploymentTool
    from backend.tools.rag import RagSearchTool
    from backend.tools.slack import (
        SlackCreateChannelTool,
        SlackGetMessagesTool,
        SlackGetUserInfoTool,
        SlackListChannelsTool,
        SlackPostMessageTool,
        SlackSearchMessagesTool,
        SlackSendDMTool,
        SlackSetTopicTool,
        SlackUploadFileTool,
    )

    return ToolRouter(
        [
            # GitHub read tools
            GitHubRepoInfoTool(),
            GitHubReadmeTool(),
            GitHubFileTreeTool(),
            GitHubFileContentTool(),
            GitHubReleasesTool(),
            GitHubContributorsTool(),
            GitHubBranchesTool(),
            GitHubSearchCodeTool(),
            GitHubUserReposTool(),
            GitHubRepoLanguagesTool(),
            GitHubIssuesTool(),
            GitHubPRsTool(),
            GitHubCommitsTool(),
            # GitHub write tools (sensitive — HITL)
            GitHubCreateIssueTool(),
            GitHubCommentOnIssueTool(),
            GitHubCommentOnPRTool(),
            GitHubCloseIssueTool(),
            # Slack read tools
            SlackPostMessageTool(),
            SlackListChannelsTool(),
            SlackGetMessagesTool(),
            SlackSendDMTool(),
            SlackSearchMessagesTool(),
            SlackGetUserInfoTool(),
            SlackUploadFileTool(),
            # Slack write tools (sensitive — HITL)
            SlackCreateChannelTool(),
            SlackSetTopicTool(),
            # RAG
            RagSearchTool(),
            # Ops (sensitive — HITL)
            RollbackDeploymentTool(),
            RestartServiceTool(),
        ]
    )


def sensitive_tool_names(router: "ToolRouter") -> set[str]:
    """Names of tools in `router` that require human approval before running."""
    return {
        name
        for name, tool in router._tools.items()
        if getattr(tool, "sensitive", False)
    }
