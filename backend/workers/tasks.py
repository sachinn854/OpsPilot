"""
Celery task definitions.

Tasks use asyncio.run() to call async backend code from within the
synchronous Celery worker process.

Available tasks:
  morning_github_report  — fetch open GitHub issues + post summary to Slack
  run_health_check       — check all services + alert on anomalies
  slack_channel_digest   — read all Slack channels, summarise activity via LLM,
                           post digest (runs twice daily)
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from backend.workers.celery_app import celery_app

logger = logging.getLogger("copilot.workers")


@celery_app.task(name="workers.morning_github_report", bind=True, max_retries=2)
def morning_github_report(self, org_id: str = "default") -> dict:
    """Fetch open GitHub issues and post a morning summary to Slack.

    Runs the full multi-agent pipeline: GitHub tool → summarise → Slack post.
    Retries up to 2 times on transient errors.
    """
    try:
        result = asyncio.run(_run_morning_report(org_id))
        logger.info("Morning report sent: %s", result)
        return result
    except Exception as exc:
        logger.error("Morning report failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="workers.run_health_check", bind=True, max_retries=1)
def run_health_check(self, services: list[str] | None = None) -> dict:
    """Check service health metrics and log any anomalies.

    Services defaults to ["api", "worker", "database"] when not specified.
    """
    services = services or ["api", "worker", "database"]
    try:
        result = asyncio.run(_check_services(services))
        logger.info("Health check done: %s", result)
        return result
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        raise self.retry(exc=exc, countdown=30)


# ---------------------------------------------------------------------------
# Async helpers (run inside asyncio.run() in the task body)
# ---------------------------------------------------------------------------

async def _run_morning_report(org_id: str) -> dict:
    """Orchestrate: GitHub issues → Slack summary."""
    from backend.tools.github import GitHubIssuesTool
    from backend.tools.slack import PostMessageTool

    issues_tool = GitHubIssuesTool()
    slack_tool = PostMessageTool()

    # Fetch open issues (mock/real depending on GITHUB_TOKEN).
    issues_result = await issues_tool.run(
        repo="owner/repo", state="open", max_results=10
    )
    summary = (
        f"*Morning GitHub Report*\n"
        f"Open issues fetched: {issues_result.ok}\n"
        f"Data: {str(issues_result.data)[:300]}"
    )

    # Post to Slack.
    slack_result = await slack_tool.run(channel="#ops", text=summary)
    return {
        "issues_ok": issues_result.ok,
        "slack_ok": slack_result.ok,
        "channel": "#ops",
    }


async def _check_services(services: list[str]) -> dict:
    """Check each service's health and return a summary."""
    from backend.tools.monitoring import GetServiceHealthTool

    health_tool = GetServiceHealthTool()
    results = {}
    for svc in services:
        r = await health_tool.run(service=svc)
        results[svc] = r.data if r.ok else {"error": r.error}
    return results


# ---------------------------------------------------------------------------
# Slack channel digest
# ---------------------------------------------------------------------------

@celery_app.task(name="workers.slack_channel_digest", bind=True, max_retries=2)
def slack_channel_digest(self, org_id: str = "default", hours: int = 12) -> dict:
    """Read all Slack channels the bot is in, summarise activity via LLM,
    and post a digest. Designed to run twice daily (9 AM and 6 PM UTC).
    """
    try:
        result = asyncio.run(_run_slack_digest(org_id, hours))
        logger.info("Slack digest sent: %s", result)
        return result
    except Exception as exc:
        logger.error("Slack digest failed: %s", exc)
        raise self.retry(exc=exc, countdown=120)


async def _run_slack_digest(org_id: str, hours: int) -> dict:
    """
    1. List all channels the bot is in.
    2. Fetch messages from the last `hours` hours per channel.
    3. Skip channels with no activity.
    4. Generate a plain-language LLM summary per channel.
    5. Combine into one digest message and post to #digest (or DM the user).
    """
    import httpx

    from backend.config import settings
    from backend.llm.openrouter_provider import OpenRouterProvider

    SLACK_API = "https://slack.com/api"

    # Resolve token
    slack_token: str | None = None
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            slack_token = await get_token(session, org_id=org_id, service="slack")
    except Exception:
        pass
    slack_token = slack_token or settings.SLACK_TOKEN
    if not slack_token:
        return {"ok": False, "error": "Slack token not configured"}

    headers = {"Authorization": f"Bearer {slack_token}", "Content-Type": "application/json"}

    async def sl_get(method: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{SLACK_API}/{method}", headers=headers, params=params)
        try:
            return r.json()
        except Exception:
            return {}

    async def sl_post(method: str, body: dict) -> dict:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(f"{SLACK_API}/{method}", headers=headers, json=body)
        try:
            return r.json()
        except Exception:
            return {}

    # ── 1. List all channels the bot has joined ──────────────────────────────
    all_channels: list[dict] = []
    cursor = None
    while True:
        params: dict = {"limit": 200, "exclude_archived": "true",
                        "types": "public_channel,private_channel"}
        if cursor:
            params["cursor"] = cursor
        data = await sl_get("conversations.list", params)
        all_channels.extend(ch for ch in data.get("channels", []) if ch.get("is_member"))
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break

    if not all_channels:
        return {"ok": False, "error": "Bot is not a member of any channels"}

    # ── 2. Fetch messages per channel (last N hours) ─────────────────────────
    since_ts = str((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())

    # Build a user-ID → display-name cache lazily
    user_cache: dict[str, str] = {}

    async def resolve_user(uid: str) -> str:
        if uid in user_cache:
            return user_cache[uid]
        d = await sl_get("users.info", {"user": uid})
        if d.get("ok"):
            p = d["user"].get("profile", {})
            name = p.get("display_name") or p.get("real_name") or d["user"].get("name") or uid
        else:
            name = uid
        user_cache[uid] = name
        return name

    channel_summaries: list[str] = []
    channels_processed = 0

    for ch in all_channels:
        ch_name = ch.get("name", ch["id"])
        data = await sl_get("conversations.history", {
            "channel": ch["id"],
            "oldest": since_ts,
            "limit": 100,
        })
        messages = [m for m in data.get("messages", []) if m.get("type") == "message"
                    and not m.get("subtype")]  # skip bot join/leave events

        if not messages:
            continue  # nothing to summarise

        # Resolve usernames and build a readable transcript
        lines: list[str] = []
        for msg in reversed(messages):  # chronological order
            uid = msg.get("user", "unknown")
            name = await resolve_user(uid) if uid != "unknown" else "unknown"
            text = (msg.get("text") or "").strip()
            if text:
                lines.append(f"{name}: {text}")

        if not lines:
            continue

        transcript = "\n".join(lines[:80])  # cap at 80 lines per channel

        # ── 3. LLM summary ───────────────────────────────────────────────────
        llm = OpenRouterProvider()
        prompt = (
            f"You are summarising a Slack channel for a busy engineer who missed these messages.\n\n"
            f"Channel: #{ch_name}\n"
            f"Time window: last {hours} hours\n\n"
            f"Messages:\n{transcript}\n\n"
            f"Write a SHORT, plain-English summary (3-6 bullet points max). "
            f"Focus on decisions made, action items, and important updates. "
            f"Skip small talk. Use simple language — no jargon."
        )
        response = await llm.chat([{"role": "user", "content": prompt}])
        summary_text = (response.content or "").strip()

        if summary_text:
            channel_summaries.append(
                f"*#{ch_name}* ({len(messages)} messages)\n{summary_text}"
            )
        channels_processed += 1

    if not channel_summaries:
        return {"ok": True, "message": "No channel activity in the last {} hours".format(hours),
                "channels_checked": len(all_channels)}

    # ── 4. Build and post digest ─────────────────────────────────────────────
    period_label = "Morning" if datetime.now(timezone.utc).hour < 13 else "Evening"
    date_str = datetime.now(timezone.utc).strftime("%d %b %Y")

    digest = (
        f"*{period_label} Digest — {date_str}* 📋\n"
        f"_Summary of the last {hours} hours across {channels_processed} active channel(s)_\n\n"
        + "\n\n---\n\n".join(channel_summaries)
    )

    # Post to #digest channel; create it if needed, fall back to #general
    digest_channel_id: str | None = None
    for target in ["digest", "general"]:
        find = await sl_get("conversations.list", {
            "limit": 200, "exclude_archived": "true",
            "types": "public_channel,private_channel",
        })
        for ch in find.get("channels", []):
            if ch.get("name") == target and ch.get("is_member"):
                digest_channel_id = ch["id"]
                break
        if digest_channel_id:
            break

    posted = False
    if digest_channel_id:
        result = await sl_post("chat.postMessage", {
            "channel": digest_channel_id,
            "text": digest,
            "mrkdwn": True,
        })
        posted = result.get("ok", False)

    # ── 5. Email delivery ────────────────────────────────────────────────────
    emails_sent = 0
    try:
        from sqlalchemy import select

        from backend.db.models import User
        from backend.db.session import AsyncSessionLocal
        from backend.workers.email_utils import send_slack_digest

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.digest_email_enabled == True)  # noqa: E712
            )
            users = result.scalars().all()

        for user in users:
            recipient = user.digest_email_override.strip() or user.email
            ok = send_slack_digest(recipient, digest, period_label)
            if ok:
                emails_sent += 1
    except Exception as exc:
        logger.warning("Email delivery failed: %s", exc)

    return {
        "ok": True,
        "channels_summarised": channels_processed,
        "channels_total": len(all_channels),
        "posted_to_slack": posted,
        "emails_sent": emails_sent,
        "digest_length": len(digest),
    }
