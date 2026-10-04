"""Unit Tests for Authentication Route Dependencies.

Verifies OAuth2 bearer scheme configuration, token validation, user retrieval,
active account enforcement, and safe HTTP exception mapping without live database.
"""

from datetime import timedelta
import inspect
from typing import Annotated
import uuid
from unittest.mock import AsyncMock, MagicMock

import fastapi.params
import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException, status
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
)
from app.modules.auth.dependencies import (
    get_credentials_exception,
    get_current_active_user,
    get_current_user,
    oauth2_scheme,
)
# Import all ORM models so that SQLAlchemy's declarative registry resolves relationships
from app.modules.auth.models import User
from app.modules.users.models import UserSettings  # noqa: F401
from app.modules.experiments.models import Experiment, PreparationChecklist  # noqa: F401
from app.modules.viva.models import VivaSession, VivaAnswer  # noqa: F401
from app.modules.documents.models import UploadedDocument  # noqa: F401


# ==============================================================================
# Test Fixtures & Helpers
# ==============================================================================


@pytest.fixture
def test_user_id() -> uuid.UUID:
    """Return a deterministic or fresh UUID for test user."""
    return uuid.uuid4()


@pytest.fixture
def active_user(test_user_id: uuid.UUID) -> User:
    """Return an active User model instance for testing."""
    return User(
        id=test_user_id,
        email="student@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash$digest",
        full_name="Alice Student",
        university="State University",
        is_active=True,
    )


@pytest.fixture
def inactive_user(test_user_id: uuid.UUID) -> User:
    """Return an inactive User model instance for testing."""
    return User(
        id=test_user_id,
        email="inactive@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$dummyhash$digest",
        full_name="Bob Suspended",
        is_active=False,
    )


def create_mock_db(user: User | None = None) -> AsyncMock:
    """Create a mock AsyncSession returning the given user or None."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_result
    return mock_db


# ==============================================================================
# OAuth2 Scheme & Direct Dependency Tests
# ==============================================================================


def test_oauth2_scheme_uses_expected_token_url():
    """Case 1: OAuth2PasswordBearer is configured with /api/v1/auth/login."""
    settings = get_settings()
    expected_url = f"{settings.API_V1_STR}/auth/login"

    assert oauth2_scheme.model.flows.password.tokenUrl == expected_url
    assert expected_url == "/api/v1/auth/login"


@pytest.mark.asyncio
async def test_valid_access_token_resolves_existing_user(active_user: User):
    """Case 2: Valid access token resolves an existing user from the database."""
    token = create_access_token(active_user.id)
    mock_db = create_mock_db(active_user)

    resolved_user = await get_current_user(token=token, db=mock_db)

    assert resolved_user == active_user
    assert resolved_user.id == active_user.id
    assert resolved_user.email == active_user.email
    assert mock_db.execute.called


@pytest.mark.asyncio
async def test_valid_uuid_subject_is_converted_and_queried_correctly(active_user: User):
    """Case 3: Subject string from token is converted into UUID and queried."""
    token = create_access_token(str(active_user.id))
    mock_db = create_mock_db(active_user)

    resolved = await get_current_user(token=token, db=mock_db)
    assert resolved.id == active_user.id

    # Verify query was executed
    assert mock_db.execute.await_count == 1
    call_args = mock_db.execute.call_args[0]
    stmt = call_args[0]
    assert stmt.is_select


@pytest.mark.asyncio
async def test_missing_user_returns_http_401(test_user_id: uuid.UUID):
    """Case 4: Valid token whose user does not exist in database raises HTTP 401."""
    token = create_access_token(test_user_id)
    mock_db = create_mock_db(user=None)  # No user found

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"
    assert exc_info.value.detail == "Could not validate credentials"


@pytest.mark.asyncio
async def test_expired_token_returns_http_401(active_user: User):
    """Case 5: Expired token raises HTTP 401."""
    expired_token = create_access_token(active_user.id, expires_delta=timedelta(seconds=-10))
    mock_db = create_mock_db(active_user)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=expired_token, db=mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"
    assert exc_info.value.detail == "Could not validate credentials"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_invalid_signature_returns_http_401(active_user: User):
    """Case 6: Token signed with a foreign key raises HTTP 401."""
    foreign_settings = Settings(JWT_SECRET_KEY=SecretStr("foreign-secret-key-32chars-minimum-len"))
    foreign_token = create_access_token(active_user.id, settings=foreign_settings)
    mock_db = create_mock_db(active_user)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=foreign_token, db=mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_malformed_token_returns_http_401(active_user: User):
    """Case 7: Malformed token string raises HTTP 401."""
    mock_db = create_mock_db(active_user)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token="not.a.valid.jwt", db=mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_refresh_token_rejected_by_current_user_dependency(active_user: User):
    """Case 8: Refresh token supplied to get_current_user is rejected with HTTP 401."""
    refresh_token = create_refresh_token(active_user.id)
    mock_db = create_mock_db(active_user)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=refresh_token, db=mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_missing_subject_is_rejected(active_user: User):
    """Case 9: Token missing subject claim raises HTTP 401."""
    import jwt
    from datetime import datetime, timezone
    settings = get_settings()
    now = datetime.now(timezone.utc)
    token_without_sub = jwt.encode(
        {"type": "access", "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=15)).timestamp())},
        settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=settings.JWT_ALGORITHM,
    )
    mock_db = create_mock_db(active_user)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token_without_sub, db=mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_invalid_uuid_subject_is_rejected(active_user: User):
    """Case 10: Token with non-UUID subject raises HTTP 401."""
    token_bad_uuid = create_access_token("not-a-valid-uuid-identifier")
    mock_db = create_mock_db(active_user)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token_bad_uuid, db=mock_db)

    assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
    assert exc_info.value.headers.get("WWW-Authenticate") == "Bearer"
    assert not mock_db.execute.called


# ==============================================================================
# Active User Dependency Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_active_user_returned_successfully(active_user: User):
    """Case 14: Active user passes get_current_active_user without error."""
    result = await get_current_active_user(current_user=active_user)
    assert result == active_user
    assert result.is_active is True


@pytest.mark.asyncio
async def test_inactive_user_returns_http_403(inactive_user: User):
    """Case 15: Inactive user raises HTTP 403 Forbidden."""
    with pytest.raises(HTTPException) as exc_info:
        await get_current_active_user(current_user=inactive_user)

    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert exc_info.value.detail == "Inactive user account"


@pytest.mark.asyncio
async def test_inactive_user_rejection_does_not_modify_user_record(inactive_user: User):
    """Case 16: Rejecting inactive user does not alter any attributes on the instance."""
    initial_id = inactive_user.id
    initial_email = inactive_user.email
    initial_active = inactive_user.is_active

    with pytest.raises(HTTPException):
        await get_current_active_user(current_user=inactive_user)

    assert inactive_user.id == initial_id
    assert inactive_user.email == initial_email
    assert inactive_user.is_active == initial_active
    assert inactive_user.is_active is False


def test_database_session_obtained_through_existing_dependency():
    """Case 17: get_current_user specifies get_db as its database session dependency."""
    sig = inspect.signature(get_current_user)
    assert "db" in sig.parameters

    type_hint = get_current_user.__annotations__.get("db")
    assert type_hint is not None

    metadata = getattr(type_hint, "__metadata__", [])
    depends_instances = [m for m in metadata if isinstance(m, fastapi.params.Depends)]
    assert len(depends_instances) == 1
    assert depends_instances[0].dependency == get_db


@pytest.mark.asyncio
async def test_unexpected_database_failure_propagates_unaltered(active_user: User):
    """Case 18: Unexpected database failures bubble up directly rather than masking as 401."""
    token = create_access_token(active_user.id)
    mock_db = AsyncMock()
    mock_db.execute.side_effect = RuntimeError("Database connection suddenly dropped")

    with pytest.raises(RuntimeError) as exc_info:
        await get_current_user(token=token, db=mock_db)

    assert "Database connection suddenly dropped" in str(exc_info.value)


# ==============================================================================
# FastAPI Integration via AsyncClient (HTTP Layer Verification)
# ==============================================================================


@pytest.fixture
def auth_test_app(active_user: User, inactive_user: User) -> FastAPI:
    """Create a lightweight test FastAPI application using auth dependencies."""
    app = FastAPI()

    # Route requiring any authenticated user
    @app.get("/api/v1/test/me")
    async def get_me(user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
        return {"id": str(user.id), "email": user.email}

    # Route requiring an active authenticated user
    @app.get("/api/v1/test/active-me")
    async def get_active_me(user: Annotated[User, Depends(get_current_active_user)]) -> dict[str, str]:
        return {"id": str(user.id), "email": user.email, "status": "active"}

    return app


@pytest.mark.asyncio
async def test_missing_bearer_credentials_returns_http_401(auth_test_app: FastAPI):
    """Case 11 & 12: Missing Authorization header returns HTTP 401 with WWW-Authenticate header."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/test/me")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_http_endpoint_with_valid_token_succeeds(
    auth_test_app: FastAPI,
    active_user: User,
):
    """Protected endpoint returns HTTP 200 with valid bearer access token."""
    mock_db = create_mock_db(active_user)
    auth_test_app.dependency_overrides[get_db] = lambda: mock_db

    token = create_access_token(active_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/test/me", headers=headers)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"id": str(active_user.id), "email": active_user.email}

    auth_test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_http_active_endpoint_rejects_inactive_user_with_403(
    auth_test_app: FastAPI,
    inactive_user: User,
):
    """Active-only endpoint rejects inactive user with HTTP 403 Forbidden."""
    mock_db = create_mock_db(inactive_user)
    auth_test_app.dependency_overrides[get_db] = lambda: mock_db

    token = create_access_token(inactive_user.id)
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/test/active-me", headers=headers)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Inactive user account"

    auth_test_app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_error_responses_do_not_expose_cryptographic_details(
    auth_test_app: FastAPI,
    active_user: User,
):
    """Case 13: 401 error responses contain only generic safe details."""
    mock_db = create_mock_db(active_user)
    auth_test_app.dependency_overrides[get_db] = lambda: mock_db

    invalid_token_header = {"Authorization": "Bearer not-a-valid-token"}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=auth_test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/test/me", headers=invalid_token_header)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Could not validate credentials"
    assert "jwt" not in response.text.lower()
    assert "secret" not in response.text.lower()
    assert "traceback" not in response.text.lower()

    auth_test_app.dependency_overrides.clear()
