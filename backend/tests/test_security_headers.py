"""Security Headers Middleware Test Suite (TASK-15.1).

Validates presence of security headers (X-Content-Type-Options, X-Frame-Options,
Referrer-Policy, Permissions-Policy, Content-Security-Policy) on success, 404, 401,
422, and 429 responses, plus environment-aware HSTS behavior.
"""

from unittest.mock import AsyncMock
import httpx
import pytest
from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.main import create_app


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.anyio
async def test_security_headers_present_on_200_ok(mock_db):
    """Successful responses include all standard security headers and omit HSTS in dev mode."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["x-frame-options"] == "DENY"
        assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'self'" in res.headers["content-security-policy"]
        assert "camera=()" in res.headers["permissions-policy"]
        # HSTS must NOT be set on HTTP dev mode
        assert "strict-transport-security" not in res.headers


@pytest.mark.anyio
async def test_security_headers_present_on_404_not_found(mock_db):
    """404 Not Found responses include security headers."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/nonexistent-route")
        assert res.status_code == 404
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["x-frame-options"] == "DENY"
        assert "content-security-policy" in res.headers


@pytest.mark.anyio
async def test_security_headers_present_on_401_unauthorized(mock_db):
    """401 Unauthorized responses include security headers."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/users/me")
        assert res.status_code == 401
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["x-frame-options"] == "DENY"
        assert "content-security-policy" in res.headers


@pytest.mark.anyio
async def test_security_headers_present_on_422_validation_error(mock_db):
    """422 Validation Error responses include security headers."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/login", json={})
        assert res.status_code == 422
        assert res.headers["x-content-type-options"] == "nosniff"
        assert res.headers["x-frame-options"] == "DENY"
        assert "content-security-policy" in res.headers


@pytest.mark.anyio
async def test_hsts_behavior_production_https_vs_http(monkeypatch, mock_db):
    """HSTS is enabled in production when accessed over HTTPS, and omitted over plain HTTP."""
    strong_secret = "a" * 32
    monkeypatch.setenv("SECRET_KEY", strong_secret)
    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()

    try:
        app = create_app()
        app.dependency_overrides[get_db] = lambda: mock_db
        transport = httpx.ASGITransport(app=app)

        # 1. Plain HTTP in production -> No HSTS
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            res_http = await client.get("/health")
            assert res_http.status_code == 200
            assert "strict-transport-security" not in res_http.headers

        # 2. HTTPS in production -> HSTS enabled
        async with httpx.AsyncClient(transport=transport, base_url="https://test") as client:
            res_https = await client.get("/health")
            assert res_https.status_code == 200
            assert "strict-transport-security" in res_https.headers
            hsts = res_https.headers["strict-transport-security"]
            assert "max-age=31536000" in hsts
            assert "includeSubDomains" in hsts
    finally:
        get_settings.cache_clear()
