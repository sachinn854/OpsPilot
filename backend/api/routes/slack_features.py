"""
Slack advanced feature endpoints:
  /v1/slack/alerts   — keyword alert CRUD
  /v1/slack/triggers — event trigger CRUD
"""
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.deps import get_current_user
from backend.db.models import SlackEventTrigger, SlackKeywordAlert, User
from backend.db.session import get_session

router = APIRouter(prefix="/v1/slack", tags=["slack"])


# ── Keyword Alerts ────────────────────────────────────────────────────────────

class AlertIn(BaseModel):
    keyword: str
    channels: str = ""        # comma-separated, empty = all channels
    notify_via: str = "both"  # "email" | "dm" | "both"


@router.get("/alerts")
async def list_alerts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(SlackKeywordAlert)
        .where(SlackKeywordAlert.org_id == current_user.id)
        .order_by(SlackKeywordAlert.created_at.desc())
    )).scalars().all()
    return [_alert_out(r) for r in rows]


@router.post("/alerts", status_code=201)
async def create_alert(
    body: AlertIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    if not body.keyword.strip():
        raise HTTPException(status_code=400, detail="Keyword cannot be empty")
    if body.notify_via not in ("email", "dm", "both"):
        raise HTTPException(status_code=400, detail="notify_via must be email, dm, or both")
    alert = SlackKeywordAlert(
        org_id=current_user.id,
        keyword=body.keyword.strip().lower(),
        channels=body.channels.strip(),
        notify_via=body.notify_via,
    )
    session.add(alert)
    await session.commit()
    return _alert_out(alert)


@router.patch("/alerts/{alert_id}")
async def toggle_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    alert = await _get_alert(alert_id, current_user.id, session)
    alert.is_active = not alert.is_active
    await session.commit()
    return _alert_out(alert)


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    alert = await _get_alert(alert_id, current_user.id, session)
    await session.delete(alert)
    await session.commit()


async def _get_alert(alert_id: str, org_id: str, session: AsyncSession) -> SlackKeywordAlert:
    row = (await session.execute(
        select(SlackKeywordAlert)
        .where(SlackKeywordAlert.id == alert_id, SlackKeywordAlert.org_id == org_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Alert not found")
    return row


def _alert_out(a: SlackKeywordAlert) -> dict:
    return {
        "id": a.id,
        "keyword": a.keyword,
        "channels": a.channels,
        "notify_via": a.notify_via,
        "is_active": a.is_active,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# ── Event Triggers ────────────────────────────────────────────────────────────

class TriggerIn(BaseModel):
    name: str
    trigger_keyword: str
    source_channel: str = ""
    action_type: str          # "create_github_issue" | "post_to_channel" | "run_copilot"
    action_config: dict = {}


@router.get("/triggers")
async def list_triggers(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    rows = (await session.execute(
        select(SlackEventTrigger)
        .where(SlackEventTrigger.org_id == current_user.id)
        .order_by(SlackEventTrigger.created_at.desc())
    )).scalars().all()
    return [_trigger_out(r) for r in rows]


@router.post("/triggers", status_code=201)
async def create_trigger(
    body: TriggerIn,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    valid_actions = ("create_github_issue", "post_to_channel", "run_copilot")
    if body.action_type not in valid_actions:
        raise HTTPException(status_code=400, detail=f"action_type must be one of {valid_actions}")
    if not body.trigger_keyword.strip():
        raise HTTPException(status_code=400, detail="trigger_keyword cannot be empty")
    t = SlackEventTrigger(
        org_id=current_user.id,
        name=body.name.strip(),
        trigger_keyword=body.trigger_keyword.strip().lower(),
        source_channel=body.source_channel.strip().lstrip("#"),
        action_type=body.action_type,
        action_config=json.dumps(body.action_config),
    )
    session.add(t)
    await session.commit()
    return _trigger_out(t)


@router.patch("/triggers/{trigger_id}")
async def toggle_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    t = await _get_trigger(trigger_id, current_user.id, session)
    t.is_active = not t.is_active
    await session.commit()
    return _trigger_out(t)


@router.delete("/triggers/{trigger_id}", status_code=204)
async def delete_trigger(
    trigger_id: str,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    t = await _get_trigger(trigger_id, current_user.id, session)
    await session.delete(t)
    await session.commit()


async def _get_trigger(trigger_id: str, org_id: str, session: AsyncSession) -> SlackEventTrigger:
    row = (await session.execute(
        select(SlackEventTrigger)
        .where(SlackEventTrigger.id == trigger_id, SlackEventTrigger.org_id == org_id)
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Trigger not found")
    return row


def _trigger_out(t: SlackEventTrigger) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "trigger_keyword": t.trigger_keyword,
        "source_channel": t.source_channel,
        "action_type": t.action_type,
        "action_config": json.loads(t.action_config or "{}"),
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }
