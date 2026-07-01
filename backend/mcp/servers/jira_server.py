from backend.mcp.adapter import MCPServer
from backend.tools.jira import (
    JiraAddCommentTool,
    JiraCreateIssueTool,
    JiraGetCommentsTool,
    JiraGetIssueTool,
    JiraGetIssuesTool,
    JiraGetProjectsTool,
    JiraTransitionIssueTool,
    JiraUpdateIssueTool,
)


class JiraServer(MCPServer):
    name = "jira"

    def tools(self):
        return [
            JiraGetProjectsTool(),
            JiraGetIssuesTool(),
            JiraGetIssueTool(),
            JiraGetCommentsTool(),
            JiraCreateIssueTool(),
            JiraUpdateIssueTool(),
            JiraAddCommentTool(),
            JiraTransitionIssueTool(),
        ]
