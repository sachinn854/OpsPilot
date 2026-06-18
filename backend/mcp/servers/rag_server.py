from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.rag import RagSearchTool


class RagServer(MCPServer):
    name = "rag"

    def tools(self) -> list[Tool]:
        return [RagSearchTool()]
