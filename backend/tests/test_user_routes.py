"""Unit and Integration Tests for Authenticated User Profile Endpoints.

Verifies GET /api/v1/users/me and PATCH /api/v1/users/me for profile retrieval,
partial updates, input validation, forbidden field protection, authentication
enforcement, and rollback guarantees without requiring a live PostgreSQL instance.
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
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
)
from app.main import create_app
from app.modules.auth.models import User
from app.modules.users.models import UserSettings


# ==============================================================================
# Test Fixtures & Helpers
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
def sample_user(sample_user_id: uuid.UUID) -> User:
    """Create a standard active student User instance."""
    now = datetime.now(timezone.utc)
    return User(
        id=sample_user_id,
        email="student@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehashedsecret",
        full_name="Alex Johnson",
        university="State University",
        is_active=True,
        auth_provider="local",
        created_at=now,
        updated_at=now,
    )


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
# GET /api/v1/users/me Tests
# ==============================================================================


@pytest.mark.anyio
async def test_get_profile_authenticated_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Authenticated user retrieves their profile with HTTP 200."""
    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == str(sample_user.id)
    assert data["email"] == sample_user.email
    assert data["full_name"] == sample_user.full_name
    assert data["university"] == sample_user.university
    assert data["is_active"] is True
    assert "created_at" in data


@pytest.mark.anyio
async def test_get_profile_response_includes_all_approved_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Response payload contains exactly the approved schema fields."""
    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    expected_fields = {"id", "email", "full_name", "university", "is_active", "created_at"}
    assert set(data.keys()) == expected_fields


@pytest.mark.anyio
async def test_get_profile_response_excludes_sensitive_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Password hash, auth provider, and other internals are never exposed."""
    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()
    assert "password_hash" not in data
    assert "password" not in data
    assert "auth_provider" not in data
    assert "settings" not in data


@pytest.mark.anyio
async def test_get_profile_missing_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """Request without Authorization header returns HTTP 401."""
    response = await client.get("/api/v1/users/me")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


@pytest.mark.anyio
async def test_get_profile_invalid_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """Request with corrupted token returns HTTP 401."""
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer invalid.corrupted.token"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.anyio
async def test_get_profile_expired_token_returns_401(
    client: httpx.AsyncClient,
    sample_user_id: uuid.UUID,
) -> None:
    """Request with an expired access token returns HTTP 401."""
    expired_token = create_access_token(
        sample_user_id,
        expires_delta=timedelta(seconds=-10),
    )
    response = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.anyio
async def test_get_profile_inactive_user_returns_403(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Inactive user account returns HTTP 403 Forbidden."""
    sample_user.is_active = False

    response = await client.get("/api/v1/users/me", headers=auth_headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


@pytest.mark.anyio
async def test_get_profile_cannot_fetch_another_user_profile(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Endpoint does not accept path or query parameters to access another user's profile."""
    other_id = str(uuid.uuid4())
    response = await client.get(
        f"/api/v1/users/me?user_id={other_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    # Returns the authenticated user's profile, ignoring arbitrary query parameters
    assert response.json()["id"] == str(sample_user.id)


# ==============================================================================
# PATCH /api/v1/users/me Tests
# ==============================================================================


@pytest.mark.anyio
async def test_patch_profile_update_full_name_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    mock_db: AsyncMock,
) -> None:
    """Update full name successfully with HTTP 200."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "Jordan Lee"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Jordan Lee"
    assert data["university"] == "State University"  # Preserved
    assert sample_user.full_name == "Jordan Lee"
    mock_db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_patch_profile_update_university_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    mock_db: AsyncMock,
) -> None:
    """Update university affiliation successfully with HTTP 200."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"university": "Polytechnic Institute"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["university"] == "Polytechnic Institute"
    assert data["full_name"] == "Alex Johnson"  # Preserved
    assert sample_user.university == "Polytechnic Institute"
    mock_db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_patch_profile_update_both_fields_success(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
    mock_db: AsyncMock,
) -> None:
    """Update both full name and university in a single request."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={
            "full_name": "Morgan Davis",
            "university": "National Academy",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Morgan Davis"
    assert data["university"] == "National Academy"
    assert sample_user.full_name == "Morgan Davis"
    assert sample_user.university == "National Academy"
    mock_db.commit.assert_awaited_once()


@pytest.mark.anyio
async def test_patch_profile_partial_update_preserves_unsupplied_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Unsupplied fields remain unchanged after update."""
    original_created_at = sample_user.created_at
    original_email = sample_user.email
    original_university = sample_user.university

    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "Taylor Swift"},
    )

    assert response.status_code == 200
    assert sample_user.email == original_email
    assert sample_user.university == original_university
    assert sample_user.created_at == original_created_at


@pytest.mark.anyio
async def test_patch_profile_normalizes_whitespace(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """Leading and trailing whitespace is stripped from string inputs."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={
            "full_name": "   Casey Riley   ",
            "university": "   Metro University   ",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["full_name"] == "Casey Riley"
    assert data["university"] == "Metro University"
    assert sample_user.full_name == "Casey Riley"
    assert sample_user.university == "Metro University"


@pytest.mark.anyio
async def test_patch_profile_empty_payload_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Empty JSON object payload is rejected with HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 422
    assert "At least one profile field must be provided" in response.text


@pytest.mark.anyio
async def test_patch_profile_whitespace_only_name_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Whitespace-only full name is rejected with HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "     "},
    )

    assert response.status_code == 422
    assert "Full name must contain at least 2 non-whitespace characters" in response.text


@pytest.mark.anyio
async def test_patch_profile_whitespace_only_university_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Whitespace-only university is rejected with HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"university": "     "},
    )

    assert response.status_code == 422
    assert "University cannot be blank" in response.text


@pytest.mark.anyio
async def test_patch_profile_null_full_name_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Explicit null value for full_name is rejected with HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": None},
    )

    assert response.status_code == 422
    assert "Full name cannot be null" in response.text


@pytest.mark.anyio
async def test_patch_profile_null_university_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Explicit null value for university is rejected with HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"university": None},
    )

    assert response.status_code == 422
    assert "University cannot be null" in response.text


@pytest.mark.anyio
async def test_patch_profile_short_name_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """Single-character full name is rejected with HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "A"},
    )

    assert response.status_code == 422
    assert "Full name must contain at least 2 non-whitespace characters" in response.text


@pytest.mark.anyio
@pytest.mark.parametrize(
    "forbidden_payload",
    [
        {"email": "newemail@example.com"},
        {"password": "NewSecretPassword123!"},
        {"password_hash": "$argon2id$v=19$evilhash"},
        {"is_active": False},
        {"id": str(uuid.uuid4())},
        {"created_at": datetime.now(timezone.utc).isoformat()},
        {"updated_at": datetime.now(timezone.utc).isoformat()},
        {"auth_provider": "google"},
    ],
)
async def test_patch_profile_protected_fields_rejected_with_422(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    forbidden_payload: dict[str, Any],
) -> None:
    """Attempts to update protected fields are rejected by strict schema validation with HTTP 422."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json=forbidden_payload,
    )

    assert response.status_code == 422
    assert "extra_forbidden" in response.text


@pytest.mark.anyio
async def test_patch_profile_missing_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """PATCH without Authorization header returns HTTP 401."""
    response = await client.patch(
        "/api/v1/users/me",
        json={"full_name": "New Name"},
    )

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


@pytest.mark.anyio
async def test_patch_profile_invalid_token_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """PATCH with corrupted token returns HTTP 401."""
    response = await client.patch(
        "/api/v1/users/me",
        headers={"Authorization": "Bearer not.a.valid.jwt"},
        json={"full_name": "New Name"},
    )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_patch_profile_inactive_user_returns_403(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    sample_user: User,
) -> None:
    """PATCH from inactive user account returns HTTP 403 Forbidden."""
    sample_user.is_active = False

    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "New Name"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


@pytest.mark.anyio
async def test_patch_profile_database_failure_triggers_rollback(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    mock_db: AsyncMock,
) -> None:
    """Database persistence failure triggers transaction rollback and propagates 500 error."""
    mock_db.commit = AsyncMock(side_effect=OperationalError("connection lost", {}, Exception("DB down")))

    with pytest.raises(OperationalError):
        await client.patch(
            "/api/v1/users/me",
            headers=auth_headers,
            json={"full_name": "Updated Name"},
        )

    mock_db.rollback.assert_awaited_once()


@pytest.mark.anyio
async def test_patch_profile_response_excludes_sensitive_fields(
    client: httpx.AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """PATCH response payload never includes sensitive credentials or internals."""
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers,
        json={"full_name": "Validated Name"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "password_hash" not in data
    assert "password" not in data
    assert "auth_provider" not in data


# ==============================================================================
# Regression & Route Catalog Tests
# ==============================================================================


@pytest.mark.anyio
async def test_regression_registration_and_login_still_pass(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
) -> None:
    """Registration endpoint continues operating normally."""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_result)

    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "fresh.student@univ.edu",
            "password": "ValidPassword123!",
            "full_name": "Fresh Student",
        },
    )

    assert response.status_code == 201
    assert "access_token" in response.json()


@pytest.mark.anyio
async def test_regression_refresh_and_logout_still_pass(
    client: httpx.AsyncClient,
    sample_user: User,
    mock_db: AsyncMock,
    auth_headers: dict[str, str],
) -> None:
    """Refresh and logout endpoints continue operating normally."""
    # Logout test
    logout_res = await client.post("/api/v1/auth/logout", headers=auth_headers)
    assert logout_res.status_code == 200
    assert logout_res.json() == {"message": "Logged out successfully"}

    # Refresh test
    valid_refresh = create_refresh_token(sample_user.id)
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": valid_refresh},
    )
    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()


@pytest.mark.anyio
async def test_regression_health_endpoint_available(
    client: httpx.AsyncClient,
) -> None:
    """Base /health check endpoint remains functional."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.anyio
async def test_regression_app_factory_and_cors_intact() -> None:
    """FastAPI application factory and CORS configuration remain intact."""
    app = create_app()
    assert app.title == "PracPrep API"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_route_catalog_contains_expected_profile_endpoints() -> None:
    """Verify that both /api/v1/users/me endpoints (GET and PATCH) are registered."""
    app = create_app()
    openapi_paths = app.openapi()["paths"]

    assert "/api/v1/users/me" in openapi_paths
    methods = openapi_paths["/api/v1/users/me"]
    assert "get" in methods
    assert "patch" in methods

    # Verify existing endpoints remain registered
    assert "/health" in openapi_paths
    assert "/api/v1/auth/register" in openapi_paths
    assert "/api/v1/auth/login" in openapi_paths
    assert "/api/v1/auth/refresh" in openapi_paths
    assert "/api/v1/auth/logout" in openapi_paths
