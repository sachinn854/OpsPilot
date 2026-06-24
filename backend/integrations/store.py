"""
Integration token store — save, fetch, delete, verify tokens per org.

Tokens are encrypted at rest using Fernet. Each org can have one token
per service (github, slack, jira, linear, etc.).
"""
import json
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import IntegrationToken
from backend.integrations.encrypt import decrypt_token, encrypt_token

SUPPORTED_SERVICES = {"github", "slack", "jira", "linear", "pagerduty"}


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
    return row


async def get_token(
    session: AsyncSession,
    *,
    org_id: str,
    service: str,
) -> str | None:
    """Return the decrypted token for (org, service), or None if not set."""
    result = await session.execute(
        select(IntegrationToken).where(
            IntegrationToken.org_id == org_id,
            IntegrationToken.service == service,
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    try:
        return decrypt_token(row.token_encrypted)
    except ValueError:
        return None


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
