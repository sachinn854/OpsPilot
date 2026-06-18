from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.ops import RestartServiceTool, RollbackDeploymentTool


class OpsServer(MCPServer):
    name = "ops"

    def tools(self) -> list[Tool]:
        return [RollbackDeploymentTool(), RestartServiceTool()]
