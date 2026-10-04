"""PostgreSQL Users and Settings Persistence Integration Tests (TASK-15.3 - Area B).

Validates user creation, email uniqueness constraints, settings 1-to-1 persistence,
default values, multi-session updates, user isolation, and cascade behavior against PostgreSQL 16.
"""

import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.auth.models import User
from app.modules.users.models import UserSettings

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_create_and_retrieve_user(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Verify creating a user in one session and retrieving from an independent session."""
    user_id = uuid.uuid4()
    email = f"test_{user_id.hex[:8]}@example.com"

    # Session 1: Create and commit
    async with session_factory() as session:
        user = User(
            id=user_id,
            email=email,
            password_hash="$2b$12$fakehashedpasswordforrealpostgrestesting",
            full_name="Postgres Integration Student",
            university="MIT",
            is_active=True,
            auth_provider="local",
        )
        session.add(user)
        await session.commit()

    # Session 2: Read from independent session
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        persisted_user = result.scalar_one_or_none()

        assert persisted_user is not None
        assert persisted_user.id == user_id
        assert persisted_user.email == email
        assert persisted_user.full_name == "Postgres Integration Student"
        assert persisted_user.university == "MIT"
        assert persisted_user.is_active is True
        assert persisted_user.created_at is not None
        assert persisted_user.created_at.tzinfo is not None  # PostgreSQL TIMESTAMPTZ


async def test_unique_email_constraint_enforced_by_postgres(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify PostgreSQL raises IntegrityError when attempting to insert duplicate emails."""
    shared_email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"

    # Insert first user
    async with session_factory() as session:
        user1 = User(
            email=shared_email,
            password_hash="hash1",
            full_name="User One",
        )
        session.add(user1)
        await session.commit()

    # Insert second user with exact same email
    async with session_factory() as session:
        user2 = User(
            email=shared_email,
            password_hash="hash2",
            full_name="User Two",
        )
        session.add(user2)
        with pytest.raises(IntegrityError) as exc_info:
            await session.commit()

        assert "unique constraint" in str(exc_info.value).lower() or "duplicate key" in str(exc_info.value).lower()


async def test_user_settings_creation_and_defaults(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify 1-to-1 UserSettings creation and default study preferences."""
    user_id = uuid.uuid4()
    async with session_factory() as session:
        user = User(
            id=user_id,
            email=f"settings_{user_id.hex[:8]}@example.com",
            password_hash="hash",
            full_name="Settings Test User",
        )
        settings = UserSettings(user=user)
        session.add(user)
        session.add(settings)
        await session.commit()

    # Verify defaults in a new session
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        retrieved_user = result.scalar_one()

        assert retrieved_user.settings is not None
        assert retrieved_user.settings.default_difficulty == "medium"
        assert retrieved_user.settings.default_question_count == 5
        assert retrieved_user.settings.preferred_focus == "all"
        assert retrieved_user.settings.user_id == user_id


async def test_user_settings_update_persists_across_sessions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify updating settings in one session persists in subsequent independent sessions."""
    user_id = uuid.uuid4()
    async with session_factory() as session:
        user = User(
            id=user_id,
            email=f"update_{user_id.hex[:8]}@example.com",
            password_hash="hash",
            full_name="Updating User",
        )
        settings = UserSettings(
            user=user,
            default_difficulty="easy",
            default_question_count=3,
            preferred_focus="theory",
        )
        session.add(user)
        session.add(settings)
        await session.commit()

    # Session 2: Update settings
    async with session_factory() as session:
        result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        user_settings = result.scalar_one()
        user_settings.default_difficulty = "hard"
        user_settings.default_question_count = 10
        user_settings.preferred_focus = "viva"
        await session.commit()

    # Session 3: Verify updated values
    async with session_factory() as session:
        result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        user_settings = result.scalar_one()
        assert user_settings.default_difficulty == "hard"
        assert user_settings.default_question_count == 10
        assert user_settings.preferred_focus == "viva"


async def test_user_isolation_for_settings(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify settings of one user do not affect or leak to another user."""
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    async with session_factory() as session:
        user1 = User(id=user1_id, email=f"user1_{user1_id.hex[:6]}@example.com", password_hash="h1", full_name="User 1")
        settings1 = UserSettings(user=user1, default_difficulty="easy", default_question_count=3)

        user2 = User(id=user2_id, email=f"user2_{user2_id.hex[:6]}@example.com", password_hash="h2", full_name="User 2")
        settings2 = UserSettings(user=user2, default_difficulty="hard", default_question_count=10)

        session.add_all([user1, settings1, user2, settings2])
        await session.commit()

    # Check isolation
    async with session_factory() as session:
        u1 = (await session.execute(select(User).where(User.id == user1_id))).scalar_one()
        u2 = (await session.execute(select(User).where(User.id == user2_id))).scalar_one()

        assert u1.settings.default_difficulty == "easy"
        assert u1.settings.default_question_count == 3
        assert u2.settings.default_difficulty == "hard"
        assert u2.settings.default_question_count == 10


async def test_cascade_delete_user_removes_settings(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify deleting a user cascades to delete their associated settings in PostgreSQL."""
    user_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"del_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Delete Me")
        settings = UserSettings(user=user)
        session.add_all([user, settings])
        await session.commit()

    # Delete user in Session 2
    async with session_factory() as session:
        user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
        await session.delete(user)
        await session.commit()

    # Verify both User and UserSettings are gone
    async with session_factory() as session:
        res_u = await session.execute(select(User).where(User.id == user_id))
        assert res_u.scalar_one_or_none() is None

        res_s = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        assert res_s.scalar_one_or_none() is None
