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
from backend.observability.metrics import ACTIVE_APPROVALS


async def create_pending_approval(
    session: AsyncSession,
    *,
    run_id: str,
    org_id: str,
    action: str,
    reason: str,
    payload: dict,
) -> Approval:
    """Record a pending approval for a paused run and notify via Slack if configured."""
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

    # Fire-and-forget Slack notification with interactive buttons
    try:
        import asyncio
        asyncio.create_task(_notify_slack_hitl(approval, org_id))
    except RuntimeError:
        pass  # no running event loop in sync contexts

    return approval


async def _notify_slack_hitl(approval: Approval, org_id: str) -> None:
    """Post an interactive Slack message with Approve/Reject buttons."""
    import httpx
    from backend.config import settings

    token: str | None = None
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as s:
            token = await get_token(s, org_id=org_id, service="slack")
    except Exception:
        pass
    token = token or settings.SLACK_TOKEN
    if not token:
        return

    # Find a suitable notification channel (#approvals → #ops → #general)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    channel_id: str | None = None
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get("https://slack.com/api/conversations.list",
                             headers=headers,
                             params={"limit": 200, "types": "public_channel,private_channel"})
    for ch in r.json().get("channels", []):
        if ch.get("name") in ("approvals", "ops", "general") and ch.get("is_member"):
            channel_id = ch["id"]
            if ch["name"] == "approvals":
                break

    if not channel_id:
        return

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"⚠️ *Human Approval Required*\n"
                    f"*Action:* `{approval.action}`\n"
                    f"*Reason:* {approval.reason}\n"
                    f"*Run ID:* `{approval.run_id}`"
                ),
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "✅ Approve"},
                    "style": "primary",
                    "action_id": f"approve_{approval.id}",
                    "value": approval.id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "❌ Reject"},
                    "style": "danger",
                    "action_id": f"reject_{approval.id}",
                    "value": approval.id,
                },
            ],
        },
    ]

    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            "https://slack.com/api/chat.postMessage",
            headers=headers,
            json={"channel": channel_id, "blocks": blocks,
                  "text": f"Approval required: {approval.action}"},
        )


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
    was_pending = approval.status == "pending"
    approval.status = "approved" if approved else "rejected"
    approval.decided_by = decided_by
    approval.decided_at = datetime.now(timezone.utc)
    if was_pending:
        ACTIVE_APPROVALS.dec()
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
