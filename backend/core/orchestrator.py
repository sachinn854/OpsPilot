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
import asyncio
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
        self._lock = asyncio.Lock()  # guard MemorySaver from concurrent writes

    # ----- public API -------------------------------------------------------
    async def stream_run(
        self,
        session: AsyncSession,
        *,
        goal: str,
        org_id: str = "default",
        top_k: int | None = None,
    ):
        """Async generator that yields SSE-formatted strings as each graph node finishes."""
        from backend.core.context import current_org_id
        current_org_id.set(org_id)
        run = Run(org_id=org_id, goal=goal, status="running")
        session.add(run)
        await session.flush()
        await session.commit()

        yield _sse({"event": "run_created", "run_id": run.id})

        _start = time.monotonic()
        config = {"configurable": {"thread_id": run.id}}
        initial: dict = {"goal": goal, "org_id": org_id, "top_k": top_k, "attempts": 0, "tool_calls": []}

        try:
            async for chunk in self.graph.astream(initial, config):
                node_name = next(iter(chunk))
                updates = chunk[node_name]
                yield _sse({"event": "node_done", "node": node_name, "detail": _node_detail(node_name, updates)})
        except Exception as exc:
            RUN_DURATION.observe(time.monotonic() - _start)
            run.status = "failed"
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            RUNS_TOTAL.labels(status="failed").inc()
            await session.commit()
            yield _sse({"event": "run_failed", "error": str(exc)})
            return

        RUN_DURATION.observe(time.monotonic() - _start)

        payload = await self._interrupt_payload(config)
        if payload is not None:
            result = await self._pause(session, run, payload)
            yield _sse({"event": "run_paused", "run_id": run.id,
                        "approval_id": result.approval_id, "action": result.pending_action})
            return

        snapshot = await self.graph.aget_state(config)
        result = await self._finalize(session, run, snapshot.values)
        yield _sse({"event": "run_complete", **result.model_dump()})

    async def run(
        self,
        session: AsyncSession,
        *,
        goal: str,
        org_id: str = "default",
        top_k: int | None = None,
    ) -> RunResult:
        from backend.core.context import current_org_id
        current_org_id.set(org_id)
        run = Run(org_id=org_id, goal=goal, status="running")
        session.add(run)
        await session.flush()  # assigns run.id

        _start = time.monotonic()
        config = {"configurable": {"thread_id": run.id}}
        try:
            async with self._lock:
                final: RunState = await asyncio.wait_for(
                    self.graph.ainvoke(
                        {
                            "goal": goal,
                            "org_id": org_id,
                            "top_k": top_k,
                            "attempts": 0,
                            "tool_calls": [],
                        },
                        config,
                    ),
                    timeout=300,  # 5 min hard cap — prevents hung LangGraph nodes
                )
        except asyncio.TimeoutError:
            RUN_DURATION.observe(time.monotonic() - _start)
            return await self._fail(session, run, TimeoutError("Run timed out after 5 minutes."))
        except Exception as exc:  # noqa: BLE001
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
            async with self._lock:
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
        # Dedup sources preserving order across retry loops.
        sources = list(dict.fromkeys(final.get("sources", [])))
        return RunResult(
            run_id=run.id,
            status=run.status,
            goal=run.goal,
            report=run.report or "",
            confidence=run.confidence or 0.0,
            attempts=run.attempts,
            plan=plan_steps,
            sources=sources,
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
        return RunResult(
            run_id=run.id,
            status="failed",
            goal=run.goal,
            report=str(exc),
            confidence=0.0,
            attempts=0,
            plan=[],
            sources=[],
            tool_calls=0,
        )


# ----- module-level helpers (not part of the class) ------------------------

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _node_detail(node: str, updates: dict) -> str:
    """Extract a short human-readable summary from a node's state updates."""
    if node == "planner":
        plan = updates.get("plan")
        if plan and hasattr(plan, "steps"):
            return f"Created {len(plan.steps)} step(s)"
        return "Plan ready"
    if node == "research":
        notes = updates.get("research_notes", "")
        sources = updates.get("sources", [])
        return f"Found {len(sources)} source(s)" if sources else f"{len(notes)} chars of notes"
    if node == "execution":
        calls = updates.get("tool_calls", [])
        return f"Called {len(calls)} tool(s)"
    if node == "critic":
        verdict = updates.get("verdict")
        conf = updates.get("confidence")
        if conf is not None:
            return f"Confidence {conf:.2f}"
        if verdict and hasattr(verdict, "confidence"):
            return f"Confidence {verdict.confidence:.2f}"
        return "Verdict ready"
    if node == "reporting":
        report = updates.get("report", "")
        return f"Report ready ({len(report)} chars)"
    if node == "security":
        sensitive = updates.get("sensitive", False)
        return "Sensitive — needs approval" if sensitive else "Safe to proceed"
    if node == "hitl":
        return "Waiting for human approval"
    return "Done"
