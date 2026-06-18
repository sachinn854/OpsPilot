"""
Role-based access control.

Three roles in ascending order of privilege: viewer < operator < admin.

The caller's role is read from the X-User-Role HTTP header (default: viewer).
Use require_role(Role.operator) as a FastAPI dependency on any route that
needs elevated access — it raises 403 when the caller's role is too low.
"""
from enum import IntEnum

from fastapi import Depends, Header, HTTPException


class Role(IntEnum):
    viewer = 1
    operator = 2
    admin = 3


def get_role(x_user_role: str = Header(default="viewer")) -> Role:
    """Read the caller's role from the X-User-Role header."""
    try:
        return Role[x_user_role.lower()]
    except KeyError:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Unknown role '{x_user_role}'. "
                "Valid values: viewer, operator, admin."
            ),
        )


def require_role(min_role: Role):
    """FastAPI dependency factory that enforces a minimum role.

    Usage::

        @router.post("/action")
        async def action(_: Role = require_role(Role.operator)):
            ...
    """
    def _check(role: Role = Depends(get_role)) -> Role:
        if role < min_role:
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Requires '{min_role.name}' role; "
                    f"caller has '{role.name}'."
                ),
            )
        return role

    return Depends(_check)
