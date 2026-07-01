"""
HubSpot tools — HubSpot CRM API v3 via Private App token.

Read tools:
  hubspot_search_contacts  — search contacts by name/email
  hubspot_get_contact      — get contact details
  hubspot_list_deals       — list recent deals
  hubspot_get_deal         — get deal details
  hubspot_list_companies   — list companies

Write tools (sensitive=True — HITL approval required):
  hubspot_create_contact   — create a new CRM contact
  hubspot_update_contact   — update contact properties
  hubspot_create_deal      — create a new deal

Config: stored as JSON in integration_tokens (service="hubspot"):
  {"token": "pat-na1-..."}
"""
import json

import httpx

from backend.tools.base import Tool, ToolResult

HS_BASE = "https://api.hubapi.com"


async def _get_hs_token(org_id: str = "default") -> str | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            raw = await get_token(session, org_id=org_id, service="hubspot")
        if not raw:
            return None
        data = json.loads(raw)
        return data.get("token")
    except Exception:
        return None


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="HubSpot not connected. Go to Settings → Connect HubSpot.")


async def _get(path: str, token: str, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{HS_BASE}/{path}", headers=_headers(token), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(path: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{HS_BASE}/{path}", headers=_headers(token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _patch(path: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.patch(f"{HS_BASE}/{path}", headers=_headers(token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


def _fmt_contact(c: dict) -> dict:
    props = c.get("properties", {})
    return {
        "id":         c.get("id"),
        "first_name": props.get("firstname", ""),
        "last_name":  props.get("lastname", ""),
        "email":      props.get("email", ""),
        "phone":      props.get("phone", ""),
        "company":    props.get("company", ""),
        "lifecycle":  props.get("lifecyclestage", ""),
        "created":    props.get("createdate", ""),
    }


def _fmt_deal(d: dict) -> dict:
    props = d.get("properties", {})
    return {
        "id":         d.get("id"),
        "name":       props.get("dealname", ""),
        "stage":      props.get("dealstage", ""),
        "amount":     props.get("amount", ""),
        "close_date": props.get("closedate", ""),
        "pipeline":   props.get("pipeline", ""),
        "created":    props.get("createdate", ""),
    }


def _fmt_company(c: dict) -> dict:
    props = c.get("properties", {})
    return {
        "id":       c.get("id"),
        "name":     props.get("name", ""),
        "domain":   props.get("domain", ""),
        "industry": props.get("industry", ""),
        "city":     props.get("city", ""),
        "country":  props.get("country", ""),
    }


# ---------------------------------------------------------------------------
# Tool 1 — Search contacts
# ---------------------------------------------------------------------------

class HubSpotSearchContactsTool(Tool):
    name = "hubspot_search_contacts"
    description = "Search HubSpot contacts by name, email, or company. Returns contact details."
    parameters = {
        "type": "object",
        "properties": {
            "query":       {"type": "string", "description": "Search query — name, email, or company."},
            "max_results": {"type": "number", "description": "Max contacts. Default 10."},
        },
        "required": ["query"],
    }

    async def run(self, query: str, max_results: int = 10) -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        body = {
            "query": query,
            "limit": min(max_results, 20),
            "properties": ["firstname", "lastname", "email", "phone", "company", "lifecyclestage", "createdate"],
        }
        status, data = await _post("crm/v3/objects/contacts/search", token, body)
        if status != 200:
            return ToolResult(ok=False, error=f"Contact search failed: {data.get('message', status)}")
        contacts = [_fmt_contact(c) for c in data.get("results", [])]
        return ToolResult(ok=True, data={"contacts": contacts, "count": len(contacts), "total": data.get("total", 0)})


# ---------------------------------------------------------------------------
# Tool 2 — Get contact
# ---------------------------------------------------------------------------

class HubSpotGetContactTool(Tool):
    name = "hubspot_get_contact"
    description = "Get full details of a HubSpot contact by contact ID."
    parameters = {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string", "description": "HubSpot contact ID."},
        },
        "required": ["contact_id"],
    }

    async def run(self, contact_id: str) -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        params = {"properties": "firstname,lastname,email,phone,company,lifecyclestage,createdate,jobtitle,website"}
        status, data = await _get(f"crm/v3/objects/contacts/{contact_id}", token, params)
        if status != 200:
            return ToolResult(ok=False, error=f"Contact '{contact_id}' not found.")
        return ToolResult(ok=True, data=_fmt_contact(data))


# ---------------------------------------------------------------------------
# Tool 3 — List deals
# ---------------------------------------------------------------------------

class HubSpotListDealsTool(Tool):
    name = "hubspot_list_deals"
    description = "List recent HubSpot deals — name, stage, amount, and close date."
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {"type": "number", "description": "Max deals. Default 10."},
        },
        "required": [],
    }

    async def run(self, max_results: int = 10) -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        params = {
            "limit": min(max_results, 50),
            "properties": "dealname,dealstage,amount,closedate,pipeline,createdate",
            "sort": "-createdate",
        }
        status, data = await _get("crm/v3/objects/deals", token, params)
        if status != 200:
            return ToolResult(ok=False, error=f"List deals failed: {data.get('message', status)}")
        deals = [_fmt_deal(d) for d in data.get("results", [])]
        return ToolResult(ok=True, data={"deals": deals, "count": len(deals)})


# ---------------------------------------------------------------------------
# Tool 4 — Get deal
# ---------------------------------------------------------------------------

class HubSpotGetDealTool(Tool):
    name = "hubspot_get_deal"
    description = "Get full details of a HubSpot deal by deal ID."
    parameters = {
        "type": "object",
        "properties": {
            "deal_id": {"type": "string", "description": "HubSpot deal ID."},
        },
        "required": ["deal_id"],
    }

    async def run(self, deal_id: str) -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        params = {"properties": "dealname,dealstage,amount,closedate,pipeline,createdate,description,hubspot_owner_id"}
        status, data = await _get(f"crm/v3/objects/deals/{deal_id}", token, params)
        if status != 200:
            return ToolResult(ok=False, error=f"Deal '{deal_id}' not found.")
        return ToolResult(ok=True, data=_fmt_deal(data))


# ---------------------------------------------------------------------------
# Tool 5 — List companies
# ---------------------------------------------------------------------------

class HubSpotListCompaniesTool(Tool):
    name = "hubspot_list_companies"
    description = "List HubSpot companies — name, domain, industry, and location."
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {"type": "number", "description": "Max companies. Default 10."},
        },
        "required": [],
    }

    async def run(self, max_results: int = 10) -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        params = {
            "limit": min(max_results, 50),
            "properties": "name,domain,industry,city,country,createdate",
        }
        status, data = await _get("crm/v3/objects/companies", token, params)
        if status != 200:
            return ToolResult(ok=False, error=f"List companies failed: {data.get('message', status)}")
        companies = [_fmt_company(c) for c in data.get("results", [])]
        return ToolResult(ok=True, data={"companies": companies, "count": len(companies)})


# ---------------------------------------------------------------------------
# Tool 6 — Create contact (sensitive)
# ---------------------------------------------------------------------------

class HubSpotCreateContactTool(Tool):
    name = "hubspot_create_contact"
    description = "Create a new HubSpot CRM contact. SENSITIVE: adds a permanent contact record. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "email":      {"type": "string", "description": "Contact email address (must be unique)."},
            "first_name": {"type": "string", "description": "First name."},
            "last_name":  {"type": "string", "description": "Last name."},
            "phone":      {"type": "string", "description": "Phone number. Optional."},
            "company":    {"type": "string", "description": "Company name. Optional."},
            "job_title":  {"type": "string", "description": "Job title. Optional."},
        },
        "required": ["email"],
    }

    async def run(self, email: str, first_name: str = "", last_name: str = "",
                  phone: str = "", company: str = "", job_title: str = "") -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        props: dict = {"email": email}
        if first_name:
            props["firstname"] = first_name
        if last_name:
            props["lastname"] = last_name
        if phone:
            props["phone"] = phone
        if company:
            props["company"] = company
        if job_title:
            props["jobtitle"] = job_title
        status, data = await _post("crm/v3/objects/contacts", token, {"properties": props})
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Create contact failed: {data.get('message', status)}")
        return ToolResult(ok=True, data=_fmt_contact(data))


# ---------------------------------------------------------------------------
# Tool 7 — Update contact (sensitive)
# ---------------------------------------------------------------------------

class HubSpotUpdateContactTool(Tool):
    name = "hubspot_update_contact"
    description = "Update a HubSpot contact's properties. SENSITIVE: modifies CRM record. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "contact_id": {"type": "string", "description": "HubSpot contact ID."},
            "first_name": {"type": "string", "description": "Updated first name. Optional."},
            "last_name":  {"type": "string", "description": "Updated last name. Optional."},
            "phone":      {"type": "string", "description": "Updated phone. Optional."},
            "company":    {"type": "string", "description": "Updated company. Optional."},
            "job_title":  {"type": "string", "description": "Updated job title. Optional."},
            "lifecycle":  {"type": "string", "description": "Lifecycle stage: subscriber, lead, marketingqualifiedlead, salesqualifiedlead, opportunity, customer, evangelist. Optional."},
        },
        "required": ["contact_id"],
    }

    async def run(self, contact_id: str, first_name: str = "", last_name: str = "",
                  phone: str = "", company: str = "", job_title: str = "", lifecycle: str = "") -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        props: dict = {}
        if first_name:
            props["firstname"] = first_name
        if last_name:
            props["lastname"] = last_name
        if phone:
            props["phone"] = phone
        if company:
            props["company"] = company
        if job_title:
            props["jobtitle"] = job_title
        if lifecycle:
            props["lifecyclestage"] = lifecycle
        if not props:
            return ToolResult(ok=False, error="Provide at least one field to update.")
        status, data = await _patch(f"crm/v3/objects/contacts/{contact_id}", token, {"properties": props})
        if status != 200:
            return ToolResult(ok=False, error=f"Update contact failed: {data.get('message', status)}")
        return ToolResult(ok=True, data=_fmt_contact(data))


# ---------------------------------------------------------------------------
# Tool 8 — Create deal (sensitive)
# ---------------------------------------------------------------------------

class HubSpotCreateDealTool(Tool):
    name = "hubspot_create_deal"
    description = "Create a new HubSpot deal in the CRM pipeline. SENSITIVE: adds a permanent deal record. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "name":       {"type": "string", "description": "Deal name."},
            "stage":      {"type": "string", "description": "Deal stage ID (e.g. 'appointmentscheduled', 'qualifiedtobuy', 'presentationscheduled', 'closedwon', 'closedlost')."},
            "amount":     {"type": "string", "description": "Deal value as a string number. Optional."},
            "close_date": {"type": "string", "description": "Expected close date in YYYY-MM-DD format. Optional."},
            "pipeline":   {"type": "string", "description": "Pipeline ID. Default: 'default'."},
        },
        "required": ["name", "stage"],
    }

    async def run(self, name: str, stage: str, amount: str = "",
                  close_date: str = "", pipeline: str = "default") -> ToolResult:
        token = await _get_hs_token()
        if not token:
            return _no_auth()
        props: dict = {"dealname": name, "dealstage": stage, "pipeline": pipeline}
        if amount:
            props["amount"] = amount
        if close_date:
            props["closedate"] = close_date
        status, data = await _post("crm/v3/objects/deals", token, {"properties": props})
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Create deal failed: {data.get('message', status)}")
        return ToolResult(ok=True, data=_fmt_deal(data))
