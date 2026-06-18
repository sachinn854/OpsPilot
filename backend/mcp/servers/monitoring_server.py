from backend.mcp.adapter import MCPServer
from backend.tools.base import Tool
from backend.tools.monitoring import GetMetricsTool, GetServiceHealthTool
from backend.tools.postgres import ExecuteSQLTool


class MonitoringServer(MCPServer):
    name = "monitoring"

    def tools(self) -> list[Tool]:
        return [GetServiceHealthTool(), GetMetricsTool(), ExecuteSQLTool()]
