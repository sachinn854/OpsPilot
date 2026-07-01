"""
Google OAuth2 endpoints.

  GET /v1/integrations/google/connect   → returns {auth_url} (frontend opens popup)
  GET /v1/integrations/google/callback  → exchanges code, stores tokens, closes popup
"""
import json
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from backend.auth.deps import get_current_user
from backend.config import settings
from backend.db.models import User
from backend.integrations.google_oauth import exchange_code, get_auth_url

router = APIRouter(prefix="/v1/integrations/google", tags=["google-oauth"])

_POPUP_SUCCESS = """
<html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#0f0f0f;color:#e5e5e5">
  <h2 style="color:#22c55e">Google Connected!</h2>
  <p>You can close this window.</p>
  <script>
    if (window.opener) {{
      window.opener.postMessage({{type:'google-connected',email:'{email}'}}, '*');
    }}
    setTimeout(() => window.close(), 1500);
  </script>
</body></html>
"""

_POPUP_ERROR = """
<html><body style="font-family:sans-serif;text-align:center;padding:40px;background:#0f0f0f;color:#e5e5e5">
  <h2 style="color:#f87171">Connection Failed</h2>
  <p>{error}</p>
  <script>setTimeout(() => window.close(), 3000);</script>
</body></html>
"""


@router.get("/connect")
async def google_connect(current_user: User = Depends(get_current_user)):
    """Generate Google OAuth URL. Frontend opens this in a popup."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth not configured (GOOGLE_CLIENT_ID missing).")
    state = jwt.encode(
        {"org_id": "default", "exp": int(datetime.now(timezone.utc).timestamp()) + 600},
        settings.JWT_SECRET,
        algorithm="HS256",
    )
    return {"auth_url": get_auth_url(state)}


@router.get("/callback", response_class=HTMLResponse)
async def google_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error:
        return HTMLResponse(_POPUP_ERROR.format(error=error))
    if not code:
        return HTMLResponse(_POPUP_ERROR.format(error="No authorization code received."))
    try:
        payload = jwt.decode(state, settings.JWT_SECRET, algorithms=["HS256"])
        org_id = payload.get("org_id", "default")
    except Exception:
        return HTMLResponse(_POPUP_ERROR.format(error="Invalid or expired state. Please try again."))

    try:
        tokens = await exchange_code(code)
    except Exception as exc:
        return HTMLResponse(_POPUP_ERROR.format(error=f"Token exchange failed: {exc}"))

    access_token  = tokens.get("access_token", "")
    refresh_token = tokens.get("refresh_token", "")
    expires_in    = tokens.get("expires_in", 3600)
    expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()

    import httpx as _httpx
    email = ""
    name  = ""
    try:
        async with _httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
        if resp.status_code == 200:
            info  = resp.json()
            email = info.get("email", "")
            name  = info.get("name", "")
    except Exception:
        pass

    creds = json.dumps({
        "access_token":  access_token,
        "refresh_token": refresh_token,
        "expiry":        expiry,
        "email":         email,
        "name":          name,
    })

    try:
        from backend.db.session import AsyncSessionLocal
        from backend.integrations.store import save_token
        async with AsyncSessionLocal() as session:
            await save_token(session, org_id=org_id, service="google",
                             token=creds, meta={"email": email, "name": name})
    except Exception as exc:
        return HTMLResponse(_POPUP_ERROR.format(error=f"Failed to save credentials: {exc}"))

    return HTMLResponse(_POPUP_SUCCESS.format(email=email))
