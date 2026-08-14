"""
Integration token store — save, fetch, delete, verify tokens per org.

Tokens are encrypted at rest using Fernet. Each org can have one token
per service (github, slack, jira, linear, etc.).
"""
import json
import time
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import IntegrationToken
from backend.integrations.encrypt import decrypt_token, encrypt_token

# In-process token cache: (org_id, service) → (decrypted_token, expiry_monotonic)
# Avoids a DB round-trip on every tool call. Invalidated on save/delete.
_TOKEN_CACHE: dict[tuple[str, str], tuple[str | None, float]] = {}
_TOKEN_TTL = 60.0  # seconds

SUPPORTED_SERVICES = {
    "github", "slack", "jira", "linear", "pagerduty", "openrouter", "google",
    "notion", "confluence", "hubspot",
}


async def save_token(
    session: AsyncSession,
    *,
    org_id: str,
    service: str,
    token: str,
    meta: dict | None = None,
) -> IntegrationToken:
    """Save (or replace) a service token for an org. Encrypts before storing."""
    # Upsert: delete existing first, then insert fresh.
    await session.execute(
        delete(IntegrationToken).where(
            IntegrationToken.org_id == org_id,
            IntegrationToken.service == service,
        )
    )
    row = IntegrationToken(
        org_id=org_id,
        service=service,
        token_encrypted=encrypt_token(token),
        meta=json.dumps(meta) if meta else None,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    # Warm the cache so the next call is instant.
    _TOKEN_CACHE[(org_id, service)] = (token, time.monotonic() + _TOKEN_TTL)
    return row


async def get_token(
    session: AsyncSession,
    *,
    org_id: str,
    service: str,
) -> str | None:
    """Return the decrypted token for (org, service), or None if not set."""
    key = (org_id, service)
    cached_val, expiry = _TOKEN_CACHE.get(key, (None, 0.0))
    if expiry > time.monotonic():
        return cached_val

    result = await session.execute(
        select(IntegrationToken).where(
            IntegrationToken.org_id == org_id,
            IntegrationToken.service == service,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        _TOKEN_CACHE[key] = (None, time.monotonic() + _TOKEN_TTL)
        return None
    try:
        value = decrypt_token(row.token_encrypted)
    except ValueError:
        value = None
    _TOKEN_CACHE[key] = (value, time.monotonic() + _TOKEN_TTL)
    return value


async def delete_token(
    session: AsyncSession,
    *,
    org_id: str,
    service: str,
) -> bool:
    """Delete the token for (org, service). Returns True if a row was deleted."""
    result = await session.execute(
        delete(IntegrationToken).where(
            IntegrationToken.org_id == org_id,
            IntegrationToken.service == service,
        )
    )
    await session.commit()
    _TOKEN_CACHE.pop((org_id, service), None)
    return result.rowcount > 0


async def list_connected(
    session: AsyncSession,
    *,
    org_id: str,
) -> list[dict]:
    """Return a list of connected services for an org (without the tokens)."""
    result = await session.execute(
        select(IntegrationToken).where(IntegrationToken.org_id == org_id)
    )
    rows = result.scalars().all()
    return [
        {
            "service": r.service,
            "connected": True,
            "meta": json.loads(r.meta) if r.meta else {},
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]
