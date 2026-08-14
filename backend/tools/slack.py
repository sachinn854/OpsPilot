"""
Slack tools — real Slack API via bot token.

Read tools:
  slack_post_message       — post a message to any channel
  slack_list_channels      — list channels the bot is in
  slack_get_messages       — read recent messages (with display names)
  slack_get_thread         — read thread replies
  slack_send_dm            — DM a user by email or display name
  slack_search_messages    — full-text search across workspace
  slack_get_user_info      — user profile by email
  slack_list_users         — list workspace members
  slack_add_reaction       — add emoji reaction to a message
  slack_upload_file        — upload a text snippet/file

Write tools (sensitive=True → HITL approval required):
  slack_create_channel     — create a new channel
  slack_set_topic          — update channel topic
  slack_invite_to_channel  — invite a user to a channel
  slack_update_message     — edit a previously sent message
  slack_delete_message     — delete a message
  slack_pin_message        — pin a message in a channel
  slack_schedule_message   — schedule a message for later

Token: Bot OAuth token (xoxb-...).
  - Set SLACK_TOKEN in .env  OR  connect via Settings page (stored encrypted in DB).
  - Required scopes: channels:read, channels:write, chat:write, chat:write.customize,
    files:write, groups:read, im:write, mpim:write, pins:write, reactions:write,
    search:read, users:read, users:read.email, usergroups:read
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


async def _get_org_token(org_id: str | None = None) -> str | None:
    try:
        from backend.core.context import current_org_id
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token
        oid = org_id or current_org_id.get()
        async with AsyncSessionLocal() as session:
            return await get_token(session, org_id=oid, service="slack")
    except Exception:
        return None


async def _token(org_id: str | None = None) -> str | None:
    return await _get_org_token(org_id) or settings.SLACK_TOKEN or None


async def _get(method: str, params: dict | None = None, token: str = "") -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{SLACK_API}/{method}", headers=_headers(token), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(method: str, body: dict, token: str = "") -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{SLACK_API}/{method}", headers=_headers(token), json=body)
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


def _no_token_error() -> ToolResult:
    return ToolResult(ok=False, error="Slack token not configured. Connect via Settings or set SLACK_TOKEN in .env.")


def _slack_error(data: dict) -> ToolResult:
    return ToolResult(ok=False, error=f"Slack API error: {data.get('error', 'unknown')}")


async def _resolve_channel(name: str, tok: str) -> str | None:
    """Resolve '#ops' or 'ops' → channel ID. Handles pagination for large workspaces."""
    if name and name[0] in ("C", "D", "G", "W") and len(name) > 5:
        return name  # already an ID
    name = name.lstrip("#").lower()
    cursor = None
    while True:
        params: dict = {"limit": 200, "exclude_archived": "true", "types": "public_channel,private_channel"}
        if cursor:
            params["cursor"] = cursor
        _, data = await _get("conversations.list", params, tok)
        for ch in data.get("channels", []):
            if ch.get("name", "").lower() == name:
                return ch["id"]
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


async def _resolve_user_by_email_or_name(identifier: str, tok: str) -> str | None:
    """Resolve email or display name → Slack user ID."""
    if "@" in identifier:
        _, data = await _get("users.lookupByEmail", {"email": identifier}, tok)
        if data.get("ok"):
            return data["user"]["id"]
        return None
    # Search by display name across users.list (paginated)
    identifier_lower = identifier.lower().lstrip("@")
    cursor = None
    while True:
        params: dict = {"limit": 200}
        if cursor:
            params["cursor"] = cursor
        _, data = await _get("users.list", params, tok)
        for m in data.get("members", []):
            p = m.get("profile", {})
            if (
                m.get("name", "").lower() == identifier_lower
                or p.get("display_name", "").lower() == identifier_lower
                or p.get("real_name", "").lower() == identifier_lower
            ):
                return m["id"]
        cursor = data.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return None


async def _build_user_map(user_ids: list[str], tok: str) -> dict[str, str]:
    """Batch-resolve user IDs → display names."""
    result: dict[str, str] = {}
    for uid in set(user_ids):
        if not uid:
            continue
        _, d = await _get("users.info", {"user": uid}, tok)
        if d.get("ok"):
            p = d["user"].get("profile", {})
            result[uid] = p.get("display_name") or p.get("real_name") or d["user"].get("name") or uid
    return result


# ---------------------------------------------------------------------------
# Tool 1 — Post message
# ---------------------------------------------------------------------------

class SlackPostMessageTool(Tool):
    name = "slack_post_message"
    description = "Post a message to a Slack channel or thread. Use for alerts, reports, and notifications."
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
        _, data = await _post("chat.postMessage", body, tok)
        if not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={"channel": data.get("channel"), "ts": data.get("ts"), "message": text[:100]})


# ---------------------------------------------------------------------------
# Tool 2 — List channels
# ---------------------------------------------------------------------------

class SlackListChannelsTool(Tool):
    name = "slack_list_channels"
    description = "List Slack channels the bot has access to. Returns names, IDs, member counts, and topics."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "number", "description": "Max channels to return. Default 50."},
            "types": {"type": "string", "description": "'public_channel', 'private_channel', or both. Default: both."},
        },
        "required": [],
    }

    async def run(self, limit: int = 50, types: str = "public_channel,private_channel") -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        _, data = await _get("conversations.list", {"limit": min(limit, 200), "exclude_archived": "true", "types": types}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        channels = [
            {"id": ch["id"], "name": ch["name"], "is_private": ch.get("is_private", False),
             "num_members": ch.get("num_members", 0), "topic": ch.get("topic", {}).get("value", "")}
            for ch in data.get("channels", [])
        ]
        return ToolResult(ok=True, data={"channels": channels, "count": len(channels)})


# ---------------------------------------------------------------------------
# Tool 3 — Get channel messages (with display names)
# ---------------------------------------------------------------------------

class SlackGetMessagesTool(Tool):
    name = "slack_get_messages"
    description = "Fetch recent messages from a Slack channel. Returns message text and author display names."
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name (e.g. '#general') or channel ID."},
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
        _, data = await _get("conversations.history", {"channel": channel_id, "limit": min(limit, 50)}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        raw = [m for m in data.get("messages", []) if m.get("type") == "message" and not m.get("subtype")]
        user_ids = [m.get("user", "") for m in raw if m.get("user")]
        user_map = await _build_user_map(user_ids, tok)
        messages = [
            {
                "ts": m.get("ts"),
                "user": user_map.get(m.get("user", ""), m.get("user", "unknown")),
                "text": m.get("text", "")[:500],
                "reply_count": m.get("reply_count", 0),
                "has_thread": m.get("reply_count", 0) > 0,
            }
            for m in raw
        ]
        return ToolResult(ok=True, data={"channel": channel, "messages": messages, "count": len(messages)})


# ---------------------------------------------------------------------------
# Tool 4 — Get thread replies
# ---------------------------------------------------------------------------

class SlackGetThreadTool(Tool):
    name = "slack_get_thread"
    description = "Fetch all replies in a Slack message thread. Provide the channel and the parent message timestamp."
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "thread_ts": {"type": "string", "description": "Timestamp of the parent message (e.g. '1234567890.123456')."},
            "limit": {"type": "number", "description": "Max replies to return. Default 50."},
        },
        "required": ["channel", "thread_ts"],
    }

    async def run(self, channel: str, thread_ts: str, limit: int = 50) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok)
        if not channel_id:
            return ToolResult(ok=False, error=f"Channel '{channel}' not found.")
        _, data = await _get("conversations.replies", {"channel": channel_id, "ts": thread_ts, "limit": min(limit, 100)}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        raw = data.get("messages", [])
        user_ids = [m.get("user", "") for m in raw if m.get("user")]
        user_map = await _build_user_map(user_ids, tok)
        replies = [
            {
                "ts": m.get("ts"),
                "user": user_map.get(m.get("user", ""), m.get("user", "unknown")),
                "text": m.get("text", "")[:500],
                "is_parent": m.get("ts") == thread_ts,
            }
            for m in raw
        ]
        return ToolResult(ok=True, data={"thread_ts": thread_ts, "replies": replies, "count": len(replies)})


# ---------------------------------------------------------------------------
# Tool 5 — Send DM (email OR display name)
# ---------------------------------------------------------------------------

class SlackSendDMTool(Tool):
    name = "slack_send_dm"
    description = "Send a direct message to a Slack user. Identify them by email address or Slack display name."
    parameters = {
        "type": "object",
        "properties": {
            "user": {"type": "string", "description": "Recipient's email (e.g. 'alice@company.com') or Slack display name (e.g. 'alice')."},
            "text": {"type": "string", "description": "Message text to send."},
        },
        "required": ["user", "text"],
    }

    async def run(self, user: str, text: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        user_id = await _resolve_user_by_email_or_name(user, tok)
        if not user_id:
            return ToolResult(ok=False, error=f"Slack user '{user}' not found. Try their email or exact display name.")
        _, im_data = await _post("conversations.open", {"users": user_id}, tok)
        if not im_data.get("ok"):
            return _slack_error(im_data)
        dm_channel = im_data["channel"]["id"]
        _, msg_data = await _post("chat.postMessage", {"channel": dm_channel, "text": text}, tok)
        if not msg_data.get("ok"):
            return _slack_error(msg_data)
        return ToolResult(ok=True, data={"to": user, "user_id": user_id, "ts": msg_data.get("ts")})


# ---------------------------------------------------------------------------
# Tool 6 — Search messages
# ---------------------------------------------------------------------------

class SlackSearchMessagesTool(Tool):
    name = "slack_search_messages"
    description = "Full-text search across all Slack messages in the workspace. Supports Slack search syntax (e.g. 'error in:#ops from:alice')."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query."},
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
# Tool 7 — Get user info
# ---------------------------------------------------------------------------

class SlackGetUserInfoTool(Tool):
    name = "slack_get_user_info"
    description = "Look up a Slack user's profile by email address. Returns name, title, status, timezone."
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
        p = u.get("profile", {})
        return ToolResult(ok=True, data={
            "id": u.get("id"), "name": u.get("name"), "real_name": p.get("real_name"),
            "display_name": p.get("display_name"), "title": p.get("title"),
            "email": p.get("email"), "status_text": p.get("status_text"),
            "timezone": u.get("tz"), "is_admin": u.get("is_admin", False),
        })


# ---------------------------------------------------------------------------
# Tool 8 — List users
# ---------------------------------------------------------------------------

class SlackListUsersTool(Tool):
    name = "slack_list_users"
    description = "List members of the Slack workspace. Returns names, emails, and admin status."
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "number", "description": "Max users to return. Default 50."},
            "include_bots": {"type": "boolean", "description": "Include bot accounts. Default false."},
        },
        "required": [],
    }

    async def run(self, limit: int = 50, include_bots: bool = False) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        _, data = await _get("users.list", {"limit": min(limit, 200)}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        members = [
            {
                "id": m["id"],
                "name": m.get("name"),
                "real_name": m.get("profile", {}).get("real_name"),
                "display_name": m.get("profile", {}).get("display_name"),
                "email": m.get("profile", {}).get("email"),
                "is_admin": m.get("is_admin", False),
                "is_bot": m.get("is_bot", False),
            }
            for m in data.get("members", [])
            if not m.get("deleted")
            and (include_bots or not m.get("is_bot"))
            and not m.get("is_ultra_restricted")
        ][:limit]
        return ToolResult(ok=True, data={"members": members, "count": len(members)})


# ---------------------------------------------------------------------------
# Tool 9 — Add reaction
# ---------------------------------------------------------------------------

class SlackAddReactionTool(Tool):
    name = "slack_add_reaction"
    description = "Add an emoji reaction to a Slack message."
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "timestamp": {"type": "string", "description": "Message timestamp (ts) to react to."},
            "emoji": {"type": "string", "description": "Emoji name without colons (e.g. 'thumbsup', 'white_check_mark')."},
        },
        "required": ["channel", "timestamp", "emoji"],
    }

    async def run(self, channel: str, timestamp: str, emoji: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok) or channel
        emoji = emoji.strip(":")
        _, data = await _post("reactions.add", {"channel": channel_id, "timestamp": timestamp, "name": emoji}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={"channel": channel, "emoji": emoji, "ts": timestamp})


# ---------------------------------------------------------------------------
# Tool 10 — Upload file / snippet
# ---------------------------------------------------------------------------

class SlackUploadFileTool(Tool):
    name = "slack_upload_file"
    description = "Upload a text snippet or file content to a Slack channel. Great for sharing logs, reports, or code blocks."
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "content": {"type": "string", "description": "Text content to upload."},
            "filename": {"type": "string", "description": "Filename to display, e.g. 'report.txt'."},
            "title": {"type": "string", "description": "Title shown above the snippet."},
        },
        "required": ["channel", "content"],
    }

    async def run(self, channel: str, content: str, filename: str = "snippet.txt", title: str = "") -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok) or channel
        # Slack v2 upload: getUploadURL → PUT → completeUpload
        _, url_data = await _post("files.getUploadURLExternal", {"filename": filename, "length": len(content.encode())}, tok)
        if not url_data.get("ok"):
            return _slack_error(url_data)
        upload_url = url_data["upload_url"]
        file_id = url_data["file_id"]
        async with httpx.AsyncClient(timeout=30) as client:
            put_resp = await client.put(upload_url, content=content.encode())
        if put_resp.status_code not in (200, 204):
            return ToolResult(ok=False, error=f"File upload failed: HTTP {put_resp.status_code}")
        _, complete_data = await _post("files.completeUploadExternal", {
            "files": [{"id": file_id, "title": title or filename}],
            "channel_id": channel_id,
        }, tok)
        if not complete_data.get("ok"):
            return _slack_error(complete_data)
        return ToolResult(ok=True, data={"file_id": file_id, "channel": channel, "filename": filename})


# ---------------------------------------------------------------------------
# Write tools (sensitive=True — HITL approval required)
# ---------------------------------------------------------------------------

class SlackCreateChannelTool(Tool):
    name = "slack_create_channel"
    description = "Create a new Slack channel. SENSITIVE: permanently changes workspace structure. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Channel name (lowercase, hyphens, e.g. 'incident-2024-db')."},
            "is_private": {"type": "boolean", "description": "Create as private channel. Default false."},
        },
        "required": ["name"],
    }

    async def run(self, name: str, is_private: bool = False) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        clean_name = name.lower().replace(" ", "-").lstrip("#")
        _, data = await _post("conversations.create", {"name": clean_name, "is_private": is_private}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        ch = data.get("channel", {})
        return ToolResult(ok=True, data={"id": ch.get("id"), "name": ch.get("name"), "is_private": ch.get("is_private")})


class SlackSetTopicTool(Tool):
    name = "slack_set_topic"
    description = "Update the topic of a Slack channel. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "topic": {"type": "string", "description": "New topic text."},
        },
        "required": ["channel", "topic"],
    }

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


class SlackInviteToChannelTool(Tool):
    name = "slack_invite_to_channel"
    description = "Invite a user to a Slack channel by email or display name. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "user": {"type": "string", "description": "User's email or Slack display name."},
        },
        "required": ["channel", "user"],
    }

    async def run(self, channel: str, user: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok)
        if not channel_id:
            return ToolResult(ok=False, error=f"Channel '{channel}' not found.")
        user_id = await _resolve_user_by_email_or_name(user, tok)
        if not user_id:
            return ToolResult(ok=False, error=f"User '{user}' not found in Slack.")
        _, data = await _post("conversations.invite", {"channel": channel_id, "users": user_id}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={"channel": channel, "user": user, "user_id": user_id})


class SlackUpdateMessageTool(Tool):
    name = "slack_update_message"
    description = "Edit a previously sent Slack message. Requires the channel and the original message timestamp. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID where the message was posted."},
            "ts": {"type": "string", "description": "Timestamp (ts) of the message to edit."},
            "text": {"type": "string", "description": "New message text."},
        },
        "required": ["channel", "ts", "text"],
    }

    async def run(self, channel: str, ts: str, text: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok) or channel
        _, data = await _post("chat.update", {"channel": channel_id, "ts": ts, "text": text}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={"channel": channel, "ts": data.get("ts"), "text": text[:100]})


class SlackDeleteMessageTool(Tool):
    name = "slack_delete_message"
    description = "Delete a Slack message by channel and timestamp. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "ts": {"type": "string", "description": "Timestamp (ts) of the message to delete."},
        },
        "required": ["channel", "ts"],
    }

    async def run(self, channel: str, ts: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok) or channel
        _, data = await _post("chat.delete", {"channel": channel_id, "ts": ts}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={"channel": channel, "deleted_ts": ts})


class SlackPinMessageTool(Tool):
    name = "slack_pin_message"
    description = "Pin a message in a Slack channel. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "ts": {"type": "string", "description": "Timestamp (ts) of the message to pin."},
        },
        "required": ["channel", "ts"],
    }

    async def run(self, channel: str, ts: str) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok) or channel
        _, data = await _post("pins.add", {"channel": channel_id, "timestamp": ts}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={"channel": channel, "pinned_ts": ts})


class SlackScheduleMessageTool(Tool):
    name = "slack_schedule_message"
    description = "Schedule a Slack message to be sent at a future time. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "channel": {"type": "string", "description": "Channel name or ID."},
            "text": {"type": "string", "description": "Message text."},
            "post_at": {"type": "number", "description": "Unix timestamp (seconds) when to send the message."},
        },
        "required": ["channel", "text", "post_at"],
    }

    async def run(self, channel: str, text: str, post_at: int) -> ToolResult:
        tok = await _token()
        if not tok:
            return _no_token_error()
        channel_id = await _resolve_channel(channel, tok) or channel
        _, data = await _post("chat.scheduleMessage", {"channel": channel_id, "text": text, "post_at": int(post_at)}, tok)
        if not data.get("ok"):
            return _slack_error(data)
        return ToolResult(ok=True, data={
            "channel": channel,
            "scheduled_message_id": data.get("scheduled_message_id"),
            "post_at": post_at,
            "text": text[:100],
        })
