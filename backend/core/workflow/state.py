"""
Shared run state.

This is the single object that flows through the LangGraph graph. Each node reads
what it needs and returns a partial update; LangGraph merges it in. Typed payloads
(Plan, Verdict, tool-call logs) live inside so every stage consumes structure.
"""
from typing import TypedDict

from backend.agents.critic import Verdict
from backend.agents.execution import ToolCallLog
from backend.agents.planner import Plan


class RunState(TypedDict, total=False):
    # inputs
    goal: str
    org_id: str
    top_k: int | None

    # planner
    plan: Plan | None
    plan_text: str

    # research
    research_notes: str
    sources: list[str]

    # security / HITL
    sensitive: bool
    security_action: str
    security_reason: str
    approved: bool

    # execution
    execution_output: str
    tool_calls: list[ToolCallLog]

    # critic
    verdict: Verdict | None
    confidence: float
    feedback: str

    # loop control + output
    attempts: int
    report: str
