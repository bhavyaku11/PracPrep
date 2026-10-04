"""Production Secret Guard Test Suite (TASK-15.1).

Validates that production startup rejects missing, empty, short, or placeholder
secrets without ever leaking secret contents into error messages, while keeping
development mode functional.
"""

import pytest
from app.core.config import Settings, get_settings, validate_production_secret_guard
from app.main import create_app


def test_development_mode_permits_default_secret():
    """Development mode permits the default placeholder secret."""
    dev_settings = Settings(ENVIRONMENT="development")
    # Should not raise
    validate_production_secret_guard(dev_settings)


def test_production_mode_accepts_strong_secret():
    """Production mode accepts strong secrets >= 32 characters."""
    strong_secret = "k" * 32
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=strong_secret,
    )
    # Should not raise
    validate_production_secret_guard(prod_settings)


def test_production_mode_rejects_default_placeholder():
    """Production mode rejects default development secret."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="insecure-dev-secret-key-change-in-production-min32chars",
    )
    with pytest.raises(ValueError) as excinfo:
        validate_production_secret_guard(prod_settings)
    err = str(excinfo.value)
    assert "Insecure default or placeholder SECRET_KEY" in err
    # Confirm secret value is NOT printed
    assert "insecure-dev-secret-key" not in err


@pytest.mark.parametrize(
    "placeholder",
    [
        "changeme" * 4,
        "secret" * 6,
        "placeholder" * 4,
        "password" * 4,
        "admin" * 7,
    ],
)
def test_production_mode_rejects_common_placeholders(placeholder):
    """Production mode rejects common placeholder substrings."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=placeholder,
    )
    with pytest.raises(ValueError) as excinfo:
        validate_production_secret_guard(prod_settings)
    assert "Insecure default or placeholder SECRET_KEY" in str(excinfo.value)
    assert placeholder not in str(excinfo.value)


def test_production_mode_rejects_short_secrets():
    """Production mode rejects secrets shorter than 32 characters."""
    short_secret = "tooshort"
    prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY=short_secret,
    )
    with pytest.raises(ValueError) as excinfo:
        validate_production_secret_guard(prod_settings)
    err = str(excinfo.value)
    assert "at least 32 characters" in err
    assert short_secret not in err


def test_create_app_enforces_production_guard(monkeypatch):
    """create_app() fails to boot in production if SECRET_KEY is invalid."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "weak")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValueError) as excinfo:
            create_app()
        assert "at least 32 characters" in str(excinfo.value)
    finally:
        get_settings.cache_clear()
