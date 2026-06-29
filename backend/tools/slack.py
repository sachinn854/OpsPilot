"""
Slack tools — real Slack API via bot token.

Read tools (no approval needed):
  slack_post_message     — post a message to any channel
  slack_list_channels    — list all public + private channels the bot is in
  slack_get_messages     — read recent messages from a channel
  slack_send_dm          — send a direct message to a user (by email)
  slack_search_messages  — search messages across the workspace
  slack_get_user_info    — get a user's name, email, status by email

Write tools (sensitive=True → HITL approval required):
  slack_create_channel   — create a new public/private channel
  slack_set_topic        — update a channel's topic

Token: Bot OAuth token (xoxb-...).
  - Set SLACK_TOKEN in .env  OR  connect via Settings page (stored encrypted in DB).
  - Required scopes: channels:read, channels:write, chat:write, files:write,
    groups:read, im:write, mpim:write, search:read, users:read, users:read.email
"""
import httpx

from backend.config import settings
from backend.tools.base import Tool, ToolResult

SLACK_API = "https://slack.com/api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def _get_org_token(org_id: str = "default") -> str | None:
    """Fetch Slack token from DB for this org. Falls back to .env SLACK_TOKEN."""
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        async with AsyncSessionLocal() as session:
            return await get_token(session, org_id=org_id, service="slack")
    except Exception:
        return None


async def _token(org_id: str = "default") -> str | None:
    """Return the best available token: DB → .env."""
    return await _get_org_token(org_id) or settings.SLACK_TOKEN or None


async def _get(method: str, params: dict | None = None, token: str = "") -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            f"{SLACK_API}/{method}",
            headers=_headers(token),
            params=params or {},
        )
    return resp.status_code, resp.json() if resp.status_code == 200 else {}


async def _post(method: str, body: dict, token: str = "") -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(
            f"{SLACK_API}/{method}",
            headers=_headers(token),
            json=body,
        )
    return resp.status_code, resp.json() if resp.status_code == 200 else {}


def _no_token_error() -> ToolResult:
    return ToolResult(
        ok=False,
        error="Slack token not configured. Connect Slack via Settings page or set SLACK_TOKEN in .env.",
    )


def _slack_error(data: dict) -> ToolResult:
    return ToolResult(ok=False, error=f"Slack API error: {data.get('error', 'unknown')}")


async def _resolve_channel(name: str, tok: str) -> str | None:
    """Resolve channel name (#ops or ops) → channel ID. Returns ID as-is if already one."""
    if name.startswith(("C", "D", "G", "W")):
        return name
    name = name.lstrip("#")
    _, data = await _get("conversations.list", {"limit": 200, "exclude_archived": "true", "types": "public_channel,private_channel"}, tok)
    for ch in data.get("channels", []):
        if ch.get("name") == name:
            return ch["id"]
    return None


# ---------------------------------------------------------------------------
# Tool 1 — Post message
# ---------------------------------------------------------------------------

class SlackPostMessageTool(Tool):
    name = "slack_post_message"
    description = (
        "Post a message to a Slack channel or thread. "
        "Use for alerts, reports, and notifications."
    )
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name (e.g. '#ops') or channel ID."},
            "text": {"type": "string", "description": "Message text. Slack markdown supported (*bold*, `code`)."},
            "thread_ts": {"type": "string", "description": "Thread timestamp to reply in a thread (optional)."},
        },
        "required": ["channel", "text"],
    }

    async def run(self, channel: str, text: str, thread_ts: str | None = None) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        channel_id = await _resolve_channel(channel, tok) or channel
        body: dict = {"channel": channel_id, "text": text}
        if thread_ts:
            body["thread_ts"] = thread_ts

        status, data = await _post("chat.postMessage", body, tok)
        if status != 200 or not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={
            "channel": data.get("channel"),
            "ts": data.get("ts"),
            "message": text[:100],
        })


# ---------------------------------------------------------------------------
# Tool 2 — List channels
# ---------------------------------------------------------------------------

class SlackListChannelsTool(Tool):
    name = "slack_list_channels"
    description = (
        "List Slack channels the bot has access to. "
        "Returns channel names, IDs, member counts, and topic."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "number", "description": "Max channels to return. Default 50."},
            "types": {"type": "string", "description": "Channel types: 'public_channel', 'private_channel', or both comma-separated. Default: public_channel."},
        },
        "required": [],
    }

    async def run(self, limit: int = 50, types: str = "public_channel,private_channel") -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        _, data = await _get("conversations.list", {
            "limit": min(limit, 200),
            "exclude_archived": "true",
            "types": types,
        }, tok)
        if not data.get("ok"):
            return _slack_error(data)

        channels = [
            {
                "id": ch["id"],
                "name": ch["name"],
                "is_private": ch.get("is_private", False),
                "num_members": ch.get("num_members", 0),
                "topic": ch.get("topic", {}).get("value", ""),
            }
            for ch in data.get("channels", [])
        ]
        return ToolResult(ok=True, data={"channels": channels, "count": len(channels)})


# ---------------------------------------------------------------------------
# Tool 3 — Get channel messages
# ---------------------------------------------------------------------------

class SlackGetMessagesTool(Tool):
    name = "slack_get_messages"
    description = (
        "Fetch recent messages from a Slack channel. "
        "Returns message text, author, and timestamp."
    )
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name (e.g. '#ops') or channel ID."},
            "limit": {"type": "number", "description": "Number of messages to fetch. Default 20, max 50."},
        },
        "required": ["channel"],
    }

    async def run(self, channel: str, limit: int = 20) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        channel_id = await _resolve_channel(channel, tok)
        if not channel_id:
            return ToolResult(ok=False, error=f"Channel '{channel}' not found.")

        _, data = await _get("conversations.history", {
            "channel": channel_id,
            "limit": min(limit, 50),
        }, tok)
        if not data.get("ok"):
            return _slack_error(data)

        messages = [
            {
                "ts": m.get("ts"),
                "user": m.get("user"),
                "text": m.get("text", "")[:500],
                "reply_count": m.get("reply_count", 0),
            }
            for m in data.get("messages", [])
            if m.get("type") == "message" and not m.get("subtype")
        ]
        return ToolResult(ok=True, data={"channel": channel, "messages": messages, "count": len(messages)})


# ---------------------------------------------------------------------------
# Tool 4 — Send DM
# ---------------------------------------------------------------------------

class SlackSendDMTool(Tool):
    name = "slack_send_dm"
    description = (
        "Send a direct message to a Slack user identified by their email address."
    )
    parameters = {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The recipient's email address."},
            "text": {"type": "string", "description": "Message text to send."},
        },
        "required": ["email", "text"],
    }

    async def run(self, email: str, text: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        # Resolve email → user ID
        _, udata = await _get("users.lookupByEmail", {"email": email}, tok)
        if not udata.get("ok"):
            return ToolResult(ok=False, error=f"User with email '{email}' not found in Slack.")

        user_id = udata["user"]["id"]

        # Open a DM channel
        _, im_data = await _post("conversations.open", {"users": user_id}, tok)
        if not im_data.get("ok"):
            return _slack_error(im_data)

        dm_channel = im_data["channel"]["id"]
        _, msg_data = await _post("chat.postMessage", {"channel": dm_channel, "text": text}, tok)
        if not msg_data.get("ok"):
            return _slack_error(msg_data)

        return ToolResult(ok=True, data={
            "to": email,
            "user_id": user_id,
            "ts": msg_data.get("ts"),
        })


# ---------------------------------------------------------------------------
# Tool 5 — Search messages
# ---------------------------------------------------------------------------

class SlackSearchMessagesTool(Tool):
    name = "slack_search_messages"
    description = (
        "Search Slack messages across the workspace. "
        "Returns matching messages with channel and timestamp."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query (Slack search syntax supported, e.g. 'deploy in:#ops')."},
            "limit": {"type": "number", "description": "Max results. Default 10."},
        },
        "required": ["query"],
    }

    async def run(self, query: str, limit: int = 10) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        _, data = await _get("search.messages", {"query": query, "count": min(limit, 20)}, tok)
        if not data.get("ok"):
            return _slack_error(data)

        matches = data.get("messages", {}).get("matches", [])
        results = [
            {
                "channel": m.get("channel", {}).get("name"),
                "ts": m.get("ts"),
                "text": m.get("text", "")[:400],
                "username": m.get("username"),
                "permalink": m.get("permalink"),
            }
            for m in matches
        ]
        return ToolResult(ok=True, data={"query": query, "results": results, "count": len(results)})


# ---------------------------------------------------------------------------
# Tool 6 — Get user info
# ---------------------------------------------------------------------------

class SlackGetUserInfoTool(Tool):
    name = "slack_get_user_info"
    description = (
        "Look up a Slack user's profile by their email address. "
        "Returns name, display name, title, status, and timezone."
    )
    parameters = {
        "type": "object",
        "properties": {
            "email": {"type": "string", "description": "The user's email address."},
        },
        "required": ["email"],
    }

    async def run(self, email: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        _, data = await _get("users.lookupByEmail", {"email": email}, tok)
        if not data.get("ok"):
            return ToolResult(ok=False, error=f"No Slack user found for email '{email}'.")

        u = data["user"]
        profile = u.get("profile", {})
        return ToolResult(ok=True, data={
            "id": u.get("id"),
            "name": u.get("name"),
            "real_name": profile.get("real_name"),
            "display_name": profile.get("display_name"),
            "title": profile.get("title"),
            "email": profile.get("email"),
            "status_text": profile.get("status_text"),
            "timezone": u.get("tz"),
            "is_admin": u.get("is_admin", False),
        })


# ---------------------------------------------------------------------------
# Tool 7 — Upload file / snippet  (sensitive=False — no system change)
# ---------------------------------------------------------------------------

class SlackUploadFileTool(Tool):
    name = "slack_upload_file"
    description = (
        "Upload a text snippet or file content to a Slack channel. "
        "Great for sharing logs, reports, or code blocks."
    )
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID to share the file in."},
            "content": {"type": "string", "description": "Text content to upload (max 1 MB)."},
            "filename": {"type": "string", "description": "Filename to display, e.g. 'report.txt'."},
            "title": {"type": "string", "description": "Title shown above the snippet."},
        },
        "required": ["channel", "content"],
    }

    async def run(
        self,
        channel: str,
        content: str,
        filename: str = "snippet.txt",
        title: str = "",
    ) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        channel_id = await _resolve_channel(channel, tok) or channel

        # Step 1: get upload URL
        _, url_data = await _post("files.getUploadURLExternal", {
            "filename": filename,
            "length": len(content.encode()),
        }, tok)
        if not url_data.get("ok"):
            return _slack_error(url_data)

        upload_url = url_data["upload_url"]
        file_id = url_data["file_id"]

        # Step 2: PUT content to upload URL
        async with httpx.AsyncClient(timeout=30) as client:
            put_resp = await client.put(upload_url, content=content.encode())
        if put_resp.status_code not in (200, 204):
            return ToolResult(ok=False, error=f"File upload failed: HTTP {put_resp.status_code}")

        # Step 3: complete upload + share to channel
        complete_body: dict = {
            "files": [{"id": file_id, "title": title or filename}],
            "channel_id": channel_id,
        }
        _, complete_data = await _post("files.completeUploadExternal", complete_body, tok)
        if not complete_data.get("ok"):
            return _slack_error(complete_data)

        return ToolResult(ok=True, data={
            "file_id": file_id,
            "channel": channel,
            "filename": filename,
        })


# ---------------------------------------------------------------------------
# Tool 8 — Create channel (SENSITIVE)
# ---------------------------------------------------------------------------

class SlackCreateChannelTool(Tool):
    name = "slack_create_channel"
    description = (
        "Create a new Slack channel. SENSITIVE: permanently changes the workspace. "
        "Requires human approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Channel name (lowercase, no spaces, e.g. 'incident-2024-db')."},
            "is_private": {"type": "boolean", "description": "Create as private channel. Default false."},
        },
        "required": ["name"],
    }
    sensitive = True

    async def run(self, name: str, is_private: bool = False) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        clean_name = name.lower().replace(" ", "-").lstrip("#")
        _, data = await _post("conversations.create", {"name": clean_name, "is_private": is_private}, tok)
        if not data.get("ok"):
            return _slack_error(data)

        ch = data.get("channel", {})
        return ToolResult(ok=True, data={
            "id": ch.get("id"),
            "name": ch.get("name"),
            "is_private": ch.get("is_private"),
        })


# ---------------------------------------------------------------------------
# Tool 9 — Set channel topic (SENSITIVE)
# ---------------------------------------------------------------------------

class SlackSetTopicTool(Tool):
    name = "slack_set_topic"
    description = (
        "Update the topic of a Slack channel. SENSITIVE: modifies channel metadata. "
        "Requires human approval."
    )
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "topic": {"type": "string", "description": "New topic text."},
        },
        "required": ["channel", "topic"],
    }
    sensitive = True

    async def run(self, channel: str, topic: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()

        channel_id = await _resolve_channel(channel, tok)
        if not channel_id:
            return ToolResult(ok=False, error=f"Channel '{channel}' not found.")

        _, data = await _post("conversations.setTopic", {"channel": channel_id, "topic": topic}, tok)
        if not data.get("ok"):
            return _slack_error(data)

        return ToolResult(ok=True, data={"channel": channel, "topic": topic})
