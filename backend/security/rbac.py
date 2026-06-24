"""
Role-based access control.

Three roles in ascending order of privilege: viewer < operator < admin.

API key validation: if API_KEY is set in settings, every request must carry
  Authorization: Bearer <API_KEY>
If it is empty (default) the check is skipped (dev mode).

The caller's role is still read from the X-User-Role header AFTER the key is
validated, so the header cannot be abused without the key.
"""
from enum import IntEnum

from fastapi import Depends, Header, HTTPException

from backend.config import settings


class Role(IntEnum):
    viewer = 1
    operator = 2
    admin = 3


def _validate_api_key(authorization: str | None = Header(default=None)) -> None:
    """Reject requests that don't carry the configured API key."""
    if not settings.API_KEY:
        return  # dev mode — no key configured, skip
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header required.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != settings.API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key.")


def get_role(
    x_user_role: str = Header(default="viewer"),
    _: None = Depends(_validate_api_key),
) -> Role:
    """Read the caller's role from the X-User-Role header (after key validation)."""
    try:
        return Role[x_user_role.lower()]
    except KeyError:
        raise HTTPException(
            status_code=403,
            detail=f"Unknown role '{x_user_role}'. Valid values: viewer, operator, admin.",
        )


def require_role(min_role: Role):
    """FastAPI dependency factory that enforces a minimum role."""
    def _check(role: Role = Depends(get_role)) -> Role:
        if role < min_role:
            raise HTTPException(
                status_code=403,
                detail=f"Requires '{min_role.name}' role; caller has '{role.name}'.",
            )
        return role

    return Depends(_check)
