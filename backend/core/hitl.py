"""
HITL Manager.

The bridge between a paused run and a human decision. The graph pauses on a
sensitive action (LangGraph interrupt); this module records the pending
`Approval`, lists what's awaiting a decision, and applies the human's
approve/reject — leaving the actual run-resume to the Orchestrator.

Keeping approval persistence here (not in the graph) means the audit trail lives
in Postgres regardless of the in-memory graph checkpoint.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Approval, Run


async def create_pending_approval(
    session: AsyncSession,
    *,
    run_id: str,
    org_id: str,
    action: str,
    reason: str,
    payload: dict,
) -> Approval:
    """Record a pending approval for a paused run."""
    approval = Approval(
        run_id=run_id,
        org_id=org_id,
        action=action,
        reason=reason,
        payload=json.dumps(payload),
        status="pending",
    )
    session.add(approval)
    await session.flush()  # assigns approval.id
    return approval


async def list_pending(session: AsyncSession, *, org_id: str) -> list[Approval]:
    result = await session.execute(
        select(Approval)
        .where(Approval.org_id == org_id, Approval.status == "pending")
        .order_by(Approval.created_at)
    )
    return list(result.scalars().all())


async def record_decision(
    session: AsyncSession,
    approval: Approval,
    *,
    approved: bool,
    decided_by: str,
) -> None:
    """Stamp the human's decision onto the approval (does not resume the run)."""
    approval.status = "approved" if approved else "rejected"
    approval.decided_by = decided_by
    approval.decided_at = datetime.now(timezone.utc)
    await session.flush()


async def get_approval(
    session: AsyncSession, approval_id: str, *, org_id: str
) -> Approval | None:
    approval = await session.get(Approval, approval_id)
    if approval is None or approval.org_id != org_id:
        return None
    return approval


async def get_run(session: AsyncSession, run_id: str, *, org_id: str) -> Run | None:
    run = await session.get(Run, run_id)
    if run is None or run.org_id != org_id:
        return None
    return run
