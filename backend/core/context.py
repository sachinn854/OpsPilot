"""
Request-scoped context variables.

Set `current_org_id` before running any tool so every integration tool
resolves the correct per-user token without needing it threaded through
every call signature.
"""
from contextvars import ContextVar

current_org_id: ContextVar[str] = ContextVar("current_org_id", default="default")
