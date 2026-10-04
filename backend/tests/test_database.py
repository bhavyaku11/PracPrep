"""Automated tests for asynchronous database infrastructure, DeclarativeBase, and get_db dependency."""

import inspect
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import (
    AsyncSessionLocal,
    Base,
    async_engine,
    create_app_engine,
    create_session_factory,
    get_db,
)


def test_declarative_base_inheritance():
    """Verify Declarative Base can be imported and subclassed by domain models."""
    class DummyItem(Base):
        __tablename__ = "dummy_test_items"
        id: Mapped[int] = mapped_column(primary_key=True)

    assert hasattr(DummyItem, "__table__")
    assert DummyItem.__tablename__ == "dummy_test_items"
    assert "id" in DummyItem.__table__.columns


def test_async_engine_configuration():
    """Verify default engine is an instance of AsyncEngine and has expected URL structure."""
    assert isinstance(async_engine, AsyncEngine)
    assert async_engine.url.drivername == "postgresql+asyncpg"


def test_custom_engine_creation():
    """Verify create_app_engine accepts custom database URL without connecting."""
    custom_url = "postgresql+asyncpg://user:pass@remote-host:5432/custom_db"
    engine = create_app_engine(database_url=custom_url, echo=True)
    assert isinstance(engine, AsyncEngine)
    assert engine.url.render_as_string(hide_password=False) == custom_url


def test_session_factory_configuration():
    """Verify AsyncSessionLocal is an async_sessionmaker with expire_on_commit=False."""
    assert isinstance(AsyncSessionLocal, async_sessionmaker)
    assert issubclass(AsyncSessionLocal.class_, AsyncSession)
    assert AsyncSessionLocal.kw.get("expire_on_commit") is False
    assert AsyncSessionLocal.kw.get("autoflush") is False


def test_custom_session_factory_creation():
    """Verify create_session_factory configures bound session factory correctly."""
    factory = create_session_factory(async_engine)
    assert isinstance(factory, async_sessionmaker)
    assert factory.kw.get("expire_on_commit") is False


def test_import_database_module_does_not_connect():
    """Verify importing database components does not initiate an active network connection."""
    # async_engine exists, but no connection pool checkout has occurred
    assert async_engine.pool.checkedin() == 0 or async_engine.pool.checkedout() == 0


def test_get_db_is_async_generator():
    """Verify get_db is an asynchronous generator function."""
    assert inspect.isasyncgenfunction(get_db)


@pytest.mark.asyncio
async def test_get_db_yields_session_and_cleans_up():
    """Verify get_db yields an AsyncSession and ensures session closure upon normal completion."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.close = AsyncMock()

    with patch("app.core.database.AsyncSessionLocal") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        sessions_yielded = []
        async for session in get_db():
            sessions_yielded.append(session)
            assert session is mock_session
            # Session must not be prematurely closed while active
            mock_session.close.assert_not_called()

        assert len(sessions_yielded) == 1
        # Upon completion, session.close must be awaited
        mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_cleans_up_on_exception():
    """Verify get_db guarantees session closure even if an exception occurs during request execution."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.close = AsyncMock()

    with patch("app.core.database.AsyncSessionLocal") as mock_factory:
        mock_factory.return_value.__aenter__.return_value = mock_session
        mock_factory.return_value.__aexit__.return_value = None

        # Simulate FastAPI dependency execution with exception injection
        gen = get_db()
        session = await anext(gen)
        assert session is mock_session

        with pytest.raises(RuntimeError, match="Simulated route error"):
            await gen.athrow(RuntimeError("Simulated route error"))

        # Session cleanup must have executed in finally block
        mock_session.close.assert_awaited_once()
