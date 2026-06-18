from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.github import GitHubCommitsTool, GitHubIssuesTool


class GitHubServer(MCPServer):
    name = "github"

    def tools(self) -> list[Tool]:
        return [GitHubIssuesTool(), GitHubCommitsTool()]
