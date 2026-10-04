"""Automated tests for Alembic async migration configuration, template, and metadata binding."""

import os
from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory
from app.core.config import get_settings
from app.core.database import Base


BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI_PATH = BACKEND_DIR / "alembic.ini"
ALEMBIC_DIR = BACKEND_DIR / "alembic"
TEMPLATE_PATH = ALEMBIC_DIR / "script.py.mako"
ENV_PY_PATH = ALEMBIC_DIR / "env.py"


def test_alembic_ini_exists_and_loads():
    """Verify alembic.ini exists and can be loaded into an Alembic Config object."""
    assert ALEMBIC_INI_PATH.exists()
    config = Config(str(ALEMBIC_INI_PATH))
    assert config.get_main_option("script_location") == "alembic"


def test_alembic_ini_does_not_hardcode_database_credentials():
    """Verify alembic.ini leaves sqlalchemy.url blank to enforce dynamic settings loading."""
    config = Config(str(ALEMBIC_INI_PATH))
    raw_url = config.get_main_option("sqlalchemy.url")
    assert raw_url is None or raw_url.strip() == ""


def test_script_directory_discovery():
    """Verify Alembic can discover the configured script directory and versions path."""
    config = Config(str(ALEMBIC_INI_PATH))
    # Point script_location to absolute path for test execution
    config.set_main_option("script_location", str(ALEMBIC_DIR))

    script_dir = ScriptDirectory.from_config(config)
    assert script_dir.dir == str(ALEMBIC_DIR)
    assert Path(script_dir.versions).exists()


def test_migration_template_structure():
    """Verify script.py.mako exists and contains typed upgrade and downgrade functions."""
    assert TEMPLATE_PATH.exists()
    content = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "def upgrade() -> None:" in content
    assert "def downgrade() -> None:" in content
    assert "revision: str = " in content
    assert "down_revision: Union[str, None] = " in content


def test_env_py_references_base_metadata_and_settings():
    """Verify env.py binds target_metadata to Base.metadata and sources URL from get_settings."""
    assert ENV_PY_PATH.exists()
    env_content = ENV_PY_PATH.read_text(encoding="utf-8")

    # Metadata binding
    assert "from app.core.database import Base" in env_content
    assert "target_metadata = Base.metadata" in env_content

    # Dynamic settings retrieval
    assert "from app.core.config import get_settings" in env_content
    assert "get_settings().DATABASE_URL" in env_content

    # Target metadata is valid DeclarativeBase metadata
    assert Base.metadata is not None


def test_offline_migration_configuration_without_database():
    """Verify offline context configuration executes cleanly with static SQL generation without a database."""
    from alembic.runtime.environment import EnvironmentContext

    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_DIR))

    script = ScriptDirectory.from_config(config)

    # Run migration environment in offline (as_sql=True) mode
    executed = False

    def dummy_fn(rev, context):
        nonlocal executed
        executed = True
        return []

    with EnvironmentContext(config, script, fn=dummy_fn, as_sql=True):
        script.run_env()

    assert executed is True


def test_baseline_migration_exists_and_contains_all_tables():
    """Verify the initial baseline migration exists and defines all 7 core tables."""
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_DIR))

    script_dir = ScriptDirectory.from_config(config)
    # Baseline migration is the root of the revision DAG
    base_revision = script_dir.get_base()
    assert base_revision is not None

    base_script = script_dir.get_revision(base_revision)
    assert base_script is not None
    assert base_script.doc is not None
    assert "create_initial_schema" in base_script.doc

    # Read baseline migration source code
    migration_path = Path(base_script.path)
    assert migration_path.exists()
    content = migration_path.read_text(encoding="utf-8")

    expected_tables = [
        "users",
        "user_settings",
        "experiments",
        "preparation_checklists",
        "viva_sessions",
        "viva_answers",
        "uploaded_documents",
    ]
    for table_name in expected_tables:
        assert f"'{table_name}'" in content, f"Table {table_name} missing from baseline migration"
        assert f"op.create_table(\n        '{table_name}'" in content or f"op.create_table(\n        \"{table_name}\"" in content or f"'{table_name}'" in content

    # Verify both upgrade and downgrade are populated
    assert "def upgrade() -> None:" in content
    assert "def downgrade() -> None:" in content
    for table_name in expected_tables:
        assert f"op.drop_table('{table_name}')" in content


def test_guest_migrations_migration_exists_and_is_valid():
    """Verify the guest migrations revision exists, creates guest_migrations table with idempotency constraint."""
    config = Config(str(ALEMBIC_INI_PATH))
    config.set_main_option("script_location", str(ALEMBIC_DIR))

    script_dir = ScriptDirectory.from_config(config)
    head_revision = script_dir.get_current_head()
    assert head_revision == "c7e3f1a2b4d5"

    head_script = script_dir.get_revision(head_revision)
    assert head_script is not None
    assert head_script.down_revision == "560f2b7c6d76"

    content = Path(head_script.path).read_text(encoding="utf-8")
    assert "'guest_migrations'" in content
    assert "uq_user_guest_migration_idempotency" in content
    assert "def upgrade() -> None:" in content
    assert "def downgrade() -> None:" in content
    assert "op.drop_table('guest_migrations')" in content


def test_alembic_metadata_discovers_all_seven_models():
    """Verify Base.metadata dynamically registers all domain tables including guest_migrations."""
    import app.modules.auth.models  # noqa: F401
    import app.modules.users.models  # noqa: F401
    import app.modules.experiments.models  # noqa: F401
    import app.modules.viva.models  # noqa: F401
    import app.modules.documents.models  # noqa: F401

    expected_tables = {
        "users",
        "user_settings",
        "experiments",
        "preparation_checklists",
        "viva_sessions",
        "viva_answers",
        "uploaded_documents",
        "guest_migrations",
    }
    assert expected_tables.issubset(set(Base.metadata.tables.keys()))


