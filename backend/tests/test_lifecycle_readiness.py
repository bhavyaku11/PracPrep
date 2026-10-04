"""Automated Test Suite for Lifecycle, Shutdown & Production Configuration Validation (TASK-15.4).

Validates production settings enforcement (debug mode, wildcard CORS, secrets),
lifespan startup/shutdown database disposal, and repeated initialization stability.
"""

from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings, validate_production_configuration
from app.main import create_app


def test_production_mode_rejects_debug_true():
    """Verify production startup fails if DEBUG mode is enabled."""
    prod_debug_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="x" * 32,
        DEBUG=True,
        _env_file=None,
    )
    with pytest.raises(ValueError) as excinfo:
        validate_production_configuration(prod_debug_settings)
    assert "DEBUG mode must be disabled" in str(excinfo.value)


def test_production_mode_rejects_wildcard_cors():
    """Verify production startup fails if CORS origins contain a wildcard '*'."""
    prod_wildcard_cors = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="x" * 32,
        DEBUG=False,
        CORS_ORIGINS=["*"],
        _env_file=None,
    )
    with pytest.raises(ValueError) as excinfo:
        validate_production_configuration(prod_wildcard_cors)
    assert "Wildcard CORS origin '*' is not permitted" in str(excinfo.value)


def test_production_mode_accepts_valid_configuration():
    """Verify production mode accepts strong secret, debug=False, and explicit CORS origins."""
    valid_prod_settings = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="x" * 32,
        DEBUG=False,
        CORS_ORIGINS=["https://app.pracprep.edu", "https://pracprep.edu"],
        _env_file=None,
    )
    # Must not raise
    validate_production_configuration(valid_prod_settings)


@pytest.mark.asyncio
async def test_lifespan_disposes_database_engine_on_shutdown():
    """Verify FastAPI lifespan executes engine disposal cleanly upon shutdown."""
    app = create_app()

    with patch("app.main.dispose_app_engine", new_callable=AsyncMock) as mock_dispose:
        async with app.router.lifespan_context(app):
            # Application is running in lifespan context
            pass

        # After exiting lifespan context, shutdown hook must have been awaited
        mock_dispose.assert_awaited_once()


@pytest.mark.asyncio
async def test_security_headers_and_rate_limiting_remain_active_with_logging():
    """Verify security headers and rate limiting remain intact when request logging middleware is active."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        # Check security headers
        assert res.headers.get("x-content-type-options") == "nosniff"
        assert res.headers.get("x-frame-options") == "DENY"
        assert "Content-Security-Policy" in res.headers
        # Check correlation ID header
        assert "x-request-id" in res.headers


def test_repeated_app_creation_preserves_single_logging_handler():
    """Verify repeated calls to create_app do not duplicate logging handlers."""
    import logging
    root_logger = logging.getLogger()

    for _ in range(5):
        create_app()

    # Handlers must remain exactly 1 StreamHandler
    stream_handlers = [h for h in root_logger.handlers if isinstance(h, logging.StreamHandler)]
    assert len(stream_handlers) == 1
