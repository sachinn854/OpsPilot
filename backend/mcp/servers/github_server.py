from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
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
            GitHubGetIssueTool(),
            GitHubPRsTool(),
            GitHubGetPRTool(),
            GitHubCommitsTool(),
            GitHubListWorkflowsTool(),
            GitHubWorkflowRunsTool(),
            GitHubCompareBranchesTool(),
            GitHubGetTagsTool(),
            GitHubListMilestonesTool(),
            # Write tools (sensitive=True — HITL approval required)
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
        ]
