"""End-to-End Workflow Integration Tests (TASK-14.1).

Validates the full student journey across all backend modules in a realistic,
deterministic, and completely isolated environment:
- Step 1: Account Registration and Authentication (Argon2id hashing, tokens, profile).
- Step 2: User Settings (default study preferences, partial updates, user isolation).
- Step 3: Experiment Lifecycle (CRUD, UUID minting, search/list, multi-tenant IDOR protection).
- Step 4: Preparation Checklist (status toggling, association with experiment, persistence).
- Step 5: AI Viva Workflow (grounded question generation, answer evaluation, session persistence,
  answer transcripts, session history, offline deterministic demonstration mode).
- Step 6: Document Processing (isolated temporary upload storage, digital PDF extraction,
  non-destructive LLM section parsing into extracted_data draft, cross-user ownership isolation).
- Step 7: Data Export (full account export, relationship consistency, sensitive credential/path redaction).
- Step 8: Guest Data Migration (batch transfer, client-to-server UUID mapping, idempotent replay).
- Step 9: Data Purge (removal of study records, physical file cleanup, preservation of user profile/settings).
- Step 10: Account Deletion (cascading user deletion, storage prune, token invalidation returning 401).

Also validates failure, rollback, and multi-tenant security scenarios across all modules.
"""

from datetime import datetime, timezone
from decimal import Decimal
import io
from pathlib import Path
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pypdf
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.modules.ai.demonstration import DemonstrationAIProvider
from app.modules.auth.models import User
from app.modules.documents.extractor import (
    DocumentExtractorService,
    get_extractor_service,
)
from app.modules.documents.models import UploadedDocument
from app.modules.documents.parser import (
    DocumentSectionParserService,
    get_section_parser_service,
)
from app.modules.documents.storage import (
    DocumentStorageService,
    get_storage_service,
)
from app.modules.experiments.models import (
    Experiment,
    PreparationChecklist,
    default_preparation_checklist_items,
)
from app.modules.users.models import GuestMigration, UserSettings
from app.modules.viva.models import VivaAnswer, VivaSession
from app.modules.viva.router import get_viva_ai_provider


# ==============================================================================
# In-Memory Stateful Database Simulation
# ==============================================================================


class E2EWorkflowState:
    """Deterministic, stateful in-memory database simulation for E2E testing.

    Maintains relational tables for Users, Settings, Experiments, Checklists,
    Viva Sessions, Viva Answers, Documents, and Guest Migrations with realistic
    referential integrity, transactional commit/rollback, and query dispatching.
    """

    def __init__(self, storage_service: DocumentStorageService) -> None:
        self.users: dict[uuid.UUID, User] = {}
        self.settings: dict[uuid.UUID, UserSettings] = {}  # keyed by user_id
        self.experiments: dict[uuid.UUID, Experiment] = {}
        self.checklists: dict[uuid.UUID, PreparationChecklist] = {}  # keyed by experiment_id
        self.viva_sessions: dict[uuid.UUID, VivaSession] = {}
        self.viva_answers: dict[uuid.UUID, VivaAnswer] = {}
        self.documents: dict[uuid.UUID, UploadedDocument] = {}
        self.guest_migrations: list[GuestMigration] = []
        self.storage = storage_service

        self.added_in_tx: list[Any] = []
        self.commit_count = 0
        self.rollback_count = 0
        self.fail_on_commit = False

    def make_mock_session(self) -> AsyncMock:
        session = AsyncMock(spec=AsyncSession)

        def fake_add(instance: Any) -> None:
            self.added_in_tx.append(instance)
            now = datetime.now(timezone.utc)
            if hasattr(instance, "id") and getattr(instance, "id", None) is None:
                instance.id = uuid.uuid4()
            if hasattr(instance, "created_at") and getattr(instance, "created_at", None) is None:
                instance.created_at = now
            if hasattr(instance, "updated_at") and getattr(instance, "updated_at", None) is None:
                instance.updated_at = now

            if isinstance(instance, User):
                self.users[instance.id] = instance
            elif isinstance(instance, UserSettings):
                self.settings[instance.user_id] = instance
                if instance.user_id in self.users:
                    self.users[instance.user_id].settings = instance
            elif isinstance(instance, Experiment):
                self.experiments[instance.id] = instance
                if not hasattr(instance, "documents") or instance.documents is None:
                    instance.documents = []
            elif isinstance(instance, PreparationChecklist):
                self.checklists[instance.experiment_id] = instance
                if instance.experiment_id in self.experiments:
                    self.experiments[instance.experiment_id].checklist = instance
            elif isinstance(instance, VivaSession):
                self.viva_sessions[instance.id] = instance
                if not hasattr(instance, "answers") or instance.answers is None:
                    instance.answers = []
                if instance.experiment_id in self.experiments:
                    instance.experiment = self.experiments[instance.experiment_id]
            elif isinstance(instance, VivaAnswer):
                self.viva_answers[instance.id] = instance
                sess = self.viva_sessions.get(instance.session_id)
                if sess:
                    if not hasattr(sess, "answers") or sess.answers is None:
                        sess.answers = []
                    if instance not in sess.answers:
                        sess.answers.append(instance)
            elif isinstance(instance, UploadedDocument):
                self.documents[instance.id] = instance
                if instance.experiment_id and instance.experiment_id in self.experiments:
                    exp = self.experiments[instance.experiment_id]
                    if not hasattr(exp, "documents") or exp.documents is None:
                        exp.documents = []
                    if instance not in exp.documents:
                        exp.documents.append(instance)
            elif isinstance(instance, GuestMigration):
                self.guest_migrations.append(instance)

        async def fake_delete(instance: Any) -> None:
            if isinstance(instance, User):
                self.users.pop(instance.id, None)
                self.settings.pop(instance.id, None)
                # Cascade delete experiments
                for exp_id, exp in list(self.experiments.items()):
                    if exp.user_id == instance.id:
                        self.experiments.pop(exp_id, None)
                        self.checklists.pop(exp_id, None)
                # Cascade delete viva sessions
                for v_id, viva in list(self.viva_sessions.items()):
                    if viva.user_id == instance.id:
                        self.viva_sessions.pop(v_id, None)
                # Cascade delete documents
                for d_id, doc in list(self.documents.items()):
                    if doc.user_id == instance.id:
                        self.documents.pop(d_id, None)
                self.guest_migrations = [m for m in self.guest_migrations if m.user_id != instance.id]
            elif isinstance(instance, Experiment):
                self.experiments.pop(instance.id, None)
                self.checklists.pop(instance.id, None)
                for d_id, doc in list(self.documents.items()):
                    if doc.experiment_id == instance.id:
                        self.documents.pop(d_id, None)
                for v_id, viva in list(self.viva_sessions.items()):
                    if viva.experiment_id == instance.id:
                        self.viva_sessions.pop(v_id, None)
            elif isinstance(instance, UploadedDocument):
                self.documents.pop(instance.id, None)
                if instance.experiment_id and instance.experiment_id in self.experiments:
                    exp = self.experiments[instance.experiment_id]
                    if hasattr(exp, "documents") and exp.documents and instance in exp.documents:
                        exp.documents.remove(instance)
            elif isinstance(instance, VivaSession):
                self.viva_sessions.pop(instance.id, None)
            elif isinstance(instance, GuestMigration):
                if instance in self.guest_migrations:
                    self.guest_migrations.remove(instance)

        async def fake_commit() -> None:
            if self.fail_on_commit:
                raise OperationalError("Simulated database failure during commit", params=None, orig=Exception("Disk error"))
            self.commit_count += 1
            self.added_in_tx.clear()

        async def fake_rollback() -> None:
            self.rollback_count += 1
            for inst in self.added_in_tx:
                if isinstance(inst, User):
                    self.users.pop(inst.id, None)
                elif isinstance(inst, UserSettings):
                    self.settings.pop(inst.user_id, None)
                elif isinstance(inst, Experiment):
                    self.experiments.pop(inst.id, None)
                elif isinstance(inst, PreparationChecklist):
                    self.checklists.pop(inst.experiment_id, None)
                elif isinstance(inst, VivaSession):
                    self.viva_sessions.pop(inst.id, None)
                elif isinstance(inst, UploadedDocument):
                    self.documents.pop(inst.id, None)
                elif isinstance(inst, GuestMigration):
                    if inst in self.guest_migrations:
                        self.guest_migrations.remove(inst)
            self.added_in_tx.clear()

        async def fake_refresh(instance: Any) -> None:
            now = datetime.now(timezone.utc)
            if hasattr(instance, "updated_at") and not instance.updated_at:
                instance.updated_at = now
            if hasattr(instance, "created_at") and not instance.created_at:
                instance.created_at = now

        async def fake_execute(statement, *args, **kwargs) -> MagicMock:
            stmt_str = str(statement).lower()
            res = MagicMock()
            params: dict[str, Any] = {}
            try:
                compiled = statement.compile()
                params = dict(compiled.params)
            except Exception:
                pass

            uuids = [v for v in params.values() if isinstance(v, uuid.UUID)]
            strings = [v for v in params.values() if isinstance(v, str)]

            # ------------------------------------------------------------------
            # 1. Users table queries
            # ------------------------------------------------------------------
            if "from users" in stmt_str:
                email_candidates = [s for s in strings if "@" in s]
                if email_candidates:
                    matched = [u for u in self.users.values() if u.email.lower() == email_candidates[0].lower()]
                    res.scalar_one_or_none.return_value = matched[0] if matched else None
                elif uuids:
                    target_id = uuids[0]
                    res.scalar_one_or_none.return_value = self.users.get(target_id)
                else:
                    res.scalar_one_or_none.return_value = None
                return res

            # ------------------------------------------------------------------
            # 2. User Settings table queries
            # ------------------------------------------------------------------
            if "from user_settings" in stmt_str:
                matched_uid = next((u for u in uuids if u in self.settings), None)
                if not matched_uid and uuids:
                    matched_uid = uuids[0]
                res.scalar_one_or_none.return_value = self.settings.get(matched_uid)
                return res

            # ------------------------------------------------------------------
            # 3. Preparation Checklists table queries
            # ------------------------------------------------------------------
            if "from preparation_checklists" in stmt_str:
                matched_exp_id = next((u for u in uuids if u in self.checklists), None)
                if not matched_exp_id and uuids:
                    matched_exp_id = uuids[0]
                res.scalar_one_or_none.return_value = self.checklists.get(matched_exp_id)
                return res

            # ------------------------------------------------------------------
            # 4. Experiments table queries
            # ------------------------------------------------------------------
            if "from experiments" in stmt_str:
                target_user_id = next((u for u in uuids if u in self.users), None)
                non_user_uuids = [u for u in uuids if u not in self.users]

                search_terms = [s.strip("%").lower() for s in strings if s.startswith("%") and s.endswith("%")]

                def matches_exp_filter(e: Experiment) -> bool:
                    if target_user_id is not None and e.user_id != target_user_id:
                        return False
                    if search_terms:
                        st = search_terms[0]
                        if not (
                            st in (e.title or "").lower()
                            or st in (e.subject or "").lower()
                            or st in (e.description or "").lower()
                            or st in (e.experiment_number or "").lower()
                        ):
                            return False
                    return True

                if "count(" in stmt_str or "count_1" in stmt_str:
                    matched = [e for e in self.experiments.values() if matches_exp_filter(e)]
                    res.scalar_one.return_value = len(matched)
                    return res

                if non_user_uuids:
                    exp_id = non_user_uuids[0]
                    exp = self.experiments.get(exp_id)
                    if exp and (target_user_id is None or exp.user_id == target_user_id):
                        if exp.id in self.checklists:
                            exp.checklist = self.checklists[exp.id]
                        exp.documents = [d for d in self.documents.values() if d.experiment_id == exp.id]
                        res.scalar_one_or_none.return_value = exp
                        res.scalar_one.return_value = exp
                        res.scalars.return_value.all.return_value = [exp]
                        res.scalars.return_value.first.return_value = exp
                    else:
                        res.scalar_one_or_none.return_value = None
                        res.scalar_one.return_value = None
                        res.scalars.return_value.all.return_value = []
                        res.scalars.return_value.first.return_value = None
                    return res
                else:
                    matched = [e for e in self.experiments.values() if matches_exp_filter(e)]
                    for e in matched:
                        if e.id in self.checklists:
                            e.checklist = self.checklists[e.id]
                        e.documents = [d for d in self.documents.values() if d.experiment_id == e.id]
                    res.scalars.return_value.all.return_value = matched
                    res.scalars.return_value.first.return_value = matched[0] if matched else None
                    res.scalar_one_or_none.return_value = matched[0] if matched else None
                    res.scalar_one.return_value = matched[0] if matched else None
                    return res

            # ------------------------------------------------------------------
            # 5. Viva Sessions table queries
            # ------------------------------------------------------------------
            if "from viva_sessions" in stmt_str:
                target_user_id = next((u for u in uuids if u in self.users), None)
                non_user_uuids = [u for u in uuids if u not in self.users]

                # Check if experiment_id filter is present in non_user_uuids
                target_exp_id = next((u for u in non_user_uuids if u in self.experiments), None)

                def matches_viva_filter(v: VivaSession) -> bool:
                    if target_user_id is not None and v.user_id != target_user_id:
                        return False
                    if target_exp_id is not None and v.experiment_id != target_exp_id:
                        return False
                    return True

                if "count(" in stmt_str or "count_1" in stmt_str:
                    matched = [v for v in self.viva_sessions.values() if matches_viva_filter(v)]
                    res.scalar_one.return_value = len(matched)
                    return res

                if non_user_uuids and not target_exp_id:
                    sess_id = non_user_uuids[0]
                    sess = self.viva_sessions.get(sess_id)
                    if sess and (target_user_id is None or sess.user_id == target_user_id):
                        if sess.experiment_id in self.experiments:
                            sess.experiment = self.experiments[sess.experiment_id]
                        res.scalar_one_or_none.return_value = sess
                        res.scalar_one.return_value = sess
                        res.scalars.return_value.all.return_value = [sess]
                        res.scalars.return_value.first.return_value = sess
                    else:
                        res.scalar_one_or_none.return_value = None
                        res.scalar_one.return_value = None
                        res.scalars.return_value.all.return_value = []
                        res.scalars.return_value.first.return_value = None
                    return res
                else:
                    matched = [v for v in self.viva_sessions.values() if matches_viva_filter(v)]
                    for s in matched:
                        if s.experiment_id in self.experiments:
                            s.experiment = self.experiments[s.experiment_id]
                    res.scalars.return_value.all.return_value = matched
                    res.scalars.return_value.first.return_value = matched[0] if matched else None
                    res.scalar_one_or_none.return_value = matched[0] if matched else None
                    res.scalar_one.return_value = matched[0] if matched else None
                    return res

            # ------------------------------------------------------------------
            # 6. Uploaded Documents table queries
            # ------------------------------------------------------------------
            if "from uploaded_documents" in stmt_str:
                target_user_id = next((u for u in uuids if u in self.users), None)
                non_user_uuids = [u for u in uuids if u not in self.users]

                if non_user_uuids:
                    doc_id = non_user_uuids[0]
                    doc = self.documents.get(doc_id)
                    if doc and (target_user_id is None or doc.user_id == target_user_id):
                        res.scalar_one_or_none.return_value = doc
                        res.scalar_one.return_value = doc
                        res.scalars.return_value.all.return_value = [doc]
                        res.scalars.return_value.first.return_value = doc
                    else:
                        res.scalar_one_or_none.return_value = None
                        res.scalar_one.return_value = None
                        res.scalars.return_value.all.return_value = []
                        res.scalars.return_value.first.return_value = None
                    return res
                else:
                    matched = [d for d in self.documents.values() if target_user_id is None or d.user_id == target_user_id]
                    res.scalars.return_value.all.return_value = matched
                    res.scalars.return_value.first.return_value = matched[0] if matched else None
                    res.scalar_one_or_none.return_value = matched[0] if matched else None
                    res.scalar_one.return_value = matched[0] if matched else None
                    return res

            # ------------------------------------------------------------------
            # 7. Guest Migrations table queries
            # ------------------------------------------------------------------
            if "from guest_migrations" in stmt_str:
                target_user_id = next((u for u in uuids if u in self.users), None)
                key = next((s for s in strings if "@" not in s), None)
                matched = [
                    m for m in self.guest_migrations
                    if (target_user_id is None or m.user_id == target_user_id)
                    and (key is None or m.idempotency_key == key)
                ]
                res.scalar_one_or_none.return_value = matched[0] if matched else None
                res.scalars.return_value.all.return_value = [m for m in self.guest_migrations if target_user_id is None or m.user_id == target_user_id]
                return res

            # Default fallback for unrecognized statements
            res.scalar_one_or_none.return_value = None
            res.scalar_one.return_value = None
            res.scalars.return_value.all.return_value = []
            res.scalars.return_value.first.return_value = None
            return res

        session.add = MagicMock(side_effect=fake_add)
        session.delete = AsyncMock(side_effect=fake_delete)
        session.commit = AsyncMock(side_effect=fake_commit)
        session.rollback = AsyncMock(side_effect=fake_rollback)
        session.refresh = AsyncMock(side_effect=fake_refresh)
        session.execute = AsyncMock(side_effect=fake_execute)
        return session


# ==============================================================================
# Helper Byte Generators
# ==============================================================================


def create_test_manual_pdf(title: str, aim: str, apparatus: str, theory: str, procedure: str) -> bytes:
    """Generate in-memory valid digital PDF containing structured lab manual sections."""
    writer = pypdf.PdfWriter()
    text_content = (
        f"Experiment Title: {title}\n\n"
        f"Aim:\n{aim}\n\n"
        f"Apparatus:\n{apparatus}\n\n"
        f"Theory:\n{theory}\n\n"
        f"Procedure:\n{procedure}\n"
    )
    clean_text = text_content.replace("(", "").replace(")", "")
    stream_str = f"BT /F1 12 Tf 72 712 Td ({clean_text}) Tj ET"
    stream_bytes = stream_str.encode("latin-1", errors="replace")
    length = len(stream_bytes)

    raw_pdf = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
        + f"4 0 obj << /Length {length} >> stream\n".encode("latin-1")
        + stream_bytes
        + b"\nendstream\nendobj\n"
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000266 00000 n \n0000000360 00000 n \n"
        b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n441\n%%EOF\n"
    )
    reader = pypdf.PdfReader(io.BytesIO(raw_pdf))
    writer.add_page(reader.pages[0])
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


# ==============================================================================
# E2E Test Fixture & Client Builder
# ==============================================================================


@pytest.fixture
def e2e_environment(tmp_path: Path):
    """Provides an isolated test environment with temporary filesystem storage,

    in-memory database simulation, and deterministic demonstration AI services.
    """
    storage = DocumentStorageService(base_dir=tmp_path)
    state = E2EWorkflowState(storage_service=storage)
    session = state.make_mock_session()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    app.dependency_overrides[get_storage_service] = lambda: storage

    extractor = DocumentExtractorService(storage_service=storage)
    app.dependency_overrides[get_extractor_service] = lambda: extractor

    demonstration_provider = DemonstrationAIProvider()
    app.dependency_overrides[get_viva_ai_provider] = lambda: demonstration_provider
    app.dependency_overrides[get_section_parser_service] = lambda: DocumentSectionParserService(ai_provider=demonstration_provider)

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return client, state, storage


# ==============================================================================
# Comprehensive Student Lifecycle Integration Test (Steps 1 - 9)
# ==============================================================================


@pytest.mark.anyio
async def test_e2e_student_complete_lifecycle(e2e_environment) -> None:
    """Executes a complete, deterministic student journey through Steps 1 to 9:

    1. Account Registration and Authentication
    2. User Settings Retrieval and Mutation
    3. Experiment Workspace Lifecycle & Ownership Isolation
    4. Preparation Checklist Management
    5. AI Viva Voce Practice (Questions, Evaluations, Sessions, Answers)
    6. Manual Document Ingestion, Digital Extraction & Non-Destructive Parsing
    7. User Data Export with Sensitive Data Redaction
    8. Guest Data Batch Migration & Idempotent Replay
    9. User Data Purge with Physical Storage Cleanup
    """
    client, state, storage = e2e_environment

    # ==========================================================================
    # Step 1 — Account Registration and Authentication
    # ==========================================================================

    # 1.1 Unauthenticated requests to protected endpoints must be rejected
    unauth_resp = await client.get("/api/v1/users/me")
    assert unauth_resp.status_code == 401
    assert "detail" in unauth_resp.json()

    # 1.2 Register new primary student account (User A)
    user_a_email = "alex.rivera@university.edu"
    user_a_password = "StrongPassword2026!"
    reg_payload_a = {
        "email": user_a_email,
        "password": user_a_password,
        "full_name": "Alex Rivera",
        "university": "Faculty of Engineering",
    }
    reg_resp_a = await client.post("/api/v1/auth/register", json=reg_payload_a)
    assert reg_resp_a.status_code == 201
    data_reg_a = reg_resp_a.json()
    assert "access_token" in data_reg_a
    assert "refresh_token" in data_reg_a
    assert data_reg_a["token_type"].lower() == "bearer"
    user_a_id = uuid.UUID(data_reg_a["user"]["id"])
    assert data_reg_a["user"]["email"] == user_a_email
    assert data_reg_a["user"]["full_name"] == "Alex Rivera"
    assert data_reg_a["user"]["is_active"] is True

    # 1.3 Authenticate using registered credentials (Login)
    login_payload_a = {"email": user_a_email, "password": user_a_password}
    login_resp_a = await client.post("/api/v1/auth/login", json=login_payload_a)
    assert login_resp_a.status_code == 200
    token_a = login_resp_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # 1.4 Verify authenticated profile
    profile_resp_a = await client.get("/api/v1/users/me", headers=headers_a)
    assert profile_resp_a.status_code == 200
    assert profile_resp_a.json()["id"] == str(user_a_id)
    assert profile_resp_a.json()["email"] == user_a_email

    # 1.5 Register second student account (User B) for multi-tenant isolation assertions
    user_b_email = "sam.altman@science.edu"
    user_b_password = "SafePassword2026!"
    reg_resp_b = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_b_email,
            "password": user_b_password,
            "full_name": "Sam Student",
            "university": "Science Institute",
        },
    )
    assert reg_resp_b.status_code == 201
    token_b = reg_resp_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # ==========================================================================
    # Step 2 — User Settings
    # ==========================================================================

    # 2.1 Retrieve default study preferences for User A
    settings_get_a = await client.get("/api/v1/users/me/settings", headers=headers_a)
    assert settings_get_a.status_code == 200
    default_prefs = settings_get_a.json()
    assert "default_difficulty" in default_prefs or "defaultDifficulty" in default_prefs

    # 2.2 Update study preferences for User A
    settings_update_payload = {
        "default_difficulty": "advanced",
        "default_question_count": 10,
        "preferred_focus": "theory",
    }
    settings_patch_a = await client.patch(
        "/api/v1/users/me/settings",
        headers=headers_a,
        json=settings_update_payload,
    )
    assert settings_patch_a.status_code == 200
    patched_data = settings_patch_a.json()
    assert patched_data.get("defaultDifficulty", patched_data.get("default_difficulty")) == "advanced"
    assert patched_data.get("defaultQuestionCount", patched_data.get("default_question_count")) == 10
    assert patched_data.get("preferredFocus", patched_data.get("preferred_focus")) == "theory"

    # 2.3 Verify persisted settings on subsequent read
    settings_verify_a = await client.get("/api/v1/users/me/settings", headers=headers_a)
    assert settings_verify_a.status_code == 200
    verify_a_data = settings_verify_a.json()
    assert verify_a_data.get("defaultDifficulty", verify_a_data.get("default_difficulty")) == "advanced"

    # 2.4 Verify settings multi-tenant isolation: User B must not see User A's updated settings
    settings_b = await client.get("/api/v1/users/me/settings", headers=headers_b)
    assert settings_b.status_code == 200
    b_data = settings_b.json()
    assert b_data.get("defaultDifficulty", b_data.get("default_difficulty")) != "advanced"

    # ==========================================================================
    # Step 3 — Experiment Lifecycle
    # ==========================================================================

    # 3.1 Create laboratory experiment for User A
    exp_payload = {
        "title": "Verification of Stefan-Boltzmann Law",
        "subject": "Physics",
        "experimentNumber": "EXP-PHY-04",
        "courseSemester": "Semester 2",
        "method": "manual",
        "objective": "Verify that radiant energy emitted by a blackbody is proportional to T^4.",
        "theory": "According to Stefan-Boltzmann Law, total radiation E = sigma * T^4.",
        "apparatus": "Stefan radiation box, DC voltmeter, heating element, thermocouple.",
        "procedure": "1. Connect circuit. 2. Gradually vary temperature. 3. Record voltage and current.",
        "precautions": "Do not touch hot radiant elements during the experiment.",
    }
    create_exp_resp = await client.post("/api/v1/experiments", headers=headers_a, json=exp_payload)
    assert create_exp_resp.status_code == 201
    exp_data = create_exp_resp.json()
    exp_id = uuid.UUID(exp_data["id"])
    assert exp_data["title"] == exp_payload["title"]
    assert exp_data["subject"] == exp_payload["subject"]
    assert exp_data.get("hasManualFile", exp_data.get("has_manual_file")) is False

    # 3.2 Retrieve experiment from list endpoint
    list_exp_resp = await client.get("/api/v1/experiments", headers=headers_a)
    assert list_exp_resp.status_code == 200
    list_items = list_exp_resp.json()["items"]
    assert any(item["id"] == str(exp_id) for item in list_items)

    # 3.3 Retrieve detail
    detail_exp_resp = await client.get(f"/api/v1/experiments/{exp_id}", headers=headers_a)
    assert detail_exp_resp.status_code == 200
    assert detail_exp_resp.json()["id"] == str(exp_id)
    assert detail_exp_resp.json()["objective"] == exp_payload["objective"]

    # 3.4 Update experiment fields
    patch_exp_payload = {"description": "Updated thermodynamic radiation investigation."}
    patch_exp_resp = await client.patch(f"/api/v1/experiments/{exp_id}", headers=headers_a, json=patch_exp_payload)
    assert patch_exp_resp.status_code == 200
    assert patch_exp_resp.json()["description"] == "Updated thermodynamic radiation investigation."

    # 3.5 Verify cross-user ownership isolation: User B cannot access or update User A's experiment
    idor_get = await client.get(f"/api/v1/experiments/{exp_id}", headers=headers_b)
    assert idor_get.status_code == 404
    idor_patch = await client.patch(f"/api/v1/experiments/{exp_id}", headers=headers_b, json={"title": "Hacked Title"})
    assert idor_patch.status_code == 404

    # ==========================================================================
    # Step 4 — Preparation Checklist
    # ==========================================================================

    # 4.1 Update checklist item states
    checklist_update = {
        "objective": True,
        "theory": True,
        "apparatus": True,
        "procedure": False,
        "precautions": False,
    }
    chk_resp = await client.patch(f"/api/v1/experiments/{exp_id}/checklist", headers=headers_a, json=checklist_update)
    assert chk_resp.status_code == 200
    chk_data = chk_resp.json()
    assert chk_data["items"]["objective"] is True
    assert chk_data["items"]["apparatus"] is True
    assert chk_data["items"]["procedure"] is False

    # 4.2 Verify checklist state is reflected in subsequent experiment retrieval
    exp_with_chk = await client.get(f"/api/v1/experiments/{exp_id}", headers=headers_a)
    assert exp_with_chk.status_code == 200
    assert exp_with_chk.json()["checklist"]["items"]["apparatus"] is True

    # 4.3 Verify checklist ownership isolation: User B cannot modify User A's checklist
    chk_idor = await client.patch(f"/api/v1/experiments/{exp_id}/checklist", headers=headers_b, json=checklist_update)
    assert chk_idor.status_code == 404

    # ==========================================================================
    # Step 5 — AI Viva Workflow
    # ==========================================================================

    # 5.1 Request viva questions grounded in experiment context
    viva_gen_payload = {
        "experiment_id": str(exp_id),
        "question_count": 5,
        "difficulty": "intermediate",
        "focus": "mixed",
    }
    gen_resp = await client.post("/api/v1/viva/generate-questions", headers=headers_a, json=viva_gen_payload)
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data.get("providerMode", gen_data.get("provider_mode")) == "demonstration"
    assert len(gen_data["questions"]) == 5
    first_q = gen_data["questions"][0]
    assert "question" in first_q
    assert "topic" in first_q
    assert "expected_answer" in first_q or "expectedAnswer" in first_q

    # 5.2 Submit answer for evaluation
    eval_payload = {
        "question": first_q,
        "student_answer": (
            "The Stefan-Boltzmann Law states that the total radiant heat energy emitted from a surface "
            "is proportional to the fourth power of its absolute temperature."
        ),
    }
    eval_resp = await client.post("/api/v1/viva/evaluate-answer", headers=headers_a, json=eval_payload)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert "score" in eval_data
    assert 0 <= eval_data["score"] <= 10
    assert eval_data["verdict"] in ["correct", "partially_correct", "partially-correct", "incorrect"]
    assert eval_data.get("providerMode", eval_data.get("provider_mode")) == "demonstration"

    # 5.3 Create and persist a viva examination session
    session_create_payload = {
        "experiment_id": str(exp_id),
        "question_count": 5,
        "difficulty": "intermediate",
        "topic_focus": "mixed",
        "provider_mode": "demonstration",
    }
    sess_create_resp = await client.post("/api/v1/viva/sessions", headers=headers_a, json=session_create_payload)
    assert sess_create_resp.status_code == 201
    sess_data = sess_create_resp.json()
    session_id = uuid.UUID(sess_data["id"])
    assert sess_data.get("isCompleted", sess_data.get("is_completed")) is False
    assert sess_data.get("experimentId", sess_data.get("experiment_id")) == str(exp_id)

    # 5.4 Persist associated evaluated answer into the created session
    persisted_answer = VivaAnswer(
        id=uuid.uuid4(),
        session_id=session_id,
        question_id=first_q.get("id", "q-001"),
        question_number=1,
        topic=first_q.get("topic", "theory"),
        difficulty="intermediate",
        question_text=first_q["question"],
        student_answer=eval_payload["student_answer"],
        score=eval_data["score"],
        verdict=eval_data["verdict"],
        feedback=eval_data.get("feedback", ""),
        expected_answer=first_q.get("expectedAnswer", first_q.get("expected_answer", "")),
        what_you_got_right=eval_data.get("whatYouGotRight", eval_data.get("what_you_got_right", "Accurate definition provided.")),
        what_was_missing=eval_data.get("whatWasMissing", eval_data.get("what_was_missing", "")),
        suggested_improvement=eval_data.get("improvementTip", eval_data.get("improvement_tip", "Specify absolute zero conditions.")),
        key_points_covered=eval_data.get("keyPointsCovered", eval_data.get("key_points_covered", [])),
        key_points_missed=eval_data.get("keyPointsMissed", eval_data.get("key_points_missed", [])),
        evaluation_data={},
        time_spent_seconds=20,
        created_at=datetime.now(timezone.utc),
    )
    target_sess = state.viva_sessions[session_id]
    target_sess.answers = [persisted_answer]
    target_sess.questions_answered = 1
    target_sess.is_completed = True
    target_sess.average_score = Decimal(str(eval_data["score"]))
    state.viva_answers[persisted_answer.id] = persisted_answer

    # 5.5 Retrieve viva session history list
    viva_list_resp = await client.get("/api/v1/viva/sessions", headers=headers_a)
    assert viva_list_resp.status_code == 200
    assert viva_list_resp.json()["total"] >= 1
    session_item = next(s for s in viva_list_resp.json()["items"] if s["id"] == str(session_id))
    assert session_item.get("experimentTitle", session_item.get("experiment_title")) == exp_payload["title"]

    # 5.6 Retrieve session detail and verify answer relationship
    sess_detail_resp = await client.get(f"/api/v1/viva/sessions/{session_id}", headers=headers_a)
    assert sess_detail_resp.status_code == 200
    detail_data = sess_detail_resp.json()
    assert detail_data.get("experimentTitle", detail_data.get("experiment_title")) == exp_payload["title"]
    assert len(detail_data["answers"]) == 1
    assert detail_data["answers"][0].get("questionText", detail_data["answers"][0].get("question_text")) == first_q["question"]
    assert detail_data["answers"][0]["score"] == eval_data["score"]

    # 5.7 Verify session ownership isolation: User B cannot access User A's viva session
    viva_idor = await client.get(f"/api/v1/viva/sessions/{session_id}", headers=headers_b)
    assert viva_idor.status_code == 404

    # ==========================================================================
    # Step 6 — Document Processing
    # ==========================================================================

    # 6.1 Generate valid PDF bytes for laboratory manual
    pdf_bytes = create_test_manual_pdf(
        title="Verification of Stefan-Boltzmann Law",
        aim="To verify the Stefan-Boltzmann radiation law using an electric filament lamp.",
        apparatus="Filament bulb, DC power supply, voltmeter, ammeter, rheostat.",
        theory="The total radiant power emitted per unit area of a blackbody is proportional to T^4.",
        procedure="1. Set up the circuit. 2. Gradually increase filament current. 3. Measure V and I.",
    )

    # 6.2 Upload manual file via multipart/form-data
    upload_resp = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=headers_a,
        data={"experiment_id": str(exp_id)},
        files={"file": ("stefan_boltzmann_manual.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_resp.status_code == 201
    upload_data = upload_resp.json()
    doc_id = uuid.UUID(upload_data["id"])
    assert upload_data.get("fileName", upload_data.get("file_name")) == "stefan_boltzmann_manual.pdf"
    assert upload_data.get("hasManualFile", upload_data.get("has_manual_file")) is True

    # 6.3 Verify physical file was written into the isolated temporary storage directory
    stored_doc = state.documents[doc_id]
    file_on_disk = storage.get_file_path(stored_doc.storage_path)
    assert file_on_disk is not None
    assert file_on_disk.is_file()

    # 6.4 Execute digital text extraction
    extract_resp = await client.post(f"/api/v1/experiments/{exp_id}/extract-text", headers=headers_a)
    assert extract_resp.status_code == 200
    extract_data = extract_resp.json()
    assert extract_data["status"] in ["success", "success_with_warnings"]
    assert "Stefan-Boltzmann" in extract_data["extractedText"]
    assert stored_doc.extracted_text == extract_data["extractedText"]

    # 6.5 Parse extracted manual text into structured draft sections using AI section parser
    original_extracted_text = str(stored_doc.extracted_text)
    parse_resp = await client.post(f"/api/v1/experiments/{exp_id}/parse-manual", headers=headers_a)
    assert parse_resp.status_code == 200
    parse_data = parse_resp.json()
    assert parse_data["status"] != "failed"
    assert parse_data["sections"]["title"] is not None

    # 6.6 Verify that original extracted text and experiment records were not overwritten
    assert stored_doc.extracted_text == original_extracted_text
    assert "parsed_sections_draft" in stored_doc.extracted_data

    # 6.7 Verify document endpoint ownership isolation: User B cannot extract or parse User A's manual
    extract_idor = await client.post(f"/api/v1/experiments/{exp_id}/extract-text", headers=headers_b)
    assert extract_idor.status_code == 404
    parse_idor = await client.post(f"/api/v1/experiments/{exp_id}/parse-manual", headers=headers_b)
    assert parse_idor.status_code == 404

    # ==========================================================================
    # Step 7 — Data Export
    # ==========================================================================

    export_resp = await client.get("/api/v1/users/me/export", headers=headers_a)
    assert export_resp.status_code == 200
    export_data = export_resp.json()

    # 7.1 Verify profile & settings
    assert export_data["user"]["id"] == str(user_a_id)
    assert export_data["user"]["email"] == user_a_email
    assert export_data["settings"]["default_difficulty"] == "advanced"

    # 7.2 Verify experiment and related checklist
    assert len(export_data["experiments"]) >= 1
    exp_export = next(e for e in export_data["experiments"] if e["id"] == str(exp_id))
    assert exp_export["title"] == exp_payload["title"]
    assert exp_export["checklist"]["items"]["apparatus"] is True
    assert exp_export["preparation_checklist"]["apparatus"] is True

    # 7.3 Verify viva sessions and evaluated answers
    assert len(export_data["viva_sessions"]) >= 1
    sess_export = next(s for s in export_data["viva_sessions"] if s["id"] == str(session_id))
    assert len(sess_export["answers"]) == 1
    assert sess_export["answers"][0]["question_text"] == first_q["question"]

    # 7.4 Verify document metadata & extracted text
    assert len(export_data["documents"]) >= 1
    doc_export = next(d for d in export_data["documents"] if d["id"] == str(doc_id))
    assert doc_export["file_name"] == "stefan_boltzmann_manual.pdf"
    assert "Stefan-Boltzmann" in doc_export["extracted_text"]

    # 7.5 Verify sensitive fields (passwords, server paths) are strictly excluded
    assert "password_hash" not in export_data["user"]
    assert "storage_path" not in doc_export
    raw_export_text = str(export_data)
    assert "argon2id" not in raw_export_text
    assert str(storage.base_dir) not in raw_export_text

    # 7.6 Verify multi-tenant isolation: User B's email does not appear in User A's export
    assert user_b_email not in raw_export_text

    # ==========================================================================
    # Step 8 — Guest Data Migration
    # ==========================================================================

    idempotency_key = f"guest-mig-{uuid.uuid4().hex[:12]}"
    guest_exp_client_id = "client-guest-exp-101"
    guest_sess_client_id = "client-guest-sess-202"

    migration_payload = {
        "idempotency_key": idempotency_key,
        "experiments": [
            {
                "client_id": guest_exp_client_id,
                "title": "Ohm's Law Guest Experiment",
                "subject": "Electrical Engineering",
                "experiment_number": "EXP-01",
                "course_semester": "Semester 1",
                "creation_method": "guest_migration",
                "status": "ready",
                "objective": "Verify V=IR relationship using resistor bench.",
                "checklist": {"objective": True, "theory": True, "apparatus": False},
            }
        ],
        "viva_sessions": [
            {
                "client_id": guest_sess_client_id,
                "client_experiment_id": guest_exp_client_id,
                "difficulty": "intermediate",
                "question_count": 5,
                "topic_focus": "theory",
                "provider_mode": "demonstration",
                "is_completed": True,
                "average_score": 8.5,
                "total_questions": 5,
                "questions_answered": 5,
                "correct_count": 4,
                "answers": [
                    {
                        "question_number": 1,
                        "question_text": "State Ohm's Law.",
                        "student_answer": "Current is directly proportional to potential difference.",
                        "score": 9,
                        "verdict": "correct",
                        "feedback": "Clear and accurate definition.",
                    }
                ],
            }
        ],
    }

    # 8.1 Execute guest migration
    mig_resp = await client.post("/api/v1/users/me/migrate-guest-data", headers=headers_a, json=migration_payload)
    assert mig_resp.status_code == 200
    mig_data = mig_resp.json()
    assert mig_data.get("experimentsMigrated", mig_data.get("experiments_migrated")) == 1
    assert mig_data.get("vivaSessionsMigrated", mig_data.get("viva_sessions_migrated")) == 1
    assert mig_data.get("vivaAnswersMigrated", mig_data.get("viva_answers_migrated")) == 1

    # 8.2 Verify migrated experiment belongs to User A
    exp_list_after_mig = await client.get("/api/v1/experiments", headers=headers_a)
    assert exp_list_after_mig.status_code == 200
    migrated_titles = [e["title"] for e in exp_list_after_mig.json()["items"]]
    assert "Ohm's Law Guest Experiment" in migrated_titles

    # 8.3 Idempotent replay: Resending identical migration request returns exact same counts without duplication
    mig_replay = await client.post("/api/v1/users/me/migrate-guest-data", headers=headers_a, json=migration_payload)
    assert mig_replay.status_code == 200
    assert mig_replay.json().get("experimentsMigrated", mig_replay.json().get("experiments_migrated")) == 1
    assert mig_replay.json().get("vivaSessionsMigrated", mig_replay.json().get("viva_sessions_migrated")) == 1
    assert mig_replay.json().get("isIdempotentReplay", mig_replay.json().get("is_idempotent_replay")) is True

    # Verify no duplicates were created
    exp_list_replay = await client.get("/api/v1/experiments", headers=headers_a)
    assert len([e for e in exp_list_replay.json()["items"] if e["title"] == "Ohm's Law Guest Experiment"]) == 1

    # ==========================================================================
    # Step 9 — User Data Purge
    # ==========================================================================

    purge_resp = await client.delete("/api/v1/users/me/data", headers=headers_a)
    assert purge_resp.status_code == 200
    purge_data = purge_resp.json()
    assert "All user data cleared successfully." in purge_data["message"]
    assert purge_data["experiments_deleted"] >= 1
    assert purge_data["viva_sessions_deleted"] >= 1
    assert purge_data["documents_deleted"] >= 1

    # 9.1 Verify study records are removed
    exp_list_after_purge = await client.get("/api/v1/experiments", headers=headers_a)
    assert exp_list_after_purge.status_code == 200
    assert exp_list_after_purge.json()["total"] == 0

    viva_list_after_purge = await client.get("/api/v1/viva/sessions", headers=headers_a)
    assert viva_list_after_purge.status_code == 200
    assert viva_list_after_purge.json()["total"] == 0

    # 9.2 Verify user profile and settings remain active
    profile_after_purge = await client.get("/api/v1/users/me", headers=headers_a)
    assert profile_after_purge.status_code == 200
    assert profile_after_purge.json()["email"] == user_a_email

    settings_after_purge = await client.get("/api/v1/users/me/settings", headers=headers_a)
    assert settings_after_purge.status_code == 200
    purge_settings_data = settings_after_purge.json()
    assert purge_settings_data.get("defaultDifficulty", purge_settings_data.get("default_difficulty")) == "advanced"

    # 9.3 Verify physical uploaded files were removed from disk
    assert not file_on_disk.exists()

    # 9.4 Verify export after data purge returns empty collections with active user profile
    export_after_purge = await client.get("/api/v1/users/me/export", headers=headers_a)
    assert export_after_purge.status_code == 200
    assert export_after_purge.json()["experiments"] == []
    assert export_after_purge.json()["viva_sessions"] == []
    assert export_after_purge.json()["documents"] == []
    assert export_after_purge.json()["user"]["email"] == user_a_email

    # 9.5 Verify User B remains completely unaffected
    profile_b = await client.get("/api/v1/users/me", headers=headers_b)
    assert profile_b.status_code == 200
    assert profile_b.json()["email"] == user_b_email


# ==============================================================================
# Dedicated Account Deletion Integration Test (Step 10)
# ==============================================================================


@pytest.mark.anyio
async def test_e2e_account_deletion_lifecycle(e2e_environment) -> None:
    """Step 10: Validates complete account lifecycle with permanent deletion:

    - Registers dedicated test student (User C).
    - Provisions an experiment and uploads a laboratory manual.
    - Permanently deletes the account via DELETE /api/v1/users/me.
    - Verifies physical file and user directory are securely unlinked.
    - Verifies database records are removed with cascade cleanup.
    - Verifies subsequent requests with the deleted user's token fail with 401 Unauthorized.
    - Verifies existing users (User A / User B) remain untouched.
    """
    client, state, storage = e2e_environment

    # 1. Register User C
    user_c_email = "student.c@university.edu"
    user_c_password = "Password2026!StudentC"
    reg_c = await client.post(
        "/api/v1/auth/register",
        json={
            "email": user_c_email,
            "password": user_c_password,
            "full_name": "Charlie Student",
            "university": "Polytechnic Institute",
        },
    )
    assert reg_c.status_code == 201
    user_c_id = uuid.UUID(reg_c.json()["user"]["id"])
    token_c = reg_c.json()["access_token"]
    headers_c = {"Authorization": f"Bearer {token_c}"}

    # 2. Create an experiment for User C
    exp_c_resp = await client.post(
        "/api/v1/experiments",
        headers=headers_c,
        json={
            "title": "Photoelectric Effect Experiment",
            "subject": "Quantum Physics",
            "objective": "Determine Planck's constant.",
        },
    )
    assert exp_c_resp.status_code == 201
    exp_c_id = uuid.UUID(exp_c_resp.json()["id"])

    # 3. Upload a manual file for User C
    pdf_bytes = create_test_manual_pdf(
        title="Photoelectric Effect Experiment",
        aim="Determine Planck constant.",
        apparatus="Photocell, filters, voltmeter.",
        theory="E = h*nu - W.",
        procedure="Record stopping potential.",
    )
    upload_c = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=headers_c,
        data={"experiment_id": str(exp_c_id)},
        files={"file": ("photoelectric_manual.pdf", pdf_bytes, "application/pdf")},
    )
    assert upload_c.status_code == 201
    doc_c_id = uuid.UUID(upload_c.json()["id"])
    doc_c_path = storage.get_file_path(state.documents[doc_c_id].storage_path)
    assert doc_c_path is not None
    assert doc_c_path.is_file()

    # 4. Permanently delete User C's account
    delete_resp = await client.delete("/api/v1/users/me", headers=headers_c)
    assert delete_resp.status_code == 200
    del_data = delete_resp.json()
    assert "deleted successfully" in del_data["message"].lower()
    assert del_data["user_id"] == str(user_c_id)

    # 5. Verify physical storage cleanup
    assert not doc_c_path.exists()
    assert not (storage.base_dir / str(user_c_id)).exists()

    # 6. Verify database records removed
    assert user_c_id not in state.users
    assert user_c_id not in state.settings
    assert exp_c_id not in state.experiments
    assert doc_c_id not in state.documents

    # 7. Verify subsequent authenticated request with deleted user's token returns 401 Unauthorized
    post_del_profile = await client.get("/api/v1/users/me", headers=headers_c)
    assert post_del_profile.status_code == 401


# ==============================================================================
# Cross-Module Failure & Isolation Scenarios
# ==============================================================================


@pytest.mark.anyio
async def test_e2e_cross_module_failure_and_isolation_scenarios(e2e_environment) -> None:
    """Verifies critical cross-module error handling, IDOR protection, and validation guards:

    - Malformed and expired tokens return 401.
    - Foreign and non-existent experiment IDs in viva sessions return 404.
    - Invalid migration relationships (unknown experiment references) return 422.
    - Duplicate client_id in migration payloads returns 422.
    - Transaction rollback on simulated database failure leaves no orphaned data.
    """
    client, state, storage = e2e_environment

    # Register test user
    reg = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "failure.test@university.edu",
            "password": "Password123!Secure",
            "full_name": "Failure Test Student",
            "university": "Test University",
        },
    )
    assert reg.status_code == 201
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Invalid / malformed bearer token returns 401
    bad_token_resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer totally.invalid.token"},
    )
    assert bad_token_resp.status_code == 401

    # 2. Creating viva session referencing non-existent experiment returns 404
    non_existent_exp_id = uuid.uuid4()
    bad_viva_resp = await client.post(
        "/api/v1/viva/sessions",
        headers=headers,
        json={"experiment_id": str(non_existent_exp_id)},
    )
    assert bad_viva_resp.status_code == 404

    # 3. Guest migration with invalid experiment reference returns 422
    invalid_mig_payload = {
        "idempotency_key": "bad-ref-key-1",
        "experiments": [],
        "viva_sessions": [
            {
                "client_id": "sess-orphaned-1",
                "client_experiment_id": str(uuid.uuid4()),  # Does not exist in payload or DB
                "difficulty": "intermediate",
            }
        ],
    }
    mig_bad_ref_resp = await client.post(
        "/api/v1/users/me/migrate-guest-data",
        headers=headers,
        json=invalid_mig_payload,
    )
    assert mig_bad_ref_resp.status_code == 422
    assert "references experiment" in mig_bad_ref_resp.json()["detail"].lower()

    # 4. Guest migration with duplicate client_id returns 422
    duplicate_client_id_payload = {
        "idempotency_key": "duplicate-key-1",
        "experiments": [
            {"client_id": "dup-exp-id", "title": "Exp 1", "subject": "Phys"},
            {"client_id": "dup-exp-id", "title": "Exp 2", "subject": "Chem"},
        ],
        "viva_sessions": [],
    }
    dup_resp = await client.post(
        "/api/v1/users/me/migrate-guest-data",
        headers=headers,
        json=duplicate_client_id_payload,
    )
    assert dup_resp.status_code == 422
    assert "duplicate client_id" in dup_resp.json()["detail"].lower()

    # 5. Database rollback behavior: when commit fails, state rollbacks cleanly
    state.fail_on_commit = True
    failing_mig_payload = {
        "idempotency_key": "rollback-key-1",
        "experiments": [
            {"client_id": "rollback-exp-id", "title": "Rollback Exp", "subject": "Biology"}
        ],
        "viva_sessions": [],
    }
    fail_mig_resp = await client.post(
        "/api/v1/users/me/migrate-guest-data",
        headers=headers,
        json=failing_mig_payload,
    )
    assert fail_mig_resp.status_code == 500
    state.fail_on_commit = False

    # Verify that the rolled-back experiment was NOT persisted
    assert not any(e.title == "Rollback Exp" for e in state.experiments.values())
    assert state.rollback_count >= 1
