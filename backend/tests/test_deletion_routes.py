"""Unit and Integration Tests for Account Deletion and Data Purge Endpoints.

Verifies:
- DELETE /api/v1/users/me for cascading user account deletion, DB record removal,
  and physical file cleanup.
- DELETE /api/v1/users/me/data for purging experiments, viva sessions, documents,
  and physical files while preserving user profile and settings.
- Multi-tenant isolation (User B is untouched when User A deletes or purges).
- Prevention of IDOR / payload manipulation targeting another user.
- Predictable repeated deletion attempts returning 401 Unauthorized.
- Safe handling of missing physical files, permission errors, and database rollback.
- Strict path traversal prevention in DocumentStorageService.cleanup_user_files.
"""

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
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
from app.modules.documents.models import UploadedDocument
from app.modules.documents.storage import (
    DocumentStorageService,
    get_storage_service,
)
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
        email="student.a@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashedsecret_a",
        full_name="Alice Student",
        university="Engineering Faculty",
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
        email="student.b@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashedsecret_b",
        full_name="Bob Student",
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
        default_question_count=5,
        preferred_focus="mixed",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def settings_b(user_b_id: uuid.UUID) -> UserSettings:
    now = datetime.now(timezone.utc)
    return UserSettings(
        id=uuid.uuid4(),
        user_id=user_b_id,
        default_difficulty="advanced",
        default_question_count=10,
        preferred_focus="theory",
        created_at=now,
        updated_at=now,
    )


def create_experiment_with_checklist(
    user_id: uuid.UUID,
    title: str = "Ohm's Law Verification",
    exp_id: Optional[uuid.UUID] = None,
) -> Experiment:
    """Helper to create an experiment with associated checklist."""
    now = datetime.now(timezone.utc)
    actual_exp_id = exp_id or uuid.uuid4()
    exp = Experiment(
        id=actual_exp_id,
        user_id=user_id,
        title=title,
        subject="Physics",
        experiment_number="EXP-01",
        course_semester="Semester 1",
        creation_method="manual",
        has_manual_file=False,
        file_name=None,
        status="ready",
        description=f"Description for {title}.",
        objective=f"Objective for {title}.",
        theory=f"Theoretical background for {title}.",
        apparatus="Standard laboratory apparatus.",
        procedure="1. Setup apparatus. 2. Record observations.",
        observations="Experimental observations table.",
        calculations="Calculated experimental values.",
        precautions="Follow laboratory safety standards.",
        created_at=now,
        updated_at=now,
    )
    chk = PreparationChecklist(
        id=uuid.uuid4(),
        experiment_id=actual_exp_id,
        items={"objective": True, "theory": True},
        created_at=now,
        updated_at=now,
        experiment=exp,
    )
    exp.checklist = chk
    return exp


def create_viva_with_answers(
    user_id: uuid.UUID,
    experiment_id: uuid.UUID,
    session_id: Optional[uuid.UUID] = None,
) -> VivaSession:
    """Helper to create a viva session with an answer."""
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
        strong_topics=["theory"],
        revision_recommendations=[],
        created_at=now,
        updated_at=now,
    )
    ans = VivaAnswer(
        id=uuid.uuid4(),
        session_id=actual_sess_id,
        question_number=1,
        question_text="State Ohm's Law.",
        student_answer="V is proportional to I.",
        score=9,
        feedback="Accurate definition.",
        suggested_improvement="Mention constant temperature.",
        created_at=now,
    )
    ans.session = session
    session.answers = [ans]
    return session


def create_document_record(
    user_id: uuid.UUID,
    experiment_id: uuid.UUID,
    file_name: str,
    storage_path: str,
    doc_id: Optional[uuid.UUID] = None,
) -> UploadedDocument:
    """Helper to create an uploaded document record."""
    now = datetime.now(timezone.utc)
    return UploadedDocument(
        id=doc_id or uuid.uuid4(),
        user_id=user_id,
        experiment_id=experiment_id,
        file_name=file_name,
        file_size_bytes=1024,
        mime_type="application/pdf",
        storage_path=storage_path,
        status="completed",
        extracted_text="Sample text",
        extracted_data={},
        error_message=None,
        created_at=now,
        updated_at=now,
    )


# ==============================================================================
# Realistic Mock State Store
# ==============================================================================


class DeletionTestState:
    """Maintains stateful in-memory database and storage for deletion tests."""

    def __init__(
        self,
        users: list[User],
        settings: list[UserSettings],
        experiments: list[Experiment],
        viva_sessions: list[VivaSession],
        documents: list[UploadedDocument],
        storage_service: DocumentStorageService,
    ) -> None:
        self.users: dict[uuid.UUID, User] = {u.id: u for u in users}
        self.settings: dict[uuid.UUID, UserSettings] = {s.user_id: s for s in settings}
        self.experiments: dict[uuid.UUID, Experiment] = {e.id: e for e in experiments}
        self.viva_sessions: dict[uuid.UUID, VivaSession] = {v.id: v for v in viva_sessions}
        self.documents: dict[uuid.UUID, UploadedDocument] = {d.id: d for d in documents}
        self.storage = storage_service
        self.deleted_instances: list[Any] = []
        self.commit_count = 0
        self.rollback_count = 0

    def make_mock_session(self) -> AsyncMock:
        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()

        async def fake_delete(instance: Any) -> None:
            self.deleted_instances.append(instance)
            if isinstance(instance, User):
                self.users.pop(instance.id, None)
                self.settings.pop(instance.id, None)
                # Cascades
                for e_id, exp in list(self.experiments.items()):
                    if exp.user_id == instance.id:
                        self.experiments.pop(e_id, None)
                for v_id, viva in list(self.viva_sessions.items()):
                    if viva.user_id == instance.id:
                        self.viva_sessions.pop(v_id, None)
                for d_id, doc in list(self.documents.items()):
                    if doc.user_id == instance.id:
                        self.documents.pop(d_id, None)
            elif isinstance(instance, Experiment):
                self.experiments.pop(instance.id, None)
            elif isinstance(instance, VivaSession):
                self.viva_sessions.pop(instance.id, None)
            elif isinstance(instance, UploadedDocument):
                self.documents.pop(instance.id, None)

        async def fake_commit() -> None:
            self.commit_count += 1

        async def fake_rollback() -> None:
            self.rollback_count += 1

        async def fake_execute(statement, *args, **kwargs) -> MagicMock:
            stmt_str = str(statement).lower()
            res = MagicMock()

            # Extract bound UUID parameter from statement if available
            target_uuid = None
            try:
                compiled = statement.compile()
                for val in compiled.params.values():
                    if isinstance(val, uuid.UUID):
                        target_uuid = val
                        break
            except Exception:
                pass

            if "from users" in stmt_str:
                if target_uuid and target_uuid in self.users:
                    res.scalar_one_or_none.return_value = self.users[target_uuid]
                elif not target_uuid and len(self.users) == 1:
                    res.scalar_one_or_none.return_value = list(self.users.values())[0]
                else:
                    res.scalar_one_or_none.return_value = None
            elif "from user_settings" in stmt_str:
                if target_uuid and target_uuid in self.settings:
                    res.scalar_one_or_none.return_value = self.settings[target_uuid]
                elif not target_uuid and len(self.settings) == 1:
                    res.scalar_one_or_none.return_value = list(self.settings.values())[0]
                else:
                    res.scalar_one_or_none.return_value = None
            elif "from uploaded_documents" in stmt_str:
                if target_uuid:
                    matched_docs = [d for d in self.documents.values() if d.user_id == target_uuid]
                else:
                    matched_docs = list(self.documents.values())
                res.scalars.return_value.all.return_value = matched_docs
            elif "from experiments" in stmt_str:
                if target_uuid:
                    matched_exps = [e for e in self.experiments.values() if e.user_id == target_uuid]
                else:
                    matched_exps = list(self.experiments.values())
                res.scalars.return_value.all.return_value = matched_exps
            elif "from viva_sessions" in stmt_str:
                if target_uuid:
                    matched_vivas = [v for v in self.viva_sessions.values() if v.user_id == target_uuid]
                else:
                    matched_vivas = list(self.viva_sessions.values())
                res.scalars.return_value.all.return_value = matched_vivas
            else:
                res.scalars.return_value.all.return_value = []
                res.scalar_one_or_none.return_value = None

            return res

        session.delete = AsyncMock(side_effect=fake_delete)
        session.commit = AsyncMock(side_effect=fake_commit)
        session.rollback = AsyncMock(side_effect=fake_rollback)
        session.execute = AsyncMock(side_effect=fake_execute)
        return session


# ==============================================================================
# Helper to create physical test files in sandbox
# ==============================================================================


def write_test_file(base_dir: Path, rel_path: str, content: bytes = b"%PDF-1.4 test") -> Path:
    target = base_dir / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


# ==============================================================================
# 1. Successful Account Deletion (DELETE /api/v1/users/me)
# ==============================================================================


@pytest.mark.anyio
async def test_delete_account_success(
    tmp_path: Path,
    user_a: User,
    settings_a: UserSettings,
) -> None:
    """Authenticated user deletes their account:

    - Returns 200 with documented success schema.
    - User record and related records are removed.
    - Physical files belonging to the user are removed from storage.
    - Empty user folder is cleaned up.
    """
    storage = DocumentStorageService(base_dir=tmp_path)
    exp = create_experiment_with_checklist(user_a.id)
    viva = create_viva_with_answers(user_a.id, exp.id)

    # Create real files on disk
    rel_path = f"{user_a.id}/{exp.id}/lab_manual.pdf"
    file_on_disk = write_test_file(tmp_path, rel_path)
    assert file_on_disk.is_file()

    doc = create_document_record(user_a.id, exp.id, "lab_manual.pdf", rel_path)

    state = DeletionTestState(
        users=[user_a],
        settings=[settings_a],
        experiments=[exp],
        viva_sessions=[viva],
        documents=[doc],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert "deleted successfully" in data["message"].lower()
    assert data["user_id"] == str(user_a.id)
    assert "deleted_at" in data

    # Verify physical file was unlinked
    assert not file_on_disk.exists()
    # Verify empty user directory was pruned
    assert not (tmp_path / str(user_a.id)).exists()

    # Verify DB state
    assert user_a.id not in state.users
    assert user_a.id not in state.settings
    assert exp.id not in state.experiments
    assert viva.id not in state.viva_sessions
    assert doc.id not in state.documents
    assert state.commit_count == 1
    assert state.rollback_count == 0


# ==============================================================================
# 2. Multi-Tenant Isolation
# ==============================================================================


@pytest.mark.anyio
async def test_delete_account_isolation_leaves_other_user_intact(
    tmp_path: Path,
    user_a: User,
    user_b: User,
    settings_a: UserSettings,
    settings_b: UserSettings,
) -> None:
    """Deleting User A does NOT affect User B's profile, settings, experiments, or physical files."""
    storage = DocumentStorageService(base_dir=tmp_path)

    # User A records & files
    exp_a = create_experiment_with_checklist(user_a.id, title="Physics A")
    viva_a = create_viva_with_answers(user_a.id, exp_a.id)
    rel_path_a = f"{user_a.id}/{exp_a.id}/manual_a.pdf"
    file_a = write_test_file(tmp_path, rel_path_a)
    doc_a = create_document_record(user_a.id, exp_a.id, "manual_a.pdf", rel_path_a)

    # User B records & files
    exp_b = create_experiment_with_checklist(user_b.id, title="Chemistry B")
    viva_b = create_viva_with_answers(user_b.id, exp_b.id)
    rel_path_b = f"{user_b.id}/{exp_b.id}/manual_b.pdf"
    file_b = write_test_file(tmp_path, rel_path_b)
    doc_b = create_document_record(user_b.id, exp_b.id, "manual_b.pdf", rel_path_b)

    state = DeletionTestState(
        users=[user_a, user_b],
        settings=[settings_a, settings_b],
        experiments=[exp_a, exp_b],
        viva_sessions=[viva_a, viva_b],
        documents=[doc_a, doc_b],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token_a = create_access_token(user_a.id)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me", headers=headers_a)

    assert response.status_code == 200

    # User A's file was deleted
    assert not file_a.exists()
    assert not (tmp_path / str(user_a.id)).exists()

    # User B's file STILL EXISTS
    assert file_b.is_file()
    assert (tmp_path / str(user_b.id)).is_dir()

    # User B's database records are untouched
    assert user_b.id in state.users
    assert user_b.id in state.settings
    assert exp_b.id in state.experiments
    assert viva_b.id in state.viva_sessions
    assert doc_b.id in state.documents


# ==============================================================================
# 3. IDOR / Parameter Tampering Resistance
# ==============================================================================


@pytest.mark.anyio
async def test_delete_account_cannot_target_other_user_via_params_or_body(
    tmp_path: Path,
    user_a: User,
    user_b: User,
    settings_a: UserSettings,
    settings_b: UserSettings,
) -> None:
    """User A passes User B's ID in query parameters or JSON body.

    The endpoint must derive identity exclusively from token and delete only User A.
    """
    storage = DocumentStorageService(base_dir=tmp_path)
    state = DeletionTestState(
        users=[user_a, user_b],
        settings=[settings_a, settings_b],
        experiments=[],
        viva_sessions=[],
        documents=[],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token_a = create_access_token(user_a.id)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Attempt via query param & JSON body
        response = await client.request(
            "DELETE",
            f"/api/v1/users/me?user_id={user_b.id}",
            headers=headers_a,
            json={"user_id": str(user_b.id), "target": str(user_b.id)},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_a.id)

    # User A was deleted, User B remains completely intact
    assert user_a.id not in state.users
    assert user_b.id in state.users


# ==============================================================================
# 4. Predictable Repeated Deletion Attempts (401 on Second Call)
# ==============================================================================


@pytest.mark.anyio
async def test_repeated_deletion_attempt_returns_401(
    tmp_path: Path,
    user_a: User,
    settings_a: UserSettings,
) -> None:
    """First deletion succeeds (200). Second deletion attempt with same token returns 401 Unauthorized."""
    storage = DocumentStorageService(base_dir=tmp_path)
    state = DeletionTestState(
        users=[user_a],
        settings=[settings_a],
        experiments=[],
        viva_sessions=[],
        documents=[],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Call 1: Success
        res1 = await client.delete("/api/v1/users/me", headers=headers)
        assert res1.status_code == 200

        # Call 2: User no longer exists in DB -> 401 Unauthorized
        res2 = await client.delete("/api/v1/users/me", headers=headers)
        assert res2.status_code == 401
        assert res2.json()["detail"] == "Could not validate credentials"


# ==============================================================================
# 5. Edge Cases: Empty Records & Missing Physical Files
# ==============================================================================


@pytest.mark.anyio
async def test_delete_account_user_with_no_associated_records(
    tmp_path: Path,
    user_a: User,
) -> None:
    """User with 0 experiments, 0 sessions, 0 docs deletes cleanly."""
    storage = DocumentStorageService(base_dir=tmp_path)
    state = DeletionTestState(
        users=[user_a],
        settings=[],
        experiments=[],
        viva_sessions=[],
        documents=[],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    assert user_a.id not in state.users


@pytest.mark.anyio
async def test_delete_account_user_with_no_uploaded_files(
    tmp_path: Path,
    user_a: User,
    settings_a: UserSettings,
) -> None:
    """User has experiments and viva sessions, but zero uploaded documents or physical files."""
    storage = DocumentStorageService(base_dir=tmp_path)
    exp = create_experiment_with_checklist(user_a.id)
    viva = create_viva_with_answers(user_a.id, exp.id)

    state = DeletionTestState(
        users=[user_a],
        settings=[settings_a],
        experiments=[exp],
        viva_sessions=[viva],
        documents=[],  # 0 documents
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    assert user_a.id not in state.users
    assert exp.id not in state.experiments
    assert viva.id not in state.viva_sessions
    assert state.commit_count == 1



@pytest.mark.anyio
async def test_delete_account_handles_missing_physical_files_safely(
    tmp_path: Path,
    user_a: User,
    settings_a: UserSettings,
) -> None:
    """UploadedDocument metadata exists in DB, but physical file on disk is already absent."""
    storage = DocumentStorageService(base_dir=tmp_path)
    exp = create_experiment_with_checklist(user_a.id)
    rel_path = f"{user_a.id}/{exp.id}/already_deleted.pdf"
    # Notice: we do NOT create the file on disk!
    assert not (tmp_path / rel_path).exists()

    doc = create_document_record(user_a.id, exp.id, "already_deleted.pdf", rel_path)

    state = DeletionTestState(
        users=[user_a],
        settings=[settings_a],
        experiments=[exp],
        viva_sessions=[],
        documents=[doc],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me", headers=headers)

    assert response.status_code == 200
    assert user_a.id not in state.users
    assert state.commit_count == 1


# ==============================================================================
# 6. Failure Recovery & Rollback Guarantees
# ==============================================================================


@pytest.mark.anyio
async def test_delete_account_filesystem_failure_aborts_db_deletion(
    tmp_path: Path,
    user_a: User,
    settings_a: UserSettings,
) -> None:
    """When filesystem deletion encounters a PermissionError:

    - Aborts immediately with HTTP 500.
    - Database commit is NOT executed.
    - User account remains in the database.
    - Error response does not leak absolute server storage paths.
    """
    storage = DocumentStorageService(base_dir=tmp_path)
    exp = create_experiment_with_checklist(user_a.id)
    rel_path = f"{user_a.id}/{exp.id}/locked.pdf"
    doc = create_document_record(user_a.id, exp.id, "locked.pdf", rel_path)

    state = DeletionTestState(
        users=[user_a],
        settings=[settings_a],
        experiments=[exp],
        viva_sessions=[],
        documents=[doc],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    # Mock storage service to simulate PermissionError
    mock_storage = MagicMock(spec=DocumentStorageService)
    mock_storage.base_dir = tmp_path
    mock_storage.cleanup_user_files.side_effect = PermissionError("Permission denied: write protected")

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: mock_storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me", headers=headers)

    assert response.status_code == 500
    body = response.json()
    assert "detail" in body
    # Must not leak filesystem paths or OS exception trace
    assert str(tmp_path) not in body["detail"]
    assert "PermissionError" not in body["detail"]

    # Database must NOT have committed
    assert state.commit_count == 0
    # User account must still be present
    assert user_a.id in state.users


@pytest.mark.anyio
async def test_delete_account_database_failure_triggers_rollback(
    tmp_path: Path,
    user_a: User,
    settings_a: UserSettings,
) -> None:
    """When database commit raises OperationalError, rollback is called and 500 is returned."""
    storage = DocumentStorageService(base_dir=tmp_path)
    state = DeletionTestState(
        users=[user_a],
        settings=[settings_a],
        experiments=[],
        viva_sessions=[],
        documents=[],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()
    mock_session.commit.side_effect = OperationalError("connection lost", None, None)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me", headers=headers)

    assert response.status_code == 500
    assert mock_session.rollback.called
    assert "OperationalError" not in response.json()["detail"]


@pytest.mark.anyio
async def test_delete_account_unauthenticated_returns_401() -> None:
    """Missing or invalid token returns HTTP 401."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # No auth
        r1 = await client.delete("/api/v1/users/me")
        assert r1.status_code == 401

        # Bad token
        r2 = await client.delete("/api/v1/users/me", headers={"Authorization": "Bearer invalid.token.payload"})
        assert r2.status_code == 401


# ==============================================================================
# 7. Data Purge (DELETE /api/v1/users/me/data)
# ==============================================================================


@pytest.mark.anyio
async def test_purge_user_data_success(
    tmp_path: Path,
    user_a: User,
    settings_a: UserSettings,
) -> None:
    """DELETE /api/v1/users/me/data:

    - Deletes experiments, checklists, viva sessions, viva answers, documents, and physical files.
    - Keeps User account and UserSettings completely intact.
    - Returns 200 with accurate count summary.
    """
    storage = DocumentStorageService(base_dir=tmp_path)
    exp1 = create_experiment_with_checklist(user_a.id, title="Exp 1")
    exp2 = create_experiment_with_checklist(user_a.id, title="Exp 2")
    viva1 = create_viva_with_answers(user_a.id, exp1.id)

    rel_path = f"{user_a.id}/{exp1.id}/manual.pdf"
    file_on_disk = write_test_file(tmp_path, rel_path)
    doc1 = create_document_record(user_a.id, exp1.id, "manual.pdf", rel_path)

    state = DeletionTestState(
        users=[user_a],
        settings=[settings_a],
        experiments=[exp1, exp2],
        viva_sessions=[viva1],
        documents=[doc1],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token = create_access_token(user_a.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me/data", headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["experiments_deleted"] == 2
    assert data["viva_sessions_deleted"] == 1
    assert data["documents_deleted"] == 1
    assert "cleared successfully" in data["message"].lower()

    # Physical file is deleted
    assert not file_on_disk.exists()

    # Experiments, viva, docs are cleared from state
    assert exp1.id not in state.experiments
    assert exp2.id not in state.experiments
    assert viva1.id not in state.viva_sessions
    assert doc1.id not in state.documents

    # BUT User and UserSettings REMAIN!
    assert user_a.id in state.users
    assert user_a.id in state.settings


@pytest.mark.anyio
async def test_purge_user_data_isolation(
    tmp_path: Path,
    user_a: User,
    user_b: User,
    settings_a: UserSettings,
    settings_b: UserSettings,
) -> None:
    """User A purges data. User B's experiments, viva sessions, documents, and files remain intact."""
    storage = DocumentStorageService(base_dir=tmp_path)

    # User A data
    exp_a = create_experiment_with_checklist(user_a.id, title="Exp A")
    viva_a = create_viva_with_answers(user_a.id, exp_a.id)

    # User B data & file
    exp_b = create_experiment_with_checklist(user_b.id, title="Exp B")
    viva_b = create_viva_with_answers(user_b.id, exp_b.id)
    rel_path_b = f"{user_b.id}/{exp_b.id}/manual_b.pdf"
    file_b = write_test_file(tmp_path, rel_path_b)
    doc_b = create_document_record(user_b.id, exp_b.id, "manual_b.pdf", rel_path_b)

    state = DeletionTestState(
        users=[user_a, user_b],
        settings=[settings_a, settings_b],
        experiments=[exp_a, exp_b],
        viva_sessions=[viva_a, viva_b],
        documents=[doc_b],
        storage_service=storage,
    )
    mock_session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_session
    app.dependency_overrides[get_storage_service] = lambda: storage

    transport = httpx.ASGITransport(app=app)
    token_a = create_access_token(user_a.id)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me/data", headers=headers_a)

    assert response.status_code == 200

    # User A records purged
    assert exp_a.id not in state.experiments
    assert viva_a.id not in state.viva_sessions

    # User B records and physical file completely intact
    assert exp_b.id in state.experiments
    assert viva_b.id in state.viva_sessions
    assert doc_b.id in state.documents
    assert file_b.is_file()


@pytest.mark.anyio
async def test_purge_user_data_unauthenticated_returns_401() -> None:
    """Calling DELETE /api/v1/users/me/data without auth returns 401."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/v1/users/me/data")
        assert response.status_code == 401


# ==============================================================================
# 8. DocumentStorageService.cleanup_user_files Security & Unit Tests
# ==============================================================================


def test_storage_cleanup_user_files_normal(tmp_path: Path) -> None:
    """Deletes existing files and prunes empty directories."""
    service = DocumentStorageService(base_dir=tmp_path)
    u_id = uuid.uuid4()
    exp_id = uuid.uuid4()

    rel_path1 = f"{u_id}/{exp_id}/manual1.pdf"
    rel_path2 = f"{u_id}/{exp_id}/manual2.pdf"
    f1 = write_test_file(tmp_path, rel_path1)
    f2 = write_test_file(tmp_path, rel_path2)

    assert f1.is_file()
    assert f2.is_file()

    count = service.cleanup_user_files(u_id, [rel_path1, rel_path2])
    assert count == 2
    assert not f1.exists()
    assert not f2.exists()
    assert not (tmp_path / str(u_id)).exists()


def test_storage_cleanup_user_files_missing_file_resilience(tmp_path: Path) -> None:
    """Nonexistent files are safely skipped without error."""
    service = DocumentStorageService(base_dir=tmp_path)
    u_id = uuid.uuid4()
    count = service.cleanup_user_files(u_id, [f"{u_id}/nonexistent.pdf"])
    assert count == 0


def test_storage_cleanup_user_files_blocks_path_traversal_outside_sandbox(tmp_path: Path) -> None:
    """Attempts to traverse outside base_dir are ignored."""
    service = DocumentStorageService(base_dir=tmp_path)
    u_id = uuid.uuid4()

    # Create a file outside the sandbox
    outside_dir = tmp_path.parent / "outside_test"
    outside_dir.mkdir(exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("critical secret")

    malicious_paths = [
        "../../outside_test/secret.txt",
        "/outside_test/secret.txt",
        "../../../etc/passwd",
    ]
    count = service.cleanup_user_files(u_id, malicious_paths)
    assert count == 0
    assert outside_file.is_file()
    assert outside_file.read_text() == "critical secret"


def test_storage_cleanup_user_files_blocks_cross_user_deletion(tmp_path: Path) -> None:
    """User A cannot delete User B's file even if malicious relative path is supplied."""
    service = DocumentStorageService(base_dir=tmp_path)
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()

    # User B's file
    user_b_rel = f"{user_b}/exp/manual_b.pdf"
    user_b_file = write_test_file(tmp_path, user_b_rel)
    assert user_b_file.is_file()

    # User A tries to pass User B's path
    cross_user_paths = [
        user_b_rel,
        f"{user_a}/../{user_b}/exp/manual_b.pdf",
    ]
    count = service.cleanup_user_files(user_a, cross_user_paths)
    assert count == 0
    # User B's file is strictly preserved
    assert user_b_file.is_file()
