from backend.mcp.adapter import MCPServer
from backend.tools.notion import (
    NotionAppendBlockTool,
    NotionCreatePageTool,
    NotionGetPageContentTool,
    NotionGetPageTool,
    NotionQueryDatabaseTool,
    NotionSearchTool,
    NotionUpdatePageTool,
)


class NotionServer(MCPServer):
    name = "notion"

    def tools(self):
        return [
            # Read
            NotionSearchTool(),
            NotionGetPageTool(),
            NotionGetPageContentTool(),
            NotionQueryDatabaseTool(),
            # Write (sensitive)
            NotionCreatePageTool(),
            NotionUpdatePageTool(),
            NotionAppendBlockTool(),
        ]
