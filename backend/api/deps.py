"""
Shared API dependencies.

The Orchestrator is a process-wide singleton because its compiled LangGraph holds
the in-memory checkpointer that keeps a paused (awaiting-approval) run alive
between the `POST /v1/runs` request that paused it and the `POST /v1/approvals/...`
request that resumes it. Both routers must use the *same* instance, so it lives
here rather than inside one route module.

The rate limiter is also defined here so all route modules share the same
Limiter instance (slowapi requires a single Limiter registered on app.state).
"""
from functools import lru_cache

from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core.orchestrator import Orchestrator
from backend.core.tool_router import build_default_router
from backend.llm.groq_provider import GroqProvider

# One limiter instance shared across all routes.
limiter = Limiter(key_func=get_remote_address)


@lru_cache
def get_orchestrator() -> Orchestrator:
    return Orchestrator(llm=GroqProvider(), router=build_default_router())
