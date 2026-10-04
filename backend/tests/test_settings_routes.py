"""Unit and Integration Tests for Authenticated User Study Settings Endpoints.

Verifies GET /api/v1/users/me/settings and PATCH /api/v1/users/me/settings for
study preferences retrieval, lazy auto-provisioning, partial updates, legacy value
normalization, input validation, forbidden field rejection, user isolation, and
transaction rollback safety.
"""

from datetime import datetime, timedelta, timezone
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
from app.modules.users.models import UserSettings


# ==============================================================================
# Test Fixtures & Setup
# ==============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    """Create a configured mock AsyncSession for route testing."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_settings(sample_user_id: uuid.UUID) -> UserSettings:
    """Create standard UserSettings instance for testing."""
    now = datetime.now(timezone.utc)
    return UserSettings(
        id=uuid.uuid4(),
        user_id=sample_user_id,
        default_difficulty="intermediate",
        default_question_count=5,
        preferred_focus="mixed",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_user(sample_user_id: uuid.UUID, sample_settings: UserSettings) -> User:
    """Create a standard active student User instance bound to sample_settings."""
    now = datetime.now(timezone.utc)
    user = User(
        id=sample_user_id,
        email="student.settings@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashedsecret",
        full_name="Alex Preferences",
        university="Engineering College",
        is_active=True,
        auth_provider="local",
        created_at=now,
        updated_at=now,
    )
    user.settings = sample_settings
    return user


@pytest.fixture
def auth_token(sample_user_id: uuid.UUID) -> str:
    """Generate a valid JWT access token for sample_user_id."""
    return create_access_token(sample_user_id)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    """Return standard Bearer authorization header."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def client(mock_db: AsyncMock, sample_user: User) -> httpx.AsyncClient:
    """Create an asynchronous HTTP test client with database dependency override."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db

    # Default execute mock returns sample_user for user lookup queries
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = sample_user
    mock_db.execute = AsyncMock(return_value=mock_result)

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ==============================================================================
# GET /api/v1/users/me/settings Tests (Scenarios 1 - 5)
# ==============================================================================


@pytest.mark.anyio
async def test_get_settings_authenticated_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    sample_settings: UserSettings,
) -> None:
    """Scenario 1: Authenticated user receives complete study settings in camelCase."""
    response = await client.get("/api/v1/users/me/settings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == str(sample_settings.id)
    assert data["userId"] == str(sample_user.id)
    assert data["defaultDifficulty"] == sample_settings.default_difficulty
    assert data["defaultQuestionCount"] == sample_settings.default_question_count
    assert data["preferredFocus"] == sample_settings.preferred_focus
    assert "createdAt" in data
    assert "updatedAt" in data

    # Ensure camelCase contract matches frontend expectation
    expected_keys = {
        "id",
        "userId",
        "defaultDifficulty",
        "defaultQuestionCount",
        "preferredFocus",
        "createdAt",
        "updatedAt",
    }
    assert set(data.keys()) == expected_keys


@pytest.mark.anyio
async def test_get_settings_auto_provisions_missing_row(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    mock_db: AsyncMock,
) -> None:
    """Scenario 2: Missing settings row is automatically provisioned on GET."""
    # Simulate missing settings row
    sample_user.settings = None

    # Database query for UserSettings returns None initially
    mock_settings_result = MagicMock()
    mock_settings_result.scalar_one_or_none.return_value = None

    # get_current_user returns sample_user, subsequent select(UserSettings) returns None
    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = sample_user

    mock_db.execute = AsyncMock(side_effect=[user_result, mock_settings_result])

    response = await client.get("/api/v1/users/me/settings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["userId"] == str(sample_user.id)
    assert data["defaultDifficulty"] == "intermediate"
    assert data["defaultQuestionCount"] == 5
    assert data["preferredFocus"] == "mixed"
    assert mock_db.add.called
    assert mock_db.commit.called


@pytest.mark.anyio
async def test_get_settings_provisioned_defaults_are_persisted(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    mock_db: AsyncMock,
) -> None:
    """Scenario 3: Auto-provisioned defaults are committed to the database."""
    sample_user.settings = None

    mock_settings_result = MagicMock()
    mock_settings_result.scalar_one_or_none.return_value = None

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = sample_user

    mock_db.execute = AsyncMock(side_effect=[user_result, mock_settings_result])

    response = await client.get("/api/v1/users/me/settings", headers=auth_headers)

    assert response.status_code == 200
    # Ensure added entity is UserSettings with expected defaults
    added_obj = mock_db.add.call_args[0][0]
    assert isinstance(added_obj, UserSettings)
    assert added_obj.user_id == sample_user.id
    assert added_obj.default_difficulty == "intermediate"
    assert added_obj.default_question_count == 5
    assert added_obj.preferred_focus == "mixed"
    mock_db.commit.assert_awaited()


@pytest.mark.anyio
async def test_get_settings_normalizes_legacy_database_values(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    sample_settings: UserSettings,
) -> None:
    """Scenario 4: Legacy 'medium' and 'all' values are normalized in responses."""
    # Legacy DB row containing 'medium' difficulty and 'all' focus
    sample_settings.default_difficulty = "medium"
    sample_settings.preferred_focus = "all"
    sample_user.settings = sample_settings

    response = await client.get("/api/v1/users/me/settings", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["defaultDifficulty"] == "intermediate"
    assert data["preferredFocus"] == "mixed"


@pytest.mark.anyio
async def test_get_settings_user_isolation(
    mock_db: AsyncMock,
    sample_user: User,
    sample_settings: UserSettings,
) -> None:
    """Scenario 5: User A cannot retrieve User B's settings, even with query params."""
    user_b_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user_b_settings = UserSettings(
        id=uuid.uuid4(),
        user_id=user_b_id,
        default_difficulty="advanced",
        default_question_count=15,
        preferred_focus="theory",
        created_at=now,
        updated_at=now,
    )
    user_b = User(
        id=user_b_id,
        email="user_b@university.edu",
        password_hash="hashed",
        full_name="User B",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user_b.settings = user_b_settings

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db

    # Authenticate as User A
    user_a_result = MagicMock()
    user_a_result.scalar_one_or_none.return_value = sample_user
    mock_db.execute = AsyncMock(return_value=user_a_result)

    token_a = create_access_token(sample_user.id)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client_a:
        # Request with malicious user ID query parameter targeting User B
        response = await client_a.get(
            f"/api/v1/users/me/settings?userId={user_b_id}&user_id={user_b_id}",
            headers=headers_a,
        )

        assert response.status_code == 200
        data = response.json()
        # Returns User A's settings only
        assert data["userId"] == str(sample_user.id)
        assert data["defaultDifficulty"] == sample_settings.default_difficulty
        assert data["userId"] != str(user_b_id)


# ==============================================================================
# PATCH /api/v1/users/me/settings Tests (Scenarios 6 - 18)
# ==============================================================================


@pytest.mark.anyio
async def test_patch_settings_update_only_difficulty(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_settings: UserSettings,
) -> None:
    """Scenario 6: Update only defaultDifficulty, other fields unchanged."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"defaultDifficulty": "advanced"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["defaultDifficulty"] == "advanced"
    assert data["defaultQuestionCount"] == 5
    assert data["preferredFocus"] == "mixed"
    assert sample_settings.default_difficulty == "advanced"


@pytest.mark.anyio
async def test_patch_settings_update_only_question_count(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_settings: UserSettings,
) -> None:
    """Scenario 7: Update only defaultQuestionCount, other fields unchanged."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"defaultQuestionCount": 15},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["defaultQuestionCount"] == 15
    assert data["defaultDifficulty"] == "intermediate"
    assert data["preferredFocus"] == "mixed"
    assert sample_settings.default_question_count == 15


@pytest.mark.anyio
async def test_patch_settings_update_only_preferred_focus(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_settings: UserSettings,
) -> None:
    """Scenario 8: Update only preferredFocus, other fields unchanged."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"preferredFocus": "theory"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["preferredFocus"] == "theory"
    assert data["defaultDifficulty"] == "intermediate"
    assert data["defaultQuestionCount"] == 5
    assert sample_settings.preferred_focus == "theory"


@pytest.mark.anyio
async def test_patch_settings_update_multiple_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_settings: UserSettings,
) -> None:
    """Scenario 9: Update multiple fields in one request."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={
            "defaultDifficulty": "beginner",
            "defaultQuestionCount": 10,
            "preferredFocus": "apparatus",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["defaultDifficulty"] == "beginner"
    assert data["defaultQuestionCount"] == 10
    assert data["preferredFocus"] == "apparatus"


@pytest.mark.anyio
async def test_patch_settings_omitted_fields_remain_unchanged(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_settings: UserSettings,
) -> None:
    """Scenario 10: Omitted fields remain strictly unchanged."""
    sample_settings.default_difficulty = "intermediate"
    sample_settings.default_question_count = 10
    sample_settings.preferred_focus = "observations"

    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"defaultDifficulty": "advanced"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["defaultDifficulty"] == "advanced"
    assert data["defaultQuestionCount"] == 10
    assert data["preferredFocus"] == "observations"


@pytest.mark.anyio
async def test_patch_settings_normalizes_legacy_aliases(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_settings: UserSettings,
) -> None:
    """Scenario 11: Legacy aliases 'medium' and 'all' are normalized to canonical values."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={
            "defaultDifficulty": "medium",
            "preferredFocus": "all",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["defaultDifficulty"] == "intermediate"
    assert data["preferredFocus"] == "mixed"
    assert sample_settings.default_difficulty == "intermediate"
    assert sample_settings.preferred_focus == "mixed"


@pytest.mark.anyio
async def test_patch_settings_supports_snake_case_input(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_settings: UserSettings,
) -> None:
    """Scenario 11b: Snake_case payload fields are accepted and normalized."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={
            "default_difficulty": "medium",
            "default_question_count": 10,
            "preferred_focus": "all",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["defaultDifficulty"] == "intermediate"
    assert data["defaultQuestionCount"] == 10
    assert data["preferredFocus"] == "mixed"


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_count", [0, 1, 7, 12, 20, -5, "five", True])
async def test_patch_settings_invalid_question_counts_return_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    invalid_count: Any,
) -> None:
    """Scenario 12: Invalid question count values return HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"defaultQuestionCount": invalid_count},
    )

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_diff", ["hard", "easy", "extreme", "expert", "", 123])
async def test_patch_settings_invalid_difficulty_returns_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    invalid_diff: Any,
) -> None:
    """Scenario 13: Invalid difficulty values return HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"defaultDifficulty": invalid_diff},
    )

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("invalid_focus", ["random", "everything", "quiz", "formulas", "", 99])
async def test_patch_settings_invalid_preferred_focus_returns_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    invalid_focus: Any,
) -> None:
    """Scenario 14: Invalid preferred-focus values return HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"preferredFocus": invalid_focus},
    )

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize(
    "forbidden_payload",
    [
        {"id": str(uuid.uuid4())},
        {"userId": str(uuid.uuid4())},
        {"user_id": str(uuid.uuid4())},
        {"createdAt": "2026-01-01T00:00:00Z"},
        {"created_at": "2026-01-01T00:00:00Z"},
        {"updatedAt": "2026-01-01T00:00:00Z"},
        {"updated_at": "2026-01-01T00:00:00Z"},
        {"theme": "dark"},
        {"density": "compact"},
        {"reducedMotion": True},
        {"unknownField": "malicious"},
    ],
)
async def test_patch_settings_protected_fields_return_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    forbidden_payload: dict[str, Any],
) -> None:
    """Scenario 15: Protected fields and unknown properties return HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json=forbidden_payload,
    )

    assert response.status_code == 422
    assert "extra_forbidden" in response.text or "Extra inputs are not permitted" in response.text


@pytest.mark.anyio
async def test_patch_settings_empty_payload_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Scenario 16: Empty PATCH payload is rejected with HTTP 422 per API conventions."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 422
    assert "At least one study preference field must be provided" in response.text


@pytest.mark.anyio
async def test_patch_settings_auto_provisions_missing_row(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    mock_db: AsyncMock,
) -> None:
    """Scenario 17: PATCH automatically provisions a missing settings row and applies updates."""
    # Simulate user having no settings record yet
    sample_user.settings = None

    mock_settings_result = MagicMock()
    mock_settings_result.scalar_one_or_none.return_value = None

    user_result = MagicMock()
    user_result.scalar_one_or_none.return_value = sample_user

    mock_db.execute = AsyncMock(side_effect=[user_result, mock_settings_result])

    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"defaultDifficulty": "advanced"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["userId"] == str(sample_user.id)
    assert data["defaultDifficulty"] == "advanced"
    assert data["defaultQuestionCount"] == 5
    assert data["preferredFocus"] == "mixed"
    assert mock_db.add.called
    assert mock_db.commit.called


@pytest.mark.anyio
async def test_patch_settings_user_isolation(
    mock_db: AsyncMock,
    sample_user: User,
    sample_settings: UserSettings,
) -> None:
    """Scenario 18: User A cannot modify User B's settings."""
    user_b_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    user_b_settings = UserSettings(
        id=uuid.uuid4(),
        user_id=user_b_id,
        default_difficulty="beginner",
        default_question_count=5,
        preferred_focus="theory",
        created_at=now,
        updated_at=now,
    )
    user_b = User(
        id=user_b_id,
        email="victim@university.edu",
        password_hash="hashed",
        full_name="User B",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    user_b.settings = user_b_settings

    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db

    # Authenticate as User A
    user_a_result = MagicMock()
    user_a_result.scalar_one_or_none.return_value = sample_user
    mock_db.execute = AsyncMock(return_value=user_a_result)

    token_a = create_access_token(sample_user.id)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client_a:
        # 1. User A tries to pass User B's ID in body -> Rejected with 422
        attack_response = await client_a.patch(
            "/api/v1/users/me/settings",
            headers=headers_a,
            json={
                "userId": str(user_b_id),
                "defaultDifficulty": "advanced",
            },
        )
        assert attack_response.status_code == 422

        # 2. Legitimate update from User A modifies only User A's settings
        update_response = await client_a.patch(
            "/api/v1/users/me/settings",
            headers=headers_a,
            json={"defaultDifficulty": "advanced"},
        )
        assert update_response.status_code == 200
        assert update_response.json()["userId"] == str(sample_user.id)
        assert sample_settings.default_difficulty == "advanced"

        # User B's settings remain completely untouched
        assert user_b_settings.default_difficulty == "beginner"


# ==============================================================================
# Authentication & Resilience Tests (Scenarios 19 - 22)
# ==============================================================================


@pytest.mark.anyio
async def test_get_settings_unauthenticated_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """Scenario 19: Unauthenticated GET returns HTTP 401."""
    response = await client.get("/api/v1/users/me/settings")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


@pytest.mark.anyio
async def test_patch_settings_unauthenticated_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """Scenario 20: Unauthenticated PATCH returns HTTP 401."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        json={"defaultDifficulty": "advanced"},
    )

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


@pytest.mark.anyio
async def test_settings_inactive_user_returns_403(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Scenario 21: Inactive users receive HTTP 403 Forbidden on both GET and PATCH."""
    sample_user.is_active = False

    get_resp = await client.get("/api/v1/users/me/settings", headers=auth_headers)
    assert get_resp.status_code == 403
    assert get_resp.json()["detail"] == "Inactive user account"

    patch_resp = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={"defaultDifficulty": "advanced"},
    )
    assert patch_resp.status_code == 403
    assert patch_resp.json()["detail"] == "Inactive user account"


@pytest.mark.anyio
async def test_patch_settings_database_failure_triggers_rollback(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    mock_db: AsyncMock,
) -> None:
    """Scenario 22: Database commit failure triggers safe transaction rollback."""
    mock_db.commit = AsyncMock(
        side_effect=OperationalError("connection lost", {}, Exception("DB down"))
    )

    with pytest.raises(OperationalError):
        await client.patch(
            "/api/v1/users/me/settings",
            headers=auth_headers,
            json={"defaultDifficulty": "advanced"},
        )

    mock_db.rollback.assert_awaited_once()


@pytest.mark.anyio
@pytest.mark.parametrize("field_name", ["defaultDifficulty", "defaultQuestionCount", "preferredFocus"])
async def test_patch_settings_null_values_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    field_name: str,
) -> None:
    """Edge Case: Explicit null values for settings fields are rejected with 422."""
    response = await client.patch(
        "/api/v1/users/me/settings",
        headers=auth_headers,
        json={field_name: None},
    )

    assert response.status_code == 422
    assert "cannot be null" in response.text
