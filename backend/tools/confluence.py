"""
Confluence tools — Confluence REST API v2 via API token.

Read tools:
  confluence_search         — search pages by keyword (CQL)
  confluence_get_page       — get full page content
  confluence_list_spaces    — list all accessible spaces
  confluence_get_space_pages — list pages in a space

Write tools (sensitive=True — HITL approval required):
  confluence_create_page    — create a new page in a space
  confluence_update_page    — update page title or content

Config: stored as JSON in integration_tokens (service="confluence"):
  {"domain": "company.atlassian.net", "email": "user@company.com", "api_token": "ATATT..."}
"""
import base64
import json

import httpx

from backend.tools.base import Tool, ToolResult


async def _get_confluence_config(org_id: str = "default") -> dict | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            raw = await get_token(session, org_id=org_id, service="confluence")
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        return None


def _base_url(domain: str) -> str:
    return f"https://{domain}/wiki/rest/api"


def _headers(email: str, api_token: str) -> dict:
    creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
    return {
        "Authorization": f"Basic {creds}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="Confluence not connected. Go to Settings → Connect Confluence.")


async def _get(url: str, email: str, token: str, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=_headers(email, token), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(url: str, email: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=_headers(email, token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _put(url: str, email: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(url, headers=_headers(email, token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


def _strip_html(html: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", html).strip()[:5000]


# ---------------------------------------------------------------------------
# Tool 1 — Search
# ---------------------------------------------------------------------------

class ConfluenceSearchTool(Tool):
    name = "confluence_search"
    description = (
        "Search Confluence pages by keyword. "
        "Returns page titles, spaces, URLs, and a short excerpt."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query":       {"type": "string", "description": "Search keyword or phrase."},
            "space_key":   {"type": "string", "description": "Limit search to a specific space key. Optional."},
            "max_results": {"type": "number", "description": "Max pages to return. Default 10."},
        },
        "required": ["query"],
    }

    async def run(self, query: str, space_key: str = "", max_results: int = 10) -> ToolResult:
        cfg = await _get_confluence_config()
        if not cfg:
            return _no_auth()
        cql = f'type=page AND text ~ "{query}"'
        if space_key:
            cql += f' AND space.key = "{space_key}"'
        params = {
            "cql":    cql,
            "limit":  min(max_results, 25),
            "expand": "space,excerpt",
        }
        status, data = await _get(
            f"{_base_url(cfg['domain'])}/content/search",
            cfg["email"], cfg["api_token"], params,
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Confluence search failed: {data.get('message', status)}")
        results = []
        for item in data.get("results", []):
            results.append({
                "id":      item.get("id"),
                "title":   item.get("title"),
                "space":   item.get("space", {}).get("key"),
                "excerpt": item.get("excerpt", ""),
                "url":     f"https://{cfg['domain']}/wiki{item.get('_links', {}).get('webui', '')}",
            })
        return ToolResult(ok=True, data={"results": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Tool 2 — Get page content
# ---------------------------------------------------------------------------

class ConfluenceGetPageTool(Tool):
    name = "confluence_get_page"
    description = "Get the full content of a Confluence page by its ID."
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {"type": "string", "description": "Confluence page ID (numeric string)."},
        },
        "required": ["page_id"],
    }

    async def run(self, page_id: str) -> ToolResult:
        cfg = await _get_confluence_config()
        if not cfg:
            return _no_auth()
        status, data = await _get(
            f"{_base_url(cfg['domain'])}/content/{page_id}",
            cfg["email"], cfg["api_token"],
            {"expand": "body.storage,version,space"},
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Page '{page_id}' not found.")
        body_html = data.get("body", {}).get("storage", {}).get("value", "")
        return ToolResult(ok=True, data={
            "id":      data.get("id"),
            "title":   data.get("title"),
            "space":   data.get("space", {}).get("key"),
            "version": data.get("version", {}).get("number"),
            "content": _strip_html(body_html),
            "url":     f"https://{cfg['domain']}/wiki{data.get('_links', {}).get('webui', '')}",
        })


# ---------------------------------------------------------------------------
# Tool 3 — List spaces
# ---------------------------------------------------------------------------

class ConfluenceListSpacesTool(Tool):
    name = "confluence_list_spaces"
    description = "List all accessible Confluence spaces — name, key, and type."
    parameters = {
        "type": "object",
        "properties": {
            "max_results": {"type": "number", "description": "Max spaces. Default 20."},
        },
        "required": [],
    }

    async def run(self, max_results: int = 20) -> ToolResult:
        cfg = await _get_confluence_config()
        if not cfg:
            return _no_auth()
        status, data = await _get(
            f"{_base_url(cfg['domain'])}/space",
            cfg["email"], cfg["api_token"],
            {"limit": min(max_results, 50), "type": "global"},
        )
        if status != 200:
            return ToolResult(ok=False, error=f"List spaces failed: {data.get('message', status)}")
        spaces = [
            {"key": s.get("key"), "name": s.get("name"), "type": s.get("type")}
            for s in data.get("results", [])
        ]
        return ToolResult(ok=True, data={"spaces": spaces, "count": len(spaces)})


# ---------------------------------------------------------------------------
# Tool 4 — Get space pages
# ---------------------------------------------------------------------------

class ConfluenceGetSpacePagesTool(Tool):
    name = "confluence_get_space_pages"
    description = "List pages inside a Confluence space by space key."
    parameters = {
        "type": "object",
        "properties": {
            "space_key":   {"type": "string", "description": "Confluence space key (e.g. 'ENG', 'HR')."},
            "max_results": {"type": "number", "description": "Max pages. Default 20."},
        },
        "required": ["space_key"],
    }

    async def run(self, space_key: str, max_results: int = 20) -> ToolResult:
        cfg = await _get_confluence_config()
        if not cfg:
            return _no_auth()
        status, data = await _get(
            f"{_base_url(cfg['domain'])}/space/{space_key}/content/page",
            cfg["email"], cfg["api_token"],
            {"limit": min(max_results, 50), "expand": "version"},
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Space '{space_key}' not found or no access.")
        pages = [
            {
                "id":      p.get("id"),
                "title":   p.get("title"),
                "version": p.get("version", {}).get("number"),
                "url":     f"https://{cfg['domain']}/wiki{p.get('_links', {}).get('webui', '')}",
            }
            for p in data.get("results", [])
        ]
        return ToolResult(ok=True, data={"space": space_key, "pages": pages, "count": len(pages)})


# ---------------------------------------------------------------------------
# Tool 5 — Create page (sensitive)
# ---------------------------------------------------------------------------

class ConfluenceCreatePageTool(Tool):
    name = "confluence_create_page"
    description = "Create a new Confluence page in a space. SENSITIVE: creates a permanent page. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "space_key": {"type": "string", "description": "Space key where the page will be created."},
            "title":     {"type": "string", "description": "Page title."},
            "content":   {"type": "string", "description": "Page body as plain text."},
            "parent_id": {"type": "string", "description": "Parent page ID. Optional — omit to create at space root."},
        },
        "required": ["space_key", "title", "content"],
    }

    async def run(self, space_key: str, title: str, content: str, parent_id: str = "") -> ToolResult:
        cfg = await _get_confluence_config()
        if not cfg:
            return _no_auth()
        html_body = content.replace("\n", "<br/>")
        body: dict = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {"storage": {"value": f"<p>{html_body}</p>", "representation": "storage"}},
        }
        if parent_id:
            body["ancestors"] = [{"id": parent_id}]
        status, data = await _post(
            f"{_base_url(cfg['domain'])}/content",
            cfg["email"], cfg["api_token"], body,
        )
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Create page failed: {data.get('message', status)}")
        return ToolResult(ok=True, data={
            "id":    data.get("id"),
            "title": data.get("title"),
            "url":   f"https://{cfg['domain']}/wiki{data.get('_links', {}).get('webui', '')}",
        })


# ---------------------------------------------------------------------------
# Tool 6 — Update page (sensitive)
# ---------------------------------------------------------------------------

class ConfluenceUpdatePageTool(Tool):
    name = "confluence_update_page"
    description = "Update an existing Confluence page title and/or content. SENSITIVE: overwrites page. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {"type": "string", "description": "Confluence page ID to update."},
            "title":   {"type": "string", "description": "New page title."},
            "content": {"type": "string", "description": "New page body as plain text."},
        },
        "required": ["page_id", "title", "content"],
    }

    async def run(self, page_id: str, title: str, content: str) -> ToolResult:
        cfg = await _get_confluence_config()
        if not cfg:
            return _no_auth()
        s, current = await _get(
            f"{_base_url(cfg['domain'])}/content/{page_id}",
            cfg["email"], cfg["api_token"], {"expand": "version"},
        )
        if s != 200:
            return ToolResult(ok=False, error=f"Page '{page_id}' not found.")
        next_version = current.get("version", {}).get("number", 0) + 1
        html_body = content.replace("\n", "<br/>")
        body = {
            "type":    "page",
            "title":   title,
            "version": {"number": next_version},
            "body": {"storage": {"value": f"<p>{html_body}</p>", "representation": "storage"}},
        }
        status, data = await _put(
            f"{_base_url(cfg['domain'])}/content/{page_id}",
            cfg["email"], cfg["api_token"], body,
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Update failed: {data.get('message', status)}")
        return ToolResult(ok=True, data={
            "id":      page_id,
            "title":   data.get("title"),
            "version": next_version,
            "url":     f"https://{cfg['domain']}/wiki{data.get('_links', {}).get('webui', '')}",
        })
