from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.slack import PostMessageTool


class SlackServer(MCPServer):
    name = "slack"

    def tools(self) -> list[Tool]:
        return [PostMessageTool()]
