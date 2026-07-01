from backend.mcp.adapter import MCPServer
from backend.tools.linear import (
    LinearAddCommentTool,
    LinearCreateIssueTool,
    LinearGetIssueTool,
    LinearGetIssuesTool,
    LinearGetProjectsTool,
    LinearGetTeamsTool,
    LinearUpdateIssueTool,
)


class LinearServer(MCPServer):
    name = "linear"

    def tools(self):
        return [
            LinearGetTeamsTool(),
            LinearGetIssuesTool(),
            LinearGetIssueTool(),
            LinearGetProjectsTool(),
            LinearCreateIssueTool(),
            LinearUpdateIssueTool(),
            LinearAddCommentTool(),
        ]
