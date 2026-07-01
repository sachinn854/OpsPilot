"""
Gmail tools — real Gmail API via OAuth2.

Read tools:
  gmail_list_emails   — list recent emails (inbox/sent/label filter)
  gmail_get_email     — get full email by ID
  gmail_search_emails — search with Gmail query syntax

Write tools (sensitive=True — HITL approval required):
  gmail_send_email    — send a new email
  gmail_reply_email   — reply to an email thread
  gmail_create_draft  — save as draft
"""
import base64
from email.mime.text import MIMEText

import httpx

from backend.integrations.google_oauth import get_valid_credentials
from backend.tools.base import Tool, ToolResult

GMAIL_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="Google account not connected. Go to Settings → Connect Google.")


async def _get(path: str, token: str, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{GMAIL_BASE}/{path}", headers=_headers(token), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(path: str, token: str, body: dict) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{GMAIL_BASE}/{path}", headers={**_headers(token), "Content-Type": "application/json"}, json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _delete(path: str, token: str) -> int:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.delete(f"{GMAIL_BASE}/{path}", headers=_headers(token))
    return resp.status_code


def _decode_body(payload: dict) -> str:
    body = payload.get("body", {})
    data = body.get("data", "")
    if data:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")[:2000]
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            d = part.get("body", {}).get("data", "")
            if d:
                return base64.urlsafe_b64decode(d + "==").decode("utf-8", errors="replace")[:2000]
    return ""


def _header_val(headers: list, name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _build_raw(to: str, subject: str, body: str, reply_to_msg_id: str = "") -> str:
    msg = MIMEText(body, "plain")
    msg["to"]      = to
    msg["subject"] = subject
    if reply_to_msg_id:
        msg["In-Reply-To"] = reply_to_msg_id
        msg["References"]  = reply_to_msg_id
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


# ---------------------------------------------------------------------------
# Tool 1 — List emails
# ---------------------------------------------------------------------------

class GmailListEmailsTool(Tool):
    name = "gmail_list_emails"
    description = (
        "List recent emails from Gmail. Filter by label (INBOX, SENT, SPAM) or a custom Gmail query. "
        "Returns subject, sender, snippet, and date."
    )
    parameters = {
        "type": "object",
        "properties": {
            "label": {"type": "string", "description": "Label to filter: INBOX, SENT, STARRED, IMPORTANT. Default: INBOX."},
            "max_results": {"type": "number", "description": "Max emails to return. Default 10."},
            "query": {"type": "string", "description": "Optional Gmail search query, e.g. 'from:boss@company.com is:unread'."},
        },
        "required": [],
    }

    async def run(self, label: str = "INBOX", max_results: int = 10, query: str = "") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        token = creds["access_token"]
        params: dict = {"maxResults": min(max_results, 20), "labelIds": label.upper()}
        if query:
            params["q"] = query
            del params["labelIds"]
        status, data = await _get("messages", token, params)
        if status != 200:
            return ToolResult(ok=False, error=f"Gmail API error {status}: {data.get('error', {}).get('message', data)}")
        messages = data.get("messages", [])
        if not messages:
            return ToolResult(ok=True, data={"emails": [], "count": 0})
        emails = []
        for m in messages[:max_results]:
            s, detail = await _get(f"messages/{m['id']}", token, {"format": "metadata", "metadataHeaders": ["From","Subject","Date"]})
            if s == 200:
                hdrs = detail.get("payload", {}).get("headers", [])
                emails.append({
                    "id":      detail["id"],
                    "subject": _header_val(hdrs, "Subject"),
                    "from":    _header_val(hdrs, "From"),
                    "date":    _header_val(hdrs, "Date"),
                    "snippet": detail.get("snippet", "")[:200],
                    "thread_id": detail.get("threadId"),
                })
        return ToolResult(ok=True, data={"emails": emails, "count": len(emails), "label": label})


# ---------------------------------------------------------------------------
# Tool 2 — Get email
# ---------------------------------------------------------------------------

class GmailGetEmailTool(Tool):
    name = "gmail_get_email"
    description = "Get the full content of a Gmail email by its message ID. Returns headers and body text."
    parameters = {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "Gmail message ID (from gmail_list_emails)."},
        },
        "required": ["message_id"],
    }

    async def run(self, message_id: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status, data = await _get(f"messages/{message_id}", creds["access_token"], {"format": "full"})
        if status != 200:
            return ToolResult(ok=False, error=f"Email '{message_id}' not found.")
        hdrs = data.get("payload", {}).get("headers", [])
        body = _decode_body(data.get("payload", {}))
        return ToolResult(ok=True, data={
            "id":        data["id"],
            "thread_id": data.get("threadId"),
            "subject":   _header_val(hdrs, "Subject"),
            "from":      _header_val(hdrs, "From"),
            "to":        _header_val(hdrs, "To"),
            "date":      _header_val(hdrs, "Date"),
            "body":      body,
            "snippet":   data.get("snippet", "")[:200],
        })


# ---------------------------------------------------------------------------
# Tool 3 — Search emails
# ---------------------------------------------------------------------------

class GmailSearchEmailsTool(Tool):
    name = "gmail_search_emails"
    description = (
        "Search Gmail using Gmail query syntax. "
        "Examples: 'from:alice@co.com subject:invoice', 'is:unread after:2024/1/1', 'has:attachment'. "
        "Returns matching emails with subject, sender, and snippet."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Gmail search query."},
            "max_results": {"type": "number", "description": "Max results. Default 10."},
        },
        "required": ["query"],
    }

    async def run(self, query: str, max_results: int = 10) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        token = creds["access_token"]
        status, data = await _get("messages", token, {"q": query, "maxResults": min(max_results, 20)})
        if status != 200:
            return ToolResult(ok=False, error=f"Search failed: {data.get('error', {}).get('message', data)}")
        messages = data.get("messages", [])
        if not messages:
            return ToolResult(ok=True, data={"emails": [], "count": 0, "query": query})
        emails = []
        for m in messages[:max_results]:
            s, detail = await _get(f"messages/{m['id']}", token, {"format": "metadata", "metadataHeaders": ["From","Subject","Date"]})
            if s == 200:
                hdrs = detail.get("payload", {}).get("headers", [])
                emails.append({
                    "id":      detail["id"],
                    "subject": _header_val(hdrs, "Subject"),
                    "from":    _header_val(hdrs, "From"),
                    "date":    _header_val(hdrs, "Date"),
                    "snippet": detail.get("snippet", "")[:200],
                })
        return ToolResult(ok=True, data={"emails": emails, "count": len(emails), "query": query})


# ---------------------------------------------------------------------------
# Tool 4 — Send email (sensitive)
# ---------------------------------------------------------------------------

class GmailSendEmailTool(Tool):
    name = "gmail_send_email"
    description = "Send an email from the connected Gmail account. SENSITIVE: sends real email. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "to":      {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string", "description": "Email subject."},
            "body":    {"type": "string", "description": "Email body (plain text)."},
        },
        "required": ["to", "subject", "body"],
    }

    async def run(self, to: str, subject: str, body: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        raw = _build_raw(to, subject, body)
        status, data = await _post("messages/send", creds["access_token"], {"raw": raw})
        if status not in (200, 202):
            return ToolResult(ok=False, error=f"Send failed: {data.get('error', {}).get('message', data)}")
        return ToolResult(ok=True, data={"message_id": data.get("id"), "to": to, "subject": subject})


# ---------------------------------------------------------------------------
# Tool 5 — Reply to email (sensitive)
# ---------------------------------------------------------------------------

class GmailReplyEmailTool(Tool):
    name = "gmail_reply_email"
    description = "Reply to an existing Gmail thread. SENSITIVE: sends real email. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "The original message ID to reply to."},
            "body":       {"type": "string", "description": "Reply text."},
        },
        "required": ["message_id", "body"],
    }

    async def run(self, message_id: str, body: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        token = creds["access_token"]
        s, orig = await _get(f"messages/{message_id}", token, {"format": "metadata", "metadataHeaders": ["From","Subject","Message-ID"]})
        if s != 200:
            return ToolResult(ok=False, error=f"Original message '{message_id}' not found.")
        hdrs      = orig.get("payload", {}).get("headers", [])
        to        = _header_val(hdrs, "From")
        subject   = "Re: " + _header_val(hdrs, "Subject").removeprefix("Re: ")
        msg_id_hdr = _header_val(hdrs, "Message-ID")
        raw = _build_raw(to, subject, body, msg_id_hdr)
        body_payload = {"raw": raw, "threadId": orig.get("threadId")}
        status, data = await _post("messages/send", token, body_payload)
        if status not in (200, 202):
            return ToolResult(ok=False, error=f"Reply failed: {data.get('error', {}).get('message', data)}")
        return ToolResult(ok=True, data={"message_id": data.get("id"), "thread_id": orig.get("threadId"), "to": to})


# ---------------------------------------------------------------------------
# Tool 6 — Create draft (sensitive)
# ---------------------------------------------------------------------------

class GmailCreateDraftTool(Tool):
    name = "gmail_create_draft"
    description = "Save an email as a Gmail draft (does not send). SENSITIVE: creates a draft in the account. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "to":      {"type": "string", "description": "Recipient email address."},
            "subject": {"type": "string", "description": "Email subject."},
            "body":    {"type": "string", "description": "Email body (plain text)."},
        },
        "required": ["to", "subject", "body"],
    }

    async def run(self, to: str, subject: str, body: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        raw = _build_raw(to, subject, body)
        status, data = await _post("drafts", creds["access_token"], {"message": {"raw": raw}})
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Draft creation failed: {data.get('error', {}).get('message', data)}")
        return ToolResult(ok=True, data={"draft_id": data.get("id"), "to": to, "subject": subject})


# ---------------------------------------------------------------------------
# Tool 7 — Trash email (sensitive)
# ---------------------------------------------------------------------------

class GmailTrashEmailTool(Tool):
    name = "gmail_trash_email"
    description = "Move a Gmail email to Trash. SENSITIVE: removes email from inbox. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "Gmail message ID to trash."},
        },
        "required": ["message_id"],
    }

    async def run(self, message_id: str) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status, data = await _post(f"messages/{message_id}/trash", creds["access_token"], {})
        if status != 200:
            return ToolResult(ok=False, error=f"Failed to trash message: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"trashed": True, "message_id": message_id})


# ---------------------------------------------------------------------------
# Tool 8 — Mark read / unread
# ---------------------------------------------------------------------------

class GmailMarkReadTool(Tool):
    name = "gmail_mark_read"
    description = "Mark a Gmail email as read or unread."
    parameters = {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "Gmail message ID."},
            "read":       {"type": "boolean", "description": "True to mark as read, False to mark as unread. Default True."},
        },
        "required": ["message_id"],
    }

    async def run(self, message_id: str, read: bool = True) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        body = {"removeLabelIds": ["UNREAD"]} if read else {"addLabelIds": ["UNREAD"]}
        status, data = await _post(f"messages/{message_id}/modify", creds["access_token"], body)
        if status != 200:
            return ToolResult(ok=False, error=f"Failed to mark message: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"message_id": message_id, "marked_as": "read" if read else "unread"})


# ---------------------------------------------------------------------------
# Tool 9 — Forward email (sensitive)
# ---------------------------------------------------------------------------

class GmailForwardEmailTool(Tool):
    name = "gmail_forward_email"
    description = "Forward an existing Gmail email to another address. SENSITIVE: sends real email. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "Gmail message ID to forward."},
            "to":         {"type": "string", "description": "Recipient email address."},
            "note":       {"type": "string", "description": "Optional note to prepend to the forwarded message."},
        },
        "required": ["message_id", "to"],
    }

    async def run(self, message_id: str, to: str, note: str = "") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        token = creds["access_token"]
        s, orig = await _get(f"messages/{message_id}", token, {"format": "full"})
        if s != 200:
            return ToolResult(ok=False, error=f"Original message '{message_id}' not found.")
        hdrs    = orig.get("payload", {}).get("headers", [])
        subject = "Fwd: " + _header_val(hdrs, "Subject").removeprefix("Fwd: ")
        orig_body = _decode_body(orig.get("payload", {}))
        fwd_body  = f"{note}\n\n---------- Forwarded message ----------\n{orig_body}" if note else f"---------- Forwarded message ----------\n{orig_body}"
        raw = _build_raw(to, subject, fwd_body)
        status, data = await _post("messages/send", token, {"raw": raw})
        if status not in (200, 202):
            return ToolResult(ok=False, error=f"Forward failed: {data.get('error', {}).get('message', status)}")
        return ToolResult(ok=True, data={"message_id": data.get("id"), "forwarded_to": to, "subject": subject})


# ---------------------------------------------------------------------------
# Tool 10 — List labels
# ---------------------------------------------------------------------------

class GmailListLabelsTool(Tool):
    name = "gmail_list_labels"
    description = "List all Gmail labels and folders in the connected account."
    parameters = {"type": "object", "properties": {}, "required": []}

    async def run(self) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status, data = await _get("labels", creds["access_token"])
        if status != 200:
            return ToolResult(ok=False, error=f"Failed to list labels: {status}")
        labels = [{"id": l["id"], "name": l["name"], "type": l.get("type")} for l in data.get("labels", [])]
        return ToolResult(ok=True, data={"labels": labels, "count": len(labels)})
