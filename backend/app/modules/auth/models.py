"""User Account ORM Model.

Defines the primary User identity entity for PracPrep authentication and ownership.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
import uuid

from sqlalchemy import Boolean, DateTime, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.users.models import UserSettings, GuestMigration
    from app.modules.experiments.models import Experiment
    from app.modules.viva.models import VivaSession
    from app.modules.documents.models import UploadedDocument


class User(Base):
    """User account entity representing a registered student or user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    university: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    auth_provider: Mapped[str] = mapped_column(
        String(50),
        default="local",
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

    # 1-to-1 relationship with UserSettings (cascading delete on user deletion)
    settings: Mapped["UserSettings"] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # 1-to-many relationship with Experiment (cascading delete on user deletion)
    experiments: Mapped[list["Experiment"]] = relationship(
        "Experiment",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # 1-to-many relationship with VivaSession (cascading delete on user deletion)
    viva_sessions: Mapped[list["VivaSession"]] = relationship(
        "VivaSession",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # 1-to-many relationship with UploadedDocument (cascading delete on user deletion)
    documents: Mapped[list["UploadedDocument"]] = relationship(
        "UploadedDocument",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # 1-to-many relationship with GuestMigration (cascading delete on user deletion)
    guest_migrations: Mapped[list["GuestMigration"]] = relationship(
        "GuestMigration",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @validates("email")
    def validate_and_normalize_email(self, key: str, address: str) -> str:
        """Normalize email address to lowercase and stripped whitespace before storage."""
        if not address or not address.strip():
            raise ValueError("Email cannot be empty")
        return address.strip().lower()

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} active={self.is_active}>"
