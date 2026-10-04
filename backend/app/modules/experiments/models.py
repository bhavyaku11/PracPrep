"""Experiment and Preparation Checklist ORM Models.

Defines the core Experiment entity and its 1-to-1 PreparationChecklist entity
for PracPrep lab preparation workspaces.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.viva.models import VivaSession
    from app.modules.documents.models import UploadedDocument


def default_preparation_checklist_items() -> dict[str, bool]:
    """Return default checklist completion state matching frontend contract."""
    return {
        "objective": False,
        "theory": False,
        "apparatus": False,
        "procedure": False,
        "precautions": False,
    }


class Experiment(Base):
    """Laboratory experiment entity representing structured student lab manual content."""

    __tablename__ = "experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Core metadata
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    experiment_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    course_semester: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    creation_method: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False,
    )
    has_manual_file: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    file_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="ready",
        index=True,
        nullable=False,
    )

    # Content sections: overview/objective and 6 standard lab manual sections
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    objective: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    theory: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    apparatus: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    procedure: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    observations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    calculations: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    precautions: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps (timezone-aware UTC)
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

    # Bidirectional relationships
    user: Mapped["User"] = relationship(
        "User",
        back_populates="experiments",
    )
    checklist: Mapped[Optional["PreparationChecklist"]] = relationship(
        "PreparationChecklist",
        back_populates="experiment",
        uselist=False,
        cascade="all, delete-orphan",
    )
    viva_sessions: Mapped[list["VivaSession"]] = relationship(
        "VivaSession",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["UploadedDocument"]] = relationship(
        "UploadedDocument",
        back_populates="experiment",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Experiment id={self.id} title={self.title!r} subject={self.subject!r} status={self.status!r}>"


class PreparationChecklist(Base):
    """Preparation checklist tracking lab readiness for a specific experiment."""

    __tablename__ = "preparation_checklists"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    items: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=default_preparation_checklist_items,
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

    # Inverse relationship to Experiment
    experiment: Mapped["Experiment"] = relationship(
        "Experiment",
        back_populates="checklist",
    )

    def __repr__(self) -> str:
        return f"<PreparationChecklist id={self.id} experiment_id={self.experiment_id}>"
