"""User Settings ORM Model.

Defines persistent student study preferences and defaults for the PracPrep platform.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, UUID, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import User


class UserSettings(Base):
    """User study preferences entity bound 1-to-1 with a User."""

    __tablename__ = "user_settings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )

    # Study preferences supported by PRD and frontend types/settings.ts
    default_difficulty: Mapped[str] = mapped_column(
        String(20),
        default="medium",
        nullable=False,
    )
    default_question_count: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    preferred_focus: Mapped[str] = mapped_column(
        String(50),
        default="all",
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Inverse relationship to User
    user: Mapped["User"] = relationship(
        "User",
        back_populates="settings",
    )

    def __repr__(self) -> str:
        return f"<UserSettings user_id={self.user_id} difficulty={self.default_difficulty!r} focus={self.preferred_focus!r}>"


class GuestMigration(Base):
    """Guest data migration tracking entity guaranteeing idempotency across requests."""

    __tablename__ = "guest_migrations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
        nullable=False,
    )
    experiments_migrated: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    viva_sessions_migrated: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    viva_answers_migrated: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_user_guest_migration_idempotency"),
    )

    # Inverse relationship to User
    user: Mapped["User"] = relationship(
        "User",
        back_populates="guest_migrations",
    )

    def __repr__(self) -> str:
        return (
            f"<GuestMigration id={self.id} user_id={self.user_id} "
            f"key={self.idempotency_key!r} status={self.status!r}>"
        )

