"""Automated tests for Experiment and PreparationChecklist SQLAlchemy 2.x models."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base
from app.modules.auth.models import User
from app.modules.users.models import UserSettings  # noqa: F401
import app.modules.viva.models  # noqa: F401
import app.modules.documents.models  # noqa: F401
from app.modules.experiments.models import (
    Experiment,
    PreparationChecklist,
    default_preparation_checklist_items,
)


def test_models_inherit_from_declarative_base():
    """Verify Experiment and PreparationChecklist inherit from the shared Base."""
    assert issubclass(Experiment, Base)
    assert issubclass(PreparationChecklist, Base)


def test_models_registered_in_base_metadata():
    """Verify both tables are registered in Base.metadata for Alembic discovery."""
    assert "experiments" in Base.metadata.tables
    assert "preparation_checklists" in Base.metadata.tables


def test_uuid_primary_keys_configured():
    """Verify primary keys are UUID types with uuid.uuid4 defaults."""
    exp_mapper = sa_inspect(Experiment)
    exp_pk = exp_mapper.primary_key
    assert len(exp_pk) == 1
    assert exp_pk[0].name == "id"
    assert exp_pk[0].type.python_type is uuid.UUID

    chk_mapper = sa_inspect(PreparationChecklist)
    chk_pk = chk_mapper.primary_key
    assert len(chk_pk) == 1
    assert chk_pk[0].name == "id"
    assert chk_pk[0].type.python_type is uuid.UUID


def test_experiment_foreign_key_to_user():
    """Verify Experiment has a valid foreign key referencing users.id with CASCADE."""
    table = Experiment.__table__
    assert table.c.user_id.nullable is False
    assert table.c.user_id.index is True

    fks = list(table.c.user_id.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "users.id"
    assert fk.ondelete == "CASCADE"


def test_experiment_content_sections_represented():
    """Verify all six standard lab manual content sections plus objective & description exist."""
    table = Experiment.__table__

    # Core metadata columns
    assert table.c.title.nullable is False
    assert table.c.subject.nullable is False
    assert table.c.creation_method.nullable is False
    assert table.c.has_manual_file.nullable is False
    assert table.c.status.nullable is False

    # Six documented lab manual content sections
    content_sections = [
        "theory",
        "apparatus",
        "procedure",
        "observations",
        "calculations",
        "precautions",
    ]
    for section in content_sections:
        assert section in table.c, f"Section {section} missing from experiments table"
        col = table.c[section]
        assert col.nullable is True, f"Section {section} should be nullable"

    # Additional documented overview sections
    assert "objective" in table.c
    assert table.c.objective.nullable is True
    assert "description" in table.c
    assert table.c.description.nullable is True


def test_preparation_checklist_foreign_key_to_experiment():
    """Verify PreparationChecklist foreign key references experiments.id with CASCADE."""
    table = PreparationChecklist.__table__
    assert table.c.experiment_id.nullable is False

    fks = list(table.c.experiment_id.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "experiments.id"
    assert fk.ondelete == "CASCADE"


def test_checklist_items_use_postgresql_jsonb():
    """Verify checklist items column uses PostgreSQL JSONB type."""
    table = PreparationChecklist.__table__
    assert "items" in table.c
    col = table.c["items"]
    assert isinstance(col.type, JSONB)
    assert col.nullable is False


def test_ownership_and_uniqueness_constraints():
    """Verify database-level uniqueness enforces one checklist per experiment."""
    table = PreparationChecklist.__table__
    assert table.c.experiment_id.unique is True


def test_timezone_aware_timestamp_columns():
    """Verify created_at and updated_at are timezone-aware UTC across both models."""
    for model in (Experiment, PreparationChecklist):
        table = model.__table__
        assert table.c.created_at.type.timezone is True
        assert table.c.created_at.nullable is False
        assert table.c.updated_at.type.timezone is True
        assert table.c.updated_at.nullable is False


def test_orm_relationships_bidirectional():
    """Verify bidirectional relationships between User <-> Experiment and Experiment <-> Checklist."""
    # User <-> Experiment
    user_mapper = sa_inspect(User)
    assert "experiments" in user_mapper.relationships
    user_exp_rel = user_mapper.relationships["experiments"]
    assert user_exp_rel.target.name == "experiments"
    assert user_exp_rel.back_populates == "user"

    exp_mapper = sa_inspect(Experiment)
    assert "user" in exp_mapper.relationships
    exp_user_rel = exp_mapper.relationships["user"]
    assert exp_user_rel.target.name == "users"
    assert exp_user_rel.back_populates == "experiments"

    # Experiment <-> PreparationChecklist
    assert "checklist" in exp_mapper.relationships
    exp_chk_rel = exp_mapper.relationships["checklist"]
    assert exp_chk_rel.target.name == "preparation_checklists"
    assert exp_chk_rel.back_populates == "experiment"
    assert exp_chk_rel.uselist is False

    chk_mapper = sa_inspect(PreparationChecklist)
    assert "experiment" in chk_mapper.relationships
    chk_exp_rel = chk_mapper.relationships["experiment"]
    assert chk_exp_rel.target.name == "experiments"
    assert chk_exp_rel.back_populates == "checklist"


def test_cascade_behavior_configured():
    """Verify cascade deletes prevent orphaned experiments and checklists."""
    user_mapper = sa_inspect(User)
    user_exp_rel = user_mapper.relationships["experiments"]
    assert user_exp_rel.cascade.delete_orphan is True

    exp_mapper = sa_inspect(Experiment)
    exp_chk_rel = exp_mapper.relationships["checklist"]
    assert exp_chk_rel.cascade.delete_orphan is True


def test_model_metadata_inspection_offline_and_defaults():
    """Verify offline instantiation, default checklist factory, and representation."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    exp = Experiment(
        id=exp_id,
        user_id=user_id,
        title="Superposition Theorem",
        subject="Basic Electrical Engineering",
        experiment_number="EXP-03",
        status="ready",
        theory="Linear bilateral network analysis.",
        apparatus="DC Power supply, resistors, multimeter.",
        procedure="1. Connect circuit. 2. Measure current.",
        precautions="Do not exceed resistor wattage.",
    )
    assert str(exp_id) in repr(exp)
    assert "Superposition Theorem" in repr(exp)
    assert "Basic Electrical Engineering" in repr(exp)

    # Verify default checklist items structure matches frontend contract
    defaults = default_preparation_checklist_items()
    assert isinstance(defaults, dict)
    expected_keys = {"objective", "theory", "apparatus", "procedure", "precautions"}
    assert set(defaults.keys()) == expected_keys
    for k in expected_keys:
        assert defaults[k] is False

    checklist = PreparationChecklist(
        experiment_id=exp_id,
        items=defaults,
    )
    assert str(exp_id) in repr(checklist)
    assert checklist.items["theory"] is False
