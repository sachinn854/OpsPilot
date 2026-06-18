"""
Celery task definitions.

Tasks use asyncio.run() to call async backend code from within the
synchronous Celery worker process.

Available tasks:
  morning_github_report  — fetch open GitHub issues + post summary to Slack
  run_health_check       — check all services + alert on anomalies
"""
import asyncio
import logging

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
