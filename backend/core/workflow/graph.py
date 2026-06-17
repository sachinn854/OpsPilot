"""
The multi-agent graph (Phase 3 + Phase 4 HITL).

    planner → research → security ──safe──► execution → critic ─┐
                            │                   ▲                │ should_retry?
                       sensitive                └──── retry ─────┤
                            ▼                                    │ report
                          hitl  ──approved──► execution          ▼
                            │                              reporting → END
                       rejected ──────────────────────────► reporting

The Security node classifies the goal/plan. A sensitive action routes to the HITL
node, which calls LangGraph `interrupt()` — pausing the run until a human approves
or rejects. Approve resumes into Execution; reject skips straight to Reporting.

Compiled with a checkpointer so the paused state survives until the decision
arrives (MemorySaver: in-process; swap for a Postgres saver to survive restarts).
"""
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from backend.agents.critic import CriticAgent
from backend.agents.execution import ExecutionAgent
from backend.agents.planner import PlannerAgent
from backend.agents.reporting import ReportingAgent
from backend.agents.research import ResearchAgent
from backend.agents.security_agent import SecurityAgent
from backend.core.reflection import should_retry
from backend.core.tool_router import ToolRouter, sensitive_tool_names
from backend.core.workflow.state import RunState
from backend.llm.base import LLMProvider


def _plan_to_text(plan) -> str:
    return "\n".join(
        f"{i}. [{s.kind}] {s.description}" for i, s in enumerate(plan.steps, start=1)
    )


def build_graph(llm: LLMProvider, router: ToolRouter):
    """Build and compile the multi-agent graph (with HITL) for one LLM + tool set."""
    planner = PlannerAgent(llm)
    research = ResearchAgent(llm)
    security = SecurityAgent(llm, sensitive_tools=sensitive_tool_names(router))
    execution = ExecutionAgent(llm, router)
    critic = CriticAgent(llm)
    reporting = ReportingAgent(llm)

    async def planner_node(state: RunState) -> RunState:
        plan = await planner.run(state["goal"], feedback=state.get("feedback"))
        return {"plan": plan, "plan_text": _plan_to_text(plan)}

    async def research_node(state: RunState) -> RunState:
        notes = await research.run(
            state["goal"],
            org_id=state.get("org_id", "default"),
            top_k=state.get("top_k"),
        )
        return {"research_notes": notes.notes, "sources": notes.sources}

    async def security_node(state: RunState) -> RunState:
        verdict = await security.run(
            state["goal"], plan_text=state.get("plan_text", "")
        )
        return {
            "sensitive": verdict.sensitive,
            "security_action": verdict.action,
            "security_reason": verdict.reason,
        }

    async def hitl_node(state: RunState) -> RunState:
        # Pause here until a human decision arrives via Command(resume=...).
        decision = interrupt(
            {
                "action": state.get("security_action", ""),
                "reason": state.get("security_reason", ""),
                "goal": state["goal"],
            }
        )
        approved = (
            bool(decision.get("approved"))
            if isinstance(decision, dict)
            else bool(decision)
        )
        if approved:
            return {"approved": True}
        return {
            "approved": False,
            "execution_output": (
                "Action rejected by the approver — the run was aborted before any "
                "change was made."
            ),
            "confidence": 0.0,
        }

    async def execution_node(state: RunState) -> RunState:
        result = await execution.run(
            state["goal"],
            plan_text=state.get("plan_text", ""),
            research_notes=state.get("research_notes", ""),
        )
        prior = state.get("tool_calls", [])
        return {
            "execution_output": result.output,
            "tool_calls": prior + result.tool_calls,
        }

    async def critic_node(state: RunState) -> RunState:
        verdict = await critic.run(
            state["goal"],
            research_notes=state.get("research_notes", ""),
            execution_output=state.get("execution_output", ""),
        )
        return {
            "verdict": verdict,
            "confidence": verdict.confidence,
            "feedback": verdict.feedback,
            "attempts": state.get("attempts", 0) + 1,
        }

    async def reporting_node(state: RunState) -> RunState:
        report = await reporting.run(
            state["goal"],
            research_notes=state.get("research_notes", ""),
            execution_output=state.get("execution_output", ""),
            confidence=state.get("confidence", 0.0),
            sources=state.get("sources", []),
        )
        return {"report": report}

    def route_after_security(state: RunState) -> str:
        return "hitl" if state.get("sensitive") else "execution"

    def route_after_hitl(state: RunState) -> str:
        return "execution" if state.get("approved") else "reporting"

    graph = StateGraph(RunState)
    graph.add_node("planner", planner_node)
    graph.add_node("research", research_node)
    graph.add_node("security", security_node)
    graph.add_node("hitl", hitl_node)
    graph.add_node("execution", execution_node)
    graph.add_node("critic", critic_node)
    graph.add_node("reporting", reporting_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "security")
    graph.add_conditional_edges(
        "security", route_after_security, {"hitl": "hitl", "execution": "execution"}
    )
    graph.add_conditional_edges(
        "hitl", route_after_hitl, {"execution": "execution", "reporting": "reporting"}
    )
    graph.add_edge("execution", "critic")
    graph.add_conditional_edges(
        "critic", should_retry, {"retry": "planner", "report": "reporting"}
    )
    graph.add_edge("reporting", END)

    return graph.compile(checkpointer=MemorySaver())
