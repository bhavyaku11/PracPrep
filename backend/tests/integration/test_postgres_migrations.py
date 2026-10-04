"""PostgreSQL Schema & Migrations Integration Tests (TASK-15.3 - Area A).

Validates table creation, column types, primary keys, foreign keys,
unique constraints, indexes, and migration idempotency against real PostgreSQL 16.
"""

from pathlib import Path
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_all_expected_tables_exist(test_engine: AsyncEngine) -> None:
    """Verify that all domain tables and Alembic version tracking table exist in PostgreSQL."""
    expected_tables = {
        "alembic_version",
        "users",
        "user_settings",
        "experiments",
        "preparation_checklists",
        "viva_sessions",
        "viva_answers",
        "uploaded_documents",
        "guest_migrations",
    }

    async with test_engine.connect() as conn:
        res = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
        ))
        actual_tables = {row[0] for row in res.fetchall()}

    assert expected_tables.issubset(actual_tables), (
        f"Missing tables in PostgreSQL: {expected_tables - actual_tables}"
    )


async def test_table_columns_and_types(test_engine: AsyncEngine) -> None:
    """Verify that key columns in PostgreSQL have expected types (e.g. UUID, JSON, TIMESTAMPTZ)."""
    def check_schema(sync_conn):
        inspector = inspect(sync_conn)

        # Check users table
        user_cols = {c["name"]: str(c["type"]).lower() for c in inspector.get_columns("users")}
        assert "id" in user_cols
        assert "uuid" in user_cols["id"]
        assert "email" in user_cols
        assert "created_at" in user_cols

        # Check experiments table
        exp_cols = {c["name"]: str(c["type"]).lower() for c in inspector.get_columns("experiments")}
        assert "id" in exp_cols
        assert "uuid" in exp_cols["id"]
        assert "title" in exp_cols
        assert "subject" in exp_cols
        assert "procedure" in exp_cols

        # Check uploaded_documents table
        doc_cols = {c["name"]: str(c["type"]).lower() for c in inspector.get_columns("uploaded_documents")}
        assert "id" in doc_cols
        assert "extracted_data" in doc_cols
        assert "json" in doc_cols["extracted_data"]

        # Check checklists table
        chk_cols = {c["name"]: str(c["type"]).lower() for c in inspector.get_columns("preparation_checklists")}
        assert "items" in chk_cols
        assert "json" in chk_cols["items"]

        # Check viva_sessions table
        viva_cols = {c["name"]: str(c["type"]).lower() for c in inspector.get_columns("viva_sessions")}
        assert "topic_analysis" in viva_cols
        assert "json" in viva_cols["topic_analysis"]

        # Check guest_migrations table
        mig_cols = {c["name"]: str(c["type"]).lower() for c in inspector.get_columns("guest_migrations")}
        assert "idempotency_key" in mig_cols
        assert "status" in mig_cols
        assert "experiments_migrated" in mig_cols

    async with test_engine.connect() as conn:
        await conn.run_sync(check_schema)


async def test_primary_key_constraints(test_engine: AsyncEngine) -> None:
    """Verify primary key constraints exist on all application tables."""
    tables_to_check = [
        "users",
        "user_settings",
        "experiments",
        "preparation_checklists",
        "viva_sessions",
        "viva_answers",
        "uploaded_documents",
        "guest_migrations",
    ]

    def check_pks(sync_conn):
        inspector = inspect(sync_conn)
        for table in tables_to_check:
            pk = inspector.get_pk_constraint(table)
            assert pk is not None, f"Table '{table}' has no primary key constraint"
            assert len(pk.get("constrained_columns", [])) > 0, f"Table '{table}' has empty primary key"

    async with test_engine.connect() as conn:
        await conn.run_sync(check_pks)


async def test_foreign_key_constraints(test_engine: AsyncEngine) -> None:
    """Verify foreign key constraints link dependent tables to their parent entities."""
    expected_fks = {
        "user_settings": ("users", ["user_id"]),
        "experiments": ("users", ["user_id"]),
        "preparation_checklists": ("experiments", ["experiment_id"]),
        "viva_sessions": ("users", ["user_id"]),
        "viva_answers": ("viva_sessions", ["session_id"]),
        "uploaded_documents": ("users", ["user_id"]),
        "guest_migrations": ("users", ["user_id"]),
    }

    def check_fks(sync_conn):
        inspector = inspect(sync_conn)
        for child_table, (parent_table, cols) in expected_fks.items():
            fks = inspector.get_foreign_keys(child_table)
            matched = False
            for fk in fks:
                if fk["referred_table"] == parent_table and fk["constrained_columns"] == cols:
                    matched = True
                    break
            assert matched, f"Missing foreign key: {child_table}.{cols} -> {parent_table}"

    async with test_engine.connect() as conn:
        await conn.run_sync(check_fks)


async def test_unique_constraints_and_indexes(test_engine: AsyncEngine) -> None:
    """Verify unique constraints and indexes in PostgreSQL."""
    def check_uniques(sync_conn):
        inspector = inspect(sync_conn)

        # users.email must be unique
        user_uniques = inspector.get_unique_constraints("users")
        user_indexes = inspector.get_indexes("users")
        email_unique = any(
            "email" in u.get("column_names", []) for u in user_uniques
        ) or any(
            i.get("unique") and "email" in i.get("column_names", []) for i in user_indexes
        )
        assert email_unique, "users.email must have a unique constraint or unique index"

        # guest_migrations composite unique: (user_id, idempotency_key)
        mig_uniques = inspector.get_unique_constraints("guest_migrations")
        mig_indexes = inspector.get_indexes("guest_migrations")
        has_idempotency_uq = any(
            set(u.get("column_names", [])) == {"user_id", "idempotency_key"} for u in mig_uniques
        ) or any(
            i.get("unique") and set(i.get("column_names", [])) == {"user_id", "idempotency_key"} for i in mig_indexes
        )
        assert has_idempotency_uq, "guest_migrations must enforce composite unique constraint (user_id, idempotency_key)"

    async with test_engine.connect() as conn:
        await conn.run_sync(check_uniques)


async def test_alembic_upgrade_head_is_idempotent(test_engine: AsyncEngine) -> None:
    """Verify running 'alembic upgrade head' against an already up-to-date schema produces no changes."""
    import asyncio
    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent.parent
    alembic_ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(alembic_ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", test_engine.url.render_as_string(hide_password=False))

    # Re-running upgrade head must not raise any exceptions
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")

    # Verify alembic_version has the latest revision
    async with test_engine.connect() as conn:
        res = await conn.execute(text("SELECT version_num FROM alembic_version"))
        version = res.scalar()
        assert version == "c7e3f1a2b4d5", f"Unexpected alembic version: {version}"
