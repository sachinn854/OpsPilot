from backend.mcp.adapter import MCPServer
from backend.tools.workflows import (
    BroadcastIncidentTool,
    GenerateStandupTool,
    NotifyPRStakeholdersTool,
    NotifyStalePRsTool,
)


class WorkflowServer(MCPServer):
    name = "workflows"

    def tools(self):
        return [
            GenerateStandupTool(),
            NotifyStalePRsTool(),
            BroadcastIncidentTool(),
            NotifyPRStakeholdersTool(),
        ]
