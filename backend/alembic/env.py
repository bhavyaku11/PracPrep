"""Alembic Environment Script for Asynchronous Migrations.

Integrates SQLAlchemy 2.x Base.metadata with the centralized application settings
and executes migrations asynchronously via asyncpg.
"""

import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Import PracPrep domain metadata and application settings
from app.core.config import get_settings
from app.core.database import Base
import app.modules.auth.models  # noqa: F401
import app.modules.users.models  # noqa: F401
import app.modules.experiments.models  # noqa: F401
import app.modules.viva.models  # noqa: F401
import app.modules.documents.models  # noqa: F401

config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set model metadata for autogenerate support
target_metadata = Base.metadata


def get_url() -> str:
    """Return the database URL from centralized application settings or config override."""
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    return get_settings().DATABASE_URL


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Configures the context with just a URL and not an Engine.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within an active synchronous connection proxy."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an asynchronous engine and execute online migrations."""
    connectable = create_async_engine(
        get_url(),
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an asyncio event loop."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
