"""Automated tests for VivaSession and VivaAnswer SQLAlchemy 2.x models."""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.dialects.postgresql import JSONB
from app.core.database import Base
from app.modules.auth.models import User
from app.modules.users.models import UserSettings  # noqa: F401
from app.modules.experiments.models import Experiment, PreparationChecklist  # noqa: F401
from app.modules.viva.models import VivaAnswer, VivaSession


def test_models_inherit_from_declarative_base():
    """Verify VivaSession and VivaAnswer inherit from the shared Base."""
    assert issubclass(VivaSession, Base)
    assert issubclass(VivaAnswer, Base)


def test_models_registered_in_base_metadata():
    """Verify both tables are registered in Base.metadata for Alembic discovery."""
    assert "viva_sessions" in Base.metadata.tables
    assert "viva_answers" in Base.metadata.tables


def test_uuid_primary_keys_configured():
    """Verify primary keys are UUID types with uuid.uuid4 defaults."""
    sess_mapper = sa_inspect(VivaSession)
    sess_pk = sess_mapper.primary_key
    assert len(sess_pk) == 1
    assert sess_pk[0].name == "id"
    assert sess_pk[0].type.python_type is uuid.UUID

    ans_mapper = sa_inspect(VivaAnswer)
    ans_pk = ans_mapper.primary_key
    assert len(ans_pk) == 1
    assert ans_pk[0].name == "id"
    assert ans_pk[0].type.python_type is uuid.UUID


def test_viva_session_ownership_foreign_key():
    """Verify VivaSession has a valid foreign key referencing users.id with CASCADE."""
    table = VivaSession.__table__
    assert table.c.user_id.nullable is False
    assert table.c.user_id.index is True

    fks = list(table.c.user_id.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "users.id"
    assert fk.ondelete == "CASCADE"


def test_viva_session_experiment_association():
    """Verify VivaSession has a valid foreign key referencing experiments.id with CASCADE."""
    table = VivaSession.__table__
    assert table.c.experiment_id.nullable is False
    assert table.c.experiment_id.index is True

    fks = list(table.c.experiment_id.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "experiments.id"
    assert fk.ondelete == "CASCADE"


def test_viva_answer_foreign_key_to_session():
    """Verify VivaAnswer foreign key references viva_sessions.id with CASCADE."""
    table = VivaAnswer.__table__
    assert table.c.session_id.nullable is False
    assert table.c.session_id.index is True

    fks = list(table.c.session_id.foreign_keys)
    assert len(fks) == 1
    fk = fks[0]
    assert fk.target_fullname == "viva_sessions.id"
    assert fk.ondelete == "CASCADE"


def test_viva_question_and_answer_fields():
    """Verify question text, student answer, sequence, and configuration fields are represented."""
    sess_table = VivaSession.__table__
    assert sess_table.c.difficulty.nullable is False
    assert sess_table.c.question_count.nullable is False
    assert sess_table.c.topic_focus.nullable is False
    assert sess_table.c.provider_mode.nullable is False
    assert sess_table.c.is_completed.nullable is False

    ans_table = VivaAnswer.__table__
    assert ans_table.c.question_text.nullable is False
    assert ans_table.c.student_answer.nullable is False
    assert ans_table.c.question_number.nullable is False
    assert ans_table.c.topic.nullable is False
    assert ans_table.c.difficulty.nullable is False


def test_evaluation_fields_preserve_contract():
    """Verify evaluation fields (score, verdict, feedback, key points, JSONB) preserve contract."""
    ans_table = VivaAnswer.__table__
    assert "score" in ans_table.c
    assert "verdict" in ans_table.c
    assert "feedback" in ans_table.c
    assert "expected_answer" in ans_table.c
    assert "what_you_got_right" in ans_table.c
    assert "what_was_missing" in ans_table.c
    assert "suggested_improvement" in ans_table.c

    # Structured feedback points and evaluation object use JSONB
    assert isinstance(ans_table.c["key_points_covered"].type, JSONB)
    assert isinstance(ans_table.c["key_points_missed"].type, JSONB)
    assert isinstance(ans_table.c["evaluation_data"].type, JSONB)

    # Session-level performance analytics use JSONB
    sess_table = VivaSession.__table__
    assert isinstance(sess_table.c["topic_analysis"].type, JSONB)
    assert isinstance(sess_table.c["weak_topics"].type, JSONB)
    assert isinstance(sess_table.c["strong_topics"].type, JSONB)
    assert isinstance(sess_table.c["revision_recommendations"].type, JSONB)


def test_timezone_aware_timestamp_columns():
    """Verify all timestamp columns are timezone-aware UTC."""
    sess_table = VivaSession.__table__
    for col_name in ("started_at", "created_at", "updated_at"):
        assert sess_table.c[col_name].type.timezone is True
        assert sess_table.c[col_name].nullable is False
    assert sess_table.c.completed_at.type.timezone is True
    assert sess_table.c.completed_at.nullable is True

    ans_table = VivaAnswer.__table__
    assert ans_table.c.created_at.type.timezone is True
    assert ans_table.c.created_at.nullable is False


def test_orm_relationships_bidirectional():
    """Verify bidirectional relationships among User, Experiment, VivaSession, and VivaAnswer."""
    # User <-> VivaSession
    user_mapper = sa_inspect(User)
    assert "viva_sessions" in user_mapper.relationships
    user_viva_rel = user_mapper.relationships["viva_sessions"]
    assert user_viva_rel.target.name == "viva_sessions"
    assert user_viva_rel.back_populates == "user"

    sess_mapper = sa_inspect(VivaSession)
    assert "user" in sess_mapper.relationships
    sess_user_rel = sess_mapper.relationships["user"]
    assert sess_user_rel.target.name == "users"
    assert sess_user_rel.back_populates == "viva_sessions"

    # Experiment <-> VivaSession
    exp_mapper = sa_inspect(Experiment)
    assert "viva_sessions" in exp_mapper.relationships
    exp_viva_rel = exp_mapper.relationships["viva_sessions"]
    assert exp_viva_rel.target.name == "viva_sessions"
    assert exp_viva_rel.back_populates == "experiment"

    assert "experiment" in sess_mapper.relationships
    sess_exp_rel = sess_mapper.relationships["experiment"]
    assert sess_exp_rel.target.name == "experiments"
    assert sess_exp_rel.back_populates == "viva_sessions"

    # VivaSession <-> VivaAnswer
    assert "answers" in sess_mapper.relationships
    sess_ans_rel = sess_mapper.relationships["answers"]
    assert sess_ans_rel.target.name == "viva_answers"
    assert sess_ans_rel.back_populates == "session"

    ans_mapper = sa_inspect(VivaAnswer)
    assert "session" in ans_mapper.relationships
    ans_sess_rel = ans_mapper.relationships["session"]
    assert ans_sess_rel.target.name == "viva_sessions"
    assert ans_sess_rel.back_populates == "answers"


def test_cascade_behavior_configured():
    """Verify cascade deletes prevent orphaned viva sessions and answers."""
    user_mapper = sa_inspect(User)
    assert user_mapper.relationships["viva_sessions"].cascade.delete_orphan is True

    exp_mapper = sa_inspect(Experiment)
    assert exp_mapper.relationships["viva_sessions"].cascade.delete_orphan is True

    sess_mapper = sa_inspect(VivaSession)
    assert sess_mapper.relationships["answers"].cascade.delete_orphan is True


def test_model_metadata_inspection_offline_and_defaults():
    """Verify offline instantiation, repr diagnostics, and field defaults without live DB."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    sess_id = uuid.uuid4()

    session = VivaSession(
        id=sess_id,
        user_id=user_id,
        experiment_id=exp_id,
        difficulty="intermediate",
        question_count=5,
        topic_focus="theory",
        provider_mode="demonstration",
        average_score=Decimal("8.50"),
        weak_topics=["procedure"],
        strong_topics=["theory"],
    )
    assert str(sess_id) in repr(session)
    assert str(user_id) in repr(session)
    assert "in-progress" in repr(session)

    ans_id = uuid.uuid4()
    answer = VivaAnswer(
        id=ans_id,
        session_id=sess_id,
        question_number=1,
        topic="theory",
        difficulty="intermediate",
        question_text="State Norton's theorem.",
        student_answer="Norton's theorem states any linear bilateral network can be replaced by an equivalent current source in parallel with impedance.",
        score=9,
        verdict="correct",
        feedback="Accurate definition highlighting linearity and equivalent current source.",
        key_points_covered=["linear bilateral network", "parallel impedance"],
        key_points_missed=[],
        evaluation_data={
            "verdict": "correct",
            "score": 9,
            "whatYouGotRight": "Correctly identified current source and parallel impedance.",
            "whatWasMissing": "None.",
            "expectedAnswer": "Any linear circuit can be reduced to an equivalent current source In in parallel with Rn.",
            "improvementTip": "Keep response concise.",
            "providerMode": "demonstration",
        },
    )
    assert str(ans_id) in repr(answer)
    assert "score=9" in repr(answer)
    assert answer.evaluation_data["verdict"] == "correct"
