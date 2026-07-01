"""
Google Sheets tools — real Sheets API via OAuth2.

Read tools:
  sheets_get_info    — get spreadsheet metadata and sheet names
  sheets_read_range  — read cell range (returns rows as arrays)

Write tools (sensitive=True — HITL approval required):
  sheets_append_row  — append a row to a sheet
  sheets_update_cell — update a specific cell or range
"""
import httpx

from backend.integrations.google_oauth import get_valid_credentials
from backend.tools.base import Tool, ToolResult

SHEETS_BASE = "https://sheets.googleapis.com/v4/spreadsheets"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="Google account not connected. Go to Settings → Connect Google.")


async def _get(url: str, token: str, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, headers=_headers(token), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(url: str, token: str, body: dict, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=_headers(token), json=body, params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _delete(url: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request("DELETE", url, headers=_headers(token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _put(url: str, token: str, body: dict, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.put(url, headers=_headers(token), json=body, params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


# ---------------------------------------------------------------------------
# Tool 1 — Get spreadsheet info
# ---------------------------------------------------------------------------

class SheetsGetInfoTool(Tool):
    name = "sheets_get_info"
    description = "Get Google Sheets spreadsheet metadata — title, sheet names, and row/column counts."
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID (from the URL: /spreadsheets/d/{ID}/)."},
        },
        "required": ["spreadsheet_id"],
    }

    async def run(self, spreadsheet_id: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status, data = await _get(f"{SHEETS_BASE}/{spreadsheet_id}", creds["access_token"],
                                   {"fields": "spreadsheetId,properties.title,sheets.properties"})
        if status != 200:
            return ToolResult(ok=False, error=f"Spreadsheet '{spreadsheet_id}' not found or no access.")
        sheets = [
            {
                "sheet_id":   s["properties"].get("sheetId"),
                "title":      s["properties"].get("title"),
                "row_count":  s["properties"].get("gridProperties", {}).get("rowCount"),
                "col_count":  s["properties"].get("gridProperties", {}).get("columnCount"),
            }
            for s in data.get("sheets", [])
        ]
        return ToolResult(ok=True, data={
            "spreadsheet_id": data.get("spreadsheetId"),
            "title":          data.get("properties", {}).get("title"),
            "sheets":         sheets,
        })


# ---------------------------------------------------------------------------
# Tool 2 — Read range
# ---------------------------------------------------------------------------

class SheetsReadRangeTool(Tool):
    name = "sheets_read_range"
    description = (
        "Read a cell range from a Google Sheet. "
        "Range examples: 'Sheet1!A1:D10', 'A1:Z100', 'Sheet1'. "
        "Returns rows as arrays of values."
    )
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
            "range":          {"type": "string", "description": "A1 notation range, e.g. 'Sheet1!A1:E20'."},
        },
        "required": ["spreadsheet_id", "range"],
    }

    async def run(self, spreadsheet_id: str, range: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status, data = await _get(
            f"{SHEETS_BASE}/{spreadsheet_id}/values/{range}",
            creds["access_token"],
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Could not read range '{range}': {data.get('error', {}).get('message', status)}")
        rows = data.get("values", [])
        return ToolResult(ok=True, data={
            "spreadsheet_id": spreadsheet_id,
            "range":          data.get("range", range),
            "rows":           rows[:200],
            "row_count":      len(rows),
        })


# ---------------------------------------------------------------------------
# Tool 3 — Append row (sensitive)
# ---------------------------------------------------------------------------

class SheetsAppendRowTool(Tool):
    name = "sheets_append_row"
    description = "Append a new row to a Google Sheet. SENSITIVE: modifies spreadsheet data. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
            "sheet_name":     {"type": "string", "description": "Sheet tab name, e.g. 'Sheet1'."},
            "values":         {"type": "array", "items": {}, "description": "Row values as an array, e.g. ['Alice', '2024-01-01', 'Done']."},
        },
        "required": ["spreadsheet_id", "sheet_name", "values"],
    }

    async def run(self, spreadsheet_id: str, sheet_name: str, values: list) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        range_str = f"{sheet_name}!A1"
        status, data = await _post(
            f"{SHEETS_BASE}/{spreadsheet_id}/values/{range_str}:append",
            creds["access_token"],
            {"values": [values]},
            params={"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"},
        )
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Append failed: {data.get('error', {}).get('message', status)}")
        updates = data.get("updates", {})
        return ToolResult(ok=True, data={
            "spreadsheet_id":  spreadsheet_id,
            "updated_range":   updates.get("updatedRange"),
            "updated_rows":    updates.get("updatedRows"),
            "values":          values,
        })


# ---------------------------------------------------------------------------
# Tool 4 — Update cell (sensitive)
# ---------------------------------------------------------------------------

class SheetsUpdateCellTool(Tool):
    name = "sheets_update_cell"
    description = "Update a specific cell or range in a Google Sheet. SENSITIVE: modifies spreadsheet data. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
            "range":          {"type": "string", "description": "A1 notation, e.g. 'Sheet1!B2' or 'Sheet1!A1:C1'."},
            "values":         {"type": "array", "items": {}, "description": "Values to write. For single cell: [['value']]. For row: [['a','b','c']]."},
        },
        "required": ["spreadsheet_id", "range", "values"],
    }

    async def run(self, spreadsheet_id: str, range: str, values: list) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        nested = values if values and isinstance(values[0], list) else [values]
        status, data = await _put(
            f"{SHEETS_BASE}/{spreadsheet_id}/values/{range}",
            creds["access_token"],
            {"range": range, "majorDimension": "ROWS", "values": nested},
            params={"valueInputOption": "USER_ENTERED"},
        )
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Update failed: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={
            "spreadsheet_id": spreadsheet_id,
            "updated_range":  data.get("updatedRange"),
            "updated_cells":  data.get("updatedCells"),
        })


# ---------------------------------------------------------------------------
# Tool 5 — Create spreadsheet (sensitive)
# ---------------------------------------------------------------------------

class SheetsCreateSpreadsheetTool(Tool):
    name = "sheets_create_spreadsheet"
    description = "Create a new Google Sheets spreadsheet. SENSITIVE: creates a new file in Drive. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "title":       {"type": "string", "description": "Spreadsheet title."},
            "sheet_names": {"type": "array", "items": {"type": "string"}, "description": "Tab names to create. Default: ['Sheet1']."},
        },
        "required": ["title"],
    }

    async def run(self, title: str, sheet_names: list[str] | None = None) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        sheets = [{"properties": {"title": n}} for n in (sheet_names or ["Sheet1"])]
        body = {"properties": {"title": title}, "sheets": sheets}
        status, data = await _post(SHEETS_BASE, creds["access_token"], body)
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Create failed: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={
            "spreadsheet_id": data.get("spreadsheetId"),
            "title":          data.get("properties", {}).get("title"),
            "url":            data.get("spreadsheetUrl"),
        })


# ---------------------------------------------------------------------------
# Tool 6 — Clear range (sensitive)
# ---------------------------------------------------------------------------

class SheetsClearRangeTool(Tool):
    name = "sheets_clear_range"
    description = "Clear all values in a cell range in a Google Sheet. SENSITIVE: deletes data. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
            "range":          {"type": "string", "description": "A1 notation range to clear, e.g. 'Sheet1!A1:D10'."},
        },
        "required": ["spreadsheet_id", "range"],
    }

    async def run(self, spreadsheet_id: str, range: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status, data = await _post(
            f"{SHEETS_BASE}/{spreadsheet_id}/values/{range}:clear",
            creds["access_token"],
            {},
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Clear failed: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"spreadsheet_id": spreadsheet_id, "cleared_range": data.get("clearedRange", range)})


# ---------------------------------------------------------------------------
# Tool 7 — Delete row (sensitive)
# ---------------------------------------------------------------------------

class SheetsDeleteRowTool(Tool):
    name = "sheets_delete_row"
    description = "Delete one or more rows from a Google Sheet by row index. SENSITIVE: permanently removes rows. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "spreadsheet_id": {"type": "string", "description": "The spreadsheet ID."},
            "sheet_id":       {"type": "number", "description": "Numeric sheet ID (from sheets_get_info). Default 0 (first sheet)."},
            "start_row":      {"type": "number", "description": "0-based row index to start deleting from."},
            "end_row":        {"type": "number", "description": "0-based row index to stop deleting at (exclusive). Omit to delete one row."},
        },
        "required": ["spreadsheet_id", "start_row"],
    }

    async def run(self, spreadsheet_id: str, start_row: int, sheet_id: int = 0, end_row: int | None = None) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        if end_row is None:
            end_row = start_row + 1
        body = {
            "requests": [{
                "deleteDimension": {
                    "range": {
                        "sheetId":    sheet_id,
                        "dimension":  "ROWS",
                        "startIndex": start_row,
                        "endIndex":   end_row,
                    }
                }
            }]
        }
        status, data = await _post(
            f"{SHEETS_BASE}/{spreadsheet_id}:batchUpdate",
            creds["access_token"],
            body,
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Delete row failed: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"spreadsheet_id": spreadsheet_id, "deleted_rows": f"{start_row}-{end_row}"})
