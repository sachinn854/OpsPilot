"""
Shared API dependencies (Phase 4).

The Orchestrator is a process-wide singleton because its compiled LangGraph holds
the in-memory checkpointer that keeps a paused (awaiting-approval) run alive
between the `POST /v1/runs` request that paused it and the `POST /v1/approvals/...`
request that resumes it. Both routers must use the *same* instance, so it lives
here rather than inside one route module.
"""
from functools import lru_cache

from backend.core.orchestrator import Orchestrator
from backend.core.tool_router import build_default_router
from backend.llm.groq_provider import GroqProvider


@lru_cache
def get_orchestrator() -> Orchestrator:
    return Orchestrator(llm=GroqProvider(), router=build_default_router())
