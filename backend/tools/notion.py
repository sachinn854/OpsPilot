"""
Notion tools — real Notion API v1 via integration token.

Read tools:
  notion_search          — search pages and databases
  notion_get_page        — get page properties
  notion_get_page_content — read blocks/content of a page
  notion_query_database  — query a Notion database with filters

Write tools (sensitive=True — HITL approval required):
  notion_create_page     — create a page inside a parent page or database
  notion_update_page     — update page title or properties
  notion_append_block    — append text/content blocks to a page

Config: stored as JSON in integration_tokens (service="notion"):
  {"token": "secret_..."}
"""
import json

import httpx

from backend.tools.base import Tool, ToolResult

NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


async def _get_notion_token(org_id: str = "default") -> str | None:
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            raw = await get_token(session, org_id=org_id, service="notion")
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
        "Notion-Version": NOTION_VERSION,
    }


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="Notion not connected. Go to Settings → Connect Notion.")


async def _get(path: str, token: str, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{NOTION_BASE}/{path}", headers=_headers(token), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(path: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{NOTION_BASE}/{path}", headers=_headers(token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _patch(path: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.patch(f"{NOTION_BASE}/{path}", headers=_headers(token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


def _extract_title(page: dict) -> str:
    props = page.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            items = prop.get("title", [])
            return "".join(t.get("plain_text", "") for t in items)
    return page.get("id", "")


def _extract_text_from_blocks(blocks: list) -> str:
    lines = []
    for block in blocks:
        btype = block.get("type", "")
        content = block.get(btype, {})
        rich = content.get("rich_text", [])
        text = "".join(t.get("plain_text", "") for t in rich)
        if text:
            lines.append(text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tool 1 — Search
# ---------------------------------------------------------------------------

class NotionSearchTool(Tool):
    name = "notion_search"
    description = (
        "Search Notion pages and databases by keyword. "
        "Returns page titles, IDs, and URLs."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query":       {"type": "string", "description": "Search query."},
            "filter_type": {"type": "string", "description": "Filter by type: 'page' or 'database'. Omit for both."},
            "max_results": {"type": "number", "description": "Max results. Default 10."},
        },
        "required": ["query"],
    }

    async def run(self, query: str, filter_type: str = "", max_results: int = 10) -> ToolResult:
        token = await _get_notion_token()
        if not token:
            return _no_auth()
        body: dict = {"query": query, "page_size": min(max_results, 20)}
        if filter_type in ("page", "database"):
            body["filter"] = {"property": "object", "value": filter_type}
        status, data = await _post("search", token, body)
        if status != 200:
            return ToolResult(ok=False, error=f"Notion search failed: {data.get('message', status)}")
        results = []
        for item in data.get("results", []):
            results.append({
                "id":    item.get("id"),
                "type":  item.get("object"),
                "title": _extract_title(item),
                "url":   item.get("url"),
            })
        return ToolResult(ok=True, data={"results": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Tool 2 — Get page
# ---------------------------------------------------------------------------

class NotionGetPageTool(Tool):
    name = "notion_get_page"
    description = "Get Notion page properties and metadata by page ID."
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {"type": "string", "description": "Notion page ID (from URL or search)."},
        },
        "required": ["page_id"],
    }

    async def run(self, page_id: str) -> ToolResult:
        token = await _get_notion_token()
        if not token:
            return _no_auth()
        status, data = await _get(f"pages/{page_id}", token)
        if status != 200:
            return ToolResult(ok=False, error=f"Page '{page_id}' not found.")
        return ToolResult(ok=True, data={
            "id":    data.get("id"),
            "title": _extract_title(data),
            "url":   data.get("url"),
            "created": data.get("created_time"),
            "edited":  data.get("last_edited_time"),
        })


# ---------------------------------------------------------------------------
# Tool 3 — Get page content (blocks)
# ---------------------------------------------------------------------------

class NotionGetPageContentTool(Tool):
    name = "notion_get_page_content"
    description = "Read the full text content of a Notion page by page ID."
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {"type": "string", "description": "Notion page ID."},
        },
        "required": ["page_id"],
    }

    async def run(self, page_id: str) -> ToolResult:
        token = await _get_notion_token()
        if not token:
            return _no_auth()
        status, data = await _get(f"blocks/{page_id}/children", token, {"page_size": "100"})
        if status != 200:
            return ToolResult(ok=False, error=f"Could not read page content: {data.get('message', status)}")
        blocks = data.get("results", [])
        text = _extract_text_from_blocks(blocks)
        return ToolResult(ok=True, data={
            "page_id":    page_id,
            "content":    text[:5000],
            "block_count": len(blocks),
        })


# ---------------------------------------------------------------------------
# Tool 4 — Query database
# ---------------------------------------------------------------------------

class NotionQueryDatabaseTool(Tool):
    name = "notion_query_database"
    description = (
        "Query a Notion database and return rows/entries. "
        "Useful for reading task lists, CRM tables, project trackers."
    )
    parameters = {
        "type": "object",
        "properties": {
            "database_id": {"type": "string", "description": "Notion database ID."},
            "max_results": {"type": "number", "description": "Max rows to return. Default 20."},
        },
        "required": ["database_id"],
    }

    async def run(self, database_id: str, max_results: int = 20) -> ToolResult:
        token = await _get_notion_token()
        if not token:
            return _no_auth()
        body = {"page_size": min(max_results, 50)}
        status, data = await _post(f"databases/{database_id}/query", token, body)
        if status != 200:
            return ToolResult(ok=False, error=f"Database query failed: {data.get('message', status)}")
        rows = []
        for item in data.get("results", []):
            rows.append({
                "id":    item.get("id"),
                "title": _extract_title(item),
                "url":   item.get("url"),
                "created": item.get("created_time"),
                "edited":  item.get("last_edited_time"),
            })
        return ToolResult(ok=True, data={"rows": rows, "count": len(rows), "database_id": database_id})


# ---------------------------------------------------------------------------
# Tool 5 — Create page (sensitive)
# ---------------------------------------------------------------------------

class NotionCreatePageTool(Tool):
    name = "notion_create_page"
    description = "Create a new Notion page inside a parent page or database. SENSITIVE: creates a new page. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "parent_id":   {"type": "string", "description": "ID of the parent page or database."},
            "parent_type": {"type": "string", "description": "'page' or 'database'. Default: page."},
            "title":       {"type": "string", "description": "Page title."},
            "content":     {"type": "string", "description": "Optional initial text content for the page body."},
        },
        "required": ["parent_id", "title"],
    }

    async def run(self, parent_id: str, title: str, parent_type: str = "page", content: str = "") -> ToolResult:
        token = await _get_notion_token()
        if not token:
            return _no_auth()
        parent_key = "database_id" if parent_type == "database" else "page_id"
        body: dict = {
            "parent": {parent_key: parent_id},
            "properties": {
                "title": {"title": [{"text": {"content": title}}]}
            },
        }
        if content:
            body["children"] = [{
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": content[:2000]}}]},
            }]
        status, data = await _post("pages", token, body)
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Create page failed: {data.get('message', status)}")
        return ToolResult(ok=True, data={
            "id":    data.get("id"),
            "title": title,
            "url":   data.get("url"),
        })


# ---------------------------------------------------------------------------
# Tool 6 — Update page (sensitive)
# ---------------------------------------------------------------------------

class NotionUpdatePageTool(Tool):
    name = "notion_update_page"
    description = "Update a Notion page title or archive it. SENSITIVE: modifies existing page. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "page_id":  {"type": "string", "description": "Notion page ID to update."},
            "title":    {"type": "string", "description": "New title for the page."},
            "archived": {"type": "boolean", "description": "Set true to archive (soft-delete) the page."},
        },
        "required": ["page_id"],
    }

    async def run(self, page_id: str, title: str = "", archived: bool = False) -> ToolResult:
        token = await _get_notion_token()
        if not token:
            return _no_auth()
        body: dict = {}
        if title:
            body["properties"] = {"title": {"title": [{"text": {"content": title}}]}}
        if archived:
            body["archived"] = True
        if not body:
            return ToolResult(ok=False, error="Provide at least 'title' or 'archived' to update.")
        status, data = await _patch(f"pages/{page_id}", token, body)
        if status != 200:
            return ToolResult(ok=False, error=f"Update failed: {data.get('message', status)}")
        return ToolResult(ok=True, data={"id": page_id, "updated": True, "url": data.get("url")})


# ---------------------------------------------------------------------------
# Tool 7 — Append block (sensitive)
# ---------------------------------------------------------------------------

class NotionAppendBlockTool(Tool):
    name = "notion_append_block"
    description = "Append text content to an existing Notion page. SENSITIVE: modifies page content. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "page_id": {"type": "string", "description": "Notion page ID to append content to."},
            "content": {"type": "string", "description": "Text content to append as a paragraph."},
        },
        "required": ["page_id", "content"],
    }

    async def run(self, page_id: str, content: str) -> ToolResult:
        token = await _get_notion_token()
        if not token:
            return _no_auth()
        body = {
            "children": [{
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": content[:2000]}}]},
            }]
        }
        status, data = await _patch(f"blocks/{page_id}/children", token, body)
        if status != 200:
            return ToolResult(ok=False, error=f"Append failed: {data.get('message', status)}")
        return ToolResult(ok=True, data={"page_id": page_id, "appended": True})
