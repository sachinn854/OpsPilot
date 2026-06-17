"""
Approvals endpoints (human-in-the-loop).

  GET  /v1/approvals             → list pending approvals (runs paused on a
                                   sensitive action, awaiting a human)
  POST /v1/approvals/{id}        → approve or reject → resumes (or aborts) the run

Approving resumes the paused LangGraph run from the exact node; rejecting lets it
finish with an "aborted" report. Org scoping stays "default" until auth lands.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_orchestrator
from backend.core import hitl
from backend.core.orchestrator import RunResult
from backend.db.session import get_session

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
    decided_by: str = "operator"


@router.get("", response_model=list[ApprovalInfo])
async def list_approvals(
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
async def decide(
    approval_id: str,
    req: DecisionRequest,
    session: AsyncSession = Depends(get_session),
) -> RunResult:
    approval = await hitl.get_approval(session, approval_id, org_id=_ORG)
    if approval is None:
        raise HTTPException(status_code=404, detail="approval not found")
    if approval.status != "pending":
        raise HTTPException(
            status_code=409, detail=f"approval already {approval.status}"
        )

    run = await hitl.get_run(session, approval.run_id, org_id=_ORG)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")

    # Stamp the decision, then resume (or abort) the paused run.
    await hitl.record_decision(
        session, approval, approved=req.approved, decided_by=req.decided_by
    )
    try:
        return await _orchestrator.resume_run(
            session, run=run, approved=req.approved
        )
    except RuntimeError as exc:  # e.g. missing GROQ_API_KEY
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:  # structured-output failure
        raise HTTPException(status_code=502, detail=f"Resume failed: {exc}")
