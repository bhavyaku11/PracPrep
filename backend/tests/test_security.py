"""Unit Tests for Security Primitives.

Covers Argon2id password hashing/verification and JWT token generation/validation.
Ensures zero leaks of secrets or sensitive token contents, safe handling of
malformed inputs, and strict claim and expiration enforcement.
"""

from datetime import datetime, timedelta, timezone
import uuid
import pytest
import jwt
from pydantic import SecretStr

from app.core.config import Settings, get_settings
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    ExpiredTokenError,
    InvalidTokenError,
    InvalidTokenTypeError,
    SecurityError,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)


# ==============================================================================
# Password Hashing Tests (Cases 1 - 6 + Edge Cases)
# ==============================================================================


def test_password_hashing_returns_value_different_from_plaintext():
    """Case 1: Password hashing returns an Argon2id hash different from plaintext."""
    raw_password = "SuperSecretPassword123!"
    hashed = hash_password(raw_password)

    assert hashed != raw_password
    assert hashed.startswith("$argon2id$")
    assert len(hashed) > len(raw_password)


def test_correct_password_verifies_successfully():
    """Case 2: Correct plaintext password verifies successfully against its hash."""
    raw_password = "MyCorrectPassword#42"
    hashed = hash_password(raw_password)

    assert verify_password(raw_password, hashed) is True


def test_incorrect_password_fails_verification():
    """Case 3: Incorrect plaintext password fails verification."""
    raw_password = "MyCorrectPassword#42"
    wrong_password = "WrongPassword#42"
    hashed = hash_password(raw_password)

    assert verify_password(wrong_password, hashed) is False


def test_identical_passwords_produce_independently_salted_hashes():
    """Case 4: Identical passwords produce different, independently salted hashes."""
    password = "ConsistentPassword123!"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2
    assert verify_password(password, hash1) is True
    assert verify_password(password, hash2) is True


def test_malformed_hash_input_handled_safely():
    """Case 5: Malformed hash input is handled safely without throwing unhandled exceptions."""
    malformed_hashes = [
        "not-a-valid-hash",
        "$argon2id$invalid$format",
        "$pbkdf2-sha256$5000$bad$hash",
        "sha256$54321$corrupt",
        "",
        "   ",
        "12345678",
    ]

    for bad_hash in malformed_hashes:
        assert verify_password("AnyPassword123!", bad_hash) is False


def test_passwords_never_exposed_in_returned_data_or_error_messages():
    """Case 6: Sensitive passwords are never exposed through returned data or error messages."""
    sensitive_password = "UltraSensitiveSecretCannotLeak999"

    hashed = hash_password(sensitive_password)
    assert sensitive_password not in hashed

    # Test error handling when empty string is passed
    with pytest.raises(ValueError) as exc_info:
        hash_password("")
    assert sensitive_password not in str(exc_info.value)

    # Test error handling when non-string is passed
    with pytest.raises(TypeError) as exc_info:
        hash_password(None)  # type: ignore[arg-type]
    assert sensitive_password not in str(exc_info.value)

    # Verification failure with invalid types returns False safely
    assert verify_password(None, hashed) is False  # type: ignore[arg-type]
    assert verify_password(sensitive_password, None) is False  # type: ignore[arg-type]


def test_needs_rehash_detection():
    """Password hash rehash detection safely reports state."""
    password = "PasswordForRehashCheck!"
    hashed = hash_password(password)

    # Current hash with current defaults should not need rehash
    assert needs_rehash(hashed) is False
    # Malformed or empty hashes report needing rehash
    assert needs_rehash("corrupted") is True
    assert needs_rehash("") is True


# ==============================================================================
# JWT Creation & Validation Tests (Cases 7 - 20)
# ==============================================================================


def test_access_token_creation_produces_valid_jwt():
    """Case 7: Access token creation produces a valid, decodable JWT string."""
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id)

    assert isinstance(token, str)
    assert len(token.split(".")) == 3  # standard header.payload.signature

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["type"] == TOKEN_TYPE_ACCESS


def test_refresh_token_creation_produces_valid_jwt():
    """Case 8: Refresh token creation produces a valid, decodable JWT string."""
    user_id = str(uuid.uuid4())
    token = create_refresh_token(user_id)

    assert isinstance(token, str)
    assert len(token.split(".")) == 3

    payload = decode_refresh_token(token)
    assert payload["sub"] == user_id
    assert payload["type"] == TOKEN_TYPE_REFRESH


def test_tokens_contain_expected_subject_and_claims():
    """Case 9: Tokens contain expected subject, iat, exp, and type claims."""
    user_id = "test-user-id-123"
    token = create_access_token(user_id)
    payload = decode_access_token(token)

    assert payload["sub"] == user_id
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert "iat" in payload and isinstance(payload["iat"], int)
    assert "exp" in payload and isinstance(payload["exp"], int)
    assert payload["exp"] > payload["iat"]


def test_access_and_refresh_token_types_are_distinguishable():
    """Case 10: Access and refresh tokens have different, distinguishable types."""
    user_id = "test-user-id-456"
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    access_payload = decode_access_token(access_token)
    refresh_payload = decode_refresh_token(refresh_token)

    assert access_payload["type"] == TOKEN_TYPE_ACCESS
    assert refresh_payload["type"] == TOKEN_TYPE_REFRESH
    assert access_payload["type"] != refresh_payload["type"]


def test_valid_access_tokens_decode_successfully():
    """Case 11: Valid access tokens decode and return the expected payload."""
    user_id = str(uuid.uuid4())
    token = create_access_token(user_id, additional_claims={"role": "student"})

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["type"] == TOKEN_TYPE_ACCESS
    assert payload["role"] == "student"


def test_valid_refresh_tokens_decode_successfully():
    """Case 12: Valid refresh tokens decode and return the expected payload."""
    user_id = str(uuid.uuid4())
    token = create_refresh_token(user_id, additional_claims={"device_id": "laptop-1"})

    payload = decode_refresh_token(token)
    assert payload["sub"] == user_id
    assert payload["type"] == TOKEN_TYPE_REFRESH
    assert payload["device_id"] == "laptop-1"


def test_expired_tokens_are_rejected():
    """Case 13: Expired tokens raise ExpiredTokenError upon validation."""
    user_id = str(uuid.uuid4())
    # Create token already expired in the past
    expired_token = create_access_token(user_id, expires_delta=timedelta(seconds=-10))

    with pytest.raises(ExpiredTokenError) as exc_info:
        decode_access_token(expired_token)

    assert "expired" in str(exc_info.value).lower()
    # Ensure it inherits from TokenError
    assert isinstance(exc_info.value, TokenError)


def test_invalid_signatures_are_rejected():
    """Case 14: Tokens signed with a different key are rejected with InvalidTokenError."""
    user_id = str(uuid.uuid4())
    wrong_settings = Settings(
        JWT_SECRET_KEY=SecretStr("completely-different-signing-secret-key-32chars"),
    )
    foreign_token = create_access_token(user_id, settings=wrong_settings)

    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(foreign_token)

    assert isinstance(exc_info.value, TokenError)
    assert "could not validate token" in str(exc_info.value).lower()


def test_malformed_tokens_are_rejected():
    """Case 15: Malformed tokens are rejected with InvalidTokenError."""
    malformed_tokens = [
        "not.a.valid.jwt.token",
        "header.payload",
        "garbage-token-string",
        "header..signature",
        "",
        "   ",
    ]

    for bad_token in malformed_tokens:
        with pytest.raises(InvalidTokenError):
            decode_token(bad_token)


def test_missing_required_claims_are_rejected():
    """Case 16: Tokens missing required claims (sub, iat, exp, or type) are rejected."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    secret = settings.JWT_SECRET_KEY.get_secret_value()
    algorithm = settings.JWT_ALGORITHM

    # Missing 'sub'
    token_missing_sub = jwt.encode(
        {"type": TOKEN_TYPE_ACCESS, "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=15)).timestamp())},
        secret,
        algorithm=algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token_missing_sub)

    # Missing 'type'
    token_missing_type = jwt.encode(
        {"sub": "user-123", "iat": int(now.timestamp()), "exp": int((now + timedelta(minutes=15)).timestamp())},
        secret,
        algorithm=algorithm,
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token_missing_type)


def test_incorrect_token_types_are_rejected():
    """Case 17: Access tokens are rejected when refresh is expected, and vice versa."""
    user_id = str(uuid.uuid4())
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    # Validating access token with decode_refresh_token must raise InvalidTokenTypeError
    with pytest.raises(InvalidTokenTypeError) as exc_info:
        decode_refresh_token(access_token)
    assert "expected 'refresh'" in str(exc_info.value)
    assert "got 'access'" in str(exc_info.value)

    # Validating refresh token with decode_access_token must raise InvalidTokenTypeError
    with pytest.raises(InvalidTokenTypeError) as exc_info:
        decode_access_token(refresh_token)
    assert "expected 'access'" in str(exc_info.value)
    assert "got 'refresh'" in str(exc_info.value)


def test_token_generation_uses_configured_expiration_values():
    """Case 18: Token generation uses configured expiration settings."""
    custom_settings = Settings(
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
        REFRESH_TOKEN_EXPIRE_DAYS=14,
    )
    user_id = "user-configured-expiration"

    access_token = create_access_token(user_id, settings=custom_settings)
    access_payload = decode_access_token(access_token, settings=custom_settings)
    access_duration = access_payload["exp"] - access_payload["iat"]
    # 30 minutes in seconds = 1800
    assert access_duration == 30 * 60

    refresh_token = create_refresh_token(user_id, settings=custom_settings)
    refresh_payload = decode_refresh_token(refresh_token, settings=custom_settings)
    refresh_duration = refresh_payload["exp"] - refresh_payload["iat"]
    # 14 days in seconds = 14 * 86400 = 1209600
    assert refresh_duration == 14 * 86400


def test_token_generation_works_with_uuid_identifiers():
    """Case 19: Token generation works directly with UUID user identifiers."""
    user_uuid = uuid.uuid4()
    access_token = create_access_token(user_uuid)
    refresh_token = create_refresh_token(user_uuid)

    access_payload = decode_access_token(access_token)
    refresh_payload = decode_refresh_token(refresh_token)

    assert access_payload["sub"] == str(user_uuid)
    assert refresh_payload["sub"] == str(user_uuid)
    # Validate UUID parsing works on sub claim
    assert uuid.UUID(access_payload["sub"]) == user_uuid
    assert uuid.UUID(refresh_payload["sub"]) == user_uuid


def test_error_messages_do_not_reveal_secrets_or_sensitive_contents():
    """Case 20: Error messages never leak signing secrets or sensitive token payloads."""
    secret_value = "insecure-dev-secret-key-change-in-production-min32chars"
    settings = get_settings()
    assert settings.JWT_SECRET_KEY.get_secret_value() == secret_value

    # Test error message on invalid signature
    bad_sig_token = create_access_token(
        "sensitive-user-id",
        settings=Settings(JWT_SECRET_KEY=SecretStr("some-completely-other-secret-key-min32")),
    )
    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token(bad_sig_token)

    err_str = str(exc_info.value)
    assert secret_value not in err_str
    assert "some-completely-other" not in err_str

    # Test error message on malformed token
    with pytest.raises(InvalidTokenError) as exc_info:
        decode_access_token("gibberish-token")
    assert secret_value not in str(exc_info.value)

    # Test that forbidden sensitive claims are stripped during token generation
    token = create_access_token(
        "user-id-safe",
        additional_claims={
            "password": "plain-text-pwd-123",
            "hashed_password": "$argon2id$...hash...",
            "secret_key": "some-secret",
            "allowed_meta": "safe-value",
        },
    )
    payload = decode_access_token(token)
    assert "password" not in payload
    assert "hashed_password" not in payload
    assert "secret_key" not in payload
    assert payload.get("allowed_meta") == "safe-value"


def test_token_subject_cannot_be_empty():
    """Token subject validation prevents empty or whitespace-only subjects."""
    with pytest.raises(ValueError) as exc_info:
        create_access_token("")
    assert "subject cannot be empty" in str(exc_info.value).lower()

    with pytest.raises(ValueError) as exc_info:
        create_refresh_token("   ")
    assert "subject cannot be empty" in str(exc_info.value).lower()
