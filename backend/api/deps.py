"""
Shared API dependencies.

Singletons live here so every route module imports the same instances:
- limiter       → slowapi rate limiter (must be on app.state)
- get_registry  → config-driven ToolRegistry (all MCPServers + TOOLS_ENABLED filter)
- get_orchestrator → LangGraph orchestrator wired with the registry's ToolRouter

The Orchestrator keeps the in-memory LangGraph checkpointer alive between the
`POST /v1/runs` that pauses a run and the `POST /v1/approvals/...` that resumes it.
"""
from functools import lru_cache

from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import settings
from backend.core.orchestrator import Orchestrator
from backend.llm.openrouter_provider import OpenRouterProvider
from backend.mcp.registry import ToolRegistry
from backend.mcp.servers.github_server import GitHubServer
from backend.mcp.servers.monitoring_server import MonitoringServer
from backend.mcp.servers.ops_server import OpsServer
from backend.mcp.servers.rag_server import RagServer
from backend.mcp.servers.search_server import SearchServer
from backend.mcp.servers.slack_server import SlackServer

# One limiter instance shared across all routes.
limiter = Limiter(key_func=get_remote_address)


@lru_cache
def get_registry() -> ToolRegistry:
    """Config-driven ToolRegistry — reads TOOLS_ENABLED from settings."""
    enabled: set[str] | None = (
        None
        if settings.TOOLS_ENABLED.strip().lower() == "all"
        else {name.strip() for name in settings.TOOLS_ENABLED.split(",") if name.strip()}
    )
    return ToolRegistry(
        servers=[
            GitHubServer(),
            OpsServer(),
            RagServer(),
            SlackServer(),
            SearchServer(),
            MonitoringServer(),
        ],
        enabled=enabled,
    )


@lru_cache
def get_orchestrator() -> Orchestrator:
    """Orchestrator singleton wired with the core tool set.

    Uses build_default_router() (5 focused tools) rather than the full MCP
    registry (12 tools). Sending 12 verbose tool schemas to Groq's free tier
    (12 000 TPM) burns ~6 000 tokens before the agent even starts thinking.
    The MCP registry is used for discovery (GET /v1/mcp/tools) only.
    """
    from backend.core.tool_router import build_default_router
    return Orchestrator(llm=OpenRouterProvider(), router=build_default_router())
