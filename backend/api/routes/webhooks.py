"""
GitHub webhook receiver.

GitHub sends a POST to /v1/webhooks/github on every subscribed event.  We:
  1. Verify the HMAC-SHA256 signature (X-Hub-Signature-256 header).
  2. Persist the raw payload as a WebhookEvent row immediately.
  3. Queue a Celery task to process the event asynchronously.
  4. Return {"ok": true} right away — GitHub requires a fast 200 response.

Supported events: push, pull_request, issues, release.
Any other event type is stored but silently skipped during processing.

Setup (one-time):
  - Set GITHUB_WEBHOOK_SECRET in .env to any strong random string.
  - In the GitHub repo → Settings → Webhooks, create a webhook pointing to
    https://<your-domain>/v1/webhooks/github with the same secret.
  - Content-Type: application/json.
"""
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from backend.config import settings
from backend.db.session import AsyncSessionLocal
from backend.db.models import WebhookEvent

logger = logging.getLogger("copilot.webhooks")

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

SUPPORTED_EVENTS = {"push", "pull_request", "issues", "release", "ping"}


def _verify_signature(payload: bytes, signature: str | None) -> None:
    """Raise 401 if the signature header is missing or invalid."""
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not secret:
        # No secret configured — skip verification (dev/test only).
        return
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header.",
        )
    expected = "sha256=" + hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature mismatch.",
        )


@router.post("/github", status_code=status.HTTP_200_OK)
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
    x_github_delivery: str | None = Header(default=None),
) -> dict:
    """Receive a GitHub webhook event, verify it, and queue for processing."""
    raw_body = await request.body()

    _verify_signature(raw_body, x_hub_signature_256)

    event_type = (x_github_event or "unknown").lower()

    # Parse payload (best-effort — store raw even if malformed JSON).
    try:
        payload_dict = json.loads(raw_body)
    except json.JSONDecodeError:
        payload_dict = {}

    action = payload_dict.get("action")  # e.g. "opened", "closed", "merged"

    # Persist event before doing anything else.
    async with AsyncSessionLocal() as session:
        event = WebhookEvent(
            org_id="default",
            source="github",
            event_type=event_type,
            action=action,
            delivery_id=x_github_delivery,
            payload=raw_body.decode("utf-8", errors="replace"),
        )
        session.add(event)
        await session.commit()
        await session.refresh(event)
        event_id = event.id

    logger.info(
        "Webhook received event=%s action=%s delivery=%s id=%s",
        event_type, action, x_github_delivery, event_id,
    )

    # ping is just a health-check from GitHub — no processing needed.
    if event_type == "ping":
        return {"ok": True, "event": "ping", "zen": payload_dict.get("zen", "")}

    if event_type in SUPPORTED_EVENTS:
        from backend.workers.webhook_handler import process_webhook_event
        process_webhook_event.delay(event_id)
    else:
        logger.debug("Unsupported webhook event type '%s' — stored but not processed.", event_type)

    return {"ok": True, "event_id": event_id, "event": event_type}
