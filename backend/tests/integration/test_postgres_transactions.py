"""PostgreSQL Transaction and Failure Behavior Integration Tests (TASK-15.3 - Area G).

Validates atomic rollback, safe unique constraint handling, savepoint behavior,
and concurrent transaction isolation against real PostgreSQL 16.
"""

import asyncio
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth.models import User
from app.modules.experiments.models import Experiment, PreparationChecklist

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_transaction_rollback_leaves_no_partial_writes(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify that when an exception occurs inside a transaction, rollback leaves no partial state."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"tx_{user_id.hex[:6]}@example.com", password_hash="h", full_name="TX User")
        session.add(user)
        await session.commit()

    # Attempt multi-insert transaction where second insert deliberately fails
    async with session_factory() as session:
        exp = Experiment(id=exp_id, user_id=user_id, title="Partial Experiment", subject="Physics")
        session.add(exp)
        await session.flush()  # exp has been sent to DB within transaction

        # Insert duplicate User violating unique email constraint
        dup_user = User(email=f"tx_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Duplicate")
        session.add(dup_user)

        with pytest.raises(IntegrityError):
            await session.commit()

        await session.rollback()

    # Verify that the flushed Experiment was rolled back completely
    async with session_factory() as session:
        res = await session.execute(select(Experiment).where(Experiment.id == exp_id))
        assert res.scalar_one_or_none() is None


async def test_savepoint_nested_transaction_rollback(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify SQLAlchemy nested transactions (PostgreSQL SAVEPOINT) allow recovering from partial failures."""
    user_id = uuid.uuid4()
    exp1_id = uuid.uuid4()
    exp2_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"sp_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Savepoint User")
        session.add(user)
        await session.commit()

    async with session_factory() as session:
        # Step 1: Add first experiment in outer transaction
        exp1 = Experiment(id=exp1_id, user_id=user_id, title="Surviving Experiment", subject="Physics")
        session.add(exp1)

        # Step 2: Use SAVEPOINT (nested transaction) for risky operation
        try:
            async with session.begin_nested():
                exp2 = Experiment(
                    id=exp2_id,
                    user_id=uuid.uuid4(),  # Invalid user_id -> FK violation
                    title="Failing Experiment",
                    subject="Physics",
                )
                session.add(exp2)
                await session.flush()
        except IntegrityError:
            # Savepoint was rolled back, outer transaction remains active and valid
            pass

        # Outer transaction commits exp1 successfully
        await session.commit()

    # Verify exp1 exists and exp2 does not
    async with session_factory() as session:
        r1 = await session.execute(select(Experiment).where(Experiment.id == exp1_id))
        assert r1.scalar_one_or_none() is not None

        r2 = await session.execute(select(Experiment).where(Experiment.id == exp2_id))
        assert r2.scalar_one_or_none() is None


async def test_concurrent_inserts_preserve_uniqueness_invariant(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify concurrent inserts targeting the same unique key result in exactly one success and one IntegrityError."""
    target_email = f"concurrent_{uuid.uuid4().hex[:8]}@example.com"

    async def try_insert_user(name: str) -> str:
        try:
            async with session_factory() as session:
                user = User(
                    email=target_email,
                    password_hash="pwd",
                    full_name=name,
                )
                session.add(user)
                await session.commit()
                return "COMMITTED"
        except IntegrityError:
            return "INTEGRITY_ERROR"

    # Run two inserts concurrently against PostgreSQL
    results = await asyncio.gather(
        try_insert_user("Concurrent User A"),
        try_insert_user("Concurrent User B"),
    )

    # In PostgreSQL, exactly one transaction must commit and one must be rejected by unique constraint
    assert sorted(results) == ["COMMITTED", "INTEGRITY_ERROR"]

    # Verify exactly one record exists in PostgreSQL
    async with session_factory() as session:
        res = await session.execute(select(User).where(User.email == target_email))
        users = res.scalars().all()
        assert len(users) == 1
