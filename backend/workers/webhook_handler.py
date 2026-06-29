"""
Celery task: process incoming GitHub webhook events.

Each event type has a dedicated handler. Handlers are intentionally simple —
they log structured data and can optionally trigger a full agent run for
high-value events (PR opened, issue created).

Extend by adding more event-type keys to _HANDLERS.
"""
import asyncio
import json
import logging

from backend.workers.celery_app import celery_app

logger = logging.getLogger("copilot.webhook_handler")


# ---------------------------------------------------------------------------
# Public task
# ---------------------------------------------------------------------------

@celery_app.task(
    name="workers.process_webhook_event",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def process_webhook_event(self, event_id: str) -> dict:
    """Load a WebhookEvent row and dispatch to the right handler."""
    try:
        result = asyncio.run(_dispatch(event_id))
        logger.info("Webhook processed event_id=%s result=%s", event_id, result)
        return result
    except Exception as exc:
        logger.error("Webhook processing failed event_id=%s: %s", event_id, exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Async dispatcher
# ---------------------------------------------------------------------------

async def _dispatch(event_id: str) -> dict:
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import WebhookEvent
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        row = await session.get(WebhookEvent, event_id)
        if row is None:
            logger.warning("WebhookEvent %s not found.", event_id)
            return {"ok": False, "reason": "event not found"}

        try:
            payload = json.loads(row.payload)
        except json.JSONDecodeError:
            payload = {}

        handler = _HANDLERS.get(row.event_type, _handle_unknown)
        result = await handler(row.event_type, row.action or "", payload)

        row.processed = True
        row.error = None if result.get("ok") else result.get("reason", "unknown error")
        await session.commit()

    return result


# ---------------------------------------------------------------------------
# Per-event-type handlers
# ---------------------------------------------------------------------------

async def _handle_push(event_type: str, action: str, payload: dict) -> dict:
    repo = payload.get("repository", {}).get("full_name", "unknown")
    ref = payload.get("ref", "")            # refs/heads/main
    branch = ref.replace("refs/heads/", "")
    commits = payload.get("commits", [])
    pusher = payload.get("pusher", {}).get("name", "unknown")

    logger.info(
        "PUSH repo=%s branch=%s pusher=%s commits=%d",
        repo, branch, pusher, len(commits),
    )
    for c in commits[:5]:   # log first 5 commits
        logger.info("  commit %s: %s", c.get("id", "")[:8], c.get("message", "")[:80])

    return {
        "ok": True,
        "event": "push",
        "repo": repo,
        "branch": branch,
        "commits": len(commits),
    }


async def _handle_pull_request(event_type: str, action: str, payload: dict) -> dict:
    repo = payload.get("repository", {}).get("full_name", "unknown")
    pr = payload.get("pull_request", {})
    number = pr.get("number")
    title = pr.get("title", "")
    author = pr.get("user", {}).get("login", "unknown")
    base = pr.get("base", {}).get("ref", "")
    head = pr.get("head", {}).get("ref", "")

    logger.info(
        "PR #%s [%s] repo=%s '%s' by %s  (%s → %s)",
        number, action, repo, title[:60], author, head, base,
    )

    # For high-value actions, we could kick off an agent run.
    # e.g. action == "opened" → auto-summarise the PR diff.
    # Kept as a hook — uncomment and wire when needed:
    # if action == "opened":
    #     await _trigger_run(f"Summarise PR #{number} in {repo}: {title}", org_id="default")

    return {
        "ok": True,
        "event": "pull_request",
        "action": action,
        "repo": repo,
        "pr": number,
    }


async def _handle_issues(event_type: str, action: str, payload: dict) -> dict:
    repo = payload.get("repository", {}).get("full_name", "unknown")
    issue = payload.get("issue", {})
    number = issue.get("number")
    title = issue.get("title", "")
    author = issue.get("user", {}).get("login", "unknown")
    labels = [l.get("name") for l in issue.get("labels", [])]

    logger.info(
        "ISSUE #%s [%s] repo=%s '%s' by %s labels=%s",
        number, action, repo, title[:60], author, labels,
    )

    return {
        "ok": True,
        "event": "issues",
        "action": action,
        "repo": repo,
        "issue": number,
    }


async def _handle_release(event_type: str, action: str, payload: dict) -> dict:
    repo = payload.get("repository", {}).get("full_name", "unknown")
    release = payload.get("release", {})
    tag = release.get("tag_name", "")
    name = release.get("name", "")
    author = release.get("author", {}).get("login", "unknown")
    prerelease = release.get("prerelease", False)

    logger.info(
        "RELEASE [%s] repo=%s tag=%s name='%s' by %s prerelease=%s",
        action, repo, tag, name[:60], author, prerelease,
    )

    return {
        "ok": True,
        "event": "release",
        "action": action,
        "repo": repo,
        "tag": tag,
    }


async def _handle_unknown(event_type: str, action: str, payload: dict) -> dict:
    logger.debug("Unhandled webhook event_type=%s action=%s", event_type, action)
    return {"ok": True, "event": event_type, "action": action, "skipped": True}


_HANDLERS = {
    "push": _handle_push,
    "pull_request": _handle_pull_request,
    "issues": _handle_issues,
    "release": _handle_release,
}
