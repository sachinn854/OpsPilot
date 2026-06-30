"""
Auth endpoints — register, login, me.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.deps import get_current_user
from backend.auth.utils import create_access_token, hash_password, verify_password
from backend.db.models import User
from backend.db.session import get_session

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, session: AsyncSession = Depends(get_session)):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    email = req.email.lower().strip()
    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=email,
        name=req.name.strip() or email.split("@")[0],
        password_hash=hash_password(req.password),
    )
    session.add(user)
    await session.commit()
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, session: AsyncSession = Depends(get_session)):
    email = req.email.lower().strip()
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_access_token(user.id, user.email)
    return TokenResponse(
        access_token=token,
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email, "name": current_user.name}
