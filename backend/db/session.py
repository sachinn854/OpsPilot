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


engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)

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
