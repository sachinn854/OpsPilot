"""
Slack Interactivity webhook — handles button clicks from Slack messages.

When a run needs HITL approval, we post an interactive Slack message with
Approve and Reject buttons. When the user clicks, Slack sends a POST here.

Setup in Slack app:
    Interactivity & Shortcuts → Request URL:
        https://<your-domain>/v1/slack/interactive
"""
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.config import settings

router = APIRouter(prefix="/v1/slack", tags=["slack"])


def _verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify the request came from Slack using the signing secret."""
    if not settings.SLACK_SIGNING_SECRET:
        return True  # skip verification if secret not configured (dev mode)
    if abs(time.time() - float(timestamp)) > 300:
        return False  # reject replays older than 5 minutes
    base = f"v0:{timestamp}:{request_body.decode()}"
    expected = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode(),
        base.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/interactive")
async def slack_interactive(request: Request, payload: str = Form(...)):
    """Handle Slack interactive component payloads (button clicks)."""
    body      = await request.body()
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "0")
    signature = request.headers.get("X-Slack-Signature", "")

    if not _verify_slack_signature(body, timestamp, signature):
        raise HTTPException(status_code=401, detail="Invalid Slack signature")

    data = json.loads(payload)

    if data.get("type") != "block_actions":
        return JSONResponse({"ok": True})

    actions = data.get("actions", [])
    if not actions:
        return JSONResponse({"ok": True})

    action   = actions[0]
    action_id = action.get("action_id", "")
    value     = action.get("value", "")

    # action_id format: "approve_<approval_id>" or "reject_<approval_id>"
    if action_id.startswith("approve_") or action_id.startswith("reject_"):
        decision  = "approved" if action_id.startswith("approve_") else "rejected"
        approval_id = value

        slack_user = data.get("user", {}).get("name", "unknown")

        try:
            from backend.api.deps import get_orchestrator
            from backend.db.session import AsyncSessionLocal
            orchestrator = get_orchestrator()
            async with AsyncSessionLocal() as session:
                await orchestrator.resume_run(
                    approval_id=approval_id,
                    decision=decision,
                    decided_by=f"slack:{slack_user}",
                    session=session,
                )

            # Update the Slack message to reflect the decision
            response_url = data.get("response_url")
            if response_url:
                import httpx
                emoji  = "✅" if decision == "approved" else "❌"
                status = "Approved" if decision == "approved" else "Rejected"
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(response_url, json={
                        "replace_original": True,
                        "text": f"{emoji} *{status}* by @{slack_user}",
                    })
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)})

    return JSONResponse({"ok": True})
