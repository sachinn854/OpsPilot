from backend.mcp.adapter import MCPServer
from backend.tools.pagerduty import (
    PagerDutyAcknowledgeIncidentTool,
    PagerDutyCreateIncidentTool,
    PagerDutyGetIncidentTool,
    PagerDutyGetOncallTool,
    PagerDutyListIncidentsTool,
    PagerDutyListServicesTool,
    PagerDutyResolveIncidentTool,
)


class PagerDutyServer(MCPServer):
    name = "pagerduty"

    def tools(self):
        return [
            # Read
            PagerDutyListIncidentsTool(),
            PagerDutyGetIncidentTool(),
            PagerDutyListServicesTool(),
            PagerDutyGetOncallTool(),
            # Write (sensitive)
            PagerDutyCreateIncidentTool(),
            PagerDutyAcknowledgeIncidentTool(),
            PagerDutyResolveIncidentTool(),
        ]
