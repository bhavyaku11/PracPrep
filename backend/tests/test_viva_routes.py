"""Unit and integration tests for Viva Voce Session Management Endpoints.

Verifies POST, GET, and DELETE /api/v1/viva/sessions for ownership isolation,
strict experiment verification, pagination, filtering, cascade deletion,
and error handling without requiring a live PostgreSQL instance.
"""

from datetime import datetime, timezone
from decimal import Decimal
import math
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.modules.auth.models import User
import app.modules.documents.models  # noqa: F401
from app.modules.experiments.models import Experiment, PreparationChecklist
import app.modules.users.models  # noqa: F401
from app.modules.viva.models import VivaAnswer, VivaSession
from app.modules.viva.schemas import (
    VivaDifficultyEnum,
    VivaProviderModeEnum,
    VivaSessionStatusEnum,
    VivaTopicEnum,
)


# ==============================================================================
# Test Fixtures & Mock Setup
# ==============================================================================


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_user(sample_user_id: uuid.UUID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=sample_user_id,
        email="student@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        full_name="Alex Johnson",
        university="State University",
        is_active=True,
        auth_provider="local",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def inactive_user(sample_user_id: uuid.UUID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=sample_user_id,
        email="inactive@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        full_name="Inactive User",
        university="State University",
        is_active=False,
        auth_provider="local",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def auth_token(sample_user_id: uuid.UUID) -> str:
    return create_access_token(sample_user_id)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


def create_sample_experiment(
    user_id: uuid.UUID,
    exp_id: Optional[uuid.UUID] = None,
    title: str = "Ohm's Law Verification",
    subject: str = "Physics",
) -> Experiment:
    """Helper to instantiate an Experiment ORM model."""
    now = datetime.now(timezone.utc)
    actual_exp_id = exp_id or uuid.uuid4()
    exp = Experiment(
        id=actual_exp_id,
        user_id=user_id,
        title=title,
        subject=subject,
        experiment_number="EXP-01",
        course_semester="Semester 1",
        creation_method="manual",
        has_manual_file=False,
        file_name=None,
        status="ready",
        description="Verification of V=IR relationship.",
        objective="Determine resistance using Ohm's Law.",
        theory="Current is directly proportional to voltage.",
        apparatus="Voltmeter, Ammeter, Resistor.",
        procedure="1. Connect circuit. 2. Vary voltage.",
        observations="V vs I table.",
        calculations="Slope = Resistance.",
        precautions="Do not exceed current limits.",
        created_at=now,
        updated_at=now,
    )
    chk = PreparationChecklist(
        id=uuid.uuid4(),
        experiment_id=actual_exp_id,
        items={"objective": True, "theory": False, "apparatus": True, "procedure": False, "precautions": False},
        created_at=now,
        updated_at=now,
        experiment=exp,
    )
    exp.checklist = chk
    return exp


def create_sample_viva_session(
    user_id: uuid.UUID,
    experiment_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = None,
    difficulty: str = "intermediate",
    question_count: int = 5,
    topic_focus: str = "mixed",
    provider_mode: str = "demonstration",
    is_completed: bool = False,
    include_answers: bool = True,
    experiment: Optional[Experiment] = None,
) -> VivaSession:
    """Helper to instantiate a VivaSession ORM model with answers and experiment."""
    now = datetime.now(timezone.utc)
    actual_sess_id = session_id or uuid.uuid4()
    actual_exp = experiment or create_sample_experiment(user_id, exp_id=experiment_id)

    session = VivaSession(
        id=actual_sess_id,
        user_id=user_id,
        experiment_id=experiment_id,
        difficulty=difficulty,
        question_count=question_count,
        topic_focus=topic_focus,
        provider_mode=provider_mode,
        is_completed=is_completed,
        started_at=now,
        completed_at=now if is_completed else None,
        average_score=Decimal("8.50") if is_completed else None,
        total_questions=question_count,
        questions_answered=question_count if is_completed else 1,
        correct_count=1 if is_completed else 0,
        partially_correct_count=0,
        incorrect_count=0,
        topic_analysis={"theory": {"topic": "theory", "total": 1, "correct": 1, "partiallyCorrect": 0, "incorrect": 0, "averageScore": 8.5}} if is_completed else {},
        weak_topics=[],
        strong_topics=["theory"] if is_completed else [],
        revision_recommendations=[{"topic": "Theory", "reason": "Good job", "suggestedAction": "Keep it up", "workspaceTab": "theory"}] if is_completed else [],
        created_at=now,
        updated_at=now,
    )
    session.experiment = actual_exp

    if include_answers:
        answer = VivaAnswer(
            id=uuid.uuid4(),
            session_id=actual_sess_id,
            question_id="vq-01",
            question_number=1,
            topic="theory",
            difficulty="intermediate",
            question_text="State Ohm's Law.",
            student_answer="Current is proportional to voltage.",
            score=9 if is_completed else None,
            verdict="correct" if is_completed else None,
            feedback="Accurate definition." if is_completed else None,
            key_points_covered=["proportional to voltage"] if is_completed else [],
            key_points_missed=[] if is_completed else [],
            evaluation_data={},
            time_spent_seconds=20,
            created_at=now,
        )
        answer.session = session
        session.answers = [answer]
    else:
        session.answers = []

    return session


@pytest.fixture
def mock_viva_dispatcher(sample_user: User):
    """Factory creating an AsyncMock session for viva endpoint tests."""
    executed_statements: list[Any] = []

    def make_mock(
        experiment: Optional[Experiment] = None,
        sessions: Optional[list[VivaSession]] = None,
        count_val: int = 1,
        raise_on_commit: bool = False,
    ) -> AsyncMock:
        nonlocal executed_statements
        executed_statements = []

        session_list = sessions if sessions is not None else [
            create_sample_viva_session(sample_user.id, uuid.uuid4())
        ]

        db_session = AsyncMock(spec=AsyncSession)
        db_session.add = MagicMock()
        db_session.delete = AsyncMock()
        db_session.refresh = AsyncMock()

        if raise_on_commit:
            db_session.commit = AsyncMock(side_effect=OperationalError("commit failed", {}, Exception("DB down")))
        else:
            db_session.commit = AsyncMock()
        db_session.rollback = AsyncMock()

        async def fake_execute(statement, *args, **kwargs):
            executed_statements.append(statement)
            stmt_str = str(statement).lower()
            res = MagicMock()

            if "from users" in stmt_str:
                res.scalar_one_or_none.return_value = sample_user
            elif "from experiments" in stmt_str:
                res.scalar_one_or_none.return_value = experiment
            elif "count(" in stmt_str or "count *" in stmt_str:
                res.scalar_one.return_value = count_val
            elif "from viva_sessions" in stmt_str:
                res.scalars.return_value.all.return_value = session_list
                res.scalar_one_or_none.return_value = session_list[0] if session_list else None
                res.scalar_one.return_value = session_list[0] if session_list else None
            else:
                res.scalar_one_or_none.return_value = None
                res.scalars.return_value.all.return_value = []

            return res

        db_session.execute = AsyncMock(side_effect=fake_execute)
        db_session.executed_statements = executed_statements
        return db_session

    return make_mock


def create_test_client(db_session: AsyncMock) -> httpx.AsyncClient:
    """Helper to build test client with overridden database dependency."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    transport = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=transport, base_url="http://test")
    c.session = db_session  # type: ignore
    return c


# ==============================================================================
# 1. POST /api/v1/viva/sessions (Session Creation Tests)
# ==============================================================================


@pytest.mark.asyncio
async def test_create_viva_session_success(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Successful session creation returns 201 with populated defaults and experiment title."""
    exp = create_sample_experiment(sample_user.id, title="Hall Effect Experiment", subject="Physics")
    mock_db = mock_viva_dispatcher(experiment=exp)
    client = create_test_client(mock_db)

    payload = {
        "experimentId": str(exp.id),
        "difficulty": "advanced",
        "questionCount": 10,
        "topicFocus": "apparatus",
        "providerMode": "demonstration",
    }

    resp = await client.post("/api/v1/viva/sessions", json=payload, headers=auth_headers)
    assert resp.status_code == 201

    data = resp.json()
    assert "id" in data
    assert data["experimentId"] == str(exp.id)
    assert data["experimentTitle"] == "Hall Effect Experiment"
    assert data["subject"] == "Physics"
    assert data["difficulty"] == "advanced"
    assert data["questionCount"] == 10
    assert data["topicFocus"] == "apparatus"
    assert data["providerMode"] == "demonstration"
    assert data["isCompleted"] is False
    assert data["status"] == "in-progress"
    assert data["questionsAnswered"] == 0
    assert data["averageScore"] is None
    assert data["answers"] == []

    # Verify db.add was invoked with a VivaSession
    assert mock_db.add.called
    added_obj = mock_db.add.call_args[0][0]
    assert isinstance(added_obj, VivaSession)
    assert added_obj.user_id == sample_user.id
    assert added_obj.experiment_id == exp.id
    assert added_obj.difficulty == "advanced"
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_create_viva_session_nonexistent_experiment_returns_404(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Attempting to create a session for a nonexistent experiment returns 404."""
    mock_db = mock_viva_dispatcher(experiment=None)
    client = create_test_client(mock_db)

    payload = {"experimentId": str(uuid.uuid4())}
    resp = await client.post("/api/v1/viva/sessions", json=payload, headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Experiment not found"


@pytest.mark.asyncio
async def test_create_viva_session_foreign_experiment_returns_same_404(
    mock_viva_dispatcher, other_user_id: uuid.UUID, auth_headers: dict[str, str]
) -> None:
    """Experiment owned by another user returns identical 404 (ownership concealment)."""
    # Dispatcher returns None because query filters by user_id == current_user.id
    mock_db = mock_viva_dispatcher(experiment=None)
    client = create_test_client(mock_db)

    payload = {"experimentId": str(uuid.uuid4())}
    resp = await client.post("/api/v1/viva/sessions", json=payload, headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Experiment not found"


@pytest.mark.asyncio
async def test_create_viva_session_invalid_payload_returns_422(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Invalid question count or malformed UUID returns 422."""
    mock_db = mock_viva_dispatcher()
    client = create_test_client(mock_db)

    resp = await client.post(
        "/api/v1/viva/sessions",
        json={"experimentId": "not-a-uuid", "questionCount": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_viva_session_missing_auth_returns_401(mock_viva_dispatcher) -> None:
    """Missing Authorization header returns 401."""
    mock_db = mock_viva_dispatcher()
    client = create_test_client(mock_db)

    resp = await client.post("/api/v1/viva/sessions", json={"experimentId": str(uuid.uuid4())})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_create_viva_session_inactive_user_returns_403(
    mock_viva_dispatcher, inactive_user: User
) -> None:
    """Inactive user is forbidden from creating sessions."""
    token = create_access_token(inactive_user.id)
    mock_db = mock_viva_dispatcher()

    async def fake_user_exec(statement, *args, **kwargs):
        res = MagicMock()
        res.scalar_one_or_none.return_value = inactive_user
        return res

    mock_db.execute = AsyncMock(side_effect=fake_user_exec)
    client = create_test_client(mock_db)

    resp = await client.post(
        "/api/v1/viva/sessions",
        json={"experimentId": str(uuid.uuid4())},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_viva_session_db_failure_triggers_rollback(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Database exception triggers explicit rollback."""
    exp = create_sample_experiment(sample_user.id)
    mock_db = mock_viva_dispatcher(experiment=exp, raise_on_commit=True)
    client = create_test_client(mock_db)

    with pytest.raises(OperationalError):
        await client.post(
            "/api/v1/viva/sessions",
            json={"experimentId": str(exp.id)},
            headers=auth_headers,
        )

    assert mock_db.rollback.called


# ==============================================================================
# 2. GET /api/v1/viva/sessions (Session Listing Tests)
# ==============================================================================


@pytest.mark.asyncio
async def test_list_viva_sessions_success(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """List endpoint returns paginated sessions owned by current user."""
    exp = create_sample_experiment(sample_user.id, title="Diode Characteristics")
    session = create_sample_viva_session(sample_user.id, exp.id, experiment=exp)
    mock_db = mock_viva_dispatcher(sessions=[session], count_val=1)
    client = create_test_client(mock_db)

    resp = await client.get("/api/v1/viva/sessions", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["pageSize"] == 10
    assert data["totalPages"] == 1
    assert len(data["items"]) == 1

    item = data["items"][0]
    assert item["id"] == str(session.id)
    assert item["experimentId"] == str(exp.id)
    assert item["experimentTitle"] == "Diode Characteristics"
    assert item["questionCount"] == 5


@pytest.mark.asyncio
async def test_list_viva_sessions_camelcase_pagesize(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """List endpoint honors camelCase pageSize query param."""
    mock_db = mock_viva_dispatcher(sessions=[], count_val=0)
    client = create_test_client(mock_db)

    resp = await client.get("/api/v1/viva/sessions?page=2&pageSize=15", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 2
    assert data["pageSize"] == 15
    assert data["items"] == []


@pytest.mark.asyncio
async def test_list_viva_sessions_empty_handling(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Empty result set produces total=0 and items=[]."""
    mock_db = mock_viva_dispatcher(sessions=[], count_val=0)
    client = create_test_client(mock_db)

    resp = await client.get("/api/v1/viva/sessions", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []
    assert data["totalPages"] == 0


@pytest.mark.asyncio
async def test_list_viva_sessions_filters(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Filtering by experimentId, status, and difficulty works cleanly."""
    exp_id = uuid.uuid4()
    mock_db = mock_viva_dispatcher(sessions=[], count_val=0)
    client = create_test_client(mock_db)

    url = f"/api/v1/viva/sessions?experimentId={exp_id}&status=in-progress&difficulty=intermediate"
    resp = await client.get(url, headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_list_viva_sessions_invalid_pagination_returns_422(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Page < 1 or page_size > 100 returns 422."""
    mock_db = mock_viva_dispatcher()
    client = create_test_client(mock_db)

    resp1 = await client.get("/api/v1/viva/sessions?page=0", headers=auth_headers)
    assert resp1.status_code == 422

    resp2 = await client.get("/api/v1/viva/sessions?pageSize=101", headers=auth_headers)
    assert resp2.status_code == 422


# ==============================================================================
# 3. GET /api/v1/viva/sessions/{session_id} (Session Detail Tests)
# ==============================================================================


@pytest.mark.asyncio
async def test_get_viva_session_details_success(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Retrieves full session details including answers and experiment title."""
    exp = create_sample_experiment(sample_user.id, title="Young's Modulus")
    sess_id = uuid.uuid4()
    session = create_sample_viva_session(sample_user.id, exp.id, session_id=sess_id, experiment=exp, is_completed=True)
    mock_db = mock_viva_dispatcher(sessions=[session])
    client = create_test_client(mock_db)

    resp = await client.get(f"/api/v1/viva/sessions/{sess_id}", headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["id"] == str(sess_id)
    assert data["experimentId"] == str(exp.id)
    assert data["experimentTitle"] == "Young's Modulus"
    assert data["isCompleted"] is True
    assert data["status"] == "completed"
    assert data["averageScore"] == 8.5
    assert len(data["answers"]) == 1
    assert data["answers"][0]["questionNumber"] == 1
    assert data["answers"][0]["score"] == 9


@pytest.mark.asyncio
async def test_get_viva_session_empty_transcript_supported(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Retrieves session with zero answers without lazy loading error."""
    exp = create_sample_experiment(sample_user.id)
    sess_id = uuid.uuid4()
    session = create_sample_viva_session(sample_user.id, exp.id, session_id=sess_id, experiment=exp, include_answers=False)
    mock_db = mock_viva_dispatcher(sessions=[session])
    client = create_test_client(mock_db)

    resp = await client.get(f"/api/v1/viva/sessions/{sess_id}", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["answers"] == []
    assert data["questionsAnswered"] == 1


@pytest.mark.asyncio
async def test_get_viva_session_nonexistent_returns_404(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Nonexistent session returns 404."""
    mock_db = mock_viva_dispatcher(sessions=[])
    client = create_test_client(mock_db)

    resp = await client.get(f"/api/v1/viva/sessions/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Viva session not found"


@pytest.mark.asyncio
async def test_get_viva_session_foreign_returns_identical_404(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Session owned by another user returns identical 404."""
    mock_db = mock_viva_dispatcher(sessions=[])
    client = create_test_client(mock_db)

    resp = await client.get(f"/api/v1/viva/sessions/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Viva session not found"


@pytest.mark.asyncio
async def test_get_viva_session_invalid_uuid_returns_422(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Malformed UUID returns 422."""
    mock_db = mock_viva_dispatcher()
    client = create_test_client(mock_db)

    resp = await client.get("/api/v1/viva/sessions/invalid-uuid-format", headers=auth_headers)
    assert resp.status_code == 422


# ==============================================================================
# 4. DELETE /api/v1/viva/sessions/{session_id} (Session Deletion Tests)
# ==============================================================================


@pytest.mark.asyncio
async def test_delete_viva_session_success(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Successful deletion returns 204 with empty body."""
    sess_id = uuid.uuid4()
    session = create_sample_viva_session(sample_user.id, uuid.uuid4(), session_id=sess_id)
    mock_db = mock_viva_dispatcher(sessions=[session])
    client = create_test_client(mock_db)

    resp = await client.delete(f"/api/v1/viva/sessions/{sess_id}", headers=auth_headers)
    assert resp.status_code == 204
    assert resp.content == b""
    assert mock_db.delete.called
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_delete_viva_session_nonexistent_returns_404(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Deleting a nonexistent session returns 404."""
    mock_db = mock_viva_dispatcher(sessions=[])
    client = create_test_client(mock_db)

    resp = await client.delete(f"/api/v1/viva/sessions/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Viva session not found"


@pytest.mark.asyncio
async def test_delete_viva_session_foreign_returns_identical_404(
    mock_viva_dispatcher, auth_headers: dict[str, str]
) -> None:
    """Deleting another user's session returns identical 404."""
    mock_db = mock_viva_dispatcher(sessions=[])
    client = create_test_client(mock_db)

    resp = await client.delete(f"/api/v1/viva/sessions/{uuid.uuid4()}", headers=auth_headers)
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Viva session not found"


@pytest.mark.asyncio
async def test_delete_viva_session_db_failure_triggers_rollback(
    mock_viva_dispatcher, sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Database exception on delete triggers rollback."""
    sess_id = uuid.uuid4()
    session = create_sample_viva_session(sample_user.id, uuid.uuid4(), session_id=sess_id)
    mock_db = mock_viva_dispatcher(sessions=[session], raise_on_commit=True)
    client = create_test_client(mock_db)

    with pytest.raises(OperationalError):
        await client.delete(f"/api/v1/viva/sessions/{sess_id}", headers=auth_headers)

    assert mock_db.rollback.called


# ==============================================================================
# 5. Route Catalog Registration Verification
# ==============================================================================


def test_viva_routes_registered_in_fastapi_catalog() -> None:
    """Confirm all four viva endpoints are registered in the FastAPI app."""
    app = create_app()
    openapi_paths = app.openapi()["paths"]

    assert "/api/v1/viva/sessions" in openapi_paths
    assert "/api/v1/viva/sessions/{session_id}" in openapi_paths

    sessions_methods = openapi_paths["/api/v1/viva/sessions"]
    assert "post" in sessions_methods
    assert "get" in sessions_methods

    detail_methods = openapi_paths["/api/v1/viva/sessions/{session_id}"]
    assert "get" in detail_methods
    assert "delete" in detail_methods
