from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import DecodeError, ExpiredSignatureError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.utils import decode_token
from backend.db.models import User
from backend.db.session import get_session

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: AsyncSession = Depends(get_session),
) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
        user_id: str = payload.get("sub", "")
        if not user_id:
            raise ValueError()
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired — please log in again")
    except (DecodeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = await session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user
