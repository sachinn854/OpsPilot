"""
PagerDuty tools — PagerDuty REST API v2 via API key.

Read tools:
  pagerduty_list_incidents    — list open/recent incidents
  pagerduty_get_incident      — get incident details
  pagerduty_list_services     — list monitored services
  pagerduty_get_oncall        — who is currently on-call

Write tools (sensitive=True — HITL approval required):
  pagerduty_create_incident   — trigger a new incident
  pagerduty_acknowledge_incident — acknowledge an incident
  pagerduty_resolve_incident  — resolve/close an incident

Config: stored as JSON in integration_tokens (service="pagerduty"):
  {"api_key": "u+..."}
"""
import json

import httpx

from backend.tools.base import Tool, ToolResult

PD_BASE = "https://api.pagerduty.com"


async def _get_pd_token(org_id: str = "default") -> str | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            raw = await get_token(session, org_id=org_id, service="pagerduty")
        if not raw:
            return None
        data = json.loads(raw)
        return data.get("api_key")
    except Exception:
        return None


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Token token={api_key}",
        "Accept": "application/vnd.pagerduty+json;version=2",
        "Content-Type": "application/json",
    }


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="PagerDuty not connected. Go to Settings → Connect PagerDuty.")


async def _get(path: str, api_key: str, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{PD_BASE}/{path}", headers=_headers(api_key), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(path: str, api_key: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{PD_BASE}/{path}", headers=_headers(api_key), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _put(path: str, api_key: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(f"{PD_BASE}/{path}", headers=_headers(api_key), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


def _fmt_incident(inc: dict) -> dict:
    return {
        "id":          inc.get("id"),
        "number":      inc.get("incident_number"),
        "title":       inc.get("title"),
        "status":      inc.get("status"),
        "urgency":     inc.get("urgency"),
        "created":     inc.get("created_at"),
        "service":     inc.get("service", {}).get("summary"),
        "assignee":    (inc.get("assignments") or [{}])[0].get("assignee", {}).get("summary", ""),
        "url":         inc.get("html_url"),
    }


# ---------------------------------------------------------------------------
# Tool 1 — List incidents
# ---------------------------------------------------------------------------

class PagerDutyListIncidentsTool(Tool):
    name = "pagerduty_list_incidents"
    description = (
        "List PagerDuty incidents. By default shows triggered and acknowledged incidents. "
        "Returns title, status, urgency, assigned team, and URL."
    )
    parameters = {
        "type": "object",
        "properties": {
            "statuses":    {"type": "string", "description": "Comma-separated statuses: 'triggered,acknowledged,resolved'. Default: triggered,acknowledged."},
            "urgency":     {"type": "string", "description": "Filter by urgency: 'high' or 'low'. Optional."},
            "max_results": {"type": "number", "description": "Max incidents. Default 10."},
        },
        "required": [],
    }

    async def run(self, statuses: str = "triggered,acknowledged", urgency: str = "", max_results: int = 10) -> ToolResult:
        api_key = await _get_pd_token()
        if not api_key:
            return _no_auth()
        params: dict = {
            "statuses[]": statuses.split(","),
            "limit": min(max_results, 25),
            "sort_by": "created_at:desc",
        }
        if urgency:
            params["urgencies[]"] = [urgency]
        status, data = await _get("incidents", api_key, params)
        if status != 200:
            return ToolResult(ok=False, error=f"List incidents failed: {data.get('error', {}).get('message', status)}")
        incidents = [_fmt_incident(i) for i in data.get("incidents", [])]
        return ToolResult(ok=True, data={"incidents": incidents, "count": len(incidents)})


# ---------------------------------------------------------------------------
# Tool 2 — Get incident
# ---------------------------------------------------------------------------

class PagerDutyGetIncidentTool(Tool):
    name = "pagerduty_get_incident"
    description = "Get full details of a PagerDuty incident by ID."
    parameters = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "PagerDuty incident ID (e.g. 'P1AB2CD')."},
        },
        "required": ["incident_id"],
    }

    async def run(self, incident_id: str) -> ToolResult:
        api_key = await _get_pd_token()
        if not api_key:
            return _no_auth()
        status, data = await _get(f"incidents/{incident_id}", api_key)
        if status != 200:
            return ToolResult(ok=False, error=f"Incident '{incident_id}' not found.")
        return ToolResult(ok=True, data=_fmt_incident(data.get("incident", {})))


# ---------------------------------------------------------------------------
# Tool 3 — List services
# ---------------------------------------------------------------------------

class PagerDutyListServicesTool(Tool):
    name = "pagerduty_list_services"
    description = "List all PagerDuty services — names, status, and escalation policies."
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {"type": "number", "description": "Max services. Default 20."},
        },
        "required": [],
    }

    async def run(self, max_results: int = 20) -> ToolResult:
        api_key = await _get_pd_token()
        if not api_key:
            return _no_auth()
        status, data = await _get("services", api_key, {"limit": min(max_results, 50)})
        if status != 200:
            return ToolResult(ok=False, error=f"List services failed: {data.get('error', {}).get('message', status)}")
        services = [
            {
                "id":     s.get("id"),
                "name":   s.get("name"),
                "status": s.get("status"),
                "escalation_policy": s.get("escalation_policy", {}).get("summary", ""),
            }
            for s in data.get("services", [])
        ]
        return ToolResult(ok=True, data={"services": services, "count": len(services)})


# ---------------------------------------------------------------------------
# Tool 4 — Get on-call
# ---------------------------------------------------------------------------

class PagerDutyGetOncallTool(Tool):
    name = "pagerduty_get_oncall"
    description = "Get the current on-call schedule — who is on-call right now for each escalation policy."
    parameters = {
        "type": "object",
        "properties": {
            "escalation_policy_ids": {"type": "string", "description": "Comma-separated escalation policy IDs to filter. Optional."},
        },
        "required": [],
    }

    async def run(self, escalation_policy_ids: str = "") -> ToolResult:
        api_key = await _get_pd_token()
        if not api_key:
            return _no_auth()
        params: dict = {"include[]": ["users"]}
        if escalation_policy_ids:
            params["escalation_policy_ids[]"] = escalation_policy_ids.split(",")
        status, data = await _get("oncalls", api_key, params)
        if status != 200:
            return ToolResult(ok=False, error=f"Get on-call failed: {data.get('error', {}).get('message', status)}")
        oncalls = [
            {
                "user":               o.get("user", {}).get("summary"),
                "email":              o.get("user", {}).get("email", ""),
                "escalation_policy":  o.get("escalation_policy", {}).get("summary"),
                "schedule":           o.get("schedule", {}).get("summary", ""),
                "start":              o.get("start"),
                "end":                o.get("end"),
            }
            for o in data.get("oncalls", [])
        ]
        return ToolResult(ok=True, data={"oncalls": oncalls, "count": len(oncalls)})


# ---------------------------------------------------------------------------
# Tool 5 — Create incident (sensitive)
# ---------------------------------------------------------------------------

class PagerDutyCreateIncidentTool(Tool):
    name = "pagerduty_create_incident"
    description = "Trigger a new PagerDuty incident. SENSITIVE: pages on-call engineers. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "title":      {"type": "string", "description": "Incident title/summary."},
            "service_id": {"type": "string", "description": "PagerDuty service ID to associate the incident with."},
            "urgency":    {"type": "string", "description": "Urgency: 'high' or 'low'. Default: high."},
            "body":       {"type": "string", "description": "Detailed incident description. Optional."},
        },
        "required": ["title", "service_id"],
    }

    async def run(self, title: str, service_id: str, urgency: str = "high", body: str = "") -> ToolResult:
        api_key = await _get_pd_token()
        if not api_key:
            return _no_auth()
        payload: dict = {
            "incident": {
                "type":    "incident",
                "title":   title,
                "urgency": urgency if urgency in ("high", "low") else "high",
                "service": {"id": service_id, "type": "service_reference"},
            }
        }
        if body:
            payload["incident"]["body"] = {"type": "incident_body", "details": body}
        status, data = await _post("incidents", api_key, payload)
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Create incident failed: {data.get('error', {}).get('message', status)}")
        inc = data.get("incident", {})
        return ToolResult(ok=True, data={
            "id":     inc.get("id"),
            "number": inc.get("incident_number"),
            "title":  inc.get("title"),
            "status": inc.get("status"),
            "url":    inc.get("html_url"),
        })


# ---------------------------------------------------------------------------
# Tool 6 — Acknowledge incident (sensitive)
# ---------------------------------------------------------------------------

class PagerDutyAcknowledgeIncidentTool(Tool):
    name = "pagerduty_acknowledge_incident"
    description = "Acknowledge a PagerDuty incident to signal you are working on it. SENSITIVE: changes incident state. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "PagerDuty incident ID."},
            "from_email":  {"type": "string", "description": "Email of the user acknowledging (required by PagerDuty API)."},
        },
        "required": ["incident_id", "from_email"],
    }

    async def run(self, incident_id: str, from_email: str) -> ToolResult:
        api_key = await _get_pd_token()
        if not api_key:
            return _no_auth()
        headers_extra = {**_headers(api_key), "From": from_email}
        body = {"incident": {"type": "incident", "status": "acknowledged"}}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.put(f"{PD_BASE}/incidents/{incident_id}", headers=headers_extra, json=body)
        if resp.status_code != 200:
            return ToolResult(ok=False, error=f"Acknowledge failed: HTTP {resp.status_code}")
        inc = resp.json().get("incident", {})
        return ToolResult(ok=True, data={"id": incident_id, "status": inc.get("status")})


# ---------------------------------------------------------------------------
# Tool 7 — Resolve incident (sensitive)
# ---------------------------------------------------------------------------

class PagerDutyResolveIncidentTool(Tool):
    name = "pagerduty_resolve_incident"
    description = "Resolve/close a PagerDuty incident. SENSITIVE: closes the incident permanently. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "PagerDuty incident ID."},
            "from_email":  {"type": "string", "description": "Email of the user resolving (required by PagerDuty API)."},
        },
        "required": ["incident_id", "from_email"],
    }

    async def run(self, incident_id: str, from_email: str) -> ToolResult:
        api_key = await _get_pd_token()
        if not api_key:
            return _no_auth()
        headers_extra = {**_headers(api_key), "From": from_email}
        body = {"incident": {"type": "incident", "status": "resolved"}}
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.put(f"{PD_BASE}/incidents/{incident_id}", headers=headers_extra, json=body)
        if resp.status_code != 200:
            return ToolResult(ok=False, error=f"Resolve failed: HTTP {resp.status_code}")
        inc = resp.json().get("incident", {})
        return ToolResult(ok=True, data={"id": incident_id, "status": inc.get("status")})
