"""Unit and Integration Tests for Experiment Creation & Listing Endpoints.

Verifies POST /api/v1/experiments and GET /api/v1/experiments for ownership
isolation, automatic checklist provisioning, atomic transactions, search,
filtering, pagination, and error handling without requiring a live PostgreSQL instance.
"""

from datetime import datetime, timezone
import math
from typing import Any
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
import app.modules.users.models  # noqa: F401
import app.modules.viva.models  # noqa: F401
import app.modules.documents.models  # noqa: F401
from app.modules.experiments.models import (
    Experiment,
    PreparationChecklist,
    default_preparation_checklist_items,
)
from app.modules.experiments.schemas import (
    CreationMethodEnum,
    ExperimentStatusEnum,
)


# ==============================================================================
# Test Fixtures & Mock Session Setup
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
def auth_token(sample_user_id: uuid.UUID) -> str:
    return create_access_token(sample_user_id)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


def create_sample_experiment(
    user_id: uuid.UUID,
    title: str = "Ohm's Law Verification",
    subject: str = "Physics",
    status: str = "ready",
) -> Experiment:
    """Helper to instantiate an Experiment ORM model with associated checklist."""
    now = datetime.now(timezone.utc)
    exp_id = uuid.uuid4()
    exp = Experiment(
        id=exp_id,
        user_id=user_id,
        title=title,
        subject=subject,
        experiment_number="EXP-01",
        course_semester="Semester 1",
        creation_method="manual",
        has_manual_file=False,
        file_name=None,
        status=status,
        description="Verification of V=IR relationship.",
        objective="Determine resistance using Ohm's Law.",
        theory="Current is directly proportional to voltage.",
        apparatus="Voltmeter, Ammeter, Resistor, DC Power Supply.",
        procedure="1. Connect circuit. 2. Vary voltage.",
        observations="Voltage vs Current table.",
        calculations="Slope = Resistance.",
        precautions="Do not exceed current limits.",
        created_at=now,
        updated_at=now,
    )
    chk = PreparationChecklist(
        id=uuid.uuid4(),
        experiment_id=exp_id,
        items=default_preparation_checklist_items(),
        created_at=now,
        updated_at=now,
        experiment=exp,
    )
    exp.checklist = chk
    return exp


@pytest.fixture
def mock_db_dispatcher(sample_user: User):
    """Factory creating an AsyncMock session that inspects queries and dispatches results."""
    executed_statements: list[Any] = []

    def make_mock(count_val: int = 1, items: list[Experiment] | None = None) -> AsyncMock:
        nonlocal executed_statements
        executed_statements = []
        items_list = items if items is not None else [create_sample_experiment(sample_user.id)]

        session = AsyncMock(spec=AsyncSession)
        session.add = MagicMock()
        session.delete = AsyncMock()
        session.commit = AsyncMock()
        session.rollback = AsyncMock()
        session.refresh = AsyncMock()

        async def fake_execute(statement, *args, **kwargs):
            executed_statements.append(statement)
            stmt_str = str(statement).lower()
            res = MagicMock()
            if "from users" in stmt_str:
                res.scalar_one_or_none.return_value = sample_user
            elif "count" in stmt_str:
                res.scalar_one.return_value = count_val
            else:
                res.scalars.return_value.all.return_value = items_list
                res.scalar_one_or_none.return_value = items_list[0] if items_list else None
                res.scalar_one.return_value = items_list[0] if items_list else None
            return res

        session.execute = AsyncMock(side_effect=fake_execute)
        session.executed_statements = executed_statements
        return session

    return make_mock


@pytest.fixture
def client(mock_db_dispatcher) -> httpx.AsyncClient:
    """Create HTTP test client with standard single-record mock."""
    session = mock_db_dispatcher(count_val=1)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)
    c = httpx.AsyncClient(transport=transport, base_url="http://test")
    c.session = session  # type: ignore
    return c


# ==============================================================================
# POST /api/v1/experiments Tests
# ==============================================================================


@pytest.mark.anyio
async def test_authenticated_user_can_create_experiment(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Authenticated user creates an experiment and receives HTTP 201 Created."""
    payload = {
        "title": "Photoelectric Effect Measurement",
        "subject": "Modern Physics",
        "experimentNumber": "EXP-05",
        "courseSemester": "Semester 2",
        "method": "manual",
        "objective": "Measure stopping potential vs frequency.",
    }
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Photoelectric Effect Measurement"
    assert data["subject"] == "Modern Physics"
    assert data["experimentNumber"] == "EXP-05"
    assert data["courseSemester"] == "Semester 2"
    assert data["creationMethod"] == "manual"
    assert data["objective"] == "Measure stopping potential vs frequency."
    assert "id" in data
    assert "createdAt" in data
    assert "updatedAt" in data


@pytest.mark.anyio
async def test_experiment_assigned_to_authenticated_user(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Created experiment is saved with user_id matching the authenticated user."""
    session: AsyncMock = client.session  # type: ignore
    payload = {
        "title": "Hall Effect Study",
        "subject": "Solid State Physics",
    }
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 201
    # Check that session.add was called with an Experiment instance having correct user_id
    added_objects = [call.args[0] for call in session.add.call_args_list]
    experiment_instances = [obj for obj in added_objects if isinstance(obj, Experiment)]
    assert len(experiment_instances) >= 1
    assert experiment_instances[0].user_id == sample_user.id


@pytest.mark.anyio
async def test_client_cannot_override_user_id(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    other_user_id: uuid.UUID,
) -> None:
    """Client cannot supply or override user_id; rejected with HTTP 422 extra_forbidden."""
    payload = {
        "title": "Attempted Hack",
        "subject": "Cybersecurity",
        "user_id": str(other_user_id),
    }
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 422
    assert "extra_forbidden" in response.text


@pytest.mark.anyio
async def test_checklist_is_provisioned_automatically(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Preparation checklist is provisioned alongside the experiment."""
    session: AsyncMock = client.session  # type: ignore
    payload = {
        "title": "RC Circuit Frequency Response",
        "subject": "Network Analysis",
    }
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert "checklist" in data
    assert data["checklist"] is not None
    assert "items" in data["checklist"]

    # Verify PreparationChecklist was added to the database session
    added_objects = [call.args[0] for call in session.add.call_args_list]
    checklist_instances = [obj for obj in added_objects if isinstance(obj, PreparationChecklist)]
    assert len(checklist_instances) >= 1


@pytest.mark.anyio
async def test_checklist_contains_five_supported_keys_initialized_to_false(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """All 5 supported checklist items are present and initialized to False."""
    payload = {
        "title": "Diffraction Grating Lab",
        "subject": "Wave Optics",
    }
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    checklist_items = data["checklist"]["items"]
    expected_keys = {"objective", "theory", "apparatus", "procedure", "precautions"}
    assert set(checklist_items.keys()) == expected_keys
    assert all(val is False for val in checklist_items.values())

    # Also verify flat preparationChecklist dictionary sync
    assert data["preparationChecklist"] == checklist_items


@pytest.mark.anyio
async def test_experiment_and_checklist_committed_atomically(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Commit is executed once atomically persisting both experiment and checklist."""
    session: AsyncMock = client.session  # type: ignore
    payload = {
        "title": "Atomic Commit Test",
        "subject": "Physics",
    }
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 201
    session.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_failure_during_commit_triggers_rollback(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Database commit failure triggers rollback and propagates error."""
    session: AsyncMock = client.session  # type: ignore
    session.commit.side_effect = OperationalError("connection lost", {}, Exception("DB down"))

    with pytest.raises(OperationalError):
        await client.post(
            "/api/v1/experiments",
            headers=auth_headers,
            json={"title": "Rollback Test", "subject": "Physics"},
        )

    session.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_sensitive_internal_fields_not_exposed_on_create(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Response payload never exposes user_id, password_hash, or secret internals."""
    payload = {
        "title": "Sanitization Test",
        "subject": "Physics",
    }
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json=payload,
    )

    assert response.status_code == 201
    data = response.json()
    assert "user_id" not in data
    assert "userId" not in data
    assert "password_hash" not in data


@pytest.mark.anyio
async def test_missing_authorization_token_on_create_rejected_with_401(
    client: httpx.AsyncClient,
) -> None:
    """Create request without Authorization header returns HTTP 401."""
    response = await client.post(
        "/api/v1/experiments",
        json={"title": "No Auth", "subject": "Physics"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_invalid_or_expired_token_on_create_rejected_with_401(
    client: httpx.AsyncClient,
) -> None:
    """Create request with corrupt Bearer token returns HTTP 401."""
    response = await client.post(
        "/api/v1/experiments",
        headers={"Authorization": "Bearer invalid.corrupted.token"},
        json={"title": "Bad Auth", "subject": "Physics"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_inactive_user_on_create_rejected_with_403(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Inactive user cannot create experiments; returns HTTP 403."""
    sample_user.is_active = False
    response = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json={"title": "Inactive Test", "subject": "Physics"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


@pytest.mark.anyio
async def test_invalid_create_payload_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Blank title or missing required fields return HTTP 422."""
    # Blank title
    res1 = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json={"title": "   ", "subject": "Physics"},
    )
    assert res1.status_code == 422

    # Missing subject
    res2 = await client.post(
        "/api/v1/experiments",
        headers=auth_headers,
        json={"title": "Valid Title"},
    )
    assert res2.status_code == 422


# ==============================================================================
# GET /api/v1/experiments Tests
# ==============================================================================


@pytest.mark.anyio
async def test_authenticated_user_receives_only_their_own_experiments(
    mock_db_dispatcher,
    sample_user: User,
    auth_headers: dict[str, str],
) -> None:
    """Listing query strictly includes WHERE user_id == current_user.id."""
    session = mock_db_dispatcher(count_val=2)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/experiments", headers=auth_headers)

    assert response.status_code == 200
    # Inspect executed statements
    stmts = [str(s).lower() for s in session.executed_statements]
    # Filter statements that query experiments table
    exp_stmts = [s for s in stmts if "from experiments" in s]
    assert len(exp_stmts) >= 2
    # Verify user_id filter is present in both count and paginated query
    for stmt in exp_stmts:
        assert "experiments.user_id =" in stmt


@pytest.mark.anyio
async def test_empty_results_returns_empty_list_and_zero_pages(
    mock_db_dispatcher,
    auth_headers: dict[str, str],
) -> None:
    """When no experiments exist, returns empty items and zero totalPages."""
    session = mock_db_dispatcher(count_val=0, items=[])
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/experiments", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["items"] == []
    assert data["total"] == 0
    assert data["totalPages"] == 0
    assert data["page"] == 1


@pytest.mark.anyio
async def test_pagination_returns_expected_subset_and_page_metadata(
    mock_db_dispatcher,
    sample_user: User,
    auth_headers: dict[str, str],
) -> None:
    """Pagination parameters page and pageSize are respected in response metadata and query."""
    exp1 = create_sample_experiment(sample_user.id, title="Exp 1")
    exp2 = create_sample_experiment(sample_user.id, title="Exp 2")
    session = mock_db_dispatcher(count_val=25, items=[exp1, exp2])
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/experiments?page=2&pageSize=10", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 25
    assert data["page"] == 2
    assert data["pageSize"] == 10
    assert data["totalPages"] == 3
    assert len(data["items"]) == 2

    # Check that LIMIT and OFFSET were applied in the final SQL statement
    stmts = [str(s).lower() for s in session.executed_statements]
    paginated_stmt = [s for s in stmts if "limit" in s]
    assert len(paginated_stmt) >= 1
    assert "offset" in paginated_stmt[0]


@pytest.mark.anyio
async def test_subject_filtering_applies_correct_where_clause(
    mock_db_dispatcher,
    auth_headers: dict[str, str],
) -> None:
    """Subject filter parameter adds WHERE experiments.subject = :subject."""
    session = mock_db_dispatcher(count_val=1)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/experiments?subject=Chemistry", headers=auth_headers)

    assert response.status_code == 200
    stmts = [str(s).lower() for s in session.executed_statements if "from experiments" in str(s).lower()]
    assert any("experiments.subject =" in s for s in stmts)


@pytest.mark.anyio
async def test_status_filtering_applies_correct_where_clause(
    mock_db_dispatcher,
    auth_headers: dict[str, str],
) -> None:
    """Status filter parameter adds WHERE experiments.status = :status."""
    session = mock_db_dispatcher(count_val=1)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/experiments?status=completed", headers=auth_headers)

    assert response.status_code == 200
    stmts = [str(s).lower() for s in session.executed_statements if "from experiments" in str(s).lower()]
    assert any("experiments.status =" in s for s in stmts)


@pytest.mark.anyio
async def test_search_is_case_insensitive_across_relevant_fields(
    mock_db_dispatcher,
    auth_headers: dict[str, str],
) -> None:
    """Search query applies case-insensitive pattern across fields."""
    session = mock_db_dispatcher(count_val=1)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/experiments?search=vernier", headers=auth_headers)

    assert response.status_code == 200
    stmts = [str(s).lower() for s in session.executed_statements if "from experiments" in str(s).lower()]
    assert any("like" in s or "ilike" in s for s in stmts)
    assert any("lower(experiments.title)" in s or "ilike" in s for s in stmts)


@pytest.mark.anyio
async def test_search_and_filters_work_together(
    mock_db_dispatcher,
    auth_headers: dict[str, str],
) -> None:
    """Combining search, subject, and status applies all corresponding filters."""
    session = mock_db_dispatcher(count_val=1)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get(
            "/api/v1/experiments?subject=Physics&status=ready&search=optics",
            headers=auth_headers,
        )

    assert response.status_code == 200
    stmts = [str(s).lower() for s in session.executed_statements if "from experiments" in str(s).lower()]
    paginated_stmt = [s for s in stmts if "limit" in s][0]
    assert "experiments.subject =" in paginated_stmt
    assert "experiments.status =" in paginated_stmt
    assert "like" in paginated_stmt or "ilike" in paginated_stmt


@pytest.mark.anyio
async def test_invalid_page_and_page_size_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Invalid query parameter bounds (page < 1, page_size < 1) return HTTP 422."""
    res1 = await client.get("/api/v1/experiments?page=0", headers=auth_headers)
    assert res1.status_code == 422

    res2 = await client.get("/api/v1/experiments?pageSize=0", headers=auth_headers)
    assert res2.status_code == 422


@pytest.mark.anyio
async def test_maximum_page_size_enforced_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Page size exceeding 100 is rejected with HTTP 422."""
    response = await client.get("/api/v1/experiments?pageSize=101", headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_results_have_deterministic_ordering(
    mock_db_dispatcher,
    auth_headers: dict[str, str],
) -> None:
    """Query orders results by updated_at DESC, id DESC."""
    session = mock_db_dispatcher(count_val=1)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/experiments", headers=auth_headers)

    assert response.status_code == 200
    stmts = [str(s).lower() for s in session.executed_statements if "order by" in str(s).lower()]
    assert len(stmts) >= 1
    assert "experiments.updated_at desc" in stmts[0]
    assert "experiments.id desc" in stmts[0]


@pytest.mark.anyio
async def test_list_items_omit_heavy_content_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """List response items omit heavy content sections."""
    response = await client.get("/api/v1/experiments", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) >= 1
    item = data["items"][0]
    assert "title" in item
    assert "subject" in item
    assert "status" in item
    assert "procedure" not in item
    assert "theory" not in item
    assert "observations" not in item
    assert "calculations" not in item
    assert "precautions" not in item


@pytest.mark.anyio
async def test_missing_authorization_token_on_list_rejected_with_401(
    client: httpx.AsyncClient,
) -> None:
    """List request without Authorization header returns HTTP 401."""
    response = await client.get("/api/v1/experiments")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_inactive_user_on_list_rejected_with_403(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Inactive user cannot list experiments; returns HTTP 403."""
    sample_user.is_active = False
    response = await client.get("/api/v1/experiments", headers=auth_headers)
    assert response.status_code == 403


@pytest.mark.anyio
async def test_database_failure_on_list_propagates_without_masking(
    mock_db_dispatcher,
    auth_headers: dict[str, str],
) -> None:
    """Database query failure during listing propagates without being masked as 401."""
    session = mock_db_dispatcher()
    session.execute.side_effect = OperationalError("connection lost", {}, Exception("DB down"))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        with pytest.raises(OperationalError):
            await c.get("/api/v1/experiments", headers=auth_headers)


# ==============================================================================
# Regression & Route Registration Tests
# ==============================================================================


@pytest.mark.anyio
async def test_regression_auth_routes_remain_functional(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Auth logout endpoint continues operating normally."""
    response = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert response.status_code == 200
    assert response.json() == {"message": "Logged out successfully"}


@pytest.mark.anyio
async def test_regression_user_profile_routes_remain_functional(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """User profile endpoint continues operating normally."""
    response = await client.get("/api/v1/users/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == sample_user.email


@pytest.mark.anyio
async def test_regression_health_endpoint_available(
    client: httpx.AsyncClient,
) -> None:
    """Base /health endpoint remains available."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_openapi_catalog_contains_experiment_endpoints() -> None:
    """Verify that all /api/v1/experiments endpoints are registered in OpenAPI."""
    app = create_app()
    openapi_paths = app.openapi()["paths"]

    assert "/api/v1/experiments" in openapi_paths
    collection_methods = openapi_paths["/api/v1/experiments"]
    assert "post" in collection_methods
    assert "get" in collection_methods

    assert "/api/v1/experiments/{experiment_id}" in openapi_paths
    item_methods = openapi_paths["/api/v1/experiments/{experiment_id}"]
    assert "get" in item_methods
    assert "patch" in item_methods
    assert "delete" in item_methods

    assert "/api/v1/experiments/{experiment_id}/checklist" in openapi_paths
    checklist_methods = openapi_paths["/api/v1/experiments/{experiment_id}/checklist"]
    assert "patch" in checklist_methods

    # Verify all previous endpoints remain intact
    assert "/health" in openapi_paths
    assert "/api/v1/auth/register" in openapi_paths
    assert "/api/v1/auth/login" in openapi_paths
    assert "/api/v1/auth/refresh" in openapi_paths
    assert "/api/v1/auth/logout" in openapi_paths
    assert "/api/v1/users/me" in openapi_paths


# ==============================================================================
# GET /api/v1/experiments/{experiment_id} Tests
# ==============================================================================


@pytest.mark.anyio
async def test_get_experiment_authenticated_owner_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Authenticated owner can retrieve an individual experiment by ID with HTTP 200."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)
    session.execute.side_effect = None

    async def fake_exec(stmt, *args, **kwargs):
        session.executed_statements.append(stmt)
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.get(f"/api/v1/experiments/{exp.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(exp.id)
    assert data["title"] == exp.title
    assert data["subject"] == exp.subject
    assert data["status"] == exp.status


@pytest.mark.anyio
async def test_get_experiment_includes_all_expected_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Retrieved experiment response contains all metadata, content sections, and checklist."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.get(f"/api/v1/experiments/{exp.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert "title" in data
    assert "subject" in data
    assert "experimentNumber" in data
    assert "courseSemester" in data
    assert "creationMethod" in data
    assert "hasManualFile" in data
    assert "fileName" in data
    assert "status" in data
    assert "description" in data
    assert "objective" in data
    assert "theory" in data
    assert "apparatus" in data
    assert "procedure" in data
    assert "observations" in data
    assert "calculations" in data
    assert "precautions" in data
    assert "checklist" in data
    assert "preparationChecklist" in data
    assert "vivaQuestionsCount" in data
    assert "createdAt" in data
    assert "updatedAt" in data


@pytest.mark.anyio
async def test_get_experiment_checklist_serializes_correctly(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Preparation checklist serializes correctly in both relational and flat dictionary formats."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.get(f"/api/v1/experiments/{exp.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    checklist_dto = data["checklist"]
    assert checklist_dto is not None
    assert checklist_dto["experimentId"] == str(exp.id)
    assert "items" in checklist_dto
    assert checklist_dto["items"]["objective"] is False

    flat_checklist = data["preparationChecklist"]
    assert flat_checklist is not None
    assert flat_checklist["objective"] is False
    assert flat_checklist["theory"] is False
    assert flat_checklist["apparatus"] is False
    assert flat_checklist["procedure"] is False
    assert flat_checklist["precautions"] is False


@pytest.mark.anyio
async def test_get_experiment_excludes_internal_ownership_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Experiment response never exposes internal user_id or sensitive metadata."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.get(f"/api/v1/experiments/{exp.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "user_id" not in data
    assert "userId" not in data
    assert "password_hash" not in data


@pytest.mark.anyio
async def test_get_experiment_nonexistent_returns_404(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Nonexistent experiment returns HTTP 404 Not Found."""
    session: AsyncMock = client.session  # type: ignore

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    random_id = uuid.uuid4()
    response = await client.get(f"/api/v1/experiments/{random_id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


@pytest.mark.anyio
async def test_get_experiment_foreign_user_returns_404_and_scopes_query(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    other_user_id: uuid.UUID,
) -> None:
    """Accessing another user's experiment returns HTTP 404 (does NOT reveal existence or return 403)."""
    session: AsyncMock = client.session  # type: ignore
    foreign_exp = create_sample_experiment(other_user_id)

    executed_queries: list[Any] = []

    async def fake_exec(stmt, *args, **kwargs):
        executed_queries.append(stmt)
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            # Query has user_id filter, so foreign_exp won't match
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    response = await client.get(f"/api/v1/experiments/{foreign_exp.id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"

    # Confirm the query strictly filtered by authenticated user's ID
    exp_queries = [q for q in executed_queries if "experiments" in str(q).lower()]
    assert len(exp_queries) >= 1
    compiled = str(exp_queries[0]).lower()
    assert "user_id" in compiled


@pytest.mark.anyio
async def test_get_experiment_invalid_uuid_returns_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Invalid non-UUID path parameter is rejected with HTTP 422 Unprocessable Entity."""
    response = await client.get("/api/v1/experiments/not-a-valid-uuid", headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_get_experiment_missing_auth_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """Unauthenticated request to GET /experiments/{id} is rejected with HTTP 401."""
    random_id = uuid.uuid4()
    response = await client.get(f"/api/v1/experiments/{random_id}")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_get_experiment_invalid_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """Request with invalid Bearer token is rejected with HTTP 401."""
    random_id = uuid.uuid4()
    response = await client.get(
        f"/api/v1/experiments/{random_id}",
        headers={"Authorization": "Bearer invalid.token.value"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_get_experiment_inactive_user_returns_403(
    mock_db_dispatcher,
    sample_user: User,
    auth_headers: dict[str, str],
) -> None:
    """Inactive user is rejected with HTTP 403 Forbidden."""
    sample_user.is_active = False
    session = mock_db_dispatcher()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    random_id = uuid.uuid4()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get(f"/api/v1/experiments/{random_id}", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


# ==============================================================================
# PATCH /api/v1/experiments/{experiment_id} Tests
# ==============================================================================


@pytest.mark.anyio
async def test_patch_experiment_partial_update_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Authenticated owner can update a single field (e.g. title) with HTTP 200."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
            res.scalar_one.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    payload = {"title": "Updated Experiment Title"}
    response = await client.patch(
        f"/api/v1/experiments/{exp.id}",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    assert exp.title == "Updated Experiment Title"
    assert session.commit.called


@pytest.mark.anyio
async def test_patch_experiment_multiple_fields_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Authenticated owner can update multiple fields simultaneously."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
            res.scalar_one.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    payload = {
        "subject": "Applied Optics",
        "status": "in-progress",
        "apparatus": "Laser, Diffraction Grating, Screen",
        "observations": "Diffraction fringes table.",
    }
    response = await client.patch(
        f"/api/v1/experiments/{exp.id}",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    assert exp.subject == "Applied Optics"
    assert exp.status == "in-progress"
    assert exp.apparatus == "Laser, Diffraction Grating, Screen"
    assert exp.observations == "Diffraction fringes table."


@pytest.mark.anyio
async def test_patch_experiment_omitted_fields_preserved(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Fields omitted in PATCH payload retain their existing values."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)
    original_procedure = exp.procedure
    original_theory = exp.theory

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
            res.scalar_one.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    payload = {"title": "Only Title Changed"}
    response = await client.patch(
        f"/api/v1/experiments/{exp.id}",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    assert exp.procedure == original_procedure
    assert exp.theory == original_theory


@pytest.mark.anyio
async def test_patch_experiment_updates_timestamp(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Updating an experiment refreshes its updated_at timestamp."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)
    old_updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    exp.updated_at = old_updated_at

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
            res.scalar_one.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    payload = {"title": "Timestamp Check"}
    response = await client.patch(
        f"/api/v1/experiments/{exp.id}",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    assert exp.updated_at > old_updated_at


@pytest.mark.anyio
@pytest.mark.parametrize(
    "forbidden_field,forbidden_value",
    [
        ("id", str(uuid.uuid4())),
        ("user_id", str(uuid.uuid4())),
        ("created_at", "2026-01-01T00:00:00Z"),
        ("updated_at", "2026-01-01T00:00:00Z"),
    ],
)
async def test_patch_experiment_protected_fields_rejected(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    forbidden_field: str,
    forbidden_value: Any,
) -> None:
    """Client cannot supply protected fields; rejected with HTTP 422 extra_forbidden."""
    random_id = uuid.uuid4()
    payload = {
        "title": "Legitimate Title",
        forbidden_field: forbidden_value,
    }
    response = await client.patch(
        f"/api/v1/experiments/{random_id}",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_patch_experiment_empty_payload_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Empty payload {} is rejected with HTTP 422."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_patch_experiment_invalid_field_types_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Invalid field values (such as null title or non-existent status) are rejected with HTTP 422."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}",
        headers=auth_headers,
        json={"title": None},
    )
    assert response.status_code == 422

    response2 = await client.patch(
        f"/api/v1/experiments/{random_id}",
        headers=auth_headers,
        json={"status": "invalid-status-xyz"},
    )
    assert response2.status_code == 422


@pytest.mark.anyio
async def test_patch_experiment_nonexistent_returns_404(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Updating a nonexistent experiment returns HTTP 404."""
    session: AsyncMock = client.session  # type: ignore

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}",
        headers=auth_headers,
        json={"title": "Updated Title"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


@pytest.mark.anyio
async def test_patch_experiment_foreign_user_returns_404(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    other_user_id: uuid.UUID,
) -> None:
    """Updating another user's experiment returns HTTP 404 (does NOT return 403 or reveal existence)."""
    session: AsyncMock = client.session  # type: ignore
    foreign_exp = create_sample_experiment(other_user_id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{foreign_exp.id}",
        headers=auth_headers,
        json={"title": "Hacked Title"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


@pytest.mark.anyio
async def test_patch_experiment_invalid_uuid_returns_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Invalid UUID in path is rejected with HTTP 422."""
    response = await client.patch(
        "/api/v1/experiments/not-a-uuid",
        headers=auth_headers,
        json={"title": "Updated"},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_patch_experiment_missing_auth_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """PATCH without auth returns HTTP 401."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}",
        json={"title": "Updated"},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_patch_experiment_inactive_user_returns_403(
    mock_db_dispatcher,
    sample_user: User,
    auth_headers: dict[str, str],
) -> None:
    """Inactive user cannot update experiments (HTTP 403)."""
    sample_user.is_active = False
    session = mock_db_dispatcher()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    random_id = uuid.uuid4()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.patch(
            f"/api/v1/experiments/{random_id}",
            headers=auth_headers,
            json={"title": "Updated"},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


@pytest.mark.anyio
async def test_patch_experiment_database_failure_triggers_rollback(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Commit failure during experiment update triggers session rollback."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
            res.scalar_one.return_value = exp
        return res

    session.execute.side_effect = fake_exec
    session.commit.side_effect = OperationalError("deadlock", {}, Exception("deadlock"))

    with pytest.raises(OperationalError):
        await client.patch(
            f"/api/v1/experiments/{exp.id}",
            headers=auth_headers,
            json={"title": "Triggers Rollback"},
        )

    assert session.rollback.called


# ==============================================================================
# DELETE /api/v1/experiments/{experiment_id} Tests
# ==============================================================================


@pytest.mark.anyio
async def test_delete_experiment_owner_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Authenticated owner can delete an experiment, returning HTTP 204 No Content."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.delete(f"/api/v1/experiments/{exp.id}", headers=auth_headers)
    assert response.status_code == 204
    assert response.content == b""
    assert session.commit.called


@pytest.mark.anyio
async def test_delete_experiment_returns_empty_body(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """HTTP 204 response body is completely empty and has no JSON payload."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.delete(f"/api/v1/experiments/{exp.id}", headers=auth_headers)
    assert response.status_code == 204
    assert len(response.content) == 0


@pytest.mark.anyio
async def test_delete_experiment_calls_db_delete(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Deleting an experiment invokes session.delete on the exact Experiment entity."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.delete(f"/api/v1/experiments/{exp.id}", headers=auth_headers)
    assert response.status_code == 204
    session.delete.assert_called_once_with(exp)


@pytest.mark.anyio
async def test_delete_experiment_nonexistent_returns_404(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Deleting a nonexistent experiment returns HTTP 404."""
    session: AsyncMock = client.session  # type: ignore

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    random_id = uuid.uuid4()
    response = await client.delete(f"/api/v1/experiments/{random_id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


@pytest.mark.anyio
async def test_delete_experiment_foreign_user_returns_404(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    other_user_id: uuid.UUID,
) -> None:
    """Deleting another user's experiment returns HTTP 404 (does NOT reveal existence or return 403)."""
    session: AsyncMock = client.session  # type: ignore
    foreign_exp = create_sample_experiment(other_user_id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    response = await client.delete(f"/api/v1/experiments/{foreign_exp.id}", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


@pytest.mark.anyio
async def test_delete_experiment_invalid_uuid_returns_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Invalid UUID in path is rejected with HTTP 422."""
    response = await client.delete("/api/v1/experiments/invalid-id-123", headers=auth_headers)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_delete_experiment_missing_auth_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """DELETE without auth returns HTTP 401."""
    random_id = uuid.uuid4()
    response = await client.delete(f"/api/v1/experiments/{random_id}")
    assert response.status_code == 401


@pytest.mark.anyio
async def test_delete_experiment_inactive_user_returns_403(
    mock_db_dispatcher,
    sample_user: User,
    auth_headers: dict[str, str],
) -> None:
    """Inactive user cannot delete experiments (HTTP 403)."""
    sample_user.is_active = False
    session = mock_db_dispatcher()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    random_id = uuid.uuid4()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.delete(f"/api/v1/experiments/{random_id}", headers=auth_headers)
    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


@pytest.mark.anyio
async def test_delete_experiment_database_failure_triggers_rollback(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Database failure during delete triggers rollback."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec
    session.commit.side_effect = OperationalError("connection lost", {}, Exception("DB down"))

    with pytest.raises(OperationalError):
        await client.delete(f"/api/v1/experiments/{exp.id}", headers=auth_headers)

    assert session.rollback.called


# ==============================================================================
# PATCH /api/v1/experiments/{experiment_id}/checklist Tests
# ==============================================================================


@pytest.mark.anyio
async def test_patch_checklist_single_item_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Updating a single checklist item sets it to true and commits changes."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{exp.id}/checklist",
        headers=auth_headers,
        json={"objective": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"]["objective"] is True
    assert exp.checklist.items["objective"] is True
    assert session.commit.called


@pytest.mark.anyio
async def test_patch_checklist_multiple_items_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Updating multiple checklist items in a single request applies all updates."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    payload = {
        "objective": True,
        "theory": True,
        "precautions": True,
    }
    response = await client.patch(
        f"/api/v1/experiments/{exp.id}/checklist",
        headers=auth_headers,
        json=payload,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"]["objective"] is True
    assert data["items"]["theory"] is True
    assert data["items"]["apparatus"] is False
    assert data["items"]["procedure"] is False
    assert data["items"]["precautions"] is True


@pytest.mark.anyio
async def test_patch_checklist_item_true_to_false(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Checklist item initially true can be toggled to false."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)
    exp.checklist.items["objective"] = True

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{exp.id}/checklist",
        headers=auth_headers,
        json={"objective": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"]["objective"] is False
    assert exp.checklist.items["objective"] is False


@pytest.mark.anyio
async def test_patch_checklist_omitted_items_preserved(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Omitted checklist items retain their existing values."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)
    exp.checklist.items["theory"] = True
    exp.checklist.items["apparatus"] = True

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{exp.id}/checklist",
        headers=auth_headers,
        json={"objective": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"]["objective"] is True
    assert data["items"]["theory"] is True
    assert data["items"]["apparatus"] is True
    assert data["items"]["procedure"] is False
    assert data["items"]["precautions"] is False


@pytest.mark.anyio
async def test_patch_checklist_response_reflects_persisted_state(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Checklist response conforms to PreparationChecklistResponse with IDs and timestamps."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{exp.id}/checklist",
        headers=auth_headers,
        json={"procedure": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(exp.checklist.id)
    assert data["experimentId"] == str(exp.id)
    assert "createdAt" in data
    assert "updatedAt" in data
    assert data["items"]["procedure"] is True


@pytest.mark.anyio
async def test_patch_checklist_timestamp_refreshed(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Updating a checklist item refreshes its updatedAt timestamp."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)
    old_updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    exp.checklist.updated_at = old_updated_at

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{exp.id}/checklist",
        headers=auth_headers,
        json={"theory": True},
    )
    assert response.status_code == 200
    assert exp.checklist.updated_at > old_updated_at


@pytest.mark.anyio
async def test_patch_checklist_empty_body_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Empty checklist request body {} is rejected with HTTP 422."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}/checklist",
        headers=auth_headers,
        json={},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_patch_checklist_unknown_key_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Checklist update with unknown key is rejected with HTTP 422 extra_forbidden."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}/checklist",
        headers=auth_headers,
        json={"unknown_section": True},
    )
    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"objective": "true"},
        {"objective": "false"},
        {"objective": 1},
        {"objective": 0},
        {"objective": None},
        {"objective": [True]},
        {"objective": {"nested": True}},
    ],
)
async def test_patch_checklist_invalid_value_types_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    invalid_payload: dict[str, Any],
) -> None:
    """Non-boolean values (strings, integers, null, arrays) are rejected with HTTP 422 without coercion."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}/checklist",
        headers=auth_headers,
        json=invalid_payload,
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_patch_checklist_invalid_uuid_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Non-UUID experiment identifier in path returns HTTP 422."""
    response = await client.patch(
        "/api/v1/experiments/not-a-uuid/checklist",
        headers=auth_headers,
        json={"objective": True},
    )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_patch_checklist_missing_auth_rejected_with_401(
    client: httpx.AsyncClient,
) -> None:
    """Unauthenticated request to PATCH checklist returns HTTP 401."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}/checklist",
        json={"objective": True},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_patch_checklist_invalid_token_rejected_with_401(
    client: httpx.AsyncClient,
) -> None:
    """Request with invalid Bearer token returns HTTP 401."""
    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}/checklist",
        headers={"Authorization": "Bearer invalid.token.xyz"},
        json={"objective": True},
    )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_patch_checklist_inactive_user_rejected_with_403(
    mock_db_dispatcher,
    sample_user: User,
    auth_headers: dict[str, str],
) -> None:
    """Inactive user is rejected with HTTP 403 Forbidden."""
    sample_user.is_active = False
    session = mock_db_dispatcher()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: session
    transport = httpx.ASGITransport(app=app)

    random_id = uuid.uuid4()
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.patch(
            f"/api/v1/experiments/{random_id}/checklist",
            headers=auth_headers,
            json={"objective": True},
        )
    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


@pytest.mark.anyio
async def test_patch_checklist_nonexistent_returns_404(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Updating checklist for a nonexistent experiment returns HTTP 404."""
    session: AsyncMock = client.session  # type: ignore

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    random_id = uuid.uuid4()
    response = await client.patch(
        f"/api/v1/experiments/{random_id}/checklist",
        headers=auth_headers,
        json={"objective": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"


@pytest.mark.anyio
async def test_patch_checklist_foreign_user_returns_404(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    other_user_id: uuid.UUID,
) -> None:
    """Updating another user's experiment checklist returns HTTP 404 (does NOT reveal existence or return 403)."""
    session: AsyncMock = client.session  # type: ignore
    foreign_exp = create_sample_experiment(other_user_id)

    executed_queries: list[Any] = []

    async def fake_exec(stmt, *args, **kwargs):
        executed_queries.append(stmt)
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{foreign_exp.id}/checklist",
        headers=auth_headers,
        json={"objective": True},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Experiment not found"

    # Confirm query explicitly checked user_id
    exp_queries = [q for q in executed_queries if "experiments" in str(q).lower()]
    assert len(exp_queries) >= 1
    assert "user_id" in str(exp_queries[0]).lower()


@pytest.mark.anyio
async def test_patch_checklist_database_failure_triggers_rollback(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Database commit failure during checklist update triggers session rollback."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        if "from users" in str(stmt).lower():
            res.scalar_one_or_none.return_value = sample_user
        else:
            res.scalar_one_or_none.return_value = exp
        return res

    session.execute.side_effect = fake_exec
    session.commit.side_effect = OperationalError("connection lost", {}, Exception("DB down"))

    with pytest.raises(OperationalError):
        await client.patch(
            f"/api/v1/experiments/{exp.id}/checklist",
            headers=auth_headers,
            json={"objective": True},
        )

    assert session.rollback.called


@pytest.mark.anyio
async def test_patch_checklist_missing_relationship_provisions_safely(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """If experiment checklist relationship is None, endpoint resolves or instantiates it safely."""
    session: AsyncMock = client.session  # type: ignore
    exp = create_sample_experiment(sample_user.id)
    exp.checklist = None  # simulate missing relation

    async def fake_exec(stmt, *args, **kwargs):
        res = MagicMock()
        stmt_str = str(stmt).lower()
        if "from users" in stmt_str:
            res.scalar_one_or_none.return_value = sample_user
        elif "from experiments" in stmt_str:
            res.scalar_one_or_none.return_value = exp
        elif "from preparation_checklists" in stmt_str:
            # Not found in separate query either
            res.scalar_one_or_none.return_value = None
        else:
            res.scalar_one_or_none.return_value = None
        return res

    session.execute.side_effect = fake_exec

    response = await client.patch(
        f"/api/v1/experiments/{exp.id}/checklist",
        headers=auth_headers,
        json={"objective": True},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["items"]["objective"] is True
    assert exp.checklist is not None


