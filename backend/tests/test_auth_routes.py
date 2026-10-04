"""Unit and Integration Tests for Registration & Login Endpoints.

Verifies user registration, Argon2id hashing, default settings provisioning,
atomic transactions, login verification, error obfuscation, and route registration
without requiring a live PostgreSQL instance.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
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
def client(mock_db: AsyncMock) -> httpx.AsyncClient:
    """Create an asynchronous HTTP test client with database dependency override."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def existing_hashed_user(sample_user_id: uuid.UUID) -> User:
    """Return a pre-existing User model with known Argon2id password hash."""
    return User(
        id=sample_user_id,
        email="registered.student@university.edu",
        password_hash=hash_password("ValidPassword123!"),
        full_name="Registered Student",
        university="State University",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


# ==============================================================================
# Registration Endpoint Tests (Cases 1 - 12)
# ==============================================================================


@pytest.mark.asyncio
async def test_successful_registration_creates_user(client: httpx.AsyncClient, mock_db: AsyncMock):
    """Case 1 & 4: Successful registration creates a user and returns valid tokens."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # No existing user
    mock_db.execute.return_value = mock_res

    payload = {
        "email": "new.student@university.edu",
        "password": "StrongPassword2026!",
        "full_name": "New Student",
        "university": "Tech Institute",
    }

    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 15 * 60
    assert data["user"]["email"] == "new.student@university.edu"
    assert data["user"]["full_name"] == "New Student"
    assert data["user"]["university"] == "Tech Institute"
    assert data["user"]["is_active"] is True
    assert mock_db.commit.called


@pytest.mark.asyncio
async def test_password_stored_as_argon2id_hash_not_plaintext(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 2: Password is stored as an Argon2id hash and plaintext never persisted."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    plain_pass = "SuperSecretPassword123!"
    payload = {
        "email": "argon.test@university.edu",
        "password": plain_pass,
        "full_name": "Argon Tester",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    # Inspect the User instance added to session
    added_objects = [call[0][0] for call in mock_db.add.call_args_list]
    users_added = [obj for obj in added_objects if isinstance(obj, User)]
    assert len(users_added) == 1
    user_instance = users_added[0]

    assert user_instance.password_hash != plain_pass
    assert user_instance.password_hash.startswith("$argon2id$")
    assert verify_password(plain_pass, user_instance.password_hash) is True


@pytest.mark.asyncio
async def test_default_user_settings_are_provisioned(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 3: Default UserSettings entity is created and linked to the new user."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    payload = {
        "email": "settings.test@university.edu",
        "password": "Password123!",
        "full_name": "Settings Tester",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    added_objects = [call[0][0] for call in mock_db.add.call_args_list]
    settings_added = [obj for obj in added_objects if isinstance(obj, UserSettings)]
    assert len(settings_added) == 1
    settings_instance = settings_added[0]

    # Verify link and default preferences
    users_added = [obj for obj in added_objects if isinstance(obj, User)]
    assert settings_instance.user == users_added[0]
    assert settings_instance.default_difficulty == "medium"
    assert settings_instance.default_question_count == 5
    assert settings_instance.preferred_focus == "all"


@pytest.mark.asyncio
async def test_registration_returns_valid_distinguishable_tokens(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 4: Registration tokens are valid decodable access and refresh JWTs."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    payload = {
        "email": "tokens.test@university.edu",
        "password": "TokenPassword123!",
        "full_name": "Token Tester",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    data = response.json()

    access_payload = decode_access_token(data["access_token"])
    refresh_payload = decode_refresh_token(data["refresh_token"])

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == str(data["user"]["id"])
    assert refresh_payload["sub"] == str(data["user"]["id"])


@pytest.mark.asyncio
async def test_returned_user_data_excludes_password_hashes(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 5: Response JSON contains no password, password_hash, or secret fields."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    payload = {
        "email": "leak.test@university.edu",
        "password": "SecretPassword123!",
        "full_name": "Leak Check",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    raw_text = response.text.lower()

    assert "password_hash" not in raw_text
    assert "argon2id" not in raw_text
    assert "secretpassword123!" not in raw_text


@pytest.mark.asyncio
async def test_email_is_normalized_consistently(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 6: Registration normalizes email to lowercase and strips surrounding whitespace."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    payload = {
        "email": "   MiXeD.CaSe@UniVerSiTy.Edu   ",
        "password": "Password123!",
        "full_name": "Case Tester",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "mixed.case@university.edu"


@pytest.mark.asyncio
async def test_duplicate_email_returns_http_409(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 7: Registering with an existing email returns HTTP 409 Conflict."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    payload = {
        "email": existing_hashed_user.email,
        "password": "SomeOtherPassword123!",
        "full_name": "Duplicate Attempt",
    }

    response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]
    assert not mock_db.commit.called


@pytest.mark.asyncio
async def test_invalid_email_is_rejected_with_422(client: httpx.AsyncClient):
    """Case 8: Invalid email format is rejected with HTTP 422 Unprocessable Entity."""
    invalid_emails = ["not-an-email", "user@", "@domain.com", "user@domain", ""]

    for bad_email in invalid_emails:
        payload = {
            "email": bad_email,
            "password": "ValidPassword123!",
            "full_name": "Invalid Email",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_empty_or_short_password_rejected_with_422(client: httpx.AsyncClient):
    """Case 9: Passwords shorter than 8 characters are rejected with HTTP 422."""
    for bad_pass in ["", "short", "1234567"]:
        payload = {
            "email": "user@university.edu",
            "password": bad_pass,
            "full_name": "Short Password",
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_blank_full_name_rejected_with_422(client: httpx.AsyncClient):
    """Case 10: Blank or single-character full name is rejected with HTTP 422."""
    for bad_name in ["", " ", "   ", "a"]:
        payload = {
            "email": "user@university.edu",
            "password": "ValidPassword123!",
            "full_name": bad_name,
        }
        response = await client.post("/api/v1/auth/register", json=payload)
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_settings_failure_rolls_back_user_creation(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 11: Database failure on commit triggers rollback ensuring atomic registration."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res
    mock_db.commit.side_effect = IntegrityError("settings_fk_fail", None, Exception())

    payload = {
        "email": "rollback.test@university.edu",
        "password": "Password123!",
        "full_name": "Rollback Tester",
    }

    response = await client.post("/api/v1/auth/register", json=payload)

    # Caught IntegrityError translates to safe conflict error and rollback
    assert response.status_code == 409
    assert mock_db.rollback.called


@pytest.mark.asyncio
async def test_database_failures_do_not_expose_internal_details(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 12: Internal database crashes rollback and bubble without leaking SQL in response."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res
    mock_db.commit.side_effect = OperationalError("SELECT * FROM internal_leak", None, Exception())

    payload = {
        "email": "dbfail.test@university.edu",
        "password": "Password123!",
        "full_name": "DB Fail Tester",
    }

    with pytest.raises(OperationalError):
        await client.post("/api/v1/auth/register", json=payload)

    assert mock_db.rollback.called


# ==============================================================================
# Login Endpoint Tests (Cases 13 - 20)
# ==============================================================================


@pytest.mark.asyncio
async def test_valid_credentials_return_tokens_and_user_data(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 13: Valid email and password return 200 with tokens and user object."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    login_payload = {
        "email": existing_hashed_user.email,
        "password": "ValidPassword123!",
    }

    response = await client.post("/api/v1/auth/login", json=login_payload)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == existing_hashed_user.email
    assert data["user"]["id"] == str(existing_hashed_user.id)


@pytest.mark.asyncio
async def test_incorrect_password_returns_http_401(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 14: Incorrect password returns HTTP 401 with generic error."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    login_payload = {
        "email": existing_hashed_user.email,
        "password": "WrongPassword999!",
    }

    response = await client.post("/api/v1/auth/login", json=login_payload)

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_unknown_email_returns_identical_generic_error(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 15: Unknown email returns identical 401 without revealing non-existence."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # No matching user
    mock_db.execute.return_value = mock_res

    login_payload = {
        "email": "nonexistent@university.edu",
        "password": "AnyPassword123!",
    }

    response = await client.post("/api/v1/auth/login", json=login_payload)

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Incorrect email or password"


@pytest.mark.asyncio
async def test_inactive_user_is_rejected_with_403(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 16: Inactive account with valid credentials is rejected with HTTP 403."""
    existing_hashed_user.is_active = False
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    login_payload = {
        "email": existing_hashed_user.email,
        "password": "ValidPassword123!",
    }

    response = await client.post("/api/v1/auth/login", json=login_payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


@pytest.mark.asyncio
async def test_login_email_normalization(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 17: Login email is stripped and lowercased before lookup."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    login_payload = {
        "email": f"  {existing_hashed_user.email.upper()}  ",
        "password": "ValidPassword123!",
    }

    response = await client.post("/api/v1/auth/login", json=login_payload)
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_password_verification_uses_security_utility(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 18: Password verification is compatible with security.verify_password."""
    assert verify_password("ValidPassword123!", existing_hashed_user.password_hash) is True
    assert verify_password("WrongPassword123!", existing_hashed_user.password_hash) is False


@pytest.mark.asyncio
async def test_login_returned_user_excludes_sensitive_fields(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 19: Login response data excludes password hashes and internals."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": existing_hashed_user.email, "password": "ValidPassword123!"},
    )
    raw_text = response.text.lower()
    assert "password_hash" not in raw_text
    assert "argon2id" not in raw_text


@pytest.mark.asyncio
async def test_database_failures_on_login_not_masked_as_auth_failure(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 20: Database connectivity errors bubble up and are not masked as 401."""
    mock_db.execute.side_effect = OperationalError("connection refused", None, Exception())

    login_payload = {
        "email": "anyone@university.edu",
        "password": "Password123!",
    }

    with pytest.raises(OperationalError):
        await client.post("/api/v1/auth/login", json=login_payload)


# ==============================================================================
# Token Refresh Endpoint Tests (Cases 25 - 35)
# ==============================================================================


@pytest.mark.asyncio
async def test_valid_refresh_token_returns_new_access_token(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 25: Valid refresh token issues a new 15-minute access token."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    refresh_token = create_refresh_token(existing_hashed_user.id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 15 * 60
    assert data["refresh_token"] == refresh_token


@pytest.mark.asyncio
async def test_returned_access_token_can_be_decoded_successfully(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 26: The newly issued access token decodes and verifies with correct claims."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    refresh_token = create_refresh_token(existing_hashed_user.id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    data = response.json()
    decoded = decode_access_token(data["access_token"])
    assert decoded["sub"] == str(existing_hashed_user.id)
    assert decoded["type"] == "access"


@pytest.mark.asyncio
async def test_refresh_token_remains_valid_and_is_not_rotated(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 27: Refresh token validity is preserved without rotation."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    initial_refresh = create_refresh_token(existing_hashed_user.id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": initial_refresh},
    )

    assert response.json()["refresh_token"] == initial_refresh
    # Verifies the submitted refresh token can still be decoded cleanly
    decoded = decode_refresh_token(initial_refresh)
    assert decoded["sub"] == str(existing_hashed_user.id)


@pytest.mark.asyncio
async def test_access_token_supplied_as_refresh_token_is_rejected_with_401(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 28: Using an access token in place of a refresh token is rejected with HTTP 401."""
    access_token = create_access_token(existing_hashed_user.id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Could not validate credentials"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_expired_refresh_token_is_rejected_with_401(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 29: Expired refresh token is rejected with HTTP 401."""
    expired_refresh = create_refresh_token(
        existing_hashed_user.id,
        expires_delta=timedelta(seconds=-10),
    )
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": expired_refresh},
    )

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Could not validate credentials"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_malformed_refresh_token_is_rejected_with_401(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 30: Malformed refresh token is rejected with HTTP 401."""
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "not.a.valid.jwt"},
    )

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_invalid_uuid_subject_in_refresh_token_rejected_with_401(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case 31: Refresh token with a non-UUID subject claim raises HTTP 401."""
    bad_uuid_token = create_refresh_token("non-uuid-string")
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": bad_uuid_token},
    )

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert not mock_db.execute.called


@pytest.mark.asyncio
async def test_nonexistent_user_on_refresh_rejected_with_401(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    sample_user_id: uuid.UUID,
):
    """Case 32: Valid refresh token for a deleted/nonexistent user raises HTTP 401."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None  # User not found in DB
    mock_db.execute.return_value = mock_res

    refresh_token = create_refresh_token(sample_user_id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
async def test_inactive_user_on_refresh_rejected_with_403(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 33: Refresh token for a deactivated account is rejected with HTTP 403."""
    existing_hashed_user.is_active = False
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    refresh_token = create_refresh_token(existing_hashed_user.id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "User account is inactive"


@pytest.mark.asyncio
async def test_database_failure_on_refresh_propagates(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 34: Unexpected database failures on refresh bubble up and are not masked as 401."""
    mock_db.execute.side_effect = OperationalError("connection dropped", None, Exception())

    refresh_token = create_refresh_token(existing_hashed_user.id)
    with pytest.raises(OperationalError):
        await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )


@pytest.mark.asyncio
async def test_refresh_response_does_not_expose_sensitive_internals(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 35: Refresh response body exposes only standard token response fields."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    refresh_token = create_refresh_token(existing_hashed_user.id)
    response = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    raw_text = response.text.lower()
    assert "password" not in raw_text
    assert "secret" not in raw_text
    assert "traceback" not in raw_text


# ==============================================================================
# Logout Endpoint Tests (Cases 36 - 42)
# ==============================================================================


@pytest.mark.asyncio
async def test_authenticated_user_logout_succeeds_with_200(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 36: Authenticated active user receives HTTP 200 with confirmation message."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    access_token = create_access_token(existing_hashed_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"message": "Logged out successfully"}


@pytest.mark.asyncio
async def test_missing_authorization_token_on_logout_rejected_with_401(
    client: httpx.AsyncClient,
):
    """Case 37: Unauthenticated request to logout returns HTTP 401 with challenge header."""
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_invalid_or_expired_access_token_on_logout_rejected_with_401(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 38: Expired access token on logout is rejected with HTTP 401."""
    expired_token = create_access_token(
        existing_hashed_user.id,
        expires_delta=timedelta(seconds=-10),
    )
    headers = {"Authorization": f"Bearer {expired_token}"}

    response = await client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 401
    assert response.headers.get("WWW-Authenticate") == "Bearer"
    assert response.json()["detail"] == "Could not validate credentials"


@pytest.mark.asyncio
async def test_inactive_user_on_logout_rejected_with_403(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 39: Deactivated account is rejected with HTTP 403 on logout."""
    existing_hashed_user.is_active = False
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    access_token = create_access_token(existing_hashed_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post("/api/v1/auth/logout", headers=headers)

    assert response.status_code == 403
    assert response.json()["detail"] == "Inactive user account"


@pytest.mark.asyncio
async def test_logout_does_not_modify_user_record(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    existing_hashed_user: User,
):
    """Case 40: Logout does not alter or delete the user record or trigger DB commits."""
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_hashed_user
    mock_db.execute.return_value = mock_res

    initial_email = existing_hashed_user.email
    initial_active = existing_hashed_user.is_active

    access_token = create_access_token(existing_hashed_user.id)
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await client.post("/api/v1/auth/logout", headers=headers)
    assert response.status_code == 200

    assert existing_hashed_user.email == initial_email
    assert existing_hashed_user.is_active == initial_active
    assert not mock_db.commit.called
    assert not mock_db.delete.called


def test_logout_stateless_architecture_contract(existing_hashed_user: User):
    """Case 41: Documents that logout relies on client disposal without server revocation."""
    # The token remains cryptographically valid until expiration since PracPrep uses stateless JWTs
    token = create_access_token(existing_hashed_user.id)
    decoded = decode_access_token(token)
    assert decoded["sub"] == str(existing_hashed_user.id)


# ==============================================================================
# Application Integration Tests (Cases 21 - 24, 42)
# ==============================================================================


def test_all_auth_routes_registered_at_correct_paths():
    """Case 42: Register, login, refresh, and logout endpoints all exist at /api/v1/auth/*."""
    app = create_app()
    openapi_paths = app.openapi()["paths"]

    expected_routes = [
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
    ]

    for path in expected_routes:
        assert path in openapi_paths
        assert "post" in openapi_paths[path]


@pytest.mark.asyncio
async def test_health_endpoint_continues_to_work():
    """Case 23: Base health endpoint remains functional after router inclusion."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_application_factory_and_cors_intact():
    """Case 24: Application factory CORS behavior remains preserved."""
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "POST",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options("/api/v1/auth/login", headers=headers)

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
