"""Security Primitives for Authentication and Token Management.

Provides Argon2id password hashing/verification and JWT token creation/validation
for access and refresh authentication workflows.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping
import uuid

import argon2
import argon2.exceptions
import jwt
import jwt.exceptions

from app.core.config import Settings, get_settings


# Standard token types
TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Required JWT claims for validation
REQUIRED_CLAIMS = ("sub", "iat", "exp", "type")

# Forbidden payload keys to prevent sensitive data leakage in tokens
FORBIDDEN_CLAIM_KEYS = {
    "password",
    "plain_password",
    "hashed_password",
    "password_hash",
    "secret",
    "secret_key",
    "token",
}


# ==============================================================================
# Security Exceptions
# ==============================================================================


class SecurityError(Exception):
    """Base exception for all security and authentication errors."""


class TokenError(SecurityError):
    """Base exception for JWT token processing errors."""


class ExpiredTokenError(TokenError):
    """Raised when a JWT token signature has expired."""


class InvalidTokenError(TokenError):
    """Raised when a JWT token is malformed, has an invalid signature, or missing claims."""


class InvalidTokenTypeError(InvalidTokenError):
    """Raised when a token type does not match the expected purpose (e.g. refresh vs access)."""


# ==============================================================================
# Password Hashing & Verification (Argon2id)
# ==============================================================================

# Argon2id password hasher instance with secure library defaults
_password_hasher = argon2.PasswordHasher(type=argon2.Type.ID)


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id with a secure random salt.

    Args:
        password: The plaintext password to hash.

    Returns:
        The Argon2id hash string containing parameters, salt, and digest.

    Raises:
        TypeError: If password is not a string.
        ValueError: If password is empty.
        SecurityError: If hashing fails unexpectedly.
    """
    if not isinstance(password, str):
        raise TypeError("Password must be a string")
    if not password:
        raise ValueError("Password cannot be empty")

    try:
        return _password_hasher.hash(password)
    except Exception as exc:
        raise SecurityError("Failed to hash password") from None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2id hash.

    Safely handles malformed hashes, invalid data types, or mismatch errors
    without exposing cryptographic internals or throwing unhandled exceptions.

    Args:
        plain_password: The plaintext candidate password.
        hashed_password: The stored Argon2id hash string.

    Returns:
        True if the password matches the hash, False otherwise.
    """
    if not isinstance(plain_password, str) or not isinstance(hashed_password, str):
        return False
    if not plain_password or not hashed_password:
        return False

    try:
        return _password_hasher.verify(hashed_password, plain_password)
    except (
        argon2.exceptions.VerificationError,
        argon2.exceptions.InvalidHashError,
        argon2.exceptions.Argon2Error,
        ValueError,
        TypeError,
    ):
        return False
    except Exception:
        return False


def needs_rehash(hashed_password: str) -> bool:
    """Determine if a stored password hash requires rehashing with updated parameters.

    Args:
        hashed_password: The stored hash to inspect.

    Returns:
        True if the hash was created with outdated parameters, False otherwise.
    """
    if not isinstance(hashed_password, str) or not hashed_password:
        return True
    try:
        return _password_hasher.check_needs_rehash(hashed_password)
    except Exception:
        return True


# ==============================================================================
# JWT Creation & Validation
# ==============================================================================


def _create_token(
    subject: str | uuid.UUID,
    token_type: str,
    expires_delta: timedelta | None = None,
    additional_claims: Mapping[str, Any] | None = None,
    *,
    settings: Settings | None = None,
) -> str:
    """Internal helper to construct and sign a JWT token.

    Args:
        subject: The unique user identifier (string or UUID).
        token_type: Token purpose (TOKEN_TYPE_ACCESS or TOKEN_TYPE_REFRESH).
        expires_delta: Optional custom expiration duration.
        additional_claims: Optional dictionary of extra claims to include.
        settings: Optional Settings instance override.

    Returns:
        Encoded and signed JWT string.

    Raises:
        ValueError: If subject is empty or invalid.
    """
    app_settings = settings or get_settings()

    sub_str = str(subject).strip()
    if not sub_str:
        raise ValueError("Token subject cannot be empty")

    now = datetime.now(timezone.utc)

    if expires_delta is not None:
        expire_at = now + expires_delta
    elif token_type == TOKEN_TYPE_ACCESS:
        expire_at = now + timedelta(minutes=app_settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    elif token_type == TOKEN_TYPE_REFRESH:
        expire_at = now + timedelta(days=app_settings.REFRESH_TOKEN_EXPIRE_DAYS)
    else:
        expire_at = now + timedelta(minutes=app_settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload: dict[str, Any] = {}

    # Include sanitized additional claims if provided
    if additional_claims:
        for key, value in additional_claims.items():
            if key.lower() not in FORBIDDEN_CLAIM_KEYS and key not in REQUIRED_CLAIMS:
                payload[key] = value

    # Enforce standard required claims
    payload.update(
        {
            "sub": sub_str,
            "type": token_type,
            "iat": int(now.timestamp()),
            "exp": int(expire_at.timestamp()),
        }
    )

    return jwt.encode(
        payload,
        app_settings.JWT_SECRET_KEY.get_secret_value(),
        algorithm=app_settings.JWT_ALGORITHM,
    )


def create_access_token(
    subject: str | uuid.UUID,
    expires_delta: timedelta | None = None,
    additional_claims: Mapping[str, Any] | None = None,
    *,
    settings: Settings | None = None,
) -> str:
    """Generate a signed JWT access token.

    Default expiration is loaded from settings (typically 15 minutes).

    Args:
        subject: User identifier (UUID or string).
        expires_delta: Optional custom expiration duration.
        additional_claims: Optional non-sensitive additional claims.
        settings: Optional Settings override.

    Returns:
        Encoded access token string.
    """
    return _create_token(
        subject=subject,
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=expires_delta,
        additional_claims=additional_claims,
        settings=settings,
    )


def create_refresh_token(
    subject: str | uuid.UUID,
    expires_delta: timedelta | None = None,
    additional_claims: Mapping[str, Any] | None = None,
    *,
    settings: Settings | None = None,
) -> str:
    """Generate a signed JWT refresh token.

    Default expiration is loaded from settings (typically 7 days).

    Args:
        subject: User identifier (UUID or string).
        expires_delta: Optional custom expiration duration.
        additional_claims: Optional non-sensitive additional claims.
        settings: Optional Settings override.

    Returns:
        Encoded refresh token string.
    """
    return _create_token(
        subject=subject,
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=expires_delta,
        additional_claims=additional_claims,
        settings=settings,
    )


def decode_token(
    token: str,
    expected_type: str | None = None,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT token.

    Verifies the cryptographic signature, expiration timestamp, and presence
    of all required standard claims (sub, iat, exp, type). Optionally validates
    the expected token type.

    Args:
        token: The encoded JWT token string.
        expected_type: Optional expected token purpose ("access" or "refresh").
        settings: Optional Settings override.

    Returns:
        Decoded payload dictionary.

    Raises:
        ExpiredTokenError: If the token expiration timestamp is in the past.
        InvalidTokenTypeError: If the token purpose does not match expected_type.
        InvalidTokenError: If the token is malformed, invalid, or missing claims.
    """
    if not isinstance(token, str) or not token.strip():
        raise InvalidTokenError("Token is empty or invalid")

    app_settings = settings or get_settings()

    try:
        payload = jwt.decode(
            token.strip(),
            app_settings.JWT_SECRET_KEY.get_secret_value(),
            algorithms=[app_settings.JWT_ALGORITHM],
            options={"require": ["sub", "iat", "exp"]},
        )
    except jwt.exceptions.ExpiredSignatureError:
        raise ExpiredTokenError("Token has expired") from None
    except (jwt.exceptions.InvalidTokenError, jwt.exceptions.PyJWTError):
        raise InvalidTokenError("Could not validate token") from None
    except Exception:
        raise InvalidTokenError("Could not validate token") from None

    # Validate required claims
    sub = payload.get("sub")
    token_type = payload.get("type")
    iat = payload.get("iat")
    exp = payload.get("exp")

    if not sub or not token_type or iat is None or exp is None:
        raise InvalidTokenError("Token is missing required claims")

    # Validate expected token type if requested
    if expected_type is not None and token_type != expected_type:
        raise InvalidTokenTypeError(
            f"Invalid token type: expected '{expected_type}', got '{token_type}'"
        )

    return payload


def decode_access_token(
    token: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT access token.

    Rejects tokens that are expired, invalid, or of a different type (such as refresh).

    Args:
        token: The encoded JWT access token string.
        settings: Optional Settings override.

    Returns:
        Decoded payload dictionary.
    """
    return decode_token(token, expected_type=TOKEN_TYPE_ACCESS, settings=settings)


def decode_refresh_token(
    token: str,
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Decode and validate a JWT refresh token.

    Rejects tokens that are expired, invalid, or of a different type (such as access).

    Args:
        token: The encoded JWT refresh token string.
        settings: Optional Settings override.

    Returns:
        Decoded payload dictionary.
    """
    return decode_token(token, expected_type=TOKEN_TYPE_REFRESH, settings=settings)
