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
        GitHubAddLabelsTool,
        GitHubBranchesTool,
        GitHubCloseIssueTool,
        GitHubClosePRTool,
        GitHubCommentOnIssueTool,
        GitHubCommentOnPRTool,
        GitHubCompareBranchesTool,
        GitHubCommitsTool,
        GitHubContributorsTool,
        GitHubCreateBranchTool,
        GitHubCreateIssueTool,
        GitHubCreatePRTool,
        GitHubFileContentTool,
        GitHubFileTreeTool,
        GitHubGetIssueTool,
        GitHubGetPRTool,
        GitHubGetTagsTool,
        GitHubIssuesTool,
        GitHubListMilestonesTool,
        GitHubListWorkflowsTool,
        GitHubMergePRTool,
        GitHubPRsTool,
        GitHubReadmeTool,
        GitHubReleasesTool,
        GitHubRepoInfoTool,
        GitHubRepoLanguagesTool,
        GitHubSearchCodeTool,
        GitHubUpdateIssueTool,
        GitHubUserReposTool,
        GitHubWorkflowRunsTool,
    )
    from backend.tools.ops import RestartServiceTool, RollbackDeploymentTool
    from backend.tools.rag import RagSearchTool
    from backend.tools.slack import (
        SlackAddReactionTool,
        SlackCreateChannelTool,
        SlackDeleteMessageTool,
        SlackGetMessagesTool,
        SlackGetThreadTool,
        SlackGetUserInfoTool,
        SlackInviteToChannelTool,
        SlackListChannelsTool,
        SlackListUsersTool,
        SlackPinMessageTool,
        SlackPostMessageTool,
        SlackScheduleMessageTool,
        SlackSearchMessagesTool,
        SlackSendDMTool,
        SlackSetTopicTool,
        SlackUpdateMessageTool,
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
            GitHubGetIssueTool(),
            GitHubPRsTool(),
            GitHubGetPRTool(),
            GitHubCommitsTool(),
            GitHubListWorkflowsTool(),
            GitHubWorkflowRunsTool(),
            GitHubCompareBranchesTool(),
            GitHubGetTagsTool(),
            GitHubListMilestonesTool(),
            # GitHub write tools (sensitive — HITL)
            GitHubCreateIssueTool(),
            GitHubUpdateIssueTool(),
            GitHubCloseIssueTool(),
            GitHubAddLabelsTool(),
            GitHubCommentOnIssueTool(),
            GitHubCreatePRTool(),
            GitHubMergePRTool(),
            GitHubClosePRTool(),
            GitHubCommentOnPRTool(),
            GitHubCreateBranchTool(),
            # Slack read tools
            SlackPostMessageTool(),
            SlackListChannelsTool(),
            SlackGetMessagesTool(),
            SlackGetThreadTool(),
            SlackSendDMTool(),
            SlackSearchMessagesTool(),
            SlackGetUserInfoTool(),
            SlackListUsersTool(),
            SlackAddReactionTool(),
            SlackUploadFileTool(),
            # Slack write tools (sensitive — HITL)
            SlackCreateChannelTool(),
            SlackSetTopicTool(),
            SlackInviteToChannelTool(),
            SlackUpdateMessageTool(),
            SlackDeleteMessageTool(),
            SlackPinMessageTool(),
            SlackScheduleMessageTool(),
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
