"""
MCP tool descriptor.

Every tool in the system is described by an MCPToolSpec. Agents and the
discovery API work with specs — the actual Tool implementation is looked up
from the registry only when a tool is called.
"""
from pydantic import BaseModel


class MCPToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict        # JSON Schema for the tool's arguments
    server: str             # which server provides it (e.g. "github", "ops")
    sensitive: bool = False # True → HITL approval required before execution
