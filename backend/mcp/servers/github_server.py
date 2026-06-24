from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
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


class GitHubServer(MCPServer):
    name = "github"

    def tools(self) -> list[Tool]:
        return [
            # Read tools
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
            # Write tools (sensitive=True — HITL approval required)
            GitHubCreateIssueTool(),
            GitHubCommentOnIssueTool(),
            GitHubCommentOnPRTool(),
            GitHubCloseIssueTool(),
        ]
