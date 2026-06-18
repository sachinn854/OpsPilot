from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.filesystem import ListFilesTool, ReadFileTool
from backend.tools.web_search import WebSearchTool


class SearchServer(MCPServer):
    name = "search"

    def tools(self) -> list[Tool]:
        return [WebSearchTool(), ReadFileTool(), ListFilesTool()]
