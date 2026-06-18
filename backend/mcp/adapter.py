"""
MCP adapter — bridges our Tool interface to MCP-compatible descriptors.

MCPServer is the abstract base class every server implements. Each server
groups a set of related tools under one name (e.g. "github", "ops"). The
ToolRegistry collects all servers, filters by config, and exposes:
  - list_specs() → MCPToolSpec list (for discovery)
  - build_router() → ToolRouter (for agents to call tools)
"""
from abc import ABC, abstractmethod

from backend.mcp.types import MCPToolSpec
from backend.tools.base import Tool


def tool_to_spec(tool: Tool, server: str) -> MCPToolSpec:
    """Produce an MCPToolSpec from any Tool instance."""
    return MCPToolSpec(
        name=tool.name,
        description=tool.description,
        parameters=tool.parameters,
        server=server,
        sensitive=getattr(tool, "sensitive", False),
    )


class MCPServer(ABC):
    """A named group of related tools exposed as a single server unit."""

    name: str  # override in subclass, e.g. name = "github"

    @abstractmethod
    def tools(self) -> list[Tool]:
        """Return all tool instances this server provides."""
        ...

    def specs(self) -> list[MCPToolSpec]:
        """Return MCP descriptors for every tool in this server."""
        return [tool_to_spec(t, self.name) for t in self.tools()]
