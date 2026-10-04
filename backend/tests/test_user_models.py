"""Automated tests for User and UserSettings SQLAlchemy 2.x declarative models."""

import uuid
import pytest
from sqlalchemy import inspect as sa_inspect
from app.core.database import Base
from app.modules.auth.models import User
from app.modules.users.models import UserSettings
import app.modules.experiments.models  # noqa: F401
import app.modules.viva.models  # noqa: F401
import app.modules.documents.models  # noqa: F401


def test_models_inherit_from_declarative_base():
    """Verify User and UserSettings inherit from the shared Base."""
    assert issubclass(User, Base)
    assert issubclass(UserSettings, Base)


def test_models_registered_in_base_metadata():
    """Verify both tables are registered in Base.metadata for Alembic discovery."""
    assert "users" in Base.metadata.tables
    assert "user_settings" in Base.metadata.tables


def test_user_model_primary_key_and_columns():
    """Verify User primary key is a UUID and columns match schema specification."""
    mapper = sa_inspect(User)
    pk_cols = mapper.primary_key
    assert len(pk_cols) == 1
    assert pk_cols[0].name == "id"
    assert pk_cols[0].type.python_type is uuid.UUID

    table = User.__table__
    assert table.c.email.unique is True
    assert table.c.email.nullable is False
    assert table.c.password_hash.nullable is False
    assert table.c.full_name.nullable is False
    assert table.c.university.nullable is True
    assert table.c.is_active.nullable is False
    assert table.c.auth_provider.nullable is False


def test_user_email_normalization():
    """Verify email normalization strips surrounding whitespace and converts to lowercase."""
    user = User(
        email="  ALEX.Morgan@PracPrep.EDU  ",
        password_hash="argon2id$hashed",
        full_name="Alex Morgan",
    )
    assert user.email == "alex.morgan@pracprep.edu"


def test_user_email_empty_rejected():
    """Verify empty or whitespace-only email raises ValueError."""
    with pytest.raises(ValueError, match="Email cannot be empty"):
        User(
            email="   ",
            password_hash="hash",
            full_name="Alex",
        )


def test_user_settings_foreign_key_and_uniqueness():
    """Verify UserSettings foreign key references users.id with unique constraint and cascade."""
    table = UserSettings.__table__
    assert table.c.user_id.unique is True
    assert table.c.user_id.nullable is False

    foreign_keys = list(table.c.user_id.foreign_keys)
    assert len(foreign_keys) == 1
    fk = foreign_keys[0]
    assert fk.target_fullname == "users.id"
    assert fk.ondelete == "CASCADE"


def test_user_settings_study_preferences_columns():
    """Verify study preference fields exist with expected defaults."""
    table = UserSettings.__table__
    assert table.c.default_difficulty.nullable is False
    assert table.c.default_question_count.nullable is False
    assert table.c.preferred_focus.nullable is False

    # Verify column defaults
    assert table.c.default_difficulty.default.arg == "medium"
    assert table.c.default_question_count.default.arg == 5
    assert table.c.preferred_focus.default.arg == "all"


def test_timezone_aware_timestamp_columns():
    """Verify created_at and updated_at are timezone-aware across both models."""
    for model in (User, UserSettings):
        table = model.__table__
        assert table.c.created_at.type.timezone is True
        assert table.c.created_at.nullable is False
        assert table.c.updated_at.type.timezone is True
        assert table.c.updated_at.nullable is False


def test_bidirectional_relationship():
    """Verify 1-to-1 relationship between User and UserSettings with delete-orphan cascade."""
    user_mapper = sa_inspect(User)
    settings_rel = user_mapper.relationships["settings"]

    assert settings_rel.target.name == "user_settings"
    assert settings_rel.uselist is False
    assert settings_rel.cascade.delete_orphan is True

    settings_mapper = sa_inspect(UserSettings)
    user_rel = settings_mapper.relationships["user"]

    assert user_rel.target.name == "users"
    assert user_rel.back_populates == "settings"


def test_model_repr():
    """Verify repr outputs clean diagnostic strings without exposing secrets."""
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="student@pracprep.edu",
        password_hash="secret_hash_not_in_repr",
        full_name="Student Name",
    )
    user_repr = repr(user)
    assert str(user_id) in user_repr
    assert "student@pracprep.edu" in user_repr
    assert "secret_hash" not in user_repr

    settings = UserSettings(
        user_id=user_id,
        default_difficulty="medium",
        preferred_focus="all",
    )
    settings_repr = repr(settings)
    assert str(user_id) in settings_repr
    assert "medium" in settings_repr
