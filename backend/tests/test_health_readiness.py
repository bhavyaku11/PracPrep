"""Automated Test Suite for Liveness & Readiness Probes (TASK-15.4).

Validates process liveness, database-backed readiness, bounded timeout handling,
failure resilience, absence of credential leakage, and suppressed log noise during probes.
"""

import asyncio
from unittest.mock import AsyncMock, patch
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import create_app


@pytest.mark.asyncio
async def test_liveness_endpoints_succeed_without_dependencies():
    """Verify /health and /health/live return 200 without requiring database connection."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Standard /health endpoint (backward compatibility)
        res_health = await client.get("/health")
        assert res_health.status_code == 200
        assert res_health.json() == {"status": "healthy"}

        # Explicit /health/live endpoint
        res_live = await client.get("/health/live")
        assert res_live.status_code == 200
        assert res_live.json() == {"status": "alive"}


@pytest.mark.asyncio
async def test_readiness_probe_succeeds_when_database_is_connected():
    """Verify /health/ready returns 200 and 'connected' when DB ping succeeds."""
    app = create_app()
    transport = ASGITransport(app=app)

    with patch("app.main.check_database_health", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = True
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/health/ready")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "ready"
            assert data["database"] == "connected"
            # Ensure no credentials or URLs are leaked
            assert "url" not in data
            assert "postgres" not in res.text.lower()


@pytest.mark.asyncio
async def test_readiness_probe_fails_safely_when_database_is_unavailable():
    """Verify /health/ready returns 503 and 'disconnected' when DB connection fails."""
    app = create_app()
    transport = ASGITransport(app=app)

    with patch("app.main.check_database_health", side_effect=ConnectionRefusedError("Database offline")):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.get("/health/ready")
            assert res.status_code == 503
            data = res.json()
            assert data["status"] == "not_ready"
            assert data["database"] == "disconnected"
            # Assert no sensitive error details, tracebacks, or credentials leaked to client
            assert "traceback" not in res.text.lower()
            assert "password" not in res.text.lower()


@pytest.mark.asyncio
async def test_readiness_probe_bounded_timeout():
    """Verify /health/ready bounds connection duration and returns 503 on timeout."""
    custom_settings = Settings(
        DATABASE_CONNECT_TIMEOUT_SECONDS=0.05,
        _env_file=None,
    )
    app = create_app(settings_override=custom_settings)
    transport = ASGITransport(app=app)

    async def hanging_connect(*args, **kwargs):
        await asyncio.sleep(1.0)

    with patch("app.main.check_database_health", side_effect=hanging_connect):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            start = asyncio.get_event_loop().time()
            res = await client.get("/health/ready")
            elapsed = asyncio.get_event_loop().time() - start

            assert res.status_code == 503
            assert res.json() == {"status": "not_ready", "database": "disconnected"}
            assert elapsed < 0.5  # Must abort rapidly within bounded timeout


@pytest.mark.asyncio
async def test_health_checks_do_not_generate_excessive_info_logs(caplog):
    """Verify successful health checks log at DEBUG level, avoiding noisy INFO logs."""
    import logging
    app = create_app()
    transport = ASGITransport(app=app)

    caplog.set_level(logging.INFO, logger="app.access")

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        await client.get("/health/live")

    # Filter for INFO messages from app.access
    info_logs = [r for r in caplog.records if r.name == "app.access" and r.levelno >= logging.INFO]
    assert len(info_logs) == 0
