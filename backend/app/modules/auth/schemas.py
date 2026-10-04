"""Authentication Pydantic Schemas.

Defines request and response data transfer objects for registration,
login, token issuance, and user profile payloads.
"""

from datetime import datetime
import re
from typing import Any, Optional
import uuid

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


# Standard RFC 5322 compliant regex for safe email validation without external dependencies
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class UserRegisterRequest(BaseModel):
    """Registration request payload."""

    email: str = Field(
        ...,
        description="Valid student or university email address",
        examples=["student@university.edu"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Account password (minimum 8 characters)",
        examples=["SecurePass123!"],
    )
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        validation_alias=AliasChoices("full_name", "name"),
        description="Full name of student",
        examples=["Alex Johnson"],
    )
    university: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional university or college affiliation",
        examples=["State University"],
    )

    model_config = ConfigDict(populate_by_name=True)

    @field_validator("email", mode="before")
    @classmethod
    def validate_and_normalize_email(cls, v: Any) -> str:
        """Strip whitespace, normalize to lowercase, and validate format."""
        if not isinstance(v, str):
            raise ValueError("Email must be a string")
        norm = v.strip().lower()
        if not norm:
            raise ValueError("Email cannot be empty")
        if not EMAIL_REGEX.match(norm):
            raise ValueError("Invalid email address format")
        return norm

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_full_name(cls, v: Any) -> str:
        """Strip whitespace and enforce minimum length."""
        if not isinstance(v, str):
            raise ValueError("Full name must be a string")
        v_stripped = v.strip()
        if not v_stripped or len(v_stripped) < 2:
            raise ValueError("Full name must be at least 2 characters")
        return v_stripped

    @field_validator("university", mode="before")
    @classmethod
    def validate_university(cls, v: Any) -> Optional[str]:
        """Strip whitespace or convert empty string to None."""
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return None

    def __repr__(self) -> str:
        """Prevent password exposure in logs or debug strings."""
        return f"<UserRegisterRequest email={self.email!r} full_name={self.full_name!r} password='***'>"


class UserLoginRequest(BaseModel):
    """Login request payload."""

    email: str = Field(
        ...,
        description="Registered email address",
        examples=["student@university.edu"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password",
        examples=["SecurePass123!"],
    )

    @field_validator("email", mode="before")
    @classmethod
    def validate_and_normalize_email(cls, v: Any) -> str:
        """Strip whitespace, normalize to lowercase, and validate format."""
        if not isinstance(v, str):
            raise ValueError("Email must be a string")
        norm = v.strip().lower()
        if not norm:
            raise ValueError("Email cannot be empty")
        if not EMAIL_REGEX.match(norm):
            raise ValueError("Invalid email address format")
        return norm

    def __repr__(self) -> str:
        """Prevent password exposure in logs or debug strings."""
        return f"<UserLoginRequest email={self.email!r} password='***'>"


class UserResponse(BaseModel):
    """Safe user profile response excluding sensitive security fields."""

    id: uuid.UUID
    email: str
    full_name: str
    university: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Authentication token response schema."""

    access_token: str = Field(description="Signed JWT access token (15-min lifetime)")
    refresh_token: str = Field(description="Signed JWT refresh token (7-day lifetime)")
    token_type: str = Field(default="bearer", description="Token type designation")
    expires_in: int = Field(description="Access token lifespan in seconds")


class AuthResponse(TokenResponse):
    """Combined authentication response containing tokens and user profile."""

    user: UserResponse = Field(description="Authenticated user profile details")

    model_config = ConfigDict(from_attributes=True)


class TokenRefreshRequest(BaseModel):
    """Token refresh request payload."""

    refresh_token: str = Field(
        ...,
        min_length=1,
        description="Valid JWT refresh token",
        examples=["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."],
    )

    @field_validator("refresh_token", mode="before")
    @classmethod
    def validate_refresh_token(cls, v: Any) -> str:
        """Strip whitespace and enforce non-empty token string."""
        if not isinstance(v, str):
            raise ValueError("Refresh token must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Refresh token cannot be empty")
        return stripped

    def __repr__(self) -> str:
        """Prevent sensitive refresh token exposure in logs or debug strings."""
        return "<TokenRefreshRequest refresh_token='***'>"


class LogoutResponse(BaseModel):
    """Response payload confirming successful logout."""

    message: str = Field(
        default="Logged out successfully",
        description="Logout confirmation message",
        examples=["Logged out successfully"],
    )


class ClerkSyncRequest(BaseModel):
    """Payload for synchronizing a Clerk-authenticated user with PracPrep backend."""

    clerk_token: Optional[str] = Field(
        default=None,
        description="Clerk session JWT token (may alternatively be passed via Authorization header)",
    )
    email: Optional[str] = Field(
        default=None,
        description="User email address provided by OAuth identity",
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("full_name", "name"),
        description="User full name",
    )
    university: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Optional student university affiliation",
    )

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("email", mode="before")
    @classmethod
    def validate_and_normalize_email(cls, v: Any) -> Optional[str]:
        """Strip whitespace and normalize to lowercase if provided."""
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("Email must be a string")
        norm = v.strip().lower()
        if not norm:
            return None
        if not EMAIL_REGEX.match(norm):
            raise ValueError("Invalid email format")
        return norm
