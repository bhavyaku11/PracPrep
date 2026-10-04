"""PostgreSQL Uploaded Documents Integration Tests (TASK-15.3 - Area E).

Validates document metadata persistence, experiment-document relationships,
foreign-key integrity, deletion, and replacement behavior against real PostgreSQL 16.
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth.models import User
from app.modules.documents.models import UploadedDocument
from app.modules.experiments.models import Experiment

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_document_metadata_persistence(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify document metadata, JSONB extracted_data, and status persist correctly in PostgreSQL."""
    user_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"doc_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Doc User")
        doc = UploadedDocument(
            id=doc_id,
            user=user,
            file_name="physics_lab_manual.pdf",
            file_size_bytes=1048576,
            mime_type="application/pdf",
            storage_path="uploads/physics_lab_manual.pdf",
            status="completed",
            extracted_text="Raw OCR text extracted from the manual.",
            extracted_data={
                "title": "Young's Modulus Experiment",
                "sections": ["objective", "apparatus", "procedure"],
                "ocr_confidence": 0.98,
            },
        )
        session.add_all([user, doc])
        await session.commit()

    # Read from independent session
    async with session_factory() as session:
        res = await session.execute(select(UploadedDocument).where(UploadedDocument.id == doc_id))
        persisted_doc = res.scalar_one()

        assert persisted_doc.file_name == "physics_lab_manual.pdf"
        assert persisted_doc.file_size_bytes == 1048576
        assert persisted_doc.mime_type == "application/pdf"
        assert persisted_doc.status == "completed"
        assert persisted_doc.extracted_text == "Raw OCR text extracted from the manual."
        assert persisted_doc.extracted_data["title"] == "Young's Modulus Experiment"
        assert persisted_doc.extracted_data["ocr_confidence"] == 0.98
        assert persisted_doc.created_at is not None
        assert persisted_doc.created_at.tzinfo is not None


async def test_document_experiment_relationship_and_cascade(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify linking a document to an experiment and cascade deletion behavior."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"doc_exp_{user_id.hex[:6]}@example.com", password_hash="h", full_name="User")
        exp = Experiment(id=exp_id, user=user, title="Chemistry Titration", subject="Chemistry")
        doc = UploadedDocument(
            id=doc_id,
            user=user,
            experiment=exp,
            file_name="titration_manual.pdf",
            file_size_bytes=204800,
            mime_type="application/pdf",
            storage_path="uploads/titration_manual.pdf",
            status="completed",
        )
        session.add_all([user, exp, doc])
        await session.commit()

    # Verify link
    async with session_factory() as session:
        doc = (await session.execute(select(UploadedDocument).where(UploadedDocument.id == doc_id))).scalar_one()
        assert doc.experiment_id == exp_id

    # Delete experiment -> document should cascade delete in PostgreSQL
    async with session_factory() as session:
        exp = (await session.execute(select(Experiment).where(Experiment.id == exp_id))).scalar_one()
        await session.delete(exp)
        await session.commit()

    # Verify document is also deleted
    async with session_factory() as session:
        res = await session.execute(select(UploadedDocument).where(UploadedDocument.id == doc_id))
        assert res.scalar_one_or_none() is None


async def test_foreign_key_integrity_violations_rejected_by_postgres(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify PostgreSQL rejects inserting a document referencing a non-existent user or experiment."""
    non_existent_id = uuid.uuid4()

    # Invalid user_id
    async with session_factory() as session:
        doc = UploadedDocument(
            user_id=non_existent_id,
            file_name="orphan.pdf",
            file_size_bytes=1000,
            mime_type="application/pdf",
            storage_path="uploads/orphan.pdf",
        )
        session.add(doc)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()
        assert "foreign key constraint" in str(exc_info.value).lower()


async def test_document_replacement_workflow(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify replacing an uploaded document for an experiment updates metadata cleanly."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    doc1_id = uuid.uuid4()
    doc2_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"repl_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Repl User")
        exp = Experiment(id=exp_id, user=user, title="Ohm's Law", subject="Physics", file_name="doc_v1.pdf")
        doc1 = UploadedDocument(
            id=doc1_id,
            user=user,
            experiment=exp,
            file_name="doc_v1.pdf",
            file_size_bytes=5000,
            mime_type="application/pdf",
            storage_path="uploads/doc_v1.pdf",
            status="completed",
        )
        session.add_all([user, exp, doc1])
        await session.commit()

    # Perform replacement in new session: delete doc1, insert doc2, update exp.file_name
    async with session_factory() as session:
        d1 = (await session.execute(select(UploadedDocument).where(UploadedDocument.id == doc1_id))).scalar_one()
        await session.delete(d1)

        exp = (await session.execute(select(Experiment).where(Experiment.id == exp_id))).scalar_one()
        exp.file_name = "doc_v2_updated.pdf"

        doc2 = UploadedDocument(
            id=doc2_id,
            user_id=user_id,
            experiment_id=exp_id,
            file_name="doc_v2_updated.pdf",
            file_size_bytes=8000,
            mime_type="application/pdf",
            storage_path="uploads/doc_v2_updated.pdf",
            status="completed",
        )
        session.add(doc2)
        await session.commit()

    # Validate final state
    async with session_factory() as session:
        # doc1 must be gone
        res1 = await session.execute(select(UploadedDocument).where(UploadedDocument.id == doc1_id))
        assert res1.scalar_one_or_none() is None

        # doc2 must be active
        res2 = await session.execute(select(UploadedDocument).where(UploadedDocument.id == doc2_id))
        active_doc = res2.scalar_one()
        assert active_doc.file_name == "doc_v2_updated.pdf"
        assert active_doc.experiment_id == exp_id

        # experiment metadata updated
        res_exp = await session.execute(select(Experiment).where(Experiment.id == exp_id))
        updated_exp = res_exp.scalar_one()
        assert updated_exp.file_name == "doc_v2_updated.pdf"
