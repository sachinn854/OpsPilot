"""
Approvals endpoints (human-in-the-loop).

  GET  /v1/approvals             → list pending approvals
  POST /v1/approvals/{id}        → approve or reject → resumes (or aborts) the run
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_orchestrator, limiter
from backend.config import settings
from backend.core import hitl
from backend.core.orchestrator import RunResult
from backend.db.models import Approval
from backend.db.session import get_session
from backend.security.rbac import Role, require_role

router = APIRouter(prefix="/v1/approvals", tags=["approvals"])

_ORG = "default"
_orchestrator = get_orchestrator()


class ApprovalInfo(BaseModel):
    id: str
    run_id: str
    action: str
    reason: str | None
    status: str


class DecisionRequest(BaseModel):
    approved: bool
    # decided_by is no longer accepted from the caller — derived server-side.


@router.get("", response_model=list[ApprovalInfo])
@limiter.limit(settings.RATE_LIMIT_APPROVALS)
async def list_approvals(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[ApprovalInfo]:
    pending = await hitl.list_pending(session, org_id=_ORG)
    return [
        ApprovalInfo(
            id=a.id,
            run_id=a.run_id,
            action=a.action,
            reason=a.reason,
            status=a.status,
        )
        for a in pending
    ]


@router.post("/{approval_id}", response_model=RunResult)
@limiter.limit(settings.RATE_LIMIT_APPROVALS)
async def decide(
    request: Request,
    approval_id: str,
    req: DecisionRequest,
    session: AsyncSession = Depends(get_session),
    _role: Role = require_role(Role.operator),
) -> RunResult:
    # SELECT FOR UPDATE — prevents two concurrent requests from both passing the
    # status check and calling resume_run() twice on the same paused run.
    result = await session.execute(
        select(Approval)
        .where(Approval.id == approval_id, Approval.org_id == _ORG)
        .with_for_update()
    )
    approval = result.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")
    if approval.status != "pending":
        raise HTTPException(status_code=409, detail=f"approval already {approval.status}")

    run = await hitl.get_run(session, approval.run_id, org_id=_ORG)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    # Server-derived identity — not caller-supplied.
    decided_by = "api-operator"

    await hitl.record_decision(
        session, approval, approved=req.approved, decided_by=decided_by
    )
    try:
        return await _orchestrator.resume_run(session, run=run, approved=req.approved)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=f"Resume failed: {exc}")
