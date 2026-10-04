"""Viva Session and Answer ORM Models.

Defines the VivaSession and VivaAnswer entities for PracPrep interactive
viva practice, evaluations, and performance analytics.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UUID
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.experiments.models import Experiment


class VivaSession(Base):
    """Viva examination practice session entity representing a student's attempt."""

    __tablename__ = "viva_sessions"

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
    experiment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("experiments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Configuration fields supported by VivaSessionConfig
    difficulty: Mapped[str] = mapped_column(
        String(50),
        default="intermediate",
        nullable=False,
    )
    question_count: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    topic_focus: Mapped[str] = mapped_column(
        String(50),
        default="mixed",
        nullable=False,
    )
    provider_mode: Mapped[str] = mapped_column(
        String(50),
        default="demonstration",
        nullable=False,
    )

    # Session lifecycle & completion metrics
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Summary performance metrics
    average_score: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 2),
        nullable=True,
    )
    total_questions: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
    )
    questions_answered: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    correct_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    partially_correct_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    incorrect_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    # Structured analytics matching frontend contracts
    topic_analysis: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
    weak_topics: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    strong_topics: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    revision_recommendations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
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
        back_populates="viva_sessions",
    )
    experiment: Mapped["Experiment"] = relationship(
        "Experiment",
        back_populates="viva_sessions",
    )
    answers: Mapped[list["VivaAnswer"]] = relationship(
        "VivaAnswer",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="VivaAnswer.question_number",
    )

    def __repr__(self) -> str:
        status = "completed" if self.is_completed else "in-progress"
        return f"<VivaSession id={self.id} user_id={self.user_id} experiment_id={self.experiment_id} status={status!r}>"


class VivaAnswer(Base):
    """Individual question and student response record within a VivaSession."""

    __tablename__ = "viva_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("viva_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Question metadata & sequence
    question_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    question_number: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    topic: Mapped[str] = mapped_column(
        String(50),
        default="theory",
        nullable=False,
    )
    difficulty: Mapped[str] = mapped_column(
        String(50),
        default="intermediate",
        nullable=False,
    )
    question_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Student submission
    student_answer: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Evaluation results matching VivaEvaluation contract
    score: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    verdict: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    feedback: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    expected_answer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    what_you_got_right: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    what_was_missing: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    suggested_improvement: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Structured feedback points
    key_points_covered: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    key_points_missed: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )
    evaluation_data: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Additional execution details
    time_spent_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Inverse relationship to VivaSession
    session: Mapped["VivaSession"] = relationship(
        "VivaSession",
        back_populates="answers",
    )

    def __repr__(self) -> str:
        return f"<VivaAnswer id={self.id} session_id={self.session_id} q_num={self.question_number} score={self.score}>"
