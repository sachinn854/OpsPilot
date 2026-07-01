from backend.mcp.adapter import MCPServer
from backend.tools.hubspot import (
    HubSpotCreateContactTool,
    HubSpotCreateDealTool,
    HubSpotGetContactTool,
    HubSpotGetDealTool,
    HubSpotListCompaniesTool,
    HubSpotListDealsTool,
    HubSpotSearchContactsTool,
    HubSpotUpdateContactTool,
)


class HubSpotServer(MCPServer):
    name = "hubspot"

    def tools(self):
        return [
            # Read
            HubSpotSearchContactsTool(),
            HubSpotGetContactTool(),
            HubSpotListDealsTool(),
            HubSpotGetDealTool(),
            HubSpotListCompaniesTool(),
            # Write (sensitive)
            HubSpotCreateContactTool(),
            HubSpotUpdateContactTool(),
            HubSpotCreateDealTool(),
        ]
