"""
Runs endpoints: drive a goal through the multi-agent system.

  POST /v1/runs        → give a goal → Planner→Research→Execution→Critic→Reporting
  GET  /v1/runs        → list past runs
  GET  /v1/runs/{id}   → fetch one run (plan, report, confidence, tool calls)
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_orchestrator, limiter
from backend.auth.deps import get_current_user
from backend.config import settings
from backend.core.orchestrator import RunResult
from backend.db.models import Run, User
from backend.db.session import get_session
from backend.security.guardrails import check_injection
from backend.security.rbac import Role, require_role

router = APIRouter(prefix="/v1/runs", tags=["runs"])

_orchestrator = get_orchestrator()


_MAX_GOAL_LEN = 2000


class RunRequest(BaseModel):
    goal: str
    top_k: int | None = None


class RunInfo(BaseModel):
    id: str
    goal: str
    status: str
    confidence: float | None
    attempts: int
    created_at: datetime | None


@router.post("", response_model=RunResult)
@limiter.limit(settings.RATE_LIMIT_RUNS)
async def create_run(
    request: Request,
    req: RunRequest,
    session: AsyncSession = Depends(get_session),
    _role: Role = require_role(Role.operator),
    user: User = Depends(get_current_user),
) -> RunResult:
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="goal cannot be empty")
    if len(req.goal) > _MAX_GOAL_LEN:
        raise HTTPException(status_code=400, detail=f"goal too long (max {_MAX_GOAL_LEN} chars)")
    guard = check_injection(req.goal)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)
    try:
        return await _orchestrator.run(
            session, goal=req.goal, org_id=str(user.id), top_k=req.top_k
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Run failed: {exc}")


@router.post("/stream")
@limiter.limit(settings.RATE_LIMIT_RUNS)
async def create_run_stream(
    request: Request,
    req: RunRequest,
    session: AsyncSession = Depends(get_session),
    _role: Role = require_role(Role.operator),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Same as POST /v1/runs but streams SSE progress events as each agent node finishes."""
    if not req.goal.strip():
        raise HTTPException(status_code=400, detail="goal cannot be empty")
    guard = check_injection(req.goal)
    if not guard.safe:
        raise HTTPException(status_code=400, detail=guard.reason)

    org_id = str(user.id)

    async def event_stream():
        try:
            async for chunk in _orchestrator.stream_run(
                session, goal=req.goal, org_id=org_id, top_k=req.top_k
            ):
                yield chunk
        except RuntimeError as exc:
            import json
            yield f"data: {json.dumps({'event': 'run_failed', 'error': str(exc)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("", response_model=list[RunInfo])
async def list_runs(
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> list[RunInfo]:
    limit = max(1, min(limit, 200))
    result = await session.execute(
        select(Run).where(Run.org_id == str(user.id)).order_by(Run.created_at.desc()).limit(limit)
    )
    return [
        RunInfo(
            id=r.id,
            goal=r.goal,
            status=r.status,
            confidence=r.confidence,
            attempts=r.attempts,
            created_at=r.created_at,
        )
        for r in result.scalars().all()
    ]


@router.get("/{run_id}")
async def get_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
) -> dict:
    run = await session.get(Run, run_id)
    if run is None or run.org_id != str(user.id):
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
