"""Pytest configuration and fixtures for PostgreSQL integration tests.

Provides isolated database connection management, preflight safety guards,
and transactional cleanup against a real PostgreSQL 16 instance.
"""

from collections.abc import AsyncGenerator
import os
from pathlib import Path
from urllib.parse import urlparse
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.database import Base

# Ensure all declarative models are imported and registered with SQLAlchemy's registry
import app.modules.auth.models  # noqa: F401
import app.modules.users.models  # noqa: F401
import app.modules.experiments.models  # noqa: F401
import app.modules.viva.models  # noqa: F401
import app.modules.documents.models  # noqa: F401

# Default isolated integration test database connection URL
DEFAULT_TEST_DB_URL = "postgresql+asyncpg://postgres_test:postgres_test_password@localhost:5433/pracprep_test"


def get_test_db_url() -> str:
    """Resolve and validate the PostgreSQL integration test database URL."""
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DB_URL)
    return url


def validate_test_database_safety(url: str) -> None:
    """Enforce strict safety guards preventing execution against non-test databases."""
    parsed = urlparse(url)
    db_name = parsed.path.lstrip("/").lower()
    dev_settings = get_settings()
    dev_db = urlparse(dev_settings.DATABASE_URL).path.lstrip("/").lower()

    # Reject if database name does not contain 'test'
    if "test" not in db_name:
        raise RuntimeError(
            f"[PostgreSQL Safety Violation] Target database '{db_name}' is not a test database. "
            "Integration tests require a database name containing 'test' (e.g. 'pracprep_test')."
        )

    # Reject if target database matches ordinary development or production database name
    if db_name == dev_db or db_name in ("pracprep", "production", "prod", "main"):
        raise RuntimeError(
            f"[PostgreSQL Safety Violation] Target database '{db_name}' matches development/production database. "
            "Refusing to execute tests against shared environments."
        )


@pytest.fixture(scope="session")
def test_db_url() -> str:
    """Return validated test database URL."""
    url = get_test_db_url()
    validate_test_database_safety(url)
    return url


@pytest_asyncio.fixture
async def test_engine(test_db_url: str) -> AsyncGenerator[AsyncEngine, None]:
    """Provide AsyncEngine with NullPool connected to the real PostgreSQL test database.

    Using NullPool ensures every connection is created and closed on the active event loop,
    preventing cross-loop connection leakage.
    """
    from sqlalchemy.pool import NullPool

    engine = create_async_engine(
        test_db_url,
        poolclass=NullPool,
        echo=False,
    )

    # Preflight connectivity check
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        raise RuntimeError(
            f"\n\n[PostgreSQL Integration Preflight Error]\n"
            f"Failed to connect to the PostgreSQL integration test database at:\n"
            f"    {test_db_url}\n\n"
            f"Root Cause: {exc}\n\n"
            f"To launch the isolated test database, run:\n"
            f"    docker compose --profile test up -d test-db\n"
        ) from exc

    yield engine

    await engine.dispose()


@pytest_asyncio.fixture
def session_factory(test_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Return an async_sessionmaker bound to the PostgreSQL test engine."""
    return async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(autouse=True)
async def clean_database(test_engine: AsyncEngine) -> AsyncGenerator[None, None]:
    """Clean all domain tables before each test to guarantee complete test isolation."""
    tables = [
        "viva_answers",
        "viva_sessions",
        "uploaded_documents",
        "preparation_checklists",
        "experiments",
        "guest_migrations",
        "user_settings",
        "users",
    ]
    truncate_sql = f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE;"
    
    async with test_engine.begin() as conn:
        await conn.execute(text(truncate_sql))

    yield

    async with test_engine.begin() as conn:
        await conn.execute(text(truncate_sql))


@pytest_asyncio.fixture
async def db_session(session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Provide an isolated AsyncSession connected to the test PostgreSQL database."""
    async with session_factory() as session:
        yield session
        await session.rollback()
