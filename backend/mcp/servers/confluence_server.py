from backend.mcp.adapter import MCPServer
from backend.tools.confluence import (
    ConfluenceCreatePageTool,
    ConfluenceGetPageTool,
    ConfluenceGetSpacePagesTool,
    ConfluenceListSpacesTool,
    ConfluenceSearchTool,
    ConfluenceUpdatePageTool,
)


class ConfluenceServer(MCPServer):
    name = "confluence"

    def tools(self):
        return [
            # Read
            ConfluenceSearchTool(),
            ConfluenceGetPageTool(),
            ConfluenceListSpacesTool(),
            ConfluenceGetSpacePagesTool(),
            # Write (sensitive)
            ConfluenceCreatePageTool(),
            ConfluenceUpdatePageTool(),
        ]
