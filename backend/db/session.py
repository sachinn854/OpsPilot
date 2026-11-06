"""
Async database setup (PostgreSQL via SQLAlchemy + asyncpg).

Provides:
  - `Base`              → declarative base for all models
  - `engine`            → async engine
  - `AsyncSessionLocal` → session factory
  - `get_session()`     → FastAPI dependency that yields a session
  - `init_db()`         → create tables (convenience; Alembic migrations come later)
"""
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


_is_remote = not any(h in settings.DATABASE_URL for h in ["localhost", "127.0.0.1"])
# Neon / Supabase connection poolers don't support prepared statements
_is_pooler = any(k in settings.DATABASE_URL for k in ["pooler.", "-pooler."])

_connect_args: dict = {}
if _is_remote:
    _connect_args["ssl"] = "require"
if _is_pooler:
    _connect_args["prepared_statement_cache_size"] = 0

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db() -> None:
    """Create all tables. Convenient for now; replaced by Alembic later."""
    import backend.db.models  # noqa: F401  (ensure models are registered)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
