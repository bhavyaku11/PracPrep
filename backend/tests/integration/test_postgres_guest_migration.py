"""PostgreSQL Guest Migration Integration Tests (TASK-15.3 - Area F).

Validates relational remapping to server-generated IDs, idempotency constraints,
multi-user isolation, and atomic rollback on partial or invalid migration against real PostgreSQL 16.
"""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.experiments.models import Experiment, PreparationChecklist
from app.modules.users.models import GuestMigration
from app.modules.viva.models import VivaAnswer, VivaSession

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_guest_migration_persistence_and_remapping(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify guest migration persists experiments and remapped viva sessions with server UUIDs."""
    user_id = uuid.uuid4()
    server_exp_id = uuid.uuid4()
    server_session_id = uuid.uuid4()
    idempotency_key = f"mig_{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    # Session 1: Perform full migration
    async with session_factory() as session:
        user = User(id=user_id, email=f"mig_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Mig User")
        session.add(user)

        # Client experiment remapped to server_exp_id
        experiment = Experiment(
            id=server_exp_id,
            user=user,
            title="Calorimetry Experiment",
            subject="Thermodynamics",
            creation_method="guest_migration",
            created_at=now,
        )
        checklist = PreparationChecklist(
            experiment=experiment,
            items={"objective": True, "theory": True, "apparatus": True, "procedure": False, "precautions": False},
        )
        session.add_all([experiment, checklist])

        # Client viva session remapped to server_exp_id and server_session_id
        viva_session = VivaSession(
            id=server_session_id,
            user=user,
            experiment=experiment,
            difficulty="intermediate",
            question_count=1,
            is_completed=True,
            created_at=now,
        )
        answer = VivaAnswer(
            session=viva_session,
            question_number=1,
            question_text="What is specific heat?",
            student_answer="Heat needed per unit mass per degree.",
            score=10,
            verdict="correct",
            created_at=now,
        )
        session.add_all([viva_session, answer])

        # Record migration tracking
        migration_record = GuestMigration(
            user=user,
            idempotency_key=idempotency_key,
            status="completed",
            experiments_migrated=1,
            viva_sessions_migrated=1,
            viva_answers_migrated=1,
            created_at=now,
        )
        session.add(migration_record)
        await session.commit()

    # Session 2: Verify in independent session
    async with session_factory() as session:
        # Check migration record
        mig_res = await session.execute(
            select(GuestMigration).where(
                GuestMigration.user_id == user_id,
                GuestMigration.idempotency_key == idempotency_key,
            )
        )
        mig = mig_res.scalar_one()
        assert mig.status == "completed"
        assert mig.experiments_migrated == 1
        assert mig.viva_sessions_migrated == 1
        assert mig.viva_answers_migrated == 1

        # Check remapped relationships
        sess_res = await session.execute(
            select(VivaSession)
            .options(selectinload(VivaSession.answers), selectinload(VivaSession.experiment))
            .where(VivaSession.id == server_session_id)
        )
        persisted_sess = sess_res.scalar_one()
        assert persisted_sess.experiment_id == server_exp_id
        assert persisted_sess.experiment.title == "Calorimetry Experiment"
        assert len(persisted_sess.answers) == 1
        assert persisted_sess.answers[0].score == 10


async def test_guest_migration_composite_unique_idempotency_constraint(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify PostgreSQL rejects duplicate migrations with the same (user_id, idempotency_key)."""
    user_id = uuid.uuid4()
    shared_key = f"idempotent_key_{uuid.uuid4().hex[:8]}"

    async with session_factory() as session:
        user = User(id=user_id, email=f"dup_{user_id.hex[:6]}@example.com", password_hash="h", full_name="User")
        session.add(user)

        mig1 = GuestMigration(
            user=user,
            idempotency_key=shared_key,
            status="completed",
            experiments_migrated=2,
        )
        session.add(mig1)
        await session.commit()

    # Attempt second migration with identical (user_id, idempotency_key)
    async with session_factory() as session:
        mig2 = GuestMigration(
            user_id=user_id,
            idempotency_key=shared_key,
            status="completed",
            experiments_migrated=2,
        )
        session.add(mig2)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()

        assert "uq_user_guest_migration_idempotency" in str(exc_info.value) or "duplicate key" in str(exc_info.value)


async def test_guest_migration_idempotency_key_multi_user_isolation(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify different users can have identical idempotency keys without constraint violation."""
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    shared_key = "common_client_migration_token_123"

    async with session_factory() as session:
        u1 = User(id=user1_id, email=f"iso1_{user1_id.hex[:6]}@example.com", password_hash="h", full_name="U1")
        u2 = User(id=user2_id, email=f"iso2_{user2_id.hex[:6]}@example.com", password_hash="h", full_name="U2")

        mig1 = GuestMigration(user=u1, idempotency_key=shared_key, status="completed", experiments_migrated=1)
        mig2 = GuestMigration(user=u2, idempotency_key=shared_key, status="completed", experiments_migrated=3)

        session.add_all([u1, u2, mig1, mig2])
        await session.commit()

    # Both must exist independently in PostgreSQL
    async with session_factory() as session:
        res1 = await session.execute(select(GuestMigration).where(GuestMigration.user_id == user1_id))
        res2 = await session.execute(select(GuestMigration).where(GuestMigration.user_id == user2_id))

        m1 = res1.scalar_one()
        m2 = res2.scalar_one()

        assert m1.idempotency_key == shared_key
        assert m1.experiments_migrated == 1
        assert m2.idempotency_key == shared_key
        assert m2.experiments_migrated == 3


async def test_atomic_rollback_on_failed_migration(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify that a failure during migration rolls back atomically, leaving no orphaned data."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    idempotency_key = f"failed_key_{uuid.uuid4().hex[:8]}"

    # Step 1: Create user
    async with session_factory() as session:
        user = User(id=user_id, email=f"rollback_{user_id.hex[:6]}@example.com", password_hash="h", full_name="User")
        session.add(user)
        await session.commit()

    # Step 2: Simulate failure mid-migration (e.g. invalid FK in viva session)
    async with session_factory() as session:
        exp = Experiment(id=exp_id, user_id=user_id, title="Will Be Rolled Back", subject="Physics")
        session.add(exp)

        # Broken viva session referencing non-existent experiment
        broken_session = VivaSession(
            user_id=user_id,
            experiment_id=uuid.uuid4(),  # Does not exist! Violates FK
        )
        session.add(broken_session)

        mig_record = GuestMigration(user_id=user_id, idempotency_key=idempotency_key, status="completed")
        session.add(mig_record)

        with pytest.raises(IntegrityError):
            await session.commit()

        await session.rollback()

    # Step 3: Verify NO partial writes leaked into PostgreSQL
    async with session_factory() as session:
        exp_res = await session.execute(select(Experiment).where(Experiment.id == exp_id))
        assert exp_res.scalar_one_or_none() is None

        mig_res = await session.execute(select(GuestMigration).where(GuestMigration.idempotency_key == idempotency_key))
        assert mig_res.scalar_one_or_none() is None
