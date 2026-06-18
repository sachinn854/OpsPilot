"""
MCP tool discovery and execution endpoints.

  GET  /v1/mcp/tools              → list all enabled tools with their MCP specs
  GET  /v1/mcp/servers            → list active server names
  POST /v1/mcp/tools/{name}       → call a tool by name (operator+ required)

The discovery endpoints let any client (or another agent) know which tools
are currently available without needing to read the source. The call endpoint
is a direct execution path — useful for testing or for orchestrating tools
outside of a full run.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_registry, limiter
from backend.config import settings
from backend.db.session import get_session
from backend.mcp.registry import ToolRegistry
from backend.mcp.types import MCPToolSpec
from backend.security.rbac import Role, require_role

router = APIRouter(prefix="/v1/mcp", tags=["mcp"])


class ToolCallRequest(BaseModel):
    arguments: dict = {}


class ServersResponse(BaseModel):
    servers: list[str]
    total_tools: int


@router.get("/tools", response_model=list[MCPToolSpec])
@limiter.limit(settings.RATE_LIMIT_RUNS)
async def list_tools(
    request: Request,
    registry: ToolRegistry = Depends(get_registry),
) -> list[MCPToolSpec]:
    """List every enabled tool with its MCP spec (name, description, schema)."""
    return registry.list_specs()


@router.get("/servers", response_model=ServersResponse)
@limiter.limit(settings.RATE_LIMIT_RUNS)
async def list_servers(
    request: Request,
    registry: ToolRegistry = Depends(get_registry),
) -> ServersResponse:
    """List active server names and total tool count."""
    specs = registry.list_specs()
    return ServersResponse(
        servers=registry.server_names(),
        total_tools=len(specs),
    )


@router.post("/tools/{tool_name}")
@limiter.limit(settings.RATE_LIMIT_RUNS)
async def call_tool(
    request: Request,
    tool_name: str,
    req: ToolCallRequest,
    registry: ToolRegistry = Depends(get_registry),
    _role: Role = require_role(Role.operator),
) -> dict:
    """Call a registered tool by name and return its result."""
    tool = registry.get_tool(tool_name)
    if tool is None:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found or not enabled.",
        )
    try:
        result = await tool.run(**req.arguments)
    except TypeError as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid arguments for '{tool_name}': {exc}",
        )
    return result.model_dump()
