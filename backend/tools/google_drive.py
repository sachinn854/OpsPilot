"""
Google Drive tools — real Drive API via OAuth2.

Read tools:
  drive_search_files  — search files by name or content
  drive_list_folder   — list files in a folder
  drive_get_file      — get file metadata
  drive_read_file     — read text content (Docs, Sheets, txt, pdf)
"""
import base64

import httpx

from backend.integrations.google_oauth import get_valid_credentials
from backend.tools.base import Tool, ToolResult

DRIVE_BASE = "https://www.googleapis.com/drive/v3"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="Google account not connected. Go to Settings → Connect Google.")


async def _post(path: str, token: str, body: dict, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{DRIVE_BASE}/{path}",
            headers={**_headers(token), "Content-Type": "application/json"},
            json=body,
            params=params or {},
        )
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _patch(path: str, token: str, body: dict, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.patch(
            f"{DRIVE_BASE}/{path}",
            headers={**_headers(token), "Content-Type": "application/json"},
            json=body,
            params=params or {},
        )
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _delete(path: str, token: str) -> int:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(f"{DRIVE_BASE}/{path}", headers=_headers(token))
    return resp.status_code


async def _get(path: str, token: str, params: dict | None = None) -> tuple[int, dict | bytes]:
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{DRIVE_BASE}/{path}", headers=_headers(token), params=params or {})
    ct = resp.headers.get("content-type", "")
    if "json" in ct:
        try:
            return resp.status_code, resp.json()
        except Exception:
            return resp.status_code, {}
    return resp.status_code, resp.content


def _fmt_file(f: dict) -> dict:
    return {
        "id":           f.get("id"),
        "name":         f.get("name"),
        "mime_type":    f.get("mimeType"),
        "size":         f.get("size"),
        "modified":     f.get("modifiedTime"),
        "web_link":     f.get("webViewLink"),
        "owner":        (f.get("owners") or [{}])[0].get("emailAddress", ""),
        "shared":       f.get("shared", False),
    }


# ---------------------------------------------------------------------------
# Tool 1 — Search files
# ---------------------------------------------------------------------------

class DriveSearchFilesTool(Tool):
    name = "drive_search_files"
    description = (
        "Search Google Drive files by name, type, or content. "
        "Examples: 'budget report', 'mimeType=application/pdf', 'name contains \"roadmap\"'. "
        "Returns file name, type, owner, and link."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query. File name, type, or Drive query syntax."},
            "max_results": {"type": "number", "description": "Max files to return. Default 10."},
            "file_type": {"type": "string", "description": "Filter by type: 'doc', 'sheet', 'slide', 'pdf', 'folder'. Optional."},
        },
        "required": ["query"],
    }

    _MIME_MAP = {
        "doc":    "application/vnd.google-apps.document",
        "sheet":  "application/vnd.google-apps.spreadsheet",
        "slide":  "application/vnd.google-apps.presentation",
        "pdf":    "application/pdf",
        "folder": "application/vnd.google-apps.folder",
    }

    async def run(self, query: str, max_results: int = 10, file_type: str = "") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        q_parts = [f"name contains '{query}' or fullText contains '{query}'"]
        if file_type and file_type.lower() in self._MIME_MAP:
            q_parts.append(f"mimeType='{self._MIME_MAP[file_type.lower()]}'")
        q_parts.append("trashed=false")
        params = {
            "q":        " and ".join(q_parts),
            "pageSize": min(max_results, 30),
            "fields":   "files(id,name,mimeType,size,modifiedTime,webViewLink,owners,shared)",
        }
        status, data = await _get("files", creds["access_token"], params)
        if status != 200 or isinstance(data, bytes):
            return ToolResult(ok=False, error=f"Drive search failed: {status}")
        files = [_fmt_file(f) for f in data.get("files", [])]
        return ToolResult(ok=True, data={"files": files, "count": len(files), "query": query})


# ---------------------------------------------------------------------------
# Tool 2 — List folder
# ---------------------------------------------------------------------------

class DriveListFolderTool(Tool):
    name = "drive_list_folder"
    description = "List files inside a specific Google Drive folder by folder ID or name."
    parameters = {
        "type": "object",
        "properties": {
            "folder_id":   {"type": "string", "description": "Google Drive folder ID. Use 'root' for My Drive."},
            "max_results": {"type": "number", "description": "Max files to return. Default 20."},
        },
        "required": ["folder_id"],
    }

    async def run(self, folder_id: str, max_results: int = 20) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        params = {
            "q":        f"'{folder_id}' in parents and trashed=false",
            "pageSize": min(max_results, 50),
            "fields":   "files(id,name,mimeType,size,modifiedTime,webViewLink)",
        }
        status, data = await _get("files", creds["access_token"], params)
        if status != 200 or isinstance(data, bytes):
            return ToolResult(ok=False, error=f"Folder listing failed: {status}")
        files = [_fmt_file(f) for f in data.get("files", [])]
        return ToolResult(ok=True, data={"folder_id": folder_id, "files": files, "count": len(files)})


# ---------------------------------------------------------------------------
# Tool 3 — Get file metadata
# ---------------------------------------------------------------------------

class DriveGetFileTool(Tool):
    name = "drive_get_file"
    description = "Get metadata of a Google Drive file by its ID — name, type, size, owner, and sharing status."
    parameters = {
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "Google Drive file ID."},
        },
        "required": ["file_id"],
    }

    async def run(self, file_id: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        params = {"fields": "id,name,mimeType,size,modifiedTime,createdTime,webViewLink,owners,shared,description"}
        status, data = await _get(f"files/{file_id}", creds["access_token"], params)
        if status != 200 or isinstance(data, bytes):
            return ToolResult(ok=False, error=f"File '{file_id}' not found.")
        return ToolResult(ok=True, data=_fmt_file(data))


# ---------------------------------------------------------------------------
# Tool 4 — Read file content
# ---------------------------------------------------------------------------

class DriveReadFileTool(Tool):
    name = "drive_read_file"
    description = "Read the text content of a Google Drive file. Works with Google Docs, plain text, and PDF files."
    parameters = {
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "Google Drive file ID."},
        },
        "required": ["file_id"],
    }

    _EXPORTABLE = {
        "application/vnd.google-apps.document":     "text/plain",
        "application/vnd.google-apps.spreadsheet":  "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    async def run(self, file_id: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        token = creds["access_token"]
        s, meta = await _get(f"files/{file_id}", token, {"fields": "mimeType,name,size"})
        if s != 200 or isinstance(meta, bytes):
            return ToolResult(ok=False, error=f"File '{file_id}' not found.")
        mime = meta.get("mimeType", "")
        name = meta.get("name", file_id)

        if mime in self._EXPORTABLE:
            export_mime = self._EXPORTABLE[mime]
            s2, content = await _get(f"files/{file_id}/export", token, {"mimeType": export_mime})
            if s2 != 200:
                return ToolResult(ok=False, error=f"Export failed: HTTP {s2}")
            text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
            return ToolResult(ok=True, data={"file_id": file_id, "name": name, "content": text[:5000]})

        if "text/" in mime:
            s2, content = await _get(f"files/{file_id}", token, {"alt": "media"})
            if s2 != 200:
                return ToolResult(ok=False, error=f"Download failed: HTTP {s2}")
            text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
            return ToolResult(ok=True, data={"file_id": file_id, "name": name, "content": text[:5000]})

        return ToolResult(ok=False, error=f"Cannot read file type '{mime}'. Supported: Google Docs, Sheets, Slides, plain text.")


# ---------------------------------------------------------------------------
# Tool 5 — Create folder (sensitive)
# ---------------------------------------------------------------------------

class DriveCreateFolderTool(Tool):
    name = "drive_create_folder"
    description = "Create a new folder in Google Drive. SENSITIVE: creates a permanent folder. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "name":      {"type": "string", "description": "Folder name."},
            "parent_id": {"type": "string", "description": "Parent folder ID. Omit to create in My Drive root."},
        },
        "required": ["name"],
    }

    async def run(self, name: str, parent_id: str = "") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        body: dict = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id:
            body["parents"] = [parent_id]
        status, data = await _post("files", creds["access_token"], body,
                                   params={"fields": "id,name,webViewLink"})
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Failed to create folder: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"folder_id": data.get("id"), "name": data.get("name"), "link": data.get("webViewLink")})


# ---------------------------------------------------------------------------
# Tool 6 — Share file (sensitive)
# ---------------------------------------------------------------------------

class DriveShareFileTool(Tool):
    name = "drive_share_file"
    description = "Share a Google Drive file or folder with a user or make it publicly accessible. SENSITIVE: changes file permissions. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "Google Drive file or folder ID."},
            "email":   {"type": "string", "description": "Email address to share with. Omit to make publicly readable."},
            "role":    {"type": "string", "description": "Permission role: 'reader', 'commenter', 'writer'. Default: reader."},
        },
        "required": ["file_id"],
    }

    async def run(self, file_id: str, email: str = "", role: str = "reader") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        body: dict = {"role": role}
        if email:
            body["type"] = "user"
            body["emailAddress"] = email
        else:
            body["type"] = "anyone"
        status, data = await _post(f"files/{file_id}/permissions", creds["access_token"], body,
                                   params={"fields": "id,role,type,emailAddress"})
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Share failed: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"file_id": file_id, "shared_with": email or "anyone", "role": role})


# ---------------------------------------------------------------------------
# Tool 7 — Delete file (sensitive)
# ---------------------------------------------------------------------------

class DriveDeleteFileTool(Tool):
    name = "drive_delete_file"
    description = "Permanently delete a Google Drive file or folder. SENSITIVE: cannot be undone. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "file_id": {"type": "string", "description": "Google Drive file or folder ID to delete."},
        },
        "required": ["file_id"],
    }

    async def run(self, file_id: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status = await _delete(f"files/{file_id}", creds["access_token"])
        if status == 204:
            return ToolResult(ok=True, data={"deleted": True, "file_id": file_id})
        if status == 404:
            return ToolResult(ok=False, error=f"File '{file_id}' not found.")
        return ToolResult(ok=False, error=f"Delete failed. Status: {status}")


# ---------------------------------------------------------------------------
# Tool 8 — Move file (sensitive)
# ---------------------------------------------------------------------------

class DriveMoveFileTool(Tool):
    name = "drive_move_file"
    description = "Move a Google Drive file to a different folder. SENSITIVE: changes file location. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "file_id":          {"type": "string", "description": "Google Drive file ID to move."},
            "new_parent_id":    {"type": "string", "description": "Destination folder ID."},
        },
        "required": ["file_id", "new_parent_id"],
    }

    async def run(self, file_id: str, new_parent_id: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        s, meta = await _get(f"files/{file_id}", creds["access_token"], {"fields": "parents"})
        if s != 200 or isinstance(meta, bytes):
            return ToolResult(ok=False, error=f"File '{file_id}' not found.")
        old_parents = ",".join(meta.get("parents", []))
        status, data = await _patch(
            f"files/{file_id}",
            creds["access_token"],
            {},
            params={"addParents": new_parent_id, "removeParents": old_parents, "fields": "id,name,parents"},
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Move failed: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"file_id": file_id, "moved_to": new_parent_id})
