"""
Runs endpoints (Phase 3): drive a goal through the multi-agent system.

  POST /v1/runs        → give a goal → Planner→Research→Execution→Critic→Reporting
  GET  /v1/runs        → list past runs
  GET  /v1/runs/{id}   → fetch one run (plan, report, confidence, tool calls)

This is the §2.3 "north-star" flow: plan, gather, act, self-verify, report.
Org scoping stays "default" until auth lands.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.orchestrator import Orchestrator, RunResult
from backend.core.tool_router import build_default_router
from backend.db.models import Run
from backend.db.session import get_session
from backend.llm.groq_provider import GroqProvider

router = APIRouter(prefix="/v1/runs", tags=["runs"])

_ORG = "default"
# Build the orchestrator once (cheap singletons; graph compiled at import time).
_orchestrator = Orchestrator(llm=GroqProvider(), router=build_default_router())


class RunRequest(BaseModel):
    goal: str
    top_k: int | None = None


class RunInfo(BaseModel):
    id: str
    goal: str
    status: str
    confidence: float | None
    attempts: int


@router.post("", response_model=RunResult)
async def create_run(
    req: RunRequest, session: AsyncSession = Depends(get_session)
) -> RunResult:
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="goal cannot be empty")
    try:
        return await _orchestrator.run(
            session, goal=req.goal, org_id=_ORG, top_k=req.top_k
        )
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:  # structured-output failure
        raise HTTPException(status_code=502, detail=f"Run failed: {exc}")


@router.get("", response_model=list[RunInfo])
async def list_runs(
    session: AsyncSession = Depends(get_session),
) -> list[RunInfo]:
    result = await session.execute(
        select(Run).where(Run.org_id == _ORG).order_by(Run.created_at.desc())
    )
    return [
        RunInfo(
            id=r.id,
            goal=r.goal,
            status=r.status,
            confidence=r.confidence,
            attempts=r.attempts,
        )
        for r in result.scalars().all()
    ]


@router.get("/{run_id}")
async def get_run(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> dict:
    run = await session.get(Run, run_id)
    if run is None or run.org_id != _ORG:
        raise HTTPException(status_code=404, detail="run not found")
    return {
        "id": run.id,
        "goal": run.goal,
        "status": run.status,
        "report": run.report,
        "confidence": run.confidence,
        "attempts": run.attempts,
        "plan": run.plan,
        "error": run.error,
    }
