"""
Config-driven tool registry.

ToolRegistry holds all MCPServers and filters them by the TOOLS_ENABLED
config setting. Agents get a ToolRouter built from whatever servers are
active — adding a new tool means adding a server + updating config, with
no changes to any agent code.

TOOLS_ENABLED examples:
    "all"                     → every server enabled
    "github,rag,ops"          → only those three
    ""  (empty)               → no tools (read-only / analysis mode)
"""
from backend.core.tool_router import ToolRouter
from backend.mcp.adapter import MCPServer
from backend.mcp.types import MCPToolSpec
from backend.tools.base import Tool


class ToolRegistry:
    def __init__(
        self,
        servers: list[MCPServer],
        enabled: set[str] | None = None,
    ) -> None:
        """
        Parameters
        ----------
        servers : list of MCPServer
            All available servers (the full catalog).
        enabled : set[str] | None
            Server names to activate. None = all servers active.
        """
        self._all: dict[str, MCPServer] = {s.name: s for s in servers}
        self._enabled: set[str] | None = enabled

    # ------------------------------------------------------------------
    def _active(self) -> list[MCPServer]:
        if self._enabled is None:
            return list(self._all.values())
        return [s for name, s in self._all.items() if name in self._enabled]

    def list_specs(self) -> list[MCPToolSpec]:
        """Return MCP descriptors for every tool across active servers."""
        specs: list[MCPToolSpec] = []
        for server in self._active():
            specs.extend(server.specs())
        return specs

    def build_router(self) -> ToolRouter:
        """Return a ToolRouter wired with all tools from active servers."""
        tools: list[Tool] = []
        for server in self._active():
            tools.extend(server.tools())
        return ToolRouter(tools)

    def get_tool(self, name: str) -> Tool | None:
        """Look up a tool by name across active servers."""
        for server in self._active():
            for tool in server.tools():
                if tool.name == name:
                    return tool
        return None

    def server_names(self) -> list[str]:
        """All enabled server names."""
        return [s.name for s in self._active()]
