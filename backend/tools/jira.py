"""
Jira tools — real Jira REST API v3 via API token.

Read tools:
  jira_get_projects    — list all accessible projects
  jira_get_issues      — search issues with JQL
  jira_get_issue       — get a single issue by key
  jira_get_board       — list sprints for a board
  jira_get_comments    — get comments on an issue

Write tools (sensitive=True — HITL approval required):
  jira_create_issue    — create a new issue
  jira_update_issue    — update status, assignee, priority
  jira_add_comment     — add a comment to an issue
  jira_transition_issue — move issue to a new status

Config: stored as JSON in integration_tokens (service="jira"):
  {"api_token": "ATATT...", "email": "user@company.com", "domain": "company.atlassian.net"}
"""
import base64
import json

import httpx

from backend.tools.base import Tool, ToolResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_jira_config(org_id: str = "default") -> dict | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            raw = await get_token(session, org_id=org_id, service="jira")
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def _auth_header(email: str, api_token: str) -> str:
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    return f"Basic {creds}"


def _headers(email: str, api_token: str) -> dict:
    return {
        "Authorization": _auth_header(email, api_token),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _base_url(domain: str) -> str:
    domain = domain.rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    return f"{domain}/rest/api/3"


def _no_config_error() -> ToolResult:
    return ToolResult(
        ok=False,
        error="Jira not configured. Connect via Settings → Integrations → Jira.",
    )


async def _get(url: str, hdrs: dict, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=hdrs, params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(url: str, hdrs: dict, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=hdrs, json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _put(url: str, hdrs: dict, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(url, headers=hdrs, json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post_no_body(url: str, hdrs: dict, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=hdrs, json=body)
    try:
        return resp.status_code, resp.json() if resp.content else {}
    except Exception:
        return resp.status_code, {}


# ---------------------------------------------------------------------------
# Tool 1 — Get projects
# ---------------------------------------------------------------------------

class JiraGetProjectsTool(Tool):
    name = "jira_get_projects"
    description = "List all Jira projects the account has access to. Returns project keys, names, and types."
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {"type": "number", "description": "Max projects to return. Default 50."},
        },
        "required": [],
    }

    async def run(self, max_results: int = 50) -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        url = f"{_base_url(cfg['domain'])}/project/search"
        status, data = await _get(url, hdrs, {"maxResults": min(max_results, 100)})
        if status != 200:
            return ToolResult(ok=False, error=f"Jira API error {status}: {data.get('errorMessages', data)}")
        projects = [
            {"key": p["key"], "name": p["name"], "type": p.get("projectTypeKey"), "id": p["id"]}
            for p in data.get("values", [])
        ]
        return ToolResult(ok=True, data={"projects": projects, "total": data.get("total", len(projects))})


# ---------------------------------------------------------------------------
# Tool 2 — Search issues with JQL
# ---------------------------------------------------------------------------

class JiraGetIssuesTool(Tool):
    name = "jira_get_issues"
    description = (
        "Search Jira issues using JQL (Jira Query Language). "
        "Examples: 'project=OPS AND status=Open', 'assignee=currentUser() AND sprint in openSprints()'. "
        "Returns key, summary, status, assignee, priority, and updated date."
    )
    parameters = {
        "type": "object",
        "properties": {
            "jql": {"type": "string", "description": "JQL query string."},
            "max_results": {"type": "number", "description": "Max issues to return. Default 20."},
            "fields": {"type": "string", "description": "Comma-separated fields to include. Default: summary,status,assignee,priority,updated,labels."},
        },
        "required": ["jql"],
    }

    async def run(self, jql: str, max_results: int = 20, fields: str = "summary,status,assignee,priority,updated,labels,description") -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        url = f"{_base_url(cfg['domain'])}/search"
        body = {"jql": jql, "maxResults": min(max_results, 50), "fields": fields.split(",")}
        status, data = await _post(url, hdrs, body)
        if status != 200:
            return ToolResult(ok=False, error=f"Jira API error {status}: {data.get('errorMessages', data)}")
        issues = []
        for i in data.get("issues", []):
            f = i.get("fields", {})
            issues.append({
                "key": i["key"],
                "summary": f.get("summary"),
                "status": f.get("status", {}).get("name"),
                "assignee": (f.get("assignee") or {}).get("displayName"),
                "priority": (f.get("priority") or {}).get("name"),
                "labels": f.get("labels", []),
                "updated": f.get("updated"),
                "url": f"https://{cfg['domain'].lstrip('https://').rstrip('/')}/browse/{i['key']}",
            })
        return ToolResult(ok=True, data={"issues": issues, "total": data.get("total", len(issues)), "jql": jql})


# ---------------------------------------------------------------------------
# Tool 3 — Get single issue
# ---------------------------------------------------------------------------

class JiraGetIssueTool(Tool):
    name = "jira_get_issue"
    description = "Get full details of a Jira issue by its key (e.g. OPS-123). Includes description, comments count, and attachments."
    parameters = {
        "type": "object",
        "properties": {
            "issue_key": {"type": "string", "description": "Jira issue key, e.g. 'OPS-123' or 'PROJ-456'."},
        },
        "required": ["issue_key"],
    }

    async def run(self, issue_key: str) -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        url = f"{_base_url(cfg['domain'])}/issue/{issue_key.upper()}"
        status, data = await _get(url, hdrs)
        if status != 200:
            return ToolResult(ok=False, error=f"Issue '{issue_key}' not found or no access.")
        f = data.get("fields", {})
        desc_raw = f.get("description") or {}
        desc_text = ""
        if isinstance(desc_raw, dict):
            for block in desc_raw.get("content", []):
                for inline in block.get("content", []):
                    desc_text += inline.get("text", "")
        return ToolResult(ok=True, data={
            "key": data["key"],
            "summary": f.get("summary"),
            "description": desc_text[:1000],
            "status": f.get("status", {}).get("name"),
            "assignee": (f.get("assignee") or {}).get("displayName"),
            "reporter": (f.get("reporter") or {}).get("displayName"),
            "priority": (f.get("priority") or {}).get("name"),
            "labels": f.get("labels", []),
            "created": f.get("created"),
            "updated": f.get("updated"),
            "comment_count": f.get("comment", {}).get("total", 0),
            "url": f"https://{cfg['domain'].lstrip('https://').rstrip('/')}/browse/{data['key']}",
        })


# ---------------------------------------------------------------------------
# Tool 4 — Get comments
# ---------------------------------------------------------------------------

class JiraGetCommentsTool(Tool):
    name = "jira_get_comments"
    description = "Get comments on a Jira issue. Returns author, timestamp, and comment text."
    parameters = {
        "type": "object",
        "properties": {
            "issue_key": {"type": "string", "description": "Jira issue key, e.g. 'OPS-123'."},
            "max_results": {"type": "number", "description": "Max comments to return. Default 10."},
        },
        "required": ["issue_key"],
    }

    async def run(self, issue_key: str, max_results: int = 10) -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        url = f"{_base_url(cfg['domain'])}/issue/{issue_key.upper()}/comment"
        status, data = await _get(url, hdrs, {"maxResults": min(max_results, 50)})
        if status != 200:
            return ToolResult(ok=False, error=f"Could not fetch comments for '{issue_key}'.")
        comments = []
        for c in data.get("comments", []):
            body_raw = c.get("body") or {}
            text = ""
            if isinstance(body_raw, dict):
                for block in body_raw.get("content", []):
                    for inline in block.get("content", []):
                        text += inline.get("text", "")
            elif isinstance(body_raw, str):
                text = body_raw
            comments.append({
                "id": c.get("id"),
                "author": (c.get("author") or {}).get("displayName"),
                "created": c.get("created"),
                "text": text[:500],
            })
        return ToolResult(ok=True, data={"issue_key": issue_key, "comments": comments, "total": data.get("total", len(comments))})


# ---------------------------------------------------------------------------
# Tool 5 — Create issue (sensitive)
# ---------------------------------------------------------------------------

class JiraCreateIssueTool(Tool):
    name = "jira_create_issue"
    description = "Create a new Jira issue in a project. SENSITIVE: creates a permanent record. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "project_key": {"type": "string", "description": "Project key, e.g. 'OPS' or 'BACKEND'."},
            "summary": {"type": "string", "description": "Issue title/summary."},
            "description": {"type": "string", "description": "Issue description (plain text)."},
            "issue_type": {"type": "string", "description": "Issue type: 'Bug', 'Task', 'Story', 'Epic'. Default: 'Task'."},
            "priority": {"type": "string", "description": "Priority: 'Highest', 'High', 'Medium', 'Low'. Default: 'Medium'."},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "Labels to attach (optional)."},
        },
        "required": ["project_key", "summary"],
    }

    async def run(
        self,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
        priority: str = "Medium",
        labels: list[str] | None = None,
    ) -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        url = f"{_base_url(cfg['domain'])}/issue"
        body: dict = {
            "fields": {
                "project": {"key": project_key.upper()},
                "summary": summary,
                "issuetype": {"name": issue_type},
                "priority": {"name": priority},
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": description}]}],
                } if description else None,
            }
        }
        if not description:
            del body["fields"]["description"]
        if labels:
            body["fields"]["labels"] = labels
        status, data = await _post(url, hdrs, body)
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Failed to create issue: {data.get('errors', data)}")
        key = data.get("key")
        return ToolResult(ok=True, data={
            "key": key,
            "url": f"https://{cfg['domain'].lstrip('https://').rstrip('/')}/browse/{key}",
            "summary": summary,
        })


# ---------------------------------------------------------------------------
# Tool 6 — Update issue (sensitive)
# ---------------------------------------------------------------------------

class JiraUpdateIssueTool(Tool):
    name = "jira_update_issue"
    description = "Update a Jira issue's summary, priority, or labels. SENSITIVE: modifies existing data. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "issue_key": {"type": "string", "description": "Jira issue key, e.g. 'OPS-123'."},
            "summary": {"type": "string", "description": "New summary (optional)."},
            "priority": {"type": "string", "description": "New priority: 'Highest', 'High', 'Medium', 'Low' (optional)."},
            "labels": {"type": "array", "items": {"type": "string"}, "description": "Replace labels (optional)."},
        },
        "required": ["issue_key"],
    }

    async def run(self, issue_key: str, summary: str | None = None, priority: str | None = None, labels: list[str] | None = None) -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        url = f"{_base_url(cfg['domain'])}/issue/{issue_key.upper()}"
        fields: dict = {}
        if summary:
            fields["summary"] = summary
        if priority:
            fields["priority"] = {"name": priority}
        if labels is not None:
            fields["labels"] = labels
        if not fields:
            return ToolResult(ok=False, error="Nothing to update. Provide summary, priority, or labels.")
        status, data = await _put(url, hdrs, {"fields": fields})
        if status not in (200, 204):
            return ToolResult(ok=False, error=f"Update failed: {data.get('errors', data)}")
        return ToolResult(ok=True, data={"key": issue_key, "updated": list(fields.keys())})


# ---------------------------------------------------------------------------
# Tool 7 — Add comment (sensitive)
# ---------------------------------------------------------------------------

class JiraAddCommentTool(Tool):
    name = "jira_add_comment"
    description = "Add a comment to a Jira issue. SENSITIVE: creates a permanent comment. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "issue_key": {"type": "string", "description": "Jira issue key, e.g. 'OPS-123'."},
            "comment": {"type": "string", "description": "Comment text to add."},
        },
        "required": ["issue_key", "comment"],
    }

    async def run(self, issue_key: str, comment: str) -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        url = f"{_base_url(cfg['domain'])}/issue/{issue_key.upper()}/comment"
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": comment}]}],
            }
        }
        status, data = await _post(url, hdrs, body)
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Failed to add comment: {data.get('errorMessages', data)}")
        return ToolResult(ok=True, data={"issue_key": issue_key, "comment_id": data.get("id"), "text": comment[:100]})


# ---------------------------------------------------------------------------
# Tool 8 — Transition issue (sensitive)
# ---------------------------------------------------------------------------

class JiraTransitionIssueTool(Tool):
    name = "jira_transition_issue"
    description = "Move a Jira issue to a new status (e.g. 'In Progress', 'Done'). SENSITIVE: changes workflow state. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "issue_key": {"type": "string", "description": "Jira issue key, e.g. 'OPS-123'."},
            "status_name": {"type": "string", "description": "Target status name, e.g. 'In Progress', 'Done', 'To Do'."},
        },
        "required": ["issue_key", "status_name"],
    }

    async def run(self, issue_key: str, status_name: str) -> ToolResult:
        cfg = await _get_jira_config()
        if not cfg:
            return _no_config_error()
        hdrs = _headers(cfg["email"], cfg["api_token"])
        key = issue_key.upper()
        trans_url = f"{_base_url(cfg['domain'])}/issue/{key}/transitions"
        status, data = await _get(trans_url, hdrs)
        if status != 200:
            return ToolResult(ok=False, error=f"Could not fetch transitions for '{key}'.")
        target = next(
            (t for t in data.get("transitions", []) if t.get("name", "").lower() == status_name.lower()),
            None,
        )
        if not target:
            available = [t["name"] for t in data.get("transitions", [])]
            return ToolResult(ok=False, error=f"Status '{status_name}' not available. Options: {available}")
        status2, _ = await _post_no_body(trans_url, hdrs, {"transition": {"id": target["id"]}})
        if status2 not in (200, 204):
            return ToolResult(ok=False, error=f"Transition failed: HTTP {status2}")
        return ToolResult(ok=True, data={"key": key, "new_status": status_name})
