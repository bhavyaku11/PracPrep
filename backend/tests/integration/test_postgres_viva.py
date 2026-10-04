"""PostgreSQL Viva Sessions and Answers Integration Tests (TASK-15.3 - Area D).

Validates viva session creation, answer ordering, JSONB evaluation data persistence,
cascade deletion, and multi-user isolation against real PostgreSQL 16.
"""

from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.modules.auth.models import User
from app.modules.experiments.models import Experiment
from app.modules.viva.models import VivaAnswer, VivaSession

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


async def test_create_viva_session_and_answers_ordering(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify VivaSession and ordered VivaAnswers persist correctly in PostgreSQL."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"viva_{user_id.hex[:6]}@example.com", password_hash="h", full_name="Viva User")
        exp = Experiment(id=exp_id, user=user, title="Boyle's Law", subject="Thermodynamics")

        viva_session = VivaSession(
            id=session_id,
            user=user,
            experiment=exp,
            difficulty="intermediate",
            question_count=3,
            topic_focus="theory",
            is_completed=True,
            average_score=Decimal("8.50"),
            total_questions=3,
            questions_answered=3,
            correct_count=2,
            partially_correct_count=1,
            incorrect_count=0,
            topic_analysis={"theory": {"accuracy": 85}},
            weak_topics=["isothermal expansion"],
            strong_topics=["ideal gas equation"],
        )

        # Intentionally insert out of order to verify order_by="VivaAnswer.question_number"
        answer3 = VivaAnswer(
            session=viva_session,
            question_number=3,
            topic="theory",
            question_text="State Boyle's Law.",
            student_answer="Pressure is inversely proportional to volume at constant temperature.",
            score=10,
            verdict="correct",
            key_points_covered=["pressure", "volume", "constant temperature"],
            key_points_missed=[],
            evaluation_data={"accuracy": 1.0},
        )
        answer1 = VivaAnswer(
            session=viva_session,
            question_number=1,
            topic="theory",
            question_text="What is an ideal gas?",
            student_answer="A gas obeying PV=nRT.",
            score=8,
            verdict="partially_correct",
            key_points_covered=["PV=nRT"],
            key_points_missed=["no intermolecular forces"],
            evaluation_data={"accuracy": 0.8},
        )
        answer2 = VivaAnswer(
            session=viva_session,
            question_number=2,
            topic="theory",
            question_text="What is constant during an isothermal process?",
            student_answer="Temperature.",
            score=10,
            verdict="correct",
            key_points_covered=["temperature"],
            key_points_missed=[],
            evaluation_data={"accuracy": 1.0},
        )

        session.add_all([user, exp, viva_session, answer3, answer1, answer2])
        await session.commit()

    # Verify retrieval with ordered answers in independent session
    async with session_factory() as session:
        stmt = (
            select(VivaSession)
            .options(selectinload(VivaSession.answers))
            .where(VivaSession.id == session_id)
        )
        res = await session.execute(stmt)
        retrieved_session = res.scalar_one()

        assert retrieved_session.id == session_id
        assert retrieved_session.average_score == Decimal("8.50")
        assert retrieved_session.topic_analysis["theory"]["accuracy"] == 85
        assert "isothermal expansion" in retrieved_session.weak_topics
        assert "ideal gas equation" in retrieved_session.strong_topics

        # Answers must be sorted by question_number (1, 2, 3)
        assert len(retrieved_session.answers) == 3
        assert [a.question_number for a in retrieved_session.answers] == [1, 2, 3]
        assert retrieved_session.answers[0].question_text == "What is an ideal gas?"
        assert retrieved_session.answers[0].key_points_missed == ["no intermolecular forces"]
        assert retrieved_session.answers[1].question_text == "What is constant during an isothermal process?"
        assert retrieved_session.answers[2].question_text == "State Boyle's Law."


async def test_cascade_delete_session_removes_answers(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify deleting a VivaSession cascades to delete its child VivaAnswers."""
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    session_id = uuid.uuid4()

    async with session_factory() as session:
        user = User(id=user_id, email=f"del_viva_{user_id.hex[:6]}@example.com", password_hash="h", full_name="User")
        exp = Experiment(id=exp_id, user=user, title="Exp", subject="Sub")
        viva = VivaSession(id=session_id, user=user, experiment=exp)
        ans = VivaAnswer(session=viva, question_number=1, question_text="Q1", student_answer="A1")
        session.add_all([user, exp, viva, ans])
        await session.commit()

    # Delete VivaSession
    async with session_factory() as session:
        viva = (await session.execute(select(VivaSession).where(VivaSession.id == session_id))).scalar_one()
        await session.delete(viva)
        await session.commit()

    # Verify both session and answers are deleted from PostgreSQL
    async with session_factory() as session:
        v_res = await session.execute(select(VivaSession).where(VivaSession.id == session_id))
        assert v_res.scalar_one_or_none() is None

        a_res = await session.execute(select(VivaAnswer).where(VivaAnswer.session_id == session_id))
        assert len(a_res.scalars().all()) == 0


async def test_user_isolation_for_viva_sessions(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify viva sessions and their evaluations belong strictly to their owner."""
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()

    session1_id = uuid.uuid4()
    session2_id = uuid.uuid4()

    async with session_factory() as session:
        u1 = User(id=user1_id, email=f"u1_viva_{user1_id.hex[:6]}@example.com", password_hash="h", full_name="User 1")
        u2 = User(id=user2_id, email=f"u2_viva_{user2_id.hex[:6]}@example.com", password_hash="h", full_name="User 2")
        exp1 = Experiment(user=u1, title="Exp 1", subject="Sub 1")
        exp2 = Experiment(user=u2, title="Exp 2", subject="Sub 2")

        v1 = VivaSession(id=session1_id, user=u1, experiment=exp1, topic_focus="theory")
        v2 = VivaSession(id=session2_id, user=u2, experiment=exp2, topic_focus="calculations")

        session.add_all([u1, u2, exp1, exp2, v1, v2])
        await session.commit()

    # Verify isolation
    async with session_factory() as session:
        res1 = await session.execute(select(VivaSession).where(VivaSession.user_id == user1_id))
        u1_sessions = res1.scalars().all()
        assert len(u1_sessions) == 1
        assert u1_sessions[0].id == session1_id
        assert u1_sessions[0].topic_focus == "theory"

        res2 = await session.execute(select(VivaSession).where(VivaSession.user_id == user2_id))
        u2_sessions = res2.scalars().all()
        assert len(u2_sessions) == 1
        assert u2_sessions[0].id == session2_id
        assert u2_sessions[0].topic_focus == "calculations"
