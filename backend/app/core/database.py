"""Asynchronous Database Infrastructure Module.

Provides SQLAlchemy 2.x DeclarativeBase, AsyncEngine, AsyncSession factory,
and the get_db dependency for FastAPI route injection.
"""

from collections.abc import AsyncGenerator
from typing import Any
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy 2.x domain models."""
    pass


def get_engine_args(echo: bool = False) -> dict[str, Any]:
    """Return standard production-safe connection pooling arguments."""
    return {
        "echo": echo,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }


def create_app_engine(database_url: str | None = None, echo: bool | None = None) -> AsyncEngine:
    """Create an asynchronous SQLAlchemy engine.

    Does not establish an active connection upon construction.
    """
    settings = get_settings()
    url = database_url or settings.DATABASE_URL
    is_echo = echo if echo is not None else settings.DEBUG
    return create_async_engine(url, **get_engine_args(echo=is_echo))


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create an async_sessionmaker configured with expire_on_commit=False."""
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


# Module-level default async engine and session factory
async_engine = create_app_engine()
AsyncSessionLocal = create_session_factory(async_engine)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an asynchronous database session.

    Ensures proper cleanup and closure upon request completion.
    Transaction commits remain the explicit responsibility of caller services.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def check_database_health() -> bool:
    """Verify database connectivity by executing a lightweight ping query."""
    from sqlalchemy import text
    async with async_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True


async def dispose_app_engine() -> None:
    """Explicitly dispose of the async database engine on application shutdown."""
    await async_engine.dispose()
