from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.github import GitHubCommitsTool, GitHubIssuesTool, GitHubPRsTool


class GitHubServer(MCPServer):
    name = "github"

    def tools(self) -> list[Tool]:
        return [GitHubIssuesTool(), GitHubPRsTool(), GitHubCommitsTool()]
