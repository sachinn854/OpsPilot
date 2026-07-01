"""
Integration token management endpoints.

  GET    /v1/integrations              → list connected services for this org
  POST   /v1/integrations/{service}    → save/update a token
  DELETE /v1/integrations/{service}    → disconnect a service
  GET    /v1/integrations/{service}/verify → verify token is valid
"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import limiter
from backend.auth.deps import get_current_user
from backend.config import settings
from backend.db.models import User
from backend.db.session import get_session
from backend.integrations.store import (
    SUPPORTED_SERVICES,
    delete_token,
    get_token,
    list_connected,
    save_token,
)

router = APIRouter(prefix="/v1/integrations", tags=["integrations"])

_ORG = "default"


class SaveTokenRequest(BaseModel):
    token: str


class ConnectedService(BaseModel):
    service: str
    connected: bool
    meta: dict = {}
    updated_at: str | None = None


def _validate_service(service: str) -> None:
    if service not in SUPPORTED_SERVICES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported service '{service}'. Supported: {sorted(SUPPORTED_SERVICES)}",
        )


@router.get("", response_model=list[ConnectedService])
@limiter.limit(settings.RATE_LIMIT_RUNS)
async def list_integrations(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> list[ConnectedService]:
    """List all services the current org has connected."""
    rows = await list_connected(session, org_id=_ORG)
    # Also surface services that have .env tokens but aren't in DB yet
    connected_services = {r["service"] for r in rows}
    result = [ConnectedService(**r) for r in rows]

    # Show GitHub as connected if GITHUB_TOKEN is in .env (even without DB row)
    if "github" not in connected_services and settings.GITHUB_TOKEN:
        result.insert(0, ConnectedService(
            service="github", connected=True,
            meta={"source": "env"}, updated_at=None
        ))
    return result


@router.post("/{service}", response_model=ConnectedService)
@limiter.limit("10/minute")
async def save_integration(
    request: Request,
    service: str,
    req: SaveTokenRequest,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(get_current_user),
) -> ConnectedService:
    """Save or replace a service token for the current org."""
    _validate_service(service)
    if not req.token.strip():
        raise HTTPException(status_code=400, detail="Token cannot be empty.")

    # Quick verify before saving
    meta = await _verify_token(service, req.token.strip())
    if meta is None:
        raise HTTPException(status_code=400, detail=f"Token verification failed for '{service}'. Check your token.")

    await save_token(session, org_id=_ORG, service=service, token=req.token.strip(), meta=meta)
    return ConnectedService(service=service, connected=True, meta=meta)


@router.delete("/{service}")
@limiter.limit("10/minute")
async def disconnect_integration(
    request: Request,
    service: str,
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(get_current_user),
) -> dict:
    """Disconnect a service by deleting its stored token."""
    _validate_service(service)
    deleted = await delete_token(session, org_id=_ORG, service=service)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No token found for '{service}'.")
    return {"service": service, "connected": False}


@router.get("/{service}/verify")
@limiter.limit("20/minute")
async def verify_integration(
    request: Request,
    service: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Verify that the stored token for a service is still valid."""
    _validate_service(service)

    # Try DB first, then .env fallback for github
    token = await get_token(session, org_id=_ORG, service=service)
    if not token and service == "github":
        token = settings.GITHUB_TOKEN or None

    if not token:
        return {"service": service, "valid": False, "reason": "No token stored."}

    meta = await _verify_token(service, token)
    if meta is None:
        return {"service": service, "valid": False, "reason": "Token rejected by the service."}
    return {"service": service, "valid": True, "meta": meta}


# ---------------------------------------------------------------------------
# Per-service verification helpers
# ---------------------------------------------------------------------------

async def _verify_token(service: str, token: str) -> dict | None:
    """Call the service API to confirm the token works. Returns metadata or None."""
    try:
        if service == "github":
            return await _verify_github(token)
        if service == "slack":
            return await _verify_slack(token)
        if service == "openrouter":
            return await _verify_openrouter(token)
        if service == "jira":
            return await _verify_jira(token)
        if service == "linear":
            return await _verify_linear(token)
        if service == "notion":
            return await _verify_notion(token)
        if service == "confluence":
            return await _verify_confluence(token)
        if service == "pagerduty":
            return await _verify_pagerduty(token)
        if service == "hubspot":
            return await _verify_hubspot(token)
        return {"note": "token accepted (no live verify)"}
    except Exception:
        return None


async def _verify_github(token: str) -> dict | None:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://api.github.com/user", headers=headers)
    if resp.status_code == 200:
        d = resp.json()
        return {"username": d.get("login"), "name": d.get("name"), "avatar_url": d.get("avatar_url")}
    # Fine-grained PATs with repo-only scope return 403 on /user.
    # Fall back to /rate_limit which any valid token can reach.
    if resp.status_code == 403:
        async with httpx.AsyncClient(timeout=10) as client:
            r2 = await client.get("https://api.github.com/rate_limit", headers=headers)
        if r2.status_code == 200:
            return {"username": "authenticated", "note": "fine-grained PAT (repo-scoped)"}
    return None


async def _verify_openrouter(token: str) -> dict | None:
    # Accept any non-empty key — real validation happens on first chat call
    return {"note": "accepted"}


async def _verify_jira(token: str) -> dict | None:
    import base64
    import json
    try:
        cfg = json.loads(token)
    except Exception:
        return None
    if not all(k in cfg for k in ("api_token", "email", "domain")):
        return None
    domain = cfg["domain"].rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    creds = base64.b64encode(f"{cfg['email']}:{cfg['api_token']}".encode()).decode()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{domain}/rest/api/3/myself",
            headers={"Authorization": f"Basic {creds}", "Accept": "application/json"},
        )
    if resp.status_code == 200:
        d = resp.json()
        return {"display_name": d.get("displayName"), "email": d.get("emailAddress"), "domain": cfg["domain"]}
    return None


async def _verify_linear(token: str) -> dict | None:
    query = "query { viewer { id name email } }"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.linear.app/graphql",
            headers={"Authorization": token, "Content-Type": "application/json"},
            json={"query": query},
        )
    if resp.status_code == 200:
        d = resp.json()
        viewer = d.get("data", {}).get("viewer", {})
        if viewer:
            return {"name": viewer.get("name"), "email": viewer.get("email")}
    return None


async def _verify_slack(token: str) -> dict | None:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code != 200:
        return None
    d = resp.json()
    if not d.get("ok"):
        return None
    return {"team": d.get("team"), "user": d.get("user"), "workspace_url": d.get("url")}


async def _verify_notion(token: str) -> dict | None:
    import json as _json
    try:
        cfg = _json.loads(token)
        api_token = cfg.get("token", "")
    except Exception:
        api_token = token
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.notion.com/v1/users/me",
            headers={
                "Authorization": f"Bearer {api_token}",
                "Notion-Version": "2022-06-28",
            },
        )
    if resp.status_code == 200:
        d = resp.json()
        return {"name": d.get("name"), "type": d.get("type")}
    return None


async def _verify_confluence(token: str) -> dict | None:
    import base64
    import json as _json
    try:
        cfg = _json.loads(token)
    except Exception:
        return None
    if not all(k in cfg for k in ("api_token", "email", "domain")):
        return None
    domain = cfg["domain"].rstrip("/")
    if not domain.startswith("http"):
        domain = f"https://{domain}"
    creds = base64.b64encode(f"{cfg['email']}:{cfg['api_token']}".encode()).decode()
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{domain}/wiki/rest/api/user/current",
            headers={"Authorization": f"Basic {creds}", "Accept": "application/json"},
        )
    if resp.status_code == 200:
        d = resp.json()
        return {"display_name": d.get("displayName"), "email": cfg["email"], "domain": cfg["domain"]}
    return None


async def _verify_pagerduty(token: str) -> dict | None:
    import json as _json
    try:
        cfg = _json.loads(token)
        api_key = cfg.get("api_key", "")
    except Exception:
        api_key = token
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.pagerduty.com/users/me",
            headers={
                "Authorization": f"Token token={api_key}",
                "Accept": "application/vnd.pagerduty+json;version=2",
            },
        )
    if resp.status_code == 200:
        d = resp.json().get("user", {})
        return {"name": d.get("name"), "email": d.get("email"), "role": d.get("role")}
    return None


async def _verify_hubspot(token: str) -> dict | None:
    import json as _json
    try:
        cfg = _json.loads(token)
        hs_token = cfg.get("token", "")
    except Exception:
        hs_token = token
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://api.hubapi.com/oauth/v1/access-tokens/" + hs_token,
            headers={"Authorization": f"Bearer {hs_token}"},
        )
    if resp.status_code == 200:
        d = resp.json()
        return {"hub_domain": d.get("hub_domain"), "user": d.get("user"), "hub_id": d.get("hub_id")}
    # Private app tokens don't support /access-tokens — try a lightweight CRM call
    async with httpx.AsyncClient(timeout=10) as client:
        resp2 = await client.get(
            "https://api.hubapi.com/crm/v3/objects/contacts?limit=1",
            headers={"Authorization": f"Bearer {hs_token}"},
        )
    if resp2.status_code == 200:
        return {"note": "token valid (private app)"}
    return None
