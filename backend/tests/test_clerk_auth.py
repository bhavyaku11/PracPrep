"""Unit and Integration Tests for Clerk Authentication & Google OAuth Identity Sync.

Validates RS256 token verification against Clerk JWKS, tamper detection,
expired token rejection, user account provisioning, settings creation,
and zero-regression compatibility with native PracPrep JWT sessions.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clerk import (
    ClerkConfigurationError,
    ClerkTokenError,
    ClerkTokenVerifier,
    reset_clerk_verifier,
)
from app.core.config import Settings
from app.core.database import get_db
from app.core.security import create_access_token, hash_password
from app.main import create_app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.users.models import UserSettings


# ==============================================================================
# Cryptographic Test Fixtures
# ==============================================================================


@pytest.fixture(scope="module")
def rsa_key_pair():
    """Generate an RSA key pair for testing RS256 JWT tokens."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()
    return private_key, public_key


@pytest.fixture
def mock_signing_key(rsa_key_pair):
    """Return a mock PyJWK signing key matching PyJWKClient interface."""
    _, public_key = rsa_key_pair
    mock_key = MagicMock()
    mock_key.key = public_key
    mock_key.key_id = "test_key_1"
    return mock_key


@pytest.fixture
def make_clerk_token(rsa_key_pair):
    """Factory fixture for signing valid or invalid Clerk RS256 tokens."""
    private_key, _ = rsa_key_pair

    def _generate(
        sub: str = "user_clerk_12345",
        email: str = "clerk.student@university.edu",
        expires_delta: timedelta = timedelta(minutes=15),
        issuer: str = "https://elegant-rhino-8071.clerk.accounts.dev",
        key=private_key,
        algorithm: str = "RS256",
        headers: dict[str, Any] | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": sub,
            "email": email,
            "iss": issuer,
            "iat": int(now.timestamp()),
            "exp": int((now + expires_delta).timestamp()),
        }
        token_headers = {"kid": "test_key_1"}
        if headers:
            token_headers.update(headers)
        return jwt.encode(payload, key, algorithm=algorithm, headers=token_headers)

    return _generate


@pytest.fixture
def mock_db() -> AsyncMock:
    """Mock database session for route testing."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def client(mock_db: AsyncMock) -> httpx.AsyncClient:
    """HTTP client with database override."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


# ==============================================================================
# Token Verifier Unit Tests
# ==============================================================================


def test_clerk_verifier_missing_jwks_url(make_clerk_token):
    """Verifier raises ClerkConfigurationError if no JWKS URL can be derived."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.clerk_jwks_url = None
    mock_settings.clerk_issuer_url = None

    token = make_clerk_token()
    verifier = ClerkTokenVerifier(jwks_url=None, issuer=None, settings=mock_settings)
    with pytest.raises(ClerkConfigurationError):
        verifier.verify_token(token)


def test_clerk_verifier_validates_rs256_token(make_clerk_token, mock_signing_key):
    """Verifier successfully decodes and validates a compliant RS256 token."""
    token = make_clerk_token(sub="user_abc_789", email="test@clerk.dev")

    verifier = ClerkTokenVerifier(
        jwks_url="https://elegant-rhino-8071.clerk.accounts.dev/.well-known/jwks.json",
        issuer="https://elegant-rhino-8071.clerk.accounts.dev",
    )
    with patch.object(verifier, "get_jwks_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_client.return_value = mock_client

        claims = verifier.verify_token(token)
        assert claims["sub"] == "user_abc_789"
        assert claims["email"] == "test@clerk.dev"


def test_clerk_verifier_rejects_expired_token(make_clerk_token, mock_signing_key):
    """Verifier rejects expired tokens with ClerkTokenError."""
    token = make_clerk_token(expires_delta=timedelta(minutes=-10))

    verifier = ClerkTokenVerifier(
        jwks_url="https://elegant-rhino-8071.clerk.accounts.dev/.well-known/jwks.json",
        issuer="https://elegant-rhino-8071.clerk.accounts.dev",
    )
    with patch.object(verifier, "get_jwks_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_client.return_value = mock_client

        with pytest.raises(ClerkTokenError) as exc_info:
            verifier.verify_token(token)
        assert "expired" in str(exc_info.value).lower()


def test_clerk_verifier_rejects_tampered_signature(make_clerk_token, mock_signing_key):
    """Verifier rejects tokens signed with an untrusted foreign private key."""
    foreign_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    tampered_token = make_clerk_token(key=foreign_private_key)

    verifier = ClerkTokenVerifier(
        jwks_url="https://elegant-rhino-8071.clerk.accounts.dev/.well-known/jwks.json",
        issuer="https://elegant-rhino-8071.clerk.accounts.dev",
    )
    with patch.object(verifier, "get_jwks_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.get_signing_key_from_jwt.return_value = mock_signing_key
        mock_get_client.return_value = mock_client

        with pytest.raises(ClerkTokenError) as exc_info:
            verifier.verify_token(tampered_token)
        assert "invalid" in str(exc_info.value).lower()


def test_clerk_verifier_rejects_non_rs256_algorithm():
    """Verifier rejects tokens with unapproved algorithms such as HS256."""
    fake_token = jwt.encode({"sub": "attacker"}, "secret", algorithm="HS256")
    verifier = ClerkTokenVerifier(
        jwks_url="https://test.clerk.accounts.dev/.well-known/jwks.json",
        issuer="https://test.clerk.accounts.dev",
    )
    with pytest.raises(ClerkTokenError) as exc_info:
        verifier.verify_token(fake_token)
    assert "Unsupported token algorithm" in str(exc_info.value)


# ==============================================================================
# Endpoint Tests: POST /api/v1/auth/clerk-sync
# ==============================================================================


@pytest.mark.asyncio
async def test_clerk_sync_provisions_new_user_and_settings(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    make_clerk_token,
    mock_signing_key,
):
    """Case: Synchronizing a new Clerk user creates a User and default UserSettings."""
    clerk_token = make_clerk_token(
        sub="user_clerk_new_01",
        email="new.google.student@university.edu",
    )

    # Database finds no existing user
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res

    with patch("app.modules.auth.router.get_clerk_verifier") as mock_get_v:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = {
            "sub": "user_clerk_new_01",
            "email": "new.google.student@university.edu",
            "name": "Google Student",
        }
        mock_get_v.return_value = mock_verifier

        response = await client.post(
            "/api/v1/auth/clerk-sync",
            headers={"Authorization": f"Bearer {clerk_token}"},
            json={
                "full_name": "Google Student",
                "university": "Tech State",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "new.google.student@university.edu"
    assert data["user"]["full_name"] == "Google Student"
    assert data["user"]["university"] == "Tech State"

    # Verify atomic creation of User and UserSettings
    assert mock_db.add.call_count == 2
    added_entities = [call.args[0] for call in mock_db.add.call_args_list]
    user_entity = next(e for e in added_entities if isinstance(e, User))
    settings_entity = next(e for e in added_entities if isinstance(e, UserSettings))

    assert user_entity.auth_provider == "clerk:user_clerk_new_01"
    assert settings_entity.default_difficulty == "medium"
    assert settings_entity.default_question_count == 5


@pytest.mark.asyncio
async def test_clerk_sync_links_existing_user(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
    make_clerk_token,
):
    """Case: Synchronizing an existing user links the Clerk identity without resetting password."""
    user_id = uuid.uuid4()
    original_pwd = hash_password("OriginalPassword123!")
    existing_user = User(
        id=user_id,
        email="existing.student@university.edu",
        password_hash=original_pwd,
        full_name="Existing Student",
        university="State Univ",
        is_active=True,
        auth_provider="local",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = existing_user
    mock_db.execute.return_value = mock_res

    with patch("app.modules.auth.router.get_clerk_verifier") as mock_get_v:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = {
            "sub": "user_clerk_existing_02",
            "email": "existing.student@university.edu",
        }
        mock_get_v.return_value = mock_verifier

        response = await client.post(
            "/api/v1/auth/clerk-sync",
            json={
                "clerk_token": "valid.clerk.jwt",
                "email": "existing.student@university.edu",
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["user"]["email"] == "existing.student@university.edu"
    assert existing_user.auth_provider == "clerk:user_clerk_existing_02"
    assert existing_user.password_hash == original_pwd  # Preserved!


@pytest.mark.asyncio
async def test_clerk_sync_inactive_user_rejected_403(
    client: httpx.AsyncClient,
    mock_db: AsyncMock,
):
    """Case: Inactive accounts are rejected with 403 Forbidden on Clerk sync."""
    inactive_user = User(
        id=uuid.uuid4(),
        email="banned@university.edu",
        password_hash="hash",
        full_name="Banned Student",
        is_active=False,
        auth_provider="local",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = inactive_user
    mock_db.execute.return_value = mock_res

    with patch("app.modules.auth.router.get_clerk_verifier") as mock_get_v:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = {
            "sub": "user_clerk_banned",
            "email": "banned@university.edu",
        }
        mock_get_v.return_value = mock_verifier

        response = await client.post(
            "/api/v1/auth/clerk-sync",
            json={
                "clerk_token": "valid.token",
                "email": "banned@university.edu",
            },
        )

    assert response.status_code == 403
    assert "inactive" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_clerk_sync_missing_token_rejected_401(client: httpx.AsyncClient):
    """Case: Missing token in both header and body returns 401 Unauthorized."""
    response = await client.post("/api/v1/auth/clerk-sync", json={})
    assert response.status_code == 401
    assert "Missing Clerk session token" in response.json()["detail"]


# ==============================================================================
# Fallback Dependency Tests: get_current_user
# ==============================================================================


@pytest.mark.asyncio
async def test_get_current_user_with_direct_clerk_token(mock_db: AsyncMock):
    """Direct Clerk Bearer token can resolve a user in get_current_user."""
    user = User(
        id=uuid.uuid4(),
        email="oauth@univ.edu",
        password_hash="hash",
        full_name="OAuth User",
        is_active=True,
        auth_provider="clerk:user_direct_1",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_res

    with patch("app.modules.auth.dependencies.get_clerk_verifier") as mock_get_v:
        mock_verifier = MagicMock()
        mock_verifier.verify_token.return_value = {
            "sub": "user_direct_1",
            "email": "oauth@univ.edu",
        }
        mock_get_v.return_value = mock_verifier

        # Using an invalid native token structure so it falls through to Clerk
        resolved_user = await get_current_user(token="clerk.rs256.token", db=mock_db)
        assert resolved_user.id == user.id
        assert resolved_user.email == "oauth@univ.edu"


@pytest.mark.asyncio
async def test_native_jwt_non_regression(mock_db: AsyncMock):
    """Native PracPrep HS256 JWT tokens continue to authenticate immediately."""
    user_id = uuid.uuid4()
    user = User(
        id=user_id,
        email="native@univ.edu",
        password_hash="hash",
        full_name="Native User",
        is_active=True,
        auth_provider="local",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = user
    mock_db.execute.return_value = mock_res

    native_token = create_access_token(user_id)
    resolved_user = await get_current_user(token=native_token, db=mock_db)
    assert resolved_user.id == user_id
    assert resolved_user.email == "native@univ.edu"
