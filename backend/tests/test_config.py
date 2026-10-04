"""Unit tests for centralized application settings and configuration loading."""

import os
import pytest
from pydantic import ValidationError
from app.core.config import Settings, get_settings


def test_default_settings_loading():
    """Verify default configuration loads with expected development defaults."""
    cfg = Settings(_env_file=None)
    assert cfg.PROJECT_NAME == "PracPrep API"
    assert cfg.VERSION == "1.0.0"
    assert cfg.API_V1_STR == "/api/v1"
    assert cfg.ENVIRONMENT == "development"
    assert cfg.DEBUG is False
    assert cfg.JWT_ALGORITHM == "HS256"
    assert cfg.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert cfg.REFRESH_TOKEN_EXPIRE_DAYS == 7
    assert "postgresql+asyncpg://" in cfg.DATABASE_URL
    assert cfg.DEFAULT_AI_PROVIDER == "demonstration"
    assert cfg.MAX_UPLOAD_SIZE_BYTES == 25 * 1024 * 1024


def test_env_var_overrides(monkeypatch):
    """Verify environment variables take precedence over defaults."""
    monkeypatch.setenv("PROJECT_NAME", "Overridden PracPrep")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")

    cfg = Settings(_env_file=None)
    assert cfg.PROJECT_NAME == "Overridden PracPrep"
    assert cfg.ACCESS_TOKEN_EXPIRE_MINUTES == 60
    assert cfg.ENVIRONMENT == "production"
    assert cfg.DEBUG is True


def test_cors_origin_parsing_comma_separated():
    """Verify CORS origins parsing from comma-separated string with trailing slashes."""
    cfg = Settings(
        CORS_ORIGINS="http://localhost:3000/, http://localhost:5173/ , https://pracprep.edu",
        _env_file=None,
    )
    assert cfg.CORS_ORIGINS == [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://pracprep.edu",
    ]


def test_cors_origin_parsing_json_array():
    """Verify CORS origins parsing from a JSON string array."""
    cfg = Settings(
        CORS_ORIGINS='["http://localhost:8080/", "https://app.pracprep.edu"]',
        _env_file=None,
    )
    assert cfg.CORS_ORIGINS == [
        "http://localhost:8080",
        "https://app.pracprep.edu",
    ]


def test_cors_origin_parsing_native_list():
    """Verify CORS origins parsing when passed as a native Python list."""
    cfg = Settings(
        CORS_ORIGINS=["http://localhost:5173/", "http://127.0.0.1:5173"],
        _env_file=None,
    )
    assert cfg.CORS_ORIGINS == [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]


def test_cors_origin_parsing_empty():
    """Verify empty or whitespace string yields an empty list."""
    cfg = Settings(CORS_ORIGINS="", _env_file=None)
    assert cfg.CORS_ORIGINS == []


def test_jwt_secret_not_exposed_in_repr():
    """Verify SecretStr masks secret key in repr and string output."""
    raw_secret = "super-secret-key-that-must-be-hidden"
    cfg = Settings(JWT_SECRET_KEY=raw_secret, _env_file=None)

    # String representation must mask secret
    assert raw_secret not in str(cfg.JWT_SECRET_KEY)
    assert raw_secret not in repr(cfg.JWT_SECRET_KEY)
    assert "**********" in str(cfg.JWT_SECRET_KEY) or "**********" in repr(cfg.JWT_SECRET_KEY)

    # Value is accessible only via get_secret_value()
    assert cfg.JWT_SECRET_KEY.get_secret_value() == raw_secret


def test_invalid_database_url_rejected():
    """Verify an empty database URL triggers validation failure."""
    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="", _env_file=None)


def test_settings_singleton_caching():
    """Verify get_settings returns the same cached instance."""
    instance_1 = get_settings()
    instance_2 = get_settings()
    assert instance_1 is instance_2
