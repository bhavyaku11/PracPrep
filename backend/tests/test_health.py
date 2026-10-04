"""Automated tests for FastAPI application factory, CORS middleware, and /health endpoint."""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from app.core.config import Settings
from app.main import create_app, app as asgi_app


def test_app_factory_creates_valid_fastapi_instance():
    """Verify create_app returns a properly configured FastAPI instance."""
    custom_settings = Settings(
        PROJECT_NAME="Custom PracPrep",
        VERSION="2.0.0",
        _env_file=None,
    )
    application = create_app(settings_override=custom_settings)
    assert isinstance(application, FastAPI)
    assert application.title == "Custom PracPrep"
    assert application.version == "2.0.0"


def test_asgi_entrypoint_import():
    """Verify application can be imported directly through its module-level ASGI entrypoint."""
    assert isinstance(asgi_app, FastAPI)
    assert asgi_app.title == "PracPrep API"


@pytest.mark.asyncio
async def test_health_endpoint_returns_200_and_expected_payload():
    """Verify GET /health returns HTTP 200 with {'status': 'healthy'} without database dependency."""
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
        # Must not expose secrets, database status, or environment dumps
        assert "database" not in response.json()
        assert "secret" not in response.text.lower()


@pytest.mark.asyncio
async def test_cors_configured_origin_allowed():
    """Verify requests with a configured Origin header receive proper CORS response headers."""
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Preflight OPTIONS request
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert "GET" in response.headers.get("access-control-allow-methods", "")

        # Actual GET request with Origin
        get_response = await client.get(
            "/health",
            headers={"Origin": "http://localhost:5173"},
        )
        assert get_response.status_code == 200
        assert get_response.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.asyncio
async def test_cors_unconfigured_origin_rejected():
    """Verify requests from unconfigured origins do not receive access-control-allow-origin headers."""
    transport = ASGITransport(app=asgi_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/health",
            headers={"Origin": "http://untrusted-external-site.com"},
        )
        assert response.status_code == 200
        # The unconfigured origin must not be reflected in access-control-allow-origin
        assert response.headers.get("access-control-allow-origin") != "http://untrusted-external-site.com"
        assert response.headers.get("access-control-allow-origin") is None
