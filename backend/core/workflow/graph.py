"""
The multi-agent graph (Phase 3).

Wires the specialized agents into a LangGraph state machine:

    planner → research → execution → critic ─┐
       ▲                                      │  should_retry?
       └──────────── retry ───────────────────┤
                                              │ report
                                              ▼
                                          reporting → END

The Critic gates the loop: if the work isn't good enough (low confidence) and the
retry budget remains, control flows back to the Planner with the Critic's feedback
so the plan is revised. Otherwise we report the best result we have.
"""
from langgraph.graph import END, StateGraph

from backend.agents.critic import CriticAgent
from backend.agents.execution import ExecutionAgent
from backend.agents.planner import PlannerAgent
from backend.agents.reporting import ReportingAgent
from backend.agents.research import ResearchAgent
from backend.core.reflection import should_retry
from backend.core.tool_router import ToolRouter
from backend.core.workflow.state import RunState
from backend.llm.base import LLMProvider


def _plan_to_text(plan) -> str:
    return "\n".join(
        f"{i}. [{s.kind}] {s.description}" for i, s in enumerate(plan.steps, start=1)
    )


def build_graph(llm: LLMProvider, router: ToolRouter):
    """Build and compile the multi-agent graph for one LLM + tool set."""
    planner = PlannerAgent(llm)
    research = ResearchAgent(llm)
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

    async def execution_node(state: RunState) -> RunState:
        result = await execution.run(
            state["goal"],
            plan_text=state.get("plan_text", ""),
            research_notes=state.get("research_notes", ""),
        )
        # accumulate tool calls across retries for the full audit trail
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

    graph = StateGraph(RunState)
    graph.add_node("planner", planner_node)
    graph.add_node("research", research_node)
    graph.add_node("execution", execution_node)
    graph.add_node("critic", critic_node)
    graph.add_node("reporting", reporting_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "research")
    graph.add_edge("research", "execution")
    graph.add_edge("execution", "critic")
    graph.add_conditional_edges(
        "critic",
        should_retry,
        {"retry": "planner", "report": "reporting"},
    )
    graph.add_edge("reporting", END)

    return graph.compile()
