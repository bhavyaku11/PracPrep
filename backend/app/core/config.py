"""Application Configuration Module.

Provides centralized, type-safe environment configuration loading using Pydantic Settings.
"""

import base64
from functools import lru_cache
import json
from typing import Any, List, Union
from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PracPrep Backend Application Settings."""

    # Project metadata
    PROJECT_NAME: str = "PracPrep API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field(default="development", description="Runtime environment (development, staging, production, testing)")
    DEBUG: bool = False

    # Logging & Observability
    LOG_LEVEL: str = Field(default="INFO", description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    LOG_FORMAT: str = Field(default="auto", description="Logging format ('auto', 'json', 'console')")
    DATABASE_CONNECT_TIMEOUT_SECONDS: float = Field(default=2.0, description="Readiness check database timeout in seconds")

    # Security & CORS
    CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:5173", "http://127.0.0.1:5173"],
        description="Allowed CORS origins list or comma-separated string"
    )

    # JWT Authentication
    JWT_SECRET_KEY: SecretStr = Field(
        default=SecretStr("insecure-dev-secret-key-change-in-production-min32chars"),
        description="Cryptographic secret key for signing JWT tokens",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "SECRET_KEY"),
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Clerk Authentication
    CLERK_PUBLISHABLE_KEY: str = Field(
        default="",
        description="Clerk publishable key (e.g. pk_test_... or pk_live_...)",
        validation_alias=AliasChoices("CLERK_PUBLISHABLE_KEY", "VITE_CLERK_PUBLISHABLE_KEY"),
    )
    CLERK_SECRET_KEY: SecretStr | None = Field(
        default=None,
        description="Optional Clerk secret key for server-to-server operations",
    )
    CLERK_ISSUER: str | None = Field(
        default=None,
        description="Explicit Clerk issuer URL; if None, derived from CLERK_PUBLISHABLE_KEY",
    )
    CLERK_JWKS_URL: str | None = Field(
        default=None,
        description="Explicit Clerk JWKS URL; if None, derived from CLERK_PUBLISHABLE_KEY",
    )

    # Rate Limiting (slowapi in-memory)
    RATE_LIMITING_ENABLED: bool = Field(
        default=True,
        description="Whether in-memory rate limiting via slowapi is enabled"
    )
    RATE_LIMIT_AUTH_DEFAULT: str = Field(
        default="5/minute",
        description="Rate limit threshold for authentication endpoints"
    )
    RATE_LIMIT_AI_DEFAULT: str = Field(
        default="10/minute",
        description="Rate limit threshold for AI viva endpoints"
    )
    RATE_LIMIT_UPLOAD_DEFAULT: str = Field(
        default="5/minute",
        description="Rate limit threshold for manual uploads"
    )
    RATE_LIMIT_DEFAULT: str = Field(
        default="60/minute",
        description="Default rate limit for general endpoints"
    )

    # Database connection
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/pracprep",
        description="Asynchronous PostgreSQL connection URL"
    )

    # AI Provider configuration
    DEFAULT_AI_PROVIDER: str = Field(
        default="demonstration",
        description="Default AI viva provider ('demonstration', 'gemini', 'openai')"
    )
    GEMINI_API_KEY: SecretStr | None = Field(
        default=None,
        description="Google Gemini API key"
    )
    GEMINI_MODEL: str = Field(
        default="gemini-2.5-flash",
        description="Google Gemini model identifier for viva examination"
    )
    GEMINI_TIMEOUT_SECONDS: float = Field(
        default=10.0,
        description="Timeout in seconds for Gemini API calls"
    )
    GEMINI_MAX_RETRIES: int = Field(
        default=3,
        description="Maximum retry attempts for transient Gemini API errors"
    )
    AI_CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = Field(
        default=3,
        ge=1,
        description="Consecutive qualifying failures before AI circuit breaker opens"
    )
    AI_CIRCUIT_BREAKER_RECOVERY_SECONDS: float = Field(
        default=30.0,
        gt=0.0,
        description="Cooldown period in seconds before circuit breaker tests recovery"
    )
    OPENAI_API_KEY: SecretStr | None = Field(
        default=None,
        description="OpenAI API key"
    )

    # Document upload limits, storage and extraction
    MAX_UPLOAD_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    UPLOAD_DIR: str = Field(
        default="uploads/documents",
        description="Base directory for uploaded documents storage"
    )
    DOCUMENT_MIN_TEXT_CHARS: int = Field(
        default=50,
        description="Minimum character count below which a document is flagged as having no digital text"
    )
    DOCUMENT_MAX_EXTRACT_PAGES: int = Field(
        default=200,
        description="Maximum pages to extract from a single document to prevent resource exhaustion"
    )

    # OCR Engine settings
    OCR_ENABLED: bool = Field(
        default=True,
        description="Whether OCR fallback is enabled for scanned documents"
    )
    OCR_LANGUAGE: str = Field(
        default="eng",
        description="Language model for Tesseract OCR"
    )
    OCR_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Timeout per page in seconds for OCR execution"
    )
    OCR_RENDERING_DPI: int = Field(
        default=200,
        description="DPI resolution for rendering PDF pages to images for OCR"
    )
    OCR_MAX_PAGES: int = Field(
        default=50,
        description="Maximum pages to process with OCR to prevent resource exhaustion"
    )
    OCR_TESSERACT_CMD: str | None = Field(
        default=None,
        description="Optional custom path to tesseract binary"
    )
    OCR_POPPLER_PATH: str | None = Field(
        default=None,
        description="Optional custom path to poppler binaries (pdftoppm)"
    )

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def clerk_domain(self) -> str | None:
        """Derive Clerk frontend API domain from CLERK_PUBLISHABLE_KEY."""
        if not self.CLERK_PUBLISHABLE_KEY or not self.CLERK_PUBLISHABLE_KEY.startswith(("pk_test_", "pk_live_")):
            return None
        try:
            parts = self.CLERK_PUBLISHABLE_KEY.split("_", 2)
            if len(parts) < 3:
                return None
            raw = parts[2]
            padded = raw + "=" * (-len(raw) % 4)
            return base64.b64decode(padded).decode("utf-8").rstrip("$")
        except Exception:
            return None

    @property
    def clerk_issuer_url(self) -> str | None:
        """Resolve Clerk expected issuer URL."""
        if self.CLERK_ISSUER:
            return self.CLERK_ISSUER.rstrip("/")
        domain = self.clerk_domain
        if domain:
            return f"https://{domain}"
        return None

    @property
    def clerk_jwks_url(self) -> str | None:
        """Resolve Clerk JWKS endpoint URL."""
        if self.CLERK_JWKS_URL:
            return self.CLERK_JWKS_URL
        domain = self.clerk_domain
        if domain:
            return f"https://{domain}/.well-known/jwks.json"
        return None

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str], Any]) -> List[str]:
        """Parse CORS origins from a comma-separated string, JSON list, or native list."""
        if isinstance(v, str):
            v_stripped = v.strip()
            if not v_stripped:
                return []
            if v_stripped.startswith("[") and v_stripped.endswith("]"):
                try:
                    parsed = json.loads(v_stripped)
                    if isinstance(parsed, list):
                        return [str(origin).rstrip("/") for origin in parsed if str(origin).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip().rstrip("/") for origin in v_stripped.split(",") if origin.strip()]
        elif isinstance(v, (list, tuple)):
            return [str(origin).strip().rstrip("/") for origin in v if str(origin).strip()]
        return []

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure database URL is non-empty."""
        if not v or not v.strip():
            raise ValueError("DATABASE_URL cannot be empty")
        return v.strip()

def validate_production_secret_guard(settings: Settings) -> None:
    """Enforce strict secret requirements in production mode.

    Rejects missing, empty, short (< 32 chars), or placeholder secrets when ENVIRONMENT is production.
    Prevents starting with insecure defaults without printing the secret value.
    """
    if settings.ENVIRONMENT.lower() == "production":
        raw_secret = settings.JWT_SECRET_KEY.get_secret_value() if settings.JWT_SECRET_KEY else ""
        trimmed = raw_secret.strip()
        insecure_keywords = [
            "insecure-dev",
            "changeme",
            "placeholder",
            "secretsecret",
            "password",
            "adminadmin",
            "default-secret",
        ]
        if not trimmed or len(trimmed) < 32:
            raise ValueError(
                "Production startup failed: A cryptographically strong SECRET_KEY "
                "of at least 32 characters is required when ENVIRONMENT is set to 'production'."
            )
        if (
            any(kw in trimmed.lower() for kw in insecure_keywords)
            or trimmed.lower() == "insecure-dev-secret-key-change-in-production-min32chars"
        ):
            raise ValueError(
                "Production startup failed: Insecure default or placeholder SECRET_KEY "
                "is not permitted when ENVIRONMENT is set to 'production'."
            )


def validate_production_configuration(settings: Settings) -> None:
    """Validate all runtime configuration requirements for production operation.

    Enforces:
    1. Cryptographically strong secret keys (no defaults/placeholders).
    2. DEBUG mode must be disabled in production.
    3. Wildcard '*' CORS origin is rejected when credentials/auth are used.
    """
    if settings.ENVIRONMENT.lower() == "production":
        # 1. Enforce secret strength
        validate_production_secret_guard(settings)

        # 2. Enforce debug mode disabled
        if settings.DEBUG:
            raise ValueError(
                "Production startup failed: DEBUG mode must be disabled when ENVIRONMENT is set to 'production'."
            )

        # 3. Enforce safe CORS origins (reject wildcard)
        if isinstance(settings.CORS_ORIGINS, list):
            if "*" in settings.CORS_ORIGINS:
                raise ValueError(
                    "Production startup failed: Wildcard CORS origin '*' is not permitted in production."
                )


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton instance of application settings."""
    return Settings()


# Shared application settings singleton
settings = get_settings()
