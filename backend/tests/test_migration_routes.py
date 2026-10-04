"""Unit and Integration Tests for Guest Data Batch Migration Endpoint.

Verifies POST /api/v1/users/me/migrate-guest-data:
- Successful migration of experiments, preparation checklists, viva sessions, and answers.
- Relationship preservation (client experiment ID mapped to newly minted server UUID).
- Linking viva session to an existing user-owned experiment.
- Correct authenticated user ownership context and rejection of cross-user ownership injection.
- Complete transaction atomicity and rollback on database error.
- Idempotency via client-generated idempotency_key (subsequent replays return original counts).
- Concurrent duplicate migration safety (IntegrityError caught and resolved as replay).
- Unauthenticated requests returning 401 Unauthorized.
- Empty migration payload handling.
- Validation failures: duplicate client_id, malformed input, missing parent experiment.
- Request size and record count limits.
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.modules.auth.models import User
from app.modules.experiments.models import Experiment, PreparationChecklist
from app.modules.users.models import GuestMigration, UserSettings
from app.modules.viva.models import VivaAnswer, VivaSession


# ==============================================================================
# Fixtures & Test State Store
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
        email="alice@student.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashalice",
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
        email="bob@student.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashbob",
        full_name="Bob Student",
        university="Science Institute",
        is_active=True,
        auth_provider="local",
        created_at=now,
        updated_at=now,
    )


class MigrationTestState:
    """Stateful mock store for migration tests simulating PostgreSQL tables."""

    def __init__(
        self,
        users: list[User],
        experiments: list[Experiment],
        viva_sessions: list[VivaSession],
        guest_migrations: list[GuestMigration],
    ) -> None:
        self.users: dict[uuid.UUID, User] = {u.id: u for u in users}
        self.experiments: dict[uuid.UUID, Experiment] = {e.id: e for e in experiments}
        self.viva_sessions: dict[uuid.UUID, VivaSession] = {v.id: v for v in viva_sessions}
        self.guest_migrations: list[GuestMigration] = list(guest_migrations)
        self.added_instances: list[Any] = []
        self.commit_count = 0
        self.rollback_count = 0
        self.fail_on_commit = False
        self.fail_on_add = False
        self.simulate_concurrent_integrity_error = False

    def make_mock_session(self) -> AsyncMock:
        session = AsyncMock(spec=AsyncSession)

        def fake_add(instance: Any) -> None:
            if self.fail_on_add:
                raise OperationalError("Simulated write error", params=None, orig=Exception("disk error"))
            self.added_instances.append(instance)
            if isinstance(instance, Experiment):
                self.experiments[instance.id] = instance
            elif isinstance(instance, VivaSession):
                self.viva_sessions[instance.id] = instance
            elif isinstance(instance, GuestMigration):
                self.guest_migrations.append(instance)

        session.add = MagicMock(side_effect=fake_add)

        async def fake_commit() -> None:
            if self.fail_on_commit:
                raise OperationalError("Simulated commit error", params=None, orig=Exception("db disconnected"))
            if self.simulate_concurrent_integrity_error:
                # Simulate concurrent duplicate race condition
                raise IntegrityError(
                    "duplicate key value violates unique constraint uq_user_guest_migration_idempotency",
                    params=None,
                    orig=Exception("duplicate key"),
                )
            self.commit_count += 1

        session.commit = AsyncMock(side_effect=fake_commit)

        async def fake_rollback() -> None:
            self.rollback_count += 1
            # Remove any added instances during failed transaction
            for inst in self.added_instances:
                if isinstance(inst, Experiment):
                    self.experiments.pop(inst.id, None)
                elif isinstance(inst, VivaSession):
                    self.viva_sessions.pop(inst.id, None)
                elif isinstance(inst, GuestMigration):
                    if inst in self.guest_migrations:
                        self.guest_migrations.remove(inst)
            self.added_instances.clear()

        session.rollback = AsyncMock(side_effect=fake_rollback)

        async def fake_execute(statement, *args, **kwargs) -> MagicMock:
            stmt_str = str(statement).lower()
            res = MagicMock()

            # 1. users lookup (for get_current_active_user)
            if "from users" in stmt_str:
                target_uuid = None
                try:
                    compiled = statement.compile()
                    for val in compiled.params.values():
                        if isinstance(val, uuid.UUID):
                            target_uuid = val
                            break
                except Exception:
                    pass
                if target_uuid and target_uuid in self.users:
                    res.scalar_one_or_none.return_value = self.users[target_uuid]
                elif len(self.users) == 1:
                    res.scalar_one_or_none.return_value = list(self.users.values())[0]
                else:
                    res.scalar_one_or_none.return_value = None
                return res

            # 2. guest_migrations lookup
            if "from guest_migrations" in stmt_str:
                compiled = statement.compile()
                uid = None
                key = None
                for val in compiled.params.values():
                    if isinstance(val, uuid.UUID):
                        uid = val
                    elif isinstance(val, str):
                        key = val
                matched = [m for m in self.guest_migrations if (not uid or m.user_id == uid) and (not key or m.idempotency_key == key)]
                res.scalar_one_or_none.return_value = matched[0] if matched else None
                return res

            # 3. experiments lookup (for checking existing experiment existence)
            if "from experiments" in stmt_str:
                compiled = statement.compile()
                exp_id = None
                user_id = None
                for val in compiled.params.values():
                    if isinstance(val, uuid.UUID):
                        if val in self.experiments:
                            exp_id = val
                        elif val in self.users:
                            user_id = val
                exp = self.experiments.get(exp_id)
                if exp and (not user_id or exp.user_id == user_id):
                    res.scalar_one_or_none.return_value = exp.id
                else:
                    res.scalar_one_or_none.return_value = None
                return res

            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []
            return res

        session.execute = AsyncMock(side_effect=fake_execute)
        return session


@pytest.fixture
def test_state(user_a: User, user_b: User) -> MigrationTestState:
    return MigrationTestState(
        users=[user_a, user_b],
        experiments=[],
        viva_sessions=[],
        guest_migrations=[],
    )


@pytest.fixture
def auth_headers(user_a: User) -> dict[str, str]:
    token = create_access_token(user_a.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_b(user_b: User) -> dict[str, str]:
    token = create_access_token(user_b.id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def app_client(test_state: MigrationTestState) -> httpx.AsyncClient:
    app = create_app()

    async def override_get_db():
        yield test_state.make_mock_session()

    app.dependency_overrides[get_db] = override_get_db
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


# ==============================================================================
# Tests
# ==============================================================================


@pytest.mark.anyio
async def test_migrate_guest_data_successful_experiments_and_checklists(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    user_a_id: uuid.UUID,
    test_state: MigrationTestState,
):
    """Verify successful migration of experiments with checklists to authenticated account."""
    payload = {
        "idempotencyKey": "mig-exp-001",
        "experiments": [
            {
                "clientId": "guest-exp-1",
                "title": "Verification of Kirchhoff's Laws",
                "subject": "Basic Electrical Engineering",
                "experimentNumber": "EXP-01",
                "courseSemester": "Semester 1",
                "method": "manual",
                "status": "ready",
                "objective": "To verify KCL and KVL in a DC network.",
                "theory": "Algebraic sum of currents at a junction is zero.",
                "apparatus": "DC power supply, resistors, ammeter, voltmeter.",
                "procedure": "1. Connect circuit. 2. Measure voltages.",
                "observations": "Voltage readings table.",
                "calculations": "Calculated current sums.",
                "precautions": "Ensure zero power during wiring.",
                "preparationChecklist": {
                    "objective": True,
                    "theory": True,
                    "apparatus": False,
                    "procedure": True,
                    "precautions": False,
                },
                "createdAtTimestamp": 1728000000000,
            }
        ],
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["idempotencyKey"] == "mig-exp-001"
    assert data["isIdempotentReplay"] is False
    assert data["experimentsMigrated"] == 1
    assert data["vivaSessionsMigrated"] == 0
    assert data["vivaAnswersMigrated"] == 0

    # Verify database persistence and ownership
    assert len(test_state.experiments) == 1
    saved_exp = list(test_state.experiments.values())[0]
    assert saved_exp.user_id == user_a_id
    assert saved_exp.title == "Verification of Kirchhoff's Laws"
    assert saved_exp.subject == "Basic Electrical Engineering"
    assert saved_exp.checklist is not None
    assert saved_exp.checklist.items["objective"] is True
    assert saved_exp.checklist.items["apparatus"] is False
    assert test_state.commit_count == 1


@pytest.mark.anyio
async def test_migrate_guest_data_successful_viva_sessions_and_answers(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    user_a_id: uuid.UUID,
    test_state: MigrationTestState,
):
    """Verify successful migration of viva sessions with answers and evaluations."""
    payload = {
        "idempotencyKey": "mig-viva-001",
        "experiments": [
            {
                "clientId": "exp-local-10",
                "title": "Logic Gates Realization",
                "subject": "Digital Electronics",
            }
        ],
        "vivaSessions": [
            {
                "clientId": "sess-local-1",
                "clientExperimentId": "exp-local-10",
                "difficulty": "intermediate",
                "questionCount": 5,
                "topicFocus": "theory",
                "providerMode": "demonstration",
                "isCompleted": True,
                "averageScore": 8.5,
                "totalQuestions": 5,
                "questionsAnswered": 5,
                "correctCount": 4,
                "partiallyCorrectCount": 1,
                "incorrectCount": 0,
                "topicAnalysis": {
                    "theory": {"total": 3, "correct": 3, "averageScore": 9.0}
                },
                "weakTopics": ["precautions"],
                "strongTopics": ["theory"],
                "answers": [
                    {
                        "questionId": "q-1",
                        "questionNumber": 1,
                        "topic": "theory",
                        "difficulty": "intermediate",
                        "questionText": "What is a NAND gate?",
                        "studentAnswer": "A universal gate combining AND and NOT.",
                        "score": 9,
                        "verdict": "correct",
                        "feedback": "Clear and accurate definition.",
                        "expectedAnswer": "An inverted AND logic gate.",
                        "whatYouGotRight": "Correctly identified as universal.",
                        "timeSpentSeconds": 25,
                    }
                ],
            }
        ],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["experimentsMigrated"] == 1
    assert data["vivaSessionsMigrated"] == 1
    assert data["vivaAnswersMigrated"] == 1

    # Verify viva session linked to new experiment
    saved_exp = list(test_state.experiments.values())[0]
    saved_sess = list(test_state.viva_sessions.values())[0]
    assert saved_sess.user_id == user_a_id
    assert saved_sess.experiment_id == saved_exp.id
    assert len(saved_sess.answers) == 1
    assert saved_sess.answers[0].question_text == "What is a NAND gate?"
    assert saved_sess.answers[0].score == 9


@pytest.mark.anyio
async def test_migrate_guest_data_preserves_relationship_between_batch_records(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_state: MigrationTestState,
):
    """Verify viva session referencing batch experiment client_id maps correctly to server UUID."""
    payload = {
        "idempotencyKey": "mig-rel-001",
        "experiments": [
            {
                "clientId": "client-uuid-alpha",
                "title": "Alpha Experiment",
                "subject": "Physics",
            },
            {
                "clientId": "client-uuid-beta",
                "title": "Beta Experiment",
                "subject": "Chemistry",
            },
        ],
        "vivaSessions": [
            {
                "clientId": "sess-beta",
                "clientExperimentId": "client-uuid-beta",
                "questionCount": 5,
                "answers": [],
            }
        ],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert len(test_state.experiments) == 2
    assert len(test_state.viva_sessions) == 1

    beta_exp = [e for e in test_state.experiments.values() if e.title == "Beta Experiment"][0]
    viva_sess = list(test_state.viva_sessions.values())[0]
    assert viva_sess.experiment_id == beta_exp.id


@pytest.mark.anyio
async def test_migrate_guest_data_links_viva_session_to_existing_experiment(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    user_a_id: uuid.UUID,
    test_state: MigrationTestState,
):
    """Verify viva session can reference an already existing experiment owned by the user."""
    existing_exp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    existing_exp = Experiment(
        id=existing_exp_id,
        user_id=user_a_id,
        title="Pre-existing Lab Experiment",
        subject="Mechanical",
        creation_method="manual",
        status="ready",
        created_at=now,
        updated_at=now,
    )
    test_state.experiments[existing_exp_id] = existing_exp

    payload = {
        "idempotencyKey": "mig-link-existing-001",
        "experiments": [],
        "vivaSessions": [
            {
                "clientId": "sess-standalone",
                "clientExperimentId": str(existing_exp_id),
                "questionCount": 5,
                "answers": [],
            }
        ],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["experimentsMigrated"] == 0
    assert data["vivaSessionsMigrated"] == 1

    saved_sess = list(test_state.viva_sessions.values())[0]
    assert saved_sess.experiment_id == existing_exp_id


@pytest.mark.anyio
async def test_migrate_guest_data_rejects_unknown_experiment_relationship(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify referencing an unknown or non-existent experiment ID returns 422 Unprocessable Entity."""
    non_existent_id = str(uuid.uuid4())
    payload = {
        "idempotencyKey": "mig-bad-rel-001",
        "experiments": [],
        "vivaSessions": [
            {
                "clientId": "sess-orphaned",
                "clientExperimentId": non_existent_id,
                "answers": [],
            }
        ],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "does not exist or does not belong" in response.json()["detail"]


@pytest.mark.anyio
async def test_migrate_guest_data_rejects_cross_user_experiment_relationship(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    user_b_id: uuid.UUID,
    test_state: MigrationTestState,
):
    """Verify attempting to link a viva session to an experiment owned by another user is rejected (IDOR prevention)."""
    bob_exp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    bob_exp = Experiment(
        id=bob_exp_id,
        user_id=user_b_id,
        title="Bob's Private Lab",
        subject="Robotics",
        creation_method="manual",
        status="ready",
        created_at=now,
        updated_at=now,
    )
    test_state.experiments[bob_exp_id] = bob_exp

    payload = {
        "idempotencyKey": "mig-idor-001",
        "experiments": [],
        "vivaSessions": [
            {
                "clientId": "sess-inject-bob",
                "clientExperimentId": str(bob_exp_id),
                "answers": [],
            }
        ],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "does not exist or does not belong" in response.json()["detail"]


@pytest.mark.anyio
async def test_migrate_guest_data_rejects_duplicate_client_id(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify duplicate client_id within the experiments payload is rejected with 422."""
    payload = {
        "idempotencyKey": "mig-dup-id-001",
        "experiments": [
            {"clientId": "same-id", "title": "First", "subject": "Math"},
            {"clientId": "same-id", "title": "Second", "subject": "Math"},
        ],
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422
    assert "Duplicate client_id found in experiments payload" in response.json()["detail"]


@pytest.mark.anyio
async def test_migrate_guest_data_empty_payload(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_state: MigrationTestState,
):
    """Verify an empty migration payload succeeds and records 0 migrated items."""
    payload = {
        "idempotencyKey": "mig-empty-001",
        "experiments": [],
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["experimentsMigrated"] == 0
    assert data["vivaSessionsMigrated"] == 0
    assert data["isIdempotentReplay"] is False
    assert len(test_state.guest_migrations) == 1


@pytest.mark.anyio
async def test_migrate_guest_data_idempotent_replay(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_state: MigrationTestState,
):
    """Verify submitting a request with the same idempotency key returns cached replay without duplicating."""
    payload = {
        "idempotencyKey": "mig-idemp-001",
        "experiments": [
            {"clientId": "exp-once", "title": "Once Only", "subject": "Physics"}
        ],
        "vivaSessions": [],
    }

    # 1. Initial submission
    res1 = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["isIdempotentReplay"] is False
    assert data1["experimentsMigrated"] == 1
    assert len(test_state.experiments) == 1

    # 2. Repeated submission with identical idempotency key
    res2 = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["isIdempotentReplay"] is True
    assert data2["experimentsMigrated"] == 1
    # Verify no duplicate experiments inserted
    assert len(test_state.experiments) == 1


@pytest.mark.anyio
async def test_migrate_guest_data_concurrent_duplicate_handling(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    user_a_id: uuid.UUID,
    test_state: MigrationTestState,
):
    """Verify that a concurrent commit hitting IntegrityError on unique constraint returns an idempotent replay."""
    # Pre-populate migration record as if committed concurrently by another worker
    now = datetime.now(timezone.utc)
    concurrent_mig = GuestMigration(
        id=uuid.uuid4(),
        user_id=user_a_id,
        idempotency_key="mig-race-001",
        experiments_migrated=1,
        viva_sessions_migrated=0,
        viva_answers_migrated=0,
        status="completed",
        created_at=now,
    )
    test_state.guest_migrations.append(concurrent_mig)
    test_state.simulate_concurrent_integrity_error = True

    payload = {
        "idempotencyKey": "mig-race-001",
        "experiments": [
            {"clientId": "exp-race", "title": "Race Test", "subject": "CS"}
        ],
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["isIdempotentReplay"] is True
    assert data["experimentsMigrated"] == 1


@pytest.mark.anyio
async def test_migrate_guest_data_atomic_rollback_on_db_failure(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_state: MigrationTestState,
):
    """Verify that if database commit fails, the transaction rolls back cleanly and no records persist."""
    test_state.fail_on_commit = True

    payload = {
        "idempotencyKey": "mig-fail-commit",
        "experiments": [
            {"clientId": "exp-fail", "title": "Doomed Experiment", "subject": "Biology"}
        ],
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 500
    assert "Failed to persist migrated records" in response.json()["detail"]
    assert test_state.rollback_count == 1
    assert len(test_state.experiments) == 0
    assert len(test_state.guest_migrations) == 0


@pytest.mark.anyio
async def test_migrate_guest_data_unauthenticated_returns_401(
    app_client: httpx.AsyncClient,
):
    """Verify unauthenticated calls are rejected with 401 Unauthorized."""
    payload = {
        "idempotencyKey": "mig-unauth",
        "experiments": [],
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_migrate_guest_data_into_account_with_existing_data(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    user_a_id: uuid.UUID,
    test_state: MigrationTestState,
):
    """Verify migrating guest records into an account that already contains data merges without clobbering."""
    now = datetime.now(timezone.utc)
    old_exp = Experiment(
        id=uuid.uuid4(),
        user_id=user_a_id,
        title="Existing Account Experiment",
        subject="Physics",
        creation_method="manual",
        status="ready",
        created_at=now,
        updated_at=now,
    )
    test_state.experiments[old_exp.id] = old_exp

    payload = {
        "idempotencyKey": "mig-merge-001",
        "experiments": [
            {"clientId": "exp-new", "title": "Migrated New Experiment", "subject": "Chemistry"}
        ],
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert len(test_state.experiments) == 2
    titles = {e.title for e in test_state.experiments.values()}
    assert "Existing Account Experiment" in titles
    assert "Migrated New Experiment" in titles


@pytest.mark.anyio
async def test_migrate_guest_data_batch_limits_enforced(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
):
    """Verify that exceeding the maximum allowable experiment count (100) returns 422."""
    too_many_experiments = [
        {"clientId": f"exp-{i}", "title": f"Exp {i}", "subject": "Science"}
        for i in range(101)
    ]
    payload = {
        "idempotencyKey": "mig-too-many",
        "experiments": too_many_experiments,
        "vivaSessions": [],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 422


@pytest.mark.anyio
async def test_migrate_guest_data_unpacks_frontend_nested_structures(
    app_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    test_state: MigrationTestState,
):
    """Verify frontend localStorage schema format (nested config, nested evaluation) is unpacked seamlessly."""
    payload = {
        "idempotency_key": "mig-unpack-001",
        "experiments": [
            {
                "id": "exp-1728000000",
                "title": "Unpack Test",
                "subject": "CS",
                "createdAtTimestamp": 1728000000000,
                "preparationChecklist": {"theory": True},
            }
        ],
        "viva_sessions": [
            {
                "id": "viva-1728000000",
                "experimentId": "exp-1728000000",
                "config": {
                    "questionCount": 5,
                    "difficulty": "advanced",
                    "focus": "procedure",
                },
                "answers": [
                    {
                        "questionId": "q-eval",
                        "questionNumber": 1,
                        "questionText": "Explain recursion.",
                        "studentAnswer": "A function that calls itself.",
                        "evaluation": {
                            "verdict": "correct",
                            "score": 10,
                            "whatYouGotRight": "Exact definition.",
                            "improvementTip": "Mention base cases.",
                        },
                    }
                ],
            }
        ],
    }

    response = await app_client.post(
        "/api/v1/users/me/migrate-guest-data",
        json=payload,
        headers=auth_headers,
    )

    assert response.status_code == 200
    saved_sess = list(test_state.viva_sessions.values())[0]
    assert saved_sess.difficulty == "advanced"
    assert saved_sess.topic_focus == "procedure"
    assert len(saved_sess.answers) == 1
    ans = saved_sess.answers[0]
    assert ans.verdict == "correct"
    assert ans.score == 10
    assert ans.what_you_got_right == "Exact definition."
    assert ans.suggested_improvement == "Mention base cases."
