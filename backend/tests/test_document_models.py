"""Automated tests for UploadedDocument SQLAlchemy 2.x declarative model."""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base
from app.modules.auth.models import User
from app.modules.users.models import UserSettings  # noqa: F401
from app.modules.experiments.models import Experiment, PreparationChecklist  # noqa: F401
from app.modules.viva.models import VivaAnswer, VivaSession  # noqa: F401
from app.modules.documents.models import UploadedDocument


def test_models_inherit_from_declarative_base():
    """Verify UploadedDocument inherits from the shared Base."""
    assert issubclass(UploadedDocument, Base)


def test_models_registered_in_base_metadata():
    """Verify uploaded_documents table is registered in Base.metadata for Alembic discovery."""
    assert "uploaded_documents" in Base.metadata.tables


def test_uuid_primary_keys_configured():
    """Verify primary key is UUID type with uuid.uuid4 default."""
    mapper = sa_inspect(UploadedDocument)
    pk_cols = mapper.primary_key
    assert len(pk_cols) == 1
    assert pk_cols[0].name == "id"
    assert pk_cols[0].type.python_type is uuid.UUID


def test_document_foreign_keys_and_cascades():
    """Verify user_id and experiment_id foreign keys and cascade configuration."""
    table = UploadedDocument.__table__

    # user_id foreign key (mandatory ownership)
    assert table.c.user_id.nullable is False
    assert table.c.user_id.index is True
    user_fks = list(table.c.user_id.foreign_keys)
    assert len(user_fks) == 1
    assert user_fks[0].target_fullname == "users.id"
    assert user_fks[0].ondelete == "CASCADE"

    # experiment_id foreign key (optional association with experiment)
    assert table.c.experiment_id.nullable is True
    assert table.c.experiment_id.index is True
    exp_fks = list(table.c.experiment_id.foreign_keys)
    assert len(exp_fks) == 1
    assert exp_fks[0].target_fullname == "experiments.id"
    assert exp_fks[0].ondelete == "CASCADE"


def test_document_metadata_and_lifecycle_fields():
    """Verify document metadata, storage, status, and extraction fields."""
    table = UploadedDocument.__table__

    # File metadata
    assert table.c.file_name.nullable is False
    assert table.c.file_size_bytes.nullable is False
    assert table.c.mime_type.nullable is False
    assert table.c.storage_path.nullable is False

    # Status field with default "pending"
    assert table.c.status.nullable is False
    assert table.c.status.default.arg == "pending"
    assert table.c.status.index is True

    # Extraction fields
    assert table.c.extracted_text.nullable is True
    assert table.c.error_message.nullable is True
    assert isinstance(table.c["extracted_data"].type, JSONB)
    assert table.c["extracted_data"].nullable is False


def test_timezone_aware_timestamp_columns():
    """Verify created_at and updated_at are timezone-aware UTC."""
    table = UploadedDocument.__table__
    assert table.c.created_at.type.timezone is True
    assert table.c.created_at.nullable is False
    assert table.c.updated_at.type.timezone is True
    assert table.c.updated_at.nullable is False


def test_orm_relationships_bidirectional():
    """Verify bidirectional relationships among User, Experiment, and UploadedDocument."""
    # User <-> UploadedDocument
    user_mapper = sa_inspect(User)
    assert "documents" in user_mapper.relationships
    user_doc_rel = user_mapper.relationships["documents"]
    assert user_doc_rel.target.name == "uploaded_documents"
    assert user_doc_rel.back_populates == "user"

    doc_mapper = sa_inspect(UploadedDocument)
    assert "user" in doc_mapper.relationships
    doc_user_rel = doc_mapper.relationships["user"]
    assert doc_user_rel.target.name == "users"
    assert doc_user_rel.back_populates == "documents"

    # Experiment <-> UploadedDocument
    exp_mapper = sa_inspect(Experiment)
    assert "documents" in exp_mapper.relationships
    exp_doc_rel = exp_mapper.relationships["documents"]
    assert exp_doc_rel.target.name == "uploaded_documents"
    assert exp_doc_rel.back_populates == "experiment"

    assert "experiment" in doc_mapper.relationships
    doc_exp_rel = doc_mapper.relationships["experiment"]
    assert doc_exp_rel.target.name == "experiments"
    assert doc_exp_rel.back_populates == "documents"


def test_cascade_behavior_configured():
    """Verify cascade deletes prevent orphaned uploaded documents."""
    user_mapper = sa_inspect(User)
    assert user_mapper.relationships["documents"].cascade.delete_orphan is True

    exp_mapper = sa_inspect(Experiment)
    assert exp_mapper.relationships["documents"].cascade.delete_orphan is True


def test_model_metadata_inspection_offline_and_defaults():
    """Verify offline instantiation, repr diagnostics, and defaults without live DB."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    doc = UploadedDocument(
        id=doc_id,
        user_id=user_id,
        experiment_id=exp_id,
        file_name="electrical_lab_manual.pdf",
        file_size_bytes=1024 * 1024 * 2,  # 2 MB
        mime_type="application/pdf",
        storage_path="/uploads/manuals/electrical_lab_manual.pdf",
        status="completed",
        extracted_text="Experiment 1: Ohm's Law Verification...",
        extracted_data={
            "title": "Ohm's Law Verification",
            "subject": "Basic Electrical",
            "objective": "Verify V = IR relationship.",
        },
    )

    assert str(doc_id) in repr(doc)
    assert "electrical_lab_manual.pdf" in repr(doc)
    assert "completed" in repr(doc)
    assert doc.extracted_data["title"] == "Ohm's Law Verification"
