"""
Run orchestrator (Phase 3).

Owns one multi-agent run end to end:
  1. create a `Run` row (status = running),
  2. drive the LangGraph graph over the goal,
  3. persist the outcome (plan, report, confidence, attempts) + every tool call,
  4. return a typed result.

The graph holds the reasoning; the orchestrator holds the *run* — state, the audit
trail, and error handling — so the two concerns stay separate (ARCHITECTURE.md §5).
"""
import json
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.tool_router import ToolRouter
from backend.core.workflow.graph import build_graph
from backend.core.workflow.state import RunState
from backend.db.models import Run, ToolCallRecord
from backend.llm.base import LLMProvider


class RunResult(BaseModel):
    run_id: str
    status: str
    goal: str
    report: str
    confidence: float
    attempts: int
    plan: list[dict]
    sources: list[str]
    tool_calls: int


class Orchestrator:
    def __init__(self, llm: LLMProvider, router: ToolRouter):
        self.llm = llm
        self.router = router
        self.graph = build_graph(llm, router)

    async def run(
        self,
        session: AsyncSession,
        *,
        goal: str,
        org_id: str = "default",
        top_k: int | None = None,
    ) -> RunResult:
        run = Run(org_id=org_id, goal=goal, status="running")
        session.add(run)
        await session.flush()  # assigns run.id

        try:
            final: RunState = await self.graph.ainvoke(
                {
                    "goal": goal,
                    "org_id": org_id,
                    "top_k": top_k,
                    "attempts": 0,
                    "tool_calls": [],
                }
            )
        except Exception as exc:  # noqa: BLE001 — record failure, don't crash the API
            run.status = "failed"
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()
            raise

        plan = final.get("plan")
        plan_steps = [s.model_dump() for s in plan.steps] if plan else []
        tool_calls = final.get("tool_calls", [])

        # Persist the outcome on the run.
        run.status = "completed"
        run.plan = json.dumps(plan_steps)
        run.report = final.get("report", "")
        run.confidence = final.get("confidence", 0.0)
        run.attempts = final.get("attempts", 0)
        run.completed_at = datetime.now(timezone.utc)

        # Persist the tool-call audit trail.
        for call in tool_calls:
            session.add(
                ToolCallRecord(
                    run_id=run.id,
                    org_id=org_id,
                    tool_name=call.tool_name,
                    arguments=json.dumps(call.arguments),
                    result=json.dumps(call.result),
                    ok=call.ok,
                )
            )

        await session.commit()

        return RunResult(
            run_id=run.id,
            status=run.status,
            goal=goal,
            report=run.report or "",
            confidence=run.confidence or 0.0,
            attempts=run.attempts,
            plan=plan_steps,
            sources=final.get("sources", []),
            tool_calls=len(tool_calls),
        )
