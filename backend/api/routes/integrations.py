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
        # For other services just accept the token (no live verification yet)
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
    # /models works with any valid OpenRouter key (free or paid)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {token}"},
        )
    if resp.status_code == 200:
        return {"models_available": len(resp.json().get("data", []))}
    if resp.status_code == 401:
        return None
    # 429 / 5xx — accept now, real failure will surface on first chat call
    return {"note": "accepted"}


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
