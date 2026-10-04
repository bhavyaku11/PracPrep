"""PostgreSQL Experiments and Preparation Checklists Integration Tests (TASK-15.3 - Area C).

Validates parent-child relationships, JSONB persistence, async relationship loading (selectinload),
cascade deletion, and user ownership isolation against real PostgreSQL 16.
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.experiments.models import Experiment, PreparationChecklist

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_create_experiment_with_checklist(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify creating an Experiment and its child PreparationChecklist persists correctly in PostgreSQL."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(
            id=user_id,
            email=f"exp_{user_id.hex[:6]}@example.com",
            password_hash="hash",
            full_name="Exp Student",
        )
        experiment = Experiment(
            id=exp_id,
            user=user,
            title="Determination of Young's Modulus",
            subject="Applied Physics",
            experiment_number="EXP-01",
            course_semester="Semester 1",
            creation_method="manual",
            status="ready",
            objective="To determine Young's modulus of a wire by Searle's method.",
            theory="Stress is proportional to strain within the elastic limit.",
            procedure="1. Mount the apparatus. 2. Apply initial load.",
        )
        checklist = PreparationChecklist(
            experiment=experiment,
            items={
                "objective": True,
                "theory": True,
                "apparatus": False,
                "procedure": False,
                "precautions": False,
            },
        )
        session.add_all([user, experiment, checklist])
        await session.commit()

    # Verify persistence in independent session with selectinload
    async with session_factory() as session:
        stmt = (
            select(Experiment)
            .options(selectinload(Experiment.checklist))
            .where(Experiment.id == exp_id)
        )
        res = await session.execute(stmt)
        retrieved_exp = res.scalar_one()

        assert retrieved_exp.title == "Determination of Young's Modulus"
        assert retrieved_exp.subject == "Applied Physics"
        assert retrieved_exp.user_id == user_id
        assert retrieved_exp.checklist is not None
        assert retrieved_exp.checklist.items["objective"] is True
        assert retrieved_exp.checklist.items["theory"] is True
        assert retrieved_exp.checklist.items["apparatus"] is False
        assert retrieved_exp.checklist.experiment_id == exp_id


async def test_checklist_jsonb_update_persists(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify JSONB modifications to PreparationChecklist persist across independent database sessions."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    # Step 1: Create experiment & checklist
    async with session_factory() as session:
        user = User(id=user_id, email=f"chk_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Chk User")
        exp = Experiment(id=exp_id, user=user, title="Ohm's Law Verification", subject="Electronics")
        chk = PreparationChecklist(experiment=exp)
        session.add_all([user, exp, chk])
        await session.commit()

    # Step 2: Update checklist JSONB items
    async with session_factory() as session:
        stmt = select(PreparationChecklist).where(PreparationChecklist.experiment_id == exp_id)
        res = await session.execute(stmt)
        chk = res.scalar_one()

        # Update JSONB dictionary
        new_items = dict(chk.items)
        new_items["apparatus"] = True
        new_items["procedure"] = True
        chk.items = new_items
        await session.commit()

    # Step 3: Validate persistence in fresh session
    async with session_factory() as session:
        stmt = select(PreparationChecklist).where(PreparationChecklist.experiment_id == exp_id)
        res = await session.execute(stmt)
        chk = res.scalar_one()

        assert chk.items["apparatus"] is True
        assert chk.items["procedure"] is True
        assert chk.items["precautions"] is False


async def test_cascade_delete_experiment_removes_checklist(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify deleting an experiment triggers CASCADE deletion of its preparation checklist in PostgreSQL."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"casc_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Casc User")
        exp = Experiment(id=exp_id, user=user, title="Spectrometer Experiment", subject="Physics")
        chk = PreparationChecklist(experiment=exp)
        session.add_all([user, exp, chk])
        await session.commit()

    # Delete experiment
    async with session_factory() as session:
        exp = (await session.execute(select(Experiment).where(Experiment.id == exp_id))).scalar_one()
        await session.delete(exp)
        await session.commit()

    # Verify both Experiment and PreparationChecklist are deleted
    async with session_factory() as session:
        exp_res = await session.execute(select(Experiment).where(Experiment.id == exp_id))
        assert exp_res.scalar_one_or_none() is None

        chk_res = await session.execute(select(PreparationChecklist).where(PreparationChecklist.experiment_id == exp_id))
        assert chk_res.scalar_one_or_none() is None


async def test_user_ownership_isolation_for_experiments(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify that experiments belonging to User A are isolated from User B queries."""
    user_a_id = uuid.uuid4()
    user_b_id = uuid.uuid4()

    exp_a_id = uuid.uuid4()
    exp_b_id = uuid.uuid4()

    async with session_factory() as session:
        user_a = User(id=user_a_id, email=f"usera_{user_a_id.hex[:6]}@example.com", password_hash="h", full_name="User A")
        user_b = User(id=user_b_id, email=f"userb_{user_b_id.hex[:6]}@example.com", password_hash="h", full_name="User B")

        exp_a = Experiment(id=exp_a_id, user=user_a, title="User A Experiment", subject="Physics")
        exp_b = Experiment(id=exp_b_id, user=user_b, title="User B Experiment", subject="Chemistry")

        session.add_all([user_a, user_b, exp_a, exp_b])
        await session.commit()

    # Query filtered by user_a_id
    async with session_factory() as session:
        res_a = await session.execute(select(Experiment).where(Experiment.user_id == user_a_id))
        user_a_experiments = res_a.scalars().all()

        assert len(user_a_experiments) == 1
        assert user_a_experiments[0].id == exp_a_id
        assert user_a_experiments[0].title == "User A Experiment"

    # Query filtered by user_b_id
    async with session_factory() as session:
        res_b = await session.execute(select(Experiment).where(Experiment.user_id == user_b_id))
        user_b_experiments = res_b.scalars().all()

        assert len(user_b_experiments) == 1
        assert user_b_experiments[0].id == exp_b_id
        assert user_b_experiments[0].title == "User B Experiment"


async def test_async_relationship_selectinload_prevents_lazy_load_failure(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify that selectinload eagerly fetches async relationships without raising MissingGreenlet error."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"async_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Async User")
        exp = Experiment(id=exp_id, user=user, title="Viscosity by Poiseuille Method", subject="Fluid Dynamics")
        chk = PreparationChecklist(experiment=exp)
        session.add_all([user, exp, chk])
        await session.commit()

    # In async SQLAlchemy, lazy loading un-loaded relationships on detached or active sessions
    # without greenlet throws MissingGreenlet. selectinload prevents this.
    async with session_factory() as session:
        stmt = (
            select(Experiment)
            .options(selectinload(Experiment.checklist), selectinload(Experiment.user))
            .where(Experiment.id == exp_id)
        )
        res = await session.execute(stmt)
        experiment = res.scalar_one()

        # Accessing checklist and user must succeed immediately without additional queries
        assert experiment.checklist is not None
        assert experiment.checklist.items["objective"] is False
        assert experiment.user.email.startswith("async_")
