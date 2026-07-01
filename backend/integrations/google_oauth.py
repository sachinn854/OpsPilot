"""
Google OAuth2 helpers.

Flow:
  1. get_auth_url(state)         → redirect user to Google consent
  2. exchange_code(code)         → access_token + refresh_token
  3. get_valid_credentials(org)  → auto-refresh if expired
"""
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

import httpx

from backend.config import settings

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/spreadsheets",
]


def get_auth_url(state: str) -> str:
    params = {
        "client_id":     settings.GOOGLE_CLIENT_ID,
        "redirect_uri":  settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(SCOPES),
        "access_type":   "offline",
        "prompt":        "consent",
        "state":         state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "code":          code,
            "client_id":     settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri":  settings.GOOGLE_REDIRECT_URI,
            "grant_type":    "authorization_code",
        })
    resp.raise_for_status()
    return resp.json()


async def _refresh(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "refresh_token": refresh_token,
            "client_id":     settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "grant_type":    "refresh_token",
        })
    resp.raise_for_status()
    return resp.json()


async def get_valid_credentials(org_id: str = "default") -> dict | None:
    """Return {access_token, email} — refreshes automatically if expired."""
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import get_token, save_token
        async with AsyncSessionLocal() as session:
            raw = await get_token(session, org_id=org_id, service="google")
            if not raw:
                return None
            creds = json.loads(raw)
            expiry_str = creds.get("expiry")
            if expiry_str:
                expiry = datetime.fromisoformat(expiry_str)
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if now >= expiry and creds.get("refresh_token"):
                    new = await _refresh(creds["refresh_token"])
                    from datetime import timedelta
                    new_expiry = datetime.now(timezone.utc) + timedelta(seconds=new.get("expires_in", 3600))
                    creds["access_token"] = new["access_token"]
                    creds["expiry"] = new_expiry.isoformat()
                    await save_token(session, org_id=org_id, service="google",
                                     token=json.dumps(creds), meta={"email": creds.get("email", "")})
            return creds
    except Exception:
        return None
