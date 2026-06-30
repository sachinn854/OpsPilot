"""
Cross-service workflow tools — combine GitHub + Slack in a single tool call.

These tools do what a human would take 10-15 minutes to do manually:
  generate_standup         — today's GitHub activity → formatted standup → Slack post
  notify_stale_prs         — find PRs with no review → DM assignees or post summary
  broadcast_incident       — post alert to #incidents + DM on-call + open GitHub issue
  notify_pr_stakeholders   — find everyone on a PR → DM each with a custom message
"""
import asyncio
from datetime import datetime, timedelta, timezone

import httpx

from backend.config import settings
from backend.tools.base import Tool, ToolResult

GITHUB_API = "https://api.github.com"
SLACK_API  = "https://slack.com/api"


# ── token helpers ─────────────────────────────────────────────────────────────

async def _gh_token(org_id: str) -> str | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as s:
            return await get_token(s, org_id=org_id, service="github")
    except Exception:
        return None


async def _sl_token(org_id: str) -> str | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as s:
            return await get_token(s, org_id=org_id, service="slack")
    except Exception:
        return None


def _gh_headers(tok: str | None) -> dict:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    t = tok or settings.GITHUB_TOKEN
    if t:
        h["Authorization"] = f"Bearer {t}"
    return h


def _sl_headers(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


async def _gh_get(path: str, tok: str | None, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{GITHUB_API}{path}", headers=_gh_headers(tok), params=params or {})
    try:
        return r.json()
    except Exception:
        return {}


async def _sl_post(method: str, body: dict, tok: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"{SLACK_API}/{method}", headers=_sl_headers(tok), json=body)
    try:
        return r.json()
    except Exception:
        return {}


async def _sl_get(method: str, params: dict, tok: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(f"{SLACK_API}/{method}", headers=_sl_headers(tok), params=params)
    try:
        return r.json()
    except Exception:
        return {}


# ── shared helpers ────────────────────────────────────────────────────────────

async def _resolve_channel(name: str, tok: str) -> str | None:
    """Channel name → channel ID."""
    if name and name[0] in ("C", "D", "G") and len(name) > 5:
        return name
    name = name.lstrip("#").lower()
    cursor = None
    while True:
        params: dict = {"limit": 200, "exclude_archived": "true",
                        "types": "public_channel,private_channel"}
        if cursor:
            params["cursor"] = cursor
        data = await _sl_get("conversations.list", params, tok)
        for ch in data.get("channels", []):
            if ch.get("name", "").lower() == name:
                return ch["id"]
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


async def _resolve_slack_user(identifier: str, tok: str) -> str | None:
    """GitHub username / display name / email → Slack user ID."""
    if "@" in identifier:
        data = await _sl_get("users.lookupByEmail", {"email": identifier}, tok)
        if data.get("ok"):
            return data["user"]["id"]
        return None
    identifier_lower = identifier.lower().lstrip("@")
    cursor = None
    while True:
        params: dict = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        data = await _sl_get("users.list", params, tok)
        for m in data.get("members", []):
            p = m.get("profile", {})
            if (m.get("name", "").lower() == identifier_lower
                    or p.get("display_name", "").lower() == identifier_lower
                    or p.get("real_name", "").lower() == identifier_lower):
                return m["id"]
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


async def _open_dm(user_id: str, tok: str) -> str | None:
    """Open a DM channel with a user, return channel ID."""
    data = await _sl_post("conversations.open", {"users": user_id}, tok)
    if data.get("ok"):
        return data["channel"]["id"]
    return None


async def _post_message(channel_id: str, text: str, tok: str) -> bool:
    data = await _sl_post("chat.postMessage", {"channel": channel_id, "text": text}, tok)
    return bool(data.get("ok"))


# ── Tool 1 — Daily standup ────────────────────────────────────────────────────

class GenerateStandupTool(Tool):
    name = "generate_standup"
    description = (
        "Generate a daily standup summary from GitHub activity (today's commits, "
        "merged PRs, open blockers) and optionally post it to a Slack channel. "
        "Use when the user asks for a standup, daily summary, or morning report."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {
                "type": "string",
                "description": "Repository in 'owner/name' format.",
            },
            "slack_channel": {
                "type": "string",
                "description": "Slack channel to post the standup (e.g. '#engineering'). "
                               "Omit to just return the text without posting.",
            },
        },
        "required": ["repo"],
    }

    async def run(self, repo: str, slack_channel: str = "", org_id: str = "default") -> ToolResult:
        gh_tok = await _gh_token(org_id)
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        since = today.isoformat()

        # Fetch in parallel
        commits_raw, prs_raw, issues_raw = await asyncio.gather(
            _gh_get(f"/repos/{repo}/commits", gh_tok, {"since": since, "per_page": 30}),
            _gh_get(f"/repos/{repo}/pulls", gh_tok, {"state": "closed", "sort": "updated",
                                                       "direction": "desc", "per_page": 20}),
            _gh_get(f"/repos/{repo}/issues", gh_tok, {"state": "open", "labels": "blocker,blocked",
                                                        "per_page": 10}),
        )

        # Filter to today
        commits = commits_raw if isinstance(commits_raw, list) else []
        merged_today = [
            p for p in (prs_raw if isinstance(prs_raw, list) else [])
            if p.get("merged_at") and p["merged_at"] >= since
        ]
        blockers = [i for i in (issues_raw if isinstance(issues_raw, list) else [])
                    if "pull_request" not in i]

        # Build standup text
        date_str = today.strftime("%A, %d %b %Y")
        lines = [f"*Daily Standup — {date_str}* 📋", f"*Repo:* `{repo}`", ""]

        lines.append("*✅ Done (commits today):*")
        if commits:
            for c in commits[:8]:
                msg = c.get("commit", {}).get("message", "").split("\n")[0][:80]
                author = c.get("commit", {}).get("author", {}).get("name", "unknown")
                lines.append(f"  • {msg} _({author})_")
        else:
            lines.append("  • No commits today")

        lines += ["", "*🔀 Merged PRs today:*"]
        if merged_today:
            for pr in merged_today[:5]:
                lines.append(f"  • #{pr['number']} {pr['title'][:70]} — @{pr['user']['login']}")
        else:
            lines.append("  • None")

        lines += ["", "*🚧 Open blockers:*"]
        if blockers:
            for issue in blockers[:5]:
                lines.append(f"  • #{issue['number']} {issue['title'][:70]}")
        else:
            lines.append("  • No blockers 🎉")

        standup_text = "\n".join(lines)

        # Post to Slack if channel given
        posted = False
        if slack_channel:
            sl_tok = await _sl_token(org_id)
            if sl_tok:
                ch_id = await _resolve_channel(slack_channel, sl_tok)
                if ch_id:
                    posted = await _post_message(ch_id, standup_text, sl_tok)

        return ToolResult(
            ok=True,
            data={
                "standup": standup_text,
                "commits_today": len(commits),
                "prs_merged_today": len(merged_today),
                "open_blockers": len(blockers),
                "posted_to_slack": posted,
                "channel": slack_channel or None,
            },
        )


# ── Tool 2 — Stale PR notifier ────────────────────────────────────────────────

class NotifyStalePRsTool(Tool):
    name = "notify_stale_prs"
    description = (
        "Find open PRs that have had no activity for N days and notify assignees "
        "via Slack DM, or post a summary to a channel. "
        "Use when the user wants to chase PR reviews or send reminders."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo": {"type": "string", "description": "Repository in 'owner/name' format."},
            "days": {"type": "integer", "description": "PRs older than this many days are 'stale'. Default 3."},
            "slack_channel": {
                "type": "string",
                "description": "Post a summary here instead of DMing each assignee. "
                               "Leave empty to DM individual assignees.",
            },
            "dm_assignees": {
                "type": "boolean",
                "description": "If true, DM each PR assignee. Default true when no channel given.",
            },
        },
        "required": ["repo"],
    }

    async def run(
        self,
        repo: str,
        days: int = 3,
        slack_channel: str = "",
        dm_assignees: bool = True,
        org_id: str = "default",
    ) -> ToolResult:
        gh_tok = await _gh_token(org_id)
        sl_tok = await _sl_token(org_id)

        prs_raw = await _gh_get(f"/repos/{repo}/pulls", gh_tok,
                                 {"state": "open", "sort": "updated", "direction": "asc", "per_page": 50})
        prs = prs_raw if isinstance(prs_raw, list) else []

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stale = []
        for pr in prs:
            updated = pr.get("updated_at", "")
            if updated and datetime.fromisoformat(updated.replace("Z", "+00:00")) < cutoff:
                age = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(updated.replace("Z", "+00:00"))).days
                stale.append({
                    "number": pr["number"],
                    "title":  pr["title"],
                    "author": pr["user"]["login"],
                    "assignees": [a["login"] for a in pr.get("assignees", [])],
                    "url":  pr["html_url"],
                    "age_days": age,
                })

        if not stale:
            return ToolResult(ok=True, data={"message": f"No stale PRs (>{days} days) found in {repo}.", "stale_count": 0})

        results: list[dict] = []

        if slack_channel and sl_tok:
            # Post a summary to the channel
            ch_id = await _resolve_channel(slack_channel, sl_tok)
            if ch_id:
                lines = [f"*🕐 Stale PRs in `{repo}` (no activity >{days} days)*", ""]
                for pr in stale:
                    assignee_str = ", ".join(f"@{a}" for a in pr["assignees"]) or "_unassigned_"
                    lines.append(f"  • <{pr['url']}|#{pr['number']} {pr['title'][:60]}> "
                                  f"— {pr['age_days']}d old · {assignee_str}")
                await _post_message(ch_id, "\n".join(lines), sl_tok)
                results.append({"action": "channel_post", "channel": slack_channel, "prs": len(stale)})

        elif dm_assignees and sl_tok:
            # DM each unique assignee
            seen_assignees: set[str] = set()
            for pr in stale:
                targets = pr["assignees"] or [pr["author"]]
                for username in targets:
                    if username in seen_assignees:
                        continue
                    seen_assignees.add(username)
                    slack_uid = await _resolve_slack_user(username, sl_tok)
                    if slack_uid:
                        dm_ch = await _open_dm(slack_uid, sl_tok)
                        if dm_ch:
                            their_prs = [p for p in stale
                                         if username in (p["assignees"] or [p["author"]])]
                            msg = f"👋 Hey @{username}! You have {len(their_prs)} stale PR(s) in `{repo}`:\n"
                            for p in their_prs:
                                msg += f"  • <{p['url']}|#{p['number']} {p['title'][:60]}> ({p['age_days']}d old)\n"
                            msg += "\nCould you review or update these? 🙏"
                            await _post_message(dm_ch, msg, sl_tok)
                            results.append({"action": "dm", "to": username, "prs": len(their_prs)})
                    else:
                        results.append({"action": "dm_failed", "reason": f"Could not find {username} in Slack"})

        return ToolResult(ok=True, data={
            "stale_count": len(stale),
            "stale_prs": stale,
            "notifications_sent": results,
        })


# ── Tool 3 — Incident broadcast ───────────────────────────────────────────────

class BroadcastIncidentTool(Tool):
    name = "broadcast_incident"
    description = (
        "Broadcast a production incident in one command: post to #incidents channel, "
        "DM the on-call person, and optionally open a GitHub issue. "
        "Use when there's a prod issue, outage, or service degradation."
    )
    parameters = {
        "type": "object",
        "properties": {
            "title":       {"type": "string", "description": "Short incident title."},
            "description": {"type": "string", "description": "What is happening and impact."},
            "severity":    {"type": "string", "enum": ["low", "medium", "high", "critical"],
                            "description": "Incident severity level."},
            "oncall_user": {"type": "string",
                            "description": "Slack display name or email of on-call person to DM."},
            "incidents_channel": {"type": "string",
                                   "description": "Slack channel for incidents. Default '#incidents'."},
            "repo":        {"type": "string",
                            "description": "GitHub repo to open an incident issue. Optional."},
        },
        "required": ["title", "description", "severity", "oncall_user"],
    }

    async def run(
        self,
        title: str,
        description: str,
        severity: str,
        oncall_user: str,
        incidents_channel: str = "#incidents",
        repo: str = "",
        org_id: str = "default",
    ) -> ToolResult:
        sl_tok = await _sl_token(org_id)
        gh_tok = await _gh_token(org_id)

        severity_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "🚨"}.get(severity, "⚠️")
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        channel_msg = (
            f"{severity_emoji} *INCIDENT — {severity.upper()}*\n"
            f"*{title}*\n\n"
            f"{description}\n\n"
            f"_Reported at {now_str}_"
        )

        actions: list[dict] = []

        if sl_tok:
            # Post to incidents channel
            ch_id = await _resolve_channel(incidents_channel.lstrip("#"), sl_tok)
            if ch_id:
                ok = await _post_message(ch_id, channel_msg, sl_tok)
                actions.append({"action": "incidents_channel", "channel": incidents_channel, "ok": ok})

            # DM on-call person
            oncall_uid = await _resolve_slack_user(oncall_user, sl_tok)
            if oncall_uid:
                dm_ch = await _open_dm(oncall_uid, sl_tok)
                if dm_ch:
                    dm_msg = (
                        f"{severity_emoji} *You're on-call — incident reported!*\n"
                        f"*{title}*\n{description}\n_Severity: {severity}_"
                    )
                    ok = await _post_message(dm_ch, dm_msg, sl_tok)
                    actions.append({"action": "oncall_dm", "to": oncall_user, "ok": ok})
            else:
                actions.append({"action": "oncall_dm", "to": oncall_user, "ok": False,
                                 "reason": "User not found in Slack"})

        # Open GitHub issue
        gh_issue_url = None
        if repo and gh_tok:
            body = (
                f"## Incident Report\n\n"
                f"**Severity:** {severity}\n"
                f"**Reported at:** {now_str}\n\n"
                f"### Description\n{description}"
            )
            data = await _gh_get(f"/repos/{repo}/issues", None)  # dummy check
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.post(
                    f"{GITHUB_API}/repos/{repo}/issues",
                    headers=_gh_headers(gh_tok),
                    json={"title": f"[INCIDENT] {title}", "body": body, "labels": ["incident", severity]},
                )
            if r.status_code == 201:
                gh_issue_url = r.json().get("html_url")
                actions.append({"action": "github_issue", "url": gh_issue_url, "ok": True})

        return ToolResult(ok=True, data={
            "incident": {"title": title, "severity": severity, "reported_at": now_str},
            "actions": actions,
            "github_issue": gh_issue_url,
        })


# ── Tool 4 — Notify PR stakeholders ──────────────────────────────────────────

class NotifyPRStakeholdersTool(Tool):
    name = "notify_pr_stakeholders"
    description = (
        "Find everyone involved in a GitHub PR (author, assignees, reviewers) "
        "and send them each a custom Slack DM. "
        "Use when you want to notify the whole team about a PR merge, conflict, or update."
    )
    parameters = {
        "type": "object",
        "properties": {
            "repo":       {"type": "string", "description": "Repository in 'owner/name' format."},
            "pr_number":  {"type": "integer", "description": "PR number."},
            "message":    {"type": "string",
                           "description": "Message to send. Use {name} to personalize with their GitHub username."},
        },
        "required": ["repo", "pr_number", "message"],
    }

    async def run(
        self,
        repo: str,
        pr_number: int,
        message: str,
        org_id: str = "default",
    ) -> ToolResult:
        gh_tok = await _gh_token(org_id)
        sl_tok = await _sl_token(org_id)

        if not sl_tok:
            return ToolResult(ok=False, error="Slack token not configured.")

        pr = await _gh_get(f"/repos/{repo}/pulls/{pr_number}", gh_tok)
        if "message" in pr and pr.get("message") == "Not Found":
            return ToolResult(ok=False, error=f"PR #{pr_number} not found in {repo}.")

        # Collect all stakeholders (deduplicated)
        stakeholders: set[str] = set()
        if pr.get("user"):
            stakeholders.add(pr["user"]["login"])
        for a in pr.get("assignees", []):
            stakeholders.add(a["login"])
        for r in pr.get("requested_reviewers", []):
            stakeholders.add(r["login"])

        pr_title = pr.get("title", f"PR #{pr_number}")
        pr_url   = pr.get("html_url", "")

        results: list[dict] = []
        for username in stakeholders:
            slack_uid = await _resolve_slack_user(username, sl_tok)
            if not slack_uid:
                results.append({"github": username, "ok": False, "reason": "Not found in Slack"})
                continue

            dm_ch = await _open_dm(slack_uid, sl_tok)
            if not dm_ch:
                results.append({"github": username, "ok": False, "reason": "Could not open DM"})
                continue

            personalized = message.replace("{name}", username)
            full_msg = f"{personalized}\n\n*PR:* <{pr_url}|#{pr_number} {pr_title}>"
            ok = await _post_message(dm_ch, full_msg, sl_tok)
            results.append({"github": username, "ok": ok})

        notified = sum(1 for r in results if r["ok"])
        return ToolResult(ok=True, data={
            "pr": {"number": pr_number, "title": pr_title, "url": pr_url},
            "stakeholders_found": len(stakeholders),
            "notified": notified,
            "results": results,
        })
