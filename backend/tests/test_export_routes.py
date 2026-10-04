"""Unit and Integration Tests for User Account Data Export Endpoint.

Verifies GET /api/v1/users/me/export for full account data retrieval,
multi-tenant ownership isolation, sensitive data exclusion, relationship preservation,
empty dataset handling, and read-only execution safety.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.modules.auth.models import User
from app.modules.documents.models import UploadedDocument
from app.modules.experiments.models import Experiment, PreparationChecklist
from app.modules.users.models import UserSettings
from app.modules.viva.models import VivaAnswer, VivaSession


# ==============================================================================
# Test Fixtures & Factories
# ==============================================================================


@pytest.fixture
def user_a_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_b_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_a(user_a_id: uuid.UUID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=user_a_id,
        email="alex.student@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashedsecret_a",
        full_name="Alex Student",
        university="Faculty of Engineering",
        is_active=True,
        auth_provider="local",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def user_b(user_b_id: uuid.UUID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=user_b_id,
        email="other.student@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashedsecret_b",
        full_name="Other Student",
        university="Science College",
        is_active=True,
        auth_provider="local",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def settings_a(user_a_id: uuid.UUID) -> UserSettings:
    now = datetime.now(timezone.utc)
    return UserSettings(
        id=uuid.uuid4(),
        user_id=user_a_id,
        default_difficulty="intermediate",
        default_question_count=10,
        preferred_focus="theory",
        created_at=now,
        updated_at=now,
    )


def create_experiment_bundle(
    user_id: uuid.UUID,
    title: str = "Ohm's Law Verification",
    subject: str = "Physics",
    objective: Optional[str] = None,
    theory: Optional[str] = None,
    exp_id: Optional[uuid.UUID] = None,
    checklist_items: Optional[dict[str, bool]] = None,
) -> Experiment:
    """Helper to create an experiment with associated checklist."""
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
        description=f"Description for {title}.",
        objective=objective or f"Objective for {title}.",
        theory=theory or f"Theoretical background for {title}.",
        apparatus="Standard laboratory apparatus.",
        procedure="1. Setup apparatus. 2. Record observations.",
        observations="Experimental observations table.",
        calculations="Calculated experimental values.",
        precautions="Follow laboratory safety standards.",
        created_at=now,
        updated_at=now,
    )
    items = checklist_items or {
        "objective": True,
        "theory": True,
        "apparatus": False,
        "procedure": False,
        "precautions": False,
    }
    chk = PreparationChecklist(
        id=uuid.uuid4(),
        experiment_id=actual_exp_id,
        items=items,
        created_at=now,
        updated_at=now,
        experiment=exp,
    )
    exp.checklist = chk
    return exp


def create_viva_session_bundle(
    user_id: uuid.UUID,
    experiment_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = None,
    include_answers: bool = True,
    question_text: str = "State Ohm's Law.",
    student_answer: str = "V is proportional to I at constant temperature.",
) -> VivaSession:
    """Helper to create a viva session with nested evaluated answers."""
    now = datetime.now(timezone.utc)
    actual_sess_id = session_id or uuid.uuid4()
    session = VivaSession(
        id=actual_sess_id,
        user_id=user_id,
        experiment_id=experiment_id,
        difficulty="intermediate",
        question_count=5,
        topic_focus="mixed",
        provider_mode="demonstration",
        is_completed=True,
        started_at=now,
        completed_at=now,
        average_score=Decimal("8.50"),
        total_questions=5,
        questions_answered=5,
        correct_count=4,
        partially_correct_count=1,
        incorrect_count=0,
        topic_analysis={"theory": {"correct": 2, "total": 2, "score": 9.0}},
        weak_topics=["precautions"],
        strong_topics=["theory", "procedure"],
        revision_recommendations=[{"topic": "precautions", "suggestion": "Review safety guidelines."}],
        created_at=now,
        updated_at=now,
    )
    if include_answers:
        ans1 = VivaAnswer(
            id=uuid.uuid4(),
            session_id=actual_sess_id,
            question_id="q-001",
            question_number=1,
            topic="theory",
            difficulty="intermediate",
            question_text=question_text,
            student_answer=student_answer,
            score=9,
            verdict="correct",
            feedback="Accurate statement.",
            expected_answer="Current through a conductor is proportional to potential difference.",
            what_you_got_right="Correct relationship stated.",
            what_was_missing="Could mention constant physical conditions.",
            suggested_improvement="Always specify temperature invariance.",
            key_points_covered=["proportional", "temperature"],
            key_points_missed=[],
            evaluation_data={"rubric_match": True},
            time_spent_seconds=25,
            created_at=now,
        )
        ans1.session = session
        session.answers = [ans1]
    else:
        session.answers = []
    return session


def create_document_bundle(
    user_id: uuid.UUID,
    experiment_id: Optional[uuid.UUID] = None,
    doc_id: Optional[uuid.UUID] = None,
    file_name: str = "lab_manual_physics.pdf",
    extracted_text: str = "LAB EXPERIMENT 1: OHM'S LAW. Objective: Measure resistance...",
) -> UploadedDocument:
    """Helper to create an uploaded document record."""
    now = datetime.now(timezone.utc)
    return UploadedDocument(
        id=doc_id or uuid.uuid4(),
        user_id=user_id,
        experiment_id=experiment_id,
        file_name=file_name,
        file_size_bytes=1048576,
        mime_type="application/pdf",
        storage_path=f"/var/secure/uploads/{file_name}",  # Must be excluded from export!
        status="completed",
        extracted_text=extracted_text,
        extracted_data={"sections_detected": ["objective", "theory", "apparatus"]},
        error_message=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def mock_db_data(
    user_a: User,
    user_b: User,
    settings_a: UserSettings,
) -> dict[str, Any]:
    """Prepares structured test dataset containing records for both users."""
    exp1_a = create_experiment_bundle(user_a.id, title="Ohm's Law")
    exp2_a = create_experiment_bundle(user_a.id, title="Spectrometer Prisms")
    viva1_a = create_viva_session_bundle(user_a.id, exp1_a.id)
    doc1_a = create_document_bundle(user_a.id, exp1_a.id)

    # Records belonging to user_b (for ownership isolation verification)
    exp1_b = create_experiment_bundle(user_b.id, title="Chemistry Titration")
    viva1_b = create_viva_session_bundle(
        user_b.id,
        exp1_b.id,
        question_text="What is the endpoint of acid-base titration?",
        student_answer="The point where indicator changes color.",
    )
    doc1_b = create_document_bundle(
        user_b.id,
        exp1_b.id,
        file_name="chemistry_titration_manual.pdf",
        extracted_text="LAB EXPERIMENT 2: ACID BASE TITRATION. Objective: Standardize NaOH...",
    )

    return {
        "users": [user_a, user_b],
        "settings": [settings_a],
        "experiments": [exp1_a, exp2_a, exp1_b],
        "viva_sessions": [viva1_a, viva1_b],
        "documents": [doc1_a, doc1_b],
    }


def make_mock_session(mock_db_data: dict[str, Any]) -> AsyncMock:
    """Creates a mock AsyncSession that accurately filters by user_id in SQL statements."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.delete = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()

    async def fake_execute(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        res = MagicMock()

        # Handle user lookup by token dependency
        if "from users" in stmt_str:
            # Check if querying for user_a or user_b
            if str(mock_db_data["users"][1].id).lower() in stmt_str:
                res.scalar_one_or_none.return_value = mock_db_data["users"][1]
            else:
                res.scalar_one_or_none.return_value = mock_db_data["users"][0]
        elif "from user_settings" in stmt_str:
            target_user_id = mock_db_data["users"][0].id
            settings_match = next(
                (s for s in mock_db_data["settings"] if s.user_id == target_user_id),
                None,
            )
            res.scalar_one_or_none.return_value = settings_match
        elif "from experiments" in stmt_str:
            target_user_id = mock_db_data["users"][0].id
            exp_matches = [
                e for e in mock_db_data["experiments"] if e.user_id == target_user_id
            ]
            res.scalars.return_value.all.return_value = exp_matches
        elif "from viva_sessions" in stmt_str:
            target_user_id = mock_db_data["users"][0].id
            viva_matches = [
                v for v in mock_db_data["viva_sessions"] if v.user_id == target_user_id
            ]
            res.scalars.return_value.all.return_value = viva_matches
        elif "from uploaded_documents" in stmt_str:
            target_user_id = mock_db_data["users"][0].id
            doc_matches = [
                d for d in mock_db_data["documents"] if d.user_id == target_user_id
            ]
            res.scalars.return_value.all.return_value = doc_matches
        else:
            res.scalars.return_value.all.return_value = []
            res.scalar_one_or_none.return_value = None

        return res

    session.execute = AsyncMock(side_effect=fake_execute)
    return session


@pytest.fixture
def auth_headers_user_a(user_a: User) -> dict[str, str]:
    token = create_access_token(user_a.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_user_b(user_b: User) -> dict[str, str]:
    token = create_access_token(user_b.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client_with_data(mock_db_data: dict[str, Any]) -> tuple[httpx.AsyncClient, AsyncMock]:
    mock_session = make_mock_session(mock_db_data)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    transport = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=transport, base_url="http://test")
    return c, mock_session


# ==============================================================================
# 1. Authenticated Export Returns HTTP 200
# ==============================================================================


@pytest.mark.anyio
async def test_export_authenticated_returns_200(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")


# ==============================================================================
# 2. Export Contains Expected Top-Level Data Sections
# ==============================================================================


@pytest.mark.anyio
async def test_export_contains_expected_top_level_sections(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    expected_sections = {
        "export_version",
        "exported_at",
        "user",
        "settings",
        "experiments",
        "viva_sessions",
        "documents",
        "summary",
    }
    for section in expected_sections:
        assert section in data, f"Missing expected top-level section: {section}"


# ==============================================================================
# 3. Profile and Settings Data Are Included
# ==============================================================================


@pytest.mark.anyio
async def test_export_profile_and_settings_included(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
    user_a: User,
    settings_a: UserSettings,
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    user_info = data["user"]
    assert user_info["id"] == str(user_a.id)
    assert user_info["email"] == user_a.email
    assert user_info["full_name"] == user_a.full_name
    assert user_info["university"] == user_a.university
    assert user_info["is_active"] is True
    assert user_info["auth_provider"] == "local"

    settings_info = data["settings"]
    assert settings_info is not None
    assert settings_info["user_id"] == str(user_a.id)
    assert settings_info["default_difficulty"] == settings_a.default_difficulty
    assert settings_info["default_question_count"] == settings_a.default_question_count
    assert settings_info["preferred_focus"] == settings_a.preferred_focus


# ==============================================================================
# 4. Multiple Experiments Belonging to User Are Included
# ==============================================================================


@pytest.mark.anyio
async def test_export_multiple_experiments_included(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    experiments = data["experiments"]
    assert len(experiments) == 2
    titles = [exp["title"] for exp in experiments]
    assert "Ohm's Law" in titles
    assert "Spectrometer Prisms" in titles


# ==============================================================================
# 5. Related Checklist Data Is Preserved
# ==============================================================================


@pytest.mark.anyio
async def test_export_related_checklist_data_preserved(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    exp = next(e for e in data["experiments"] if e["title"] == "Ohm's Law")
    assert exp["checklist"] is not None
    assert "items" in exp["checklist"]
    assert exp["checklist"]["items"]["objective"] is True
    assert exp["checklist"]["items"]["theory"] is True
    assert exp["checklist"]["items"]["apparatus"] is False

    # Also verify flat preparation_checklist dictionary is synchronized
    assert exp["preparation_checklist"]["objective"] is True


# ==============================================================================
# 6. Viva Sessions and Associated Answers/Evaluations Are Included
# ==============================================================================


@pytest.mark.anyio
async def test_export_viva_sessions_and_answers_included(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    viva_sessions = data["viva_sessions"]
    assert len(viva_sessions) == 1
    session = viva_sessions[0]
    assert session["difficulty"] == "intermediate"
    assert session["is_completed"] is True
    assert session["average_score"] == 8.5
    assert len(session["answers"]) == 1

    answer = session["answers"][0]
    assert answer["question_text"] == "State Ohm's Law."
    assert answer["student_answer"] == "V is proportional to I at constant temperature."
    assert answer["score"] == 9
    assert answer["verdict"] == "correct"
    assert "proportional" in answer["key_points_covered"]


# ==============================================================================
# 7. Document Metadata and Stored Extracted Content Included
# ==============================================================================


@pytest.mark.anyio
async def test_export_document_metadata_and_extracted_content_included(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    documents = data["documents"]
    assert len(documents) == 1
    doc = documents[0]
    assert doc["file_name"] == "lab_manual_physics.pdf"
    assert doc["file_size_bytes"] == 1048576
    assert doc["mime_type"] == "application/pdf"
    assert doc["status"] == "completed"
    assert "LAB EXPERIMENT 1: OHM'S LAW" in doc["extracted_text"]
    assert "sections_detected" in doc["extracted_data"]


# ==============================================================================
# 8. Empty Datasets Produce Valid Responses Rather than Errors
# ==============================================================================


@pytest.mark.anyio
async def test_export_empty_dataset_produces_valid_response(
    user_a: User,
) -> None:
    """User with no experiments, viva sessions, documents, or settings gets HTTP 200."""
    user_without_settings = User(
        id=user_a.id,
        email="empty.user@university.edu",
        password_hash="$argon2id$somehash",
        full_name="Empty User",
        university="Empty State",
        is_active=True,
        auth_provider="local",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    user_without_settings.settings = None

    empty_session = AsyncMock(spec=AsyncSession)
    empty_session.commit = AsyncMock()
    empty_session.delete = AsyncMock()
    empty_session.add = MagicMock()

    async def fake_empty_execute(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        res = MagicMock()
        if "from users" in stmt_str:
            res.scalar_one_or_none.return_value = user_without_settings
        elif "from user_settings" in stmt_str:
            res.scalar_one_or_none.return_value = None
        else:
            res.scalars.return_value.all.return_value = []
            res.scalar_one_or_none.return_value = None
        return res

    empty_session.execute = AsyncMock(side_effect=fake_empty_execute)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: empty_session
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")

    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/users/me/export", headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["experiments"] == []
    assert data["viva_sessions"] == []
    assert data["documents"] == []
    assert data["summary"]["experiments_count"] == 0
    assert data["summary"]["viva_sessions_count"] == 0
    assert data["summary"]["documents_count"] == 0
    assert data["user"]["email"] == "empty.user@university.edu"
    assert data["settings"] is not None
    assert data["settings"]["default_difficulty"] == "intermediate"

    # Crucial: verify no database modification occurred
    empty_session.commit.assert_not_awaited()
    empty_session.add.assert_not_called()


# ==============================================================================
# 9. Unauthenticated Requests Return HTTP 401
# ==============================================================================


@pytest.mark.anyio
async def test_export_unauthenticated_returns_401(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
) -> None:
    client, _ = client_with_data
    # No auth header
    response = await client.get("/api/v1/users/me/export")
    assert response.status_code == 401

    # Invalid token
    response_invalid = await client.get(
        "/api/v1/users/me/export",
        headers={"Authorization": "Bearer invalid.token.payload"},
    )
    assert response_invalid.status_code == 401


# ==============================================================================
# 10. A User Cannot Export Another User's Data
# ==============================================================================


@pytest.mark.anyio
async def test_export_ownership_isolation(
    mock_db_data: dict[str, Any],
    user_b: User,
) -> None:
    """When User B requests export, User A's data is never returned."""
    session = AsyncMock(spec=AsyncSession)

    async def fake_execute_user_b(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        res = MagicMock()
        if "from users" in stmt_str:
            res.scalar_one_or_none.return_value = user_b
        elif "from user_settings" in stmt_str:
            # User B has no settings saved
            res.scalar_one_or_none.return_value = None
        elif "from experiments" in stmt_str:
            # Only user B's experiments
            exp_b = [e for e in mock_db_data["experiments"] if e.user_id == user_b.id]
            res.scalars.return_value.all.return_value = exp_b
        elif "from viva_sessions" in stmt_str:
            viva_b = [v for v in mock_db_data["viva_sessions"] if v.user_id == user_b.id]
            res.scalars.return_value.all.return_value = viva_b
        elif "from uploaded_documents" in stmt_str:
            doc_b = [d for d in mock_db_data["documents"] if d.user_id == user_b.id]
            res.scalars.return_value.all.return_value = doc_b
        else:
            res.scalars.return_value.all.return_value = []
        return res

    session.execute = AsyncMock(side_effect=fake_execute_user_b)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")

    token_b = create_access_token(user_b.id)
    headers_b = {"Authorization": f"Bearer {token_b}"}

    response = await client.get("/api/v1/users/me/export", headers=headers_b)
    assert response.status_code == 200
    data = response.json()

    # User B should only see their 1 experiment ("Chemistry Titration")
    assert len(data["experiments"]) == 1
    assert data["experiments"][0]["title"] == "Chemistry Titration"
    assert data["user"]["id"] == str(user_b.id)
    assert data["user"]["email"] == user_b.email

    # Verify no User A data leaked
    all_json_text = response.text
    assert "Alex Student" not in all_json_text
    assert "Ohm's Law" not in all_json_text
    assert "Spectrometer Prisms" not in all_json_text


# ==============================================================================
# 11. Sensitive Authentication Fields and Server Paths Are Excluded
# ==============================================================================


@pytest.mark.anyio
async def test_export_excludes_sensitive_fields(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    raw_text = response.text

    # Credentials & password hashes must never be exposed
    assert "password_hash" not in raw_text
    assert "somehashedsecret_a" not in raw_text
    assert "argon2id" not in raw_text

    # Server filesystem storage path must never be exposed
    assert "storage_path" not in raw_text
    assert "/var/secure/uploads" not in raw_text


# ==============================================================================
# 12. Export Does Not Modify or Delete Any Database Records
# ==============================================================================


@pytest.mark.anyio
async def test_export_is_strictly_read_only(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, session = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200

    # Ensure no write operations were performed
    session.add.assert_not_called()
    session.delete.assert_not_awaited()
    session.commit.assert_not_awaited()


# ==============================================================================
# 13. Timestamps and UUIDs Serialize Correctly
# ==============================================================================


@pytest.mark.anyio
async def test_export_timestamps_and_uuids_serialize_correctly(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    # Verify UUID format
    assert uuid.UUID(data["user"]["id"])
    assert uuid.UUID(data["settings"]["id"])
    for exp in data["experiments"]:
        assert uuid.UUID(exp["id"])
        assert uuid.UUID(exp["user_id"])
        assert uuid.UUID(exp["checklist"]["id"])
        assert uuid.UUID(exp["checklist"]["experiment_id"])

    # Verify ISO 8601 timestamp formats
    assert datetime.fromisoformat(data["exported_at"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(data["user"]["created_at"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(data["experiments"][0]["created_at"].replace("Z", "+00:00"))
    assert datetime.fromisoformat(data["viva_sessions"][0]["created_at"].replace("Z", "+00:00"))


# ==============================================================================
# 14. Inactive Users Are Rejected
# ==============================================================================


@pytest.mark.anyio
async def test_export_inactive_user_rejected(
    user_a: User,
) -> None:
    inactive_user = User(
        id=user_a.id,
        email="inactive@university.edu",
        password_hash="$argon2id$somehash",
        full_name="Inactive Student",
        is_active=False,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_session = AsyncMock(spec=AsyncSession)

    async def fake_inactive_execute(statement, *args, **kwargs):
        res = MagicMock()
        res.scalar_one_or_none.return_value = inactive_user
        return res

    mock_session.execute = AsyncMock(side_effect=fake_inactive_execute)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")

    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/api/v1/users/me/export", headers=headers)
    assert response.status_code == 403
    assert "Inactive user" in response.json()["detail"]


# ==============================================================================
# 15. Summary Counts Match Array Lengths and Relationship References
# ==============================================================================


@pytest.mark.anyio
async def test_export_summary_counts_and_relationships(
    client_with_data: tuple[httpx.AsyncClient, AsyncMock],
    auth_headers_user_a: dict[str, str],
    user_a: User,
) -> None:
    client, _ = client_with_data
    response = await client.get("/api/v1/users/me/export", headers=auth_headers_user_a)
    assert response.status_code == 200
    data = response.json()

    # Record counts
    assert data["summary"]["experiments_count"] == len(data["experiments"])
    assert data["summary"]["viva_sessions_count"] == len(data["viva_sessions"])
    assert data["summary"]["documents_count"] == len(data["documents"])
    assert data["experiments_count"] == len(data["experiments"])

    # Relationship references
    exp_id = data["experiments"][0]["id"]
    checklist_exp_id = data["experiments"][0]["checklist"]["experiment_id"]
    assert exp_id == checklist_exp_id

    viva_sess = data["viva_sessions"][0]
    assert viva_sess["user_id"] == str(user_a.id)
    assert viva_sess["answers"][0]["session_id"] == viva_sess["id"]
