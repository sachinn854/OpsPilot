"""
Google Calendar + Meet tools — real Calendar API via OAuth2.

Read tools:
  calendar_list_events      — list upcoming events
  calendar_get_event        — get event details
  calendar_find_free_slot   — find available time in a day

Write tools (sensitive=True — HITL approval required):
  calendar_create_event     — create a calendar event
  calendar_create_meeting   — create event with Google Meet link
"""
from datetime import datetime, timedelta, timezone

import httpx

from backend.integrations.google_oauth import get_valid_credentials
from backend.tools.base import Tool, ToolResult

CAL_BASE = "https://www.googleapis.com/calendar/v3"


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _no_auth() -> ToolResult:
    return ToolResult(ok=False, error="Google account not connected. Go to Settings → Connect Google.")


async def _get(path: str, token: str, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{CAL_BASE}/{path}", headers=_headers(token), params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _patch(path: str, token: str, body: dict, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.patch(f"{CAL_BASE}/{path}", headers=_headers(token), json=body, params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _post(path: str, token: str, body: dict, params: dict | None = None) -> tuple[int, dict]:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(f"{CAL_BASE}/{path}", headers=_headers(token), json=body, params=params or {})
    try:
        return resp.status_code, resp.json()
    except Exception:
        return resp.status_code, {}


async def _delete(path: str, token: str) -> int:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.delete(f"{CAL_BASE}/{path}", headers=_headers(token))
    return resp.status_code


def _fmt_event(e: dict) -> dict:
    start = e.get("start", {})
    end   = e.get("end", {})
    return {
        "id":          e.get("id"),
        "summary":     e.get("summary", "(No title)"),
        "start":       start.get("dateTime") or start.get("date"),
        "end":         end.get("dateTime") or end.get("date"),
        "location":    e.get("location", ""),
        "description": (e.get("description") or "")[:300],
        "attendees":   [a.get("email") for a in e.get("attendees", [])],
        "meet_link":   e.get("hangoutLink", ""),
        "html_link":   e.get("htmlLink", ""),
    }


# ---------------------------------------------------------------------------
# Tool 1 — List events
# ---------------------------------------------------------------------------

class CalendarListEventsTool(Tool):
    name = "calendar_list_events"
    description = "List upcoming Google Calendar events. Returns title, start/end time, attendees, and Meet link if any."
    parameters = {
        "type": "object",
        "properties": {
            "days_ahead": {"type": "number", "description": "How many days ahead to look. Default 7."},
            "max_results": {"type": "number", "description": "Max events to return. Default 10."},
            "calendar_id": {"type": "string", "description": "Calendar ID. Default: primary."},
        },
        "required": [],
    }

    async def run(self, days_ahead: int = 7, max_results: int = 10, calendar_id: str = "primary") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        now    = datetime.now(timezone.utc)
        until  = now + timedelta(days=days_ahead)
        status, data = await _get(
            f"calendars/{calendar_id}/events",
            creds["access_token"],
            {
                "timeMin":      now.isoformat(),
                "timeMax":      until.isoformat(),
                "maxResults":   min(max_results, 50),
                "singleEvents": "true",
                "orderBy":      "startTime",
            },
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Calendar API error {status}: {data.get('error', {}).get('message', data)}")
        events = [_fmt_event(e) for e in data.get("items", [])]
        return ToolResult(ok=True, data={"events": events, "count": len(events), "days_ahead": days_ahead})


# ---------------------------------------------------------------------------
# Tool 2 — Get event
# ---------------------------------------------------------------------------

class CalendarGetEventTool(Tool):
    name = "calendar_get_event"
    description = "Get full details of a Google Calendar event by its event ID."
    parameters = {
        "type": "object",
        "properties": {
            "event_id":    {"type": "string", "description": "Calendar event ID."},
            "calendar_id": {"type": "string", "description": "Calendar ID. Default: primary."},
        },
        "required": ["event_id"],
    }

    async def run(self, event_id: str, calendar_id: str = "primary") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status, data = await _get(f"calendars/{calendar_id}/events/{event_id}", creds["access_token"])
        if status != 200:
            return ToolResult(ok=False, error=f"Event '{event_id}' not found.")
        return ToolResult(ok=True, data=_fmt_event(data))


# ---------------------------------------------------------------------------
# Tool 3 — Find free slot
# ---------------------------------------------------------------------------

class CalendarFindFreeSlotTool(Tool):
    name = "calendar_find_free_slot"
    description = "Find available time slots in a day for scheduling a meeting. Returns free windows."
    parameters = {
        "type": "object",
        "properties": {
            "date":          {"type": "string", "description": "Date to check in YYYY-MM-DD format."},
            "duration_min":  {"type": "number", "description": "Meeting duration in minutes. Default 60."},
            "work_start_hour": {"type": "number", "description": "Work day start hour (0-23). Default 9."},
            "work_end_hour":   {"type": "number", "description": "Work day end hour (0-23). Default 18."},
        },
        "required": ["date"],
    }

    async def run(self, date: str, duration_min: int = 60, work_start_hour: int = 9, work_end_hour: int = 18) -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        try:
            day = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
        except ValueError:
            return ToolResult(ok=False, error=f"Invalid date format: '{date}'. Use YYYY-MM-DD.")

        time_min = day.replace(hour=work_start_hour, minute=0, second=0)
        time_max = day.replace(hour=work_end_hour,   minute=0, second=0)

        status, data = await _get(
            "calendars/primary/events",
            creds["access_token"],
            {
                "timeMin":      time_min.isoformat(),
                "timeMax":      time_max.isoformat(),
                "singleEvents": "true",
                "orderBy":      "startTime",
            },
        )
        if status != 200:
            return ToolResult(ok=False, error=f"Calendar error {status}")

        busy: list[tuple[datetime, datetime]] = []
        for e in data.get("items", []):
            s = e.get("start", {})
            en = e.get("end", {})
            try:
                s_dt  = datetime.fromisoformat(s.get("dateTime", ""))
                e_dt  = datetime.fromisoformat(en.get("dateTime", ""))
                if s_dt.tzinfo is None:
                    s_dt = s_dt.replace(tzinfo=timezone.utc)
                if e_dt.tzinfo is None:
                    e_dt = e_dt.replace(tzinfo=timezone.utc)
                busy.append((s_dt, e_dt))
            except Exception:
                continue

        free_slots = []
        current = time_min
        duration = timedelta(minutes=duration_min)
        for b_start, b_end in sorted(busy):
            if current + duration <= b_start:
                free_slots.append({
                    "start": current.isoformat(),
                    "end":   (current + duration).isoformat(),
                })
            current = max(current, b_end)
        if current + duration <= time_max:
            free_slots.append({
                "start": current.isoformat(),
                "end":   (current + duration).isoformat(),
            })

        return ToolResult(ok=True, data={"date": date, "duration_min": duration_min, "free_slots": free_slots[:5]})


# ---------------------------------------------------------------------------
# Tool 4 — Create event (sensitive)
# ---------------------------------------------------------------------------

class CalendarCreateEventTool(Tool):
    name = "calendar_create_event"
    description = "Create a Google Calendar event. SENSITIVE: creates a permanent calendar entry. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "title":       {"type": "string", "description": "Event title."},
            "start":       {"type": "string", "description": "Start time in ISO 8601 format, e.g. '2024-06-01T14:00:00'."},
            "end":         {"type": "string", "description": "End time in ISO 8601 format."},
            "description": {"type": "string", "description": "Event description (optional)."},
            "attendees":   {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses (optional)."},
            "location":    {"type": "string", "description": "Physical or virtual location (optional)."},
        },
        "required": ["title", "start", "end"],
    }

    async def run(self, title: str, start: str, end: str, description: str = "", attendees: list[str] | None = None, location: str = "") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        event: dict = {
            "summary":   title,
            "start":     {"dateTime": start, "timeZone": "UTC"},
            "end":       {"dateTime": end,   "timeZone": "UTC"},
        }
        if description:
            event["description"] = description
        if location:
            event["location"] = location
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]
        status, data = await _post("calendars/primary/events", creds["access_token"], event)
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Failed to create event: {data.get('error', {}).get('message', data)}")
        return ToolResult(ok=True, data=_fmt_event(data))


# ---------------------------------------------------------------------------
# Tool 5 — Create meeting with Meet link (sensitive)
# ---------------------------------------------------------------------------

class CalendarCreateMeetingTool(Tool):
    name = "calendar_create_meeting"
    description = "Create a Google Calendar event with a Google Meet video link. SENSITIVE: sends invites and creates Meet room. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "title":       {"type": "string", "description": "Meeting title."},
            "start":       {"type": "string", "description": "Start time in ISO 8601 format, e.g. '2024-06-01T14:00:00'."},
            "end":         {"type": "string", "description": "End time in ISO 8601 format."},
            "attendees":   {"type": "array", "items": {"type": "string"}, "description": "Attendee email addresses."},
            "description": {"type": "string", "description": "Meeting agenda or description (optional)."},
        },
        "required": ["title", "start", "end"],
    }

    async def run(self, title: str, start: str, end: str, attendees: list[str] | None = None, description: str = "") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        import uuid
        event: dict = {
            "summary":     title,
            "start":       {"dateTime": start, "timeZone": "UTC"},
            "end":         {"dateTime": end,   "timeZone": "UTC"},
            "conferenceData": {
                "createRequest": {
                    "requestId":            str(uuid.uuid4()),
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            },
        }
        if description:
            event["description"] = description
        if attendees:
            event["attendees"] = [{"email": a} for a in attendees]
        status, data = await _post(
            "calendars/primary/events",
            creds["access_token"],
            event,
            params={"conferenceDataVersion": "1"},
        )
        if status not in (200, 201):
            return ToolResult(ok=False, error=f"Failed to create meeting: {data.get('error', {}).get('message', data)}")
        result = _fmt_event(data)
        return ToolResult(ok=True, data=result)


# ---------------------------------------------------------------------------
# Tool 6 — Delete event (sensitive)
# ---------------------------------------------------------------------------

class CalendarDeleteEventTool(Tool):
    name = "calendar_delete_event"
    description = "Delete a Google Calendar event by its event ID. SENSITIVE: permanently removes the event and cancels invites. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "event_id":    {"type": "string", "description": "Calendar event ID to delete."},
            "calendar_id": {"type": "string", "description": "Calendar ID. Default: primary."},
        },
        "required": ["event_id"],
    }

    async def run(self, event_id: str, calendar_id: str = "primary") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        status = await _delete(f"calendars/{calendar_id}/events/{event_id}", creds["access_token"])
        if status == 204:
            return ToolResult(ok=True, data={"deleted": True, "event_id": event_id})
        if status == 404:
            return ToolResult(ok=False, error=f"Event '{event_id}' not found.")
        return ToolResult(ok=False, error=f"Failed to delete event. Status: {status}")


# ---------------------------------------------------------------------------
# Tool 7 — Update event (sensitive)
# ---------------------------------------------------------------------------

class CalendarUpdateEventTool(Tool):
    name = "calendar_update_event"
    description = "Update an existing Google Calendar event — change title, time, attendees, or description. SENSITIVE: modifies existing event. Requires human approval."
    sensitive = True
    parameters = {
        "type": "object",
        "properties": {
            "event_id":    {"type": "string", "description": "Calendar event ID to update."},
            "title":       {"type": "string", "description": "New event title (optional)."},
            "start":       {"type": "string", "description": "New start time in ISO 8601 format (optional)."},
            "end":         {"type": "string", "description": "New end time in ISO 8601 format (optional)."},
            "description": {"type": "string", "description": "New description (optional)."},
            "attendees":   {"type": "array", "items": {"type": "string"}, "description": "Updated attendee email list (optional, replaces existing)."},
            "calendar_id": {"type": "string", "description": "Calendar ID. Default: primary."},
        },
        "required": ["event_id"],
    }

    async def run(self, event_id: str, title: str = "", start: str = "", end: str = "",
                  description: str = "", attendees: list[str] | None = None,
                  calendar_id: str = "primary") -> ToolResult:
        creds = await get_valid_credentials()
        if not creds:
            return _no_auth()
        patch: dict = {}
        if title:
            patch["summary"] = title
        if start:
            patch["start"] = {"dateTime": start}
        if end:
            patch["end"] = {"dateTime": end}
        if description:
            patch["description"] = description
        if attendees is not None:
            patch["attendees"] = [{"email": a} for a in attendees]
        if not patch:
            return ToolResult(ok=False, error="No fields provided to update.")
        status, data = await _patch(f"calendars/{calendar_id}/events/{event_id}", creds["access_token"], patch)
        if status != 200:
            return ToolResult(ok=False, error=f"Update failed: {data.get('error', {}).get('message', data)}")
        return ToolResult(ok=True, data=_fmt_event(data))
