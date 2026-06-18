"""
Run orchestrator.

Owns one multi-agent run end to end:
  1. create a `Run` row (status = running),
  2. drive the LangGraph graph over the goal,
  3a. if a sensitive action pauses the graph (HITL) → record a pending `Approval`,
      mark the run `awaiting_approval`, and stop here,
  3b. otherwise persist the outcome (plan, report, confidence, attempts) + tool calls,
  4. on a human decision, `resume_run()` continues from the exact paused node.

The graph holds the reasoning; the orchestrator holds the *run* — state, the audit
trail, pause/resume, and error handling.
"""
import json
import time
from datetime import datetime, timezone

from langgraph.types import Command
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.hitl import create_pending_approval
from backend.core.tool_router import ToolRouter
from backend.core.workflow.graph import build_graph
from backend.core.workflow.state import RunState
from backend.db.models import Approval, Run, ToolCallRecord
from backend.llm.base import LLMProvider
from backend.observability.metrics import (
    ACTIVE_APPROVALS,
    RUNS_TOTAL,
    RUN_DURATION,
    TOOL_CALLS_TOTAL,
)


class RunResult(BaseModel):
    run_id: str
    status: str  # completed | awaiting_approval | failed
    goal: str
    report: str
    confidence: float
    attempts: int
    plan: list[dict]
    sources: list[str]
    tool_calls: int
    # set only when status == awaiting_approval
    approval_id: str | None = None
    pending_action: str | None = None


class Orchestrator:
    def __init__(self, llm: LLMProvider, router: ToolRouter):
        self.llm = llm
        self.router = router
        self.graph = build_graph(llm, router)

    # ----- public API -------------------------------------------------------
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

        _start = time.monotonic()
        config = {"configurable": {"thread_id": run.id}}
        try:
            final: RunState = await self.graph.ainvoke(
                {
                    "goal": goal,
                    "org_id": org_id,
                    "top_k": top_k,
                    "attempts": 0,
                    "tool_calls": [],
                },
                config,
            )
        except Exception as exc:  # noqa: BLE001 — record failure, don't crash the API
            RUN_DURATION.observe(time.monotonic() - _start)
            return await self._fail(session, run, exc)

        RUN_DURATION.observe(time.monotonic() - _start)
        payload = await self._interrupt_payload(config)
        if payload is not None:
            return await self._pause(session, run, payload)

        return await self._finalize(session, run, final)

    async def resume_run(
        self,
        session: AsyncSession,
        *,
        run: Run,
        approved: bool,
    ) -> RunResult:
        """Continue a paused run from the HITL node with the human's decision."""
        config = {"configurable": {"thread_id": run.id}}
        run.status = "running"
        try:
            final: RunState = await self.graph.ainvoke(
                Command(resume={"approved": approved}), config
            )
        except Exception as exc:  # noqa: BLE001
            return await self._fail(session, run, exc)

        payload = await self._interrupt_payload(config)
        if payload is not None:  # paused again on another sensitive action
            return await self._pause(session, run, payload)

        return await self._finalize(session, run, final)

    # ----- internals --------------------------------------------------------
    async def _interrupt_payload(self, config: dict) -> dict | None:
        """Return the pending interrupt's payload if the graph is paused, else None."""
        snapshot = await self.graph.aget_state(config)
        if not snapshot.next:
            return None
        for task in snapshot.tasks:
            for intr in getattr(task, "interrupts", ()):
                return intr.value
        return {}  # paused but no payload surfaced

    async def _pause(
        self, session: AsyncSession, run: Run, payload: dict
    ) -> RunResult:
        action = payload.get("action") or "sensitive action"
        reason = payload.get("reason") or ""
        approval = await create_pending_approval(
            session,
            run_id=run.id,
            org_id=run.org_id,
            action=action,
            reason=reason,
            payload=payload,
        )
        run.status = "awaiting_approval"
        RUNS_TOTAL.labels(status="awaiting_approval").inc()
        ACTIVE_APPROVALS.inc()
        await session.commit()
        return RunResult(
            run_id=run.id,
            status="awaiting_approval",
            goal=run.goal,
            report="",
            confidence=0.0,
            attempts=0,
            plan=[],
            sources=[],
            tool_calls=0,
            approval_id=approval.id,
            pending_action=action,
        )

    async def _finalize(
        self, session: AsyncSession, run: Run, final: RunState
    ) -> RunResult:
        plan = final.get("plan")
        plan_steps = [s.model_dump() for s in plan.steps] if plan else []
        tool_calls = final.get("tool_calls", [])

        run.status = "completed"
        run.plan = json.dumps(plan_steps)
        run.report = final.get("report", "")
        run.confidence = final.get("confidence", 0.0)
        run.attempts = final.get("attempts", 0)
        run.completed_at = datetime.now(timezone.utc)

        RUNS_TOTAL.labels(status="completed").inc()
        for call in tool_calls:
            TOOL_CALLS_TOTAL.labels(tool_name=call.tool_name, ok=str(call.ok).lower()).inc()
            session.add(
                ToolCallRecord(
                    run_id=run.id,
                    org_id=run.org_id,
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
            goal=run.goal,
            report=run.report or "",
            confidence=run.confidence or 0.0,
            attempts=run.attempts,
            plan=plan_steps,
            sources=final.get("sources", []),
            tool_calls=len(tool_calls),
        )

    async def _fail(
        self, session: AsyncSession, run: Run, exc: Exception
    ) -> RunResult:
        run.status = "failed"
        run.error = str(exc)
        run.completed_at = datetime.now(timezone.utc)
        RUNS_TOTAL.labels(status="failed").inc()
        await session.commit()
        raise exc
