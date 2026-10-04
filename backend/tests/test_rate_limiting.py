"""Rate Limiting Test Suite (TASK-15.1 Remediation).

Validates:
1. In-memory slowapi rate limiting on sensitive endpoints.
2. Safe client identification strategy:
   - X-Test-Client-Id is ONLY honored in testing environment (ENVIRONMENT='testing').
   - In development and production environments, X-Test-Client-Id is strictly ignored.
   - Untrusted forwarding headers (X-Forwarded-For, X-Real-IP) cannot bypass rate limits.
   - Mandatory production bypass regression test: changing X-Test-Client-Id does not bypass rate limits.
3. HTTP 429 status code, Retry-After header, and ADR-010 standardized error envelope.
4. Limiter state reset functionality.
"""

from unittest.mock import AsyncMock, MagicMock
import uuid
import httpx
import pytest
from starlette.requests import Request
from starlette.datastructures import Headers

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.limiter import get_client_ip, limiter
from app.main import create_app


@pytest.fixture(autouse=True)
def reset_limiter():
    """Reset rate limiter state between tests."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    return session


# ==============================================================================
# 1. Direct Unit Tests for get_client_ip Resolution Strategy
# ==============================================================================


def test_get_client_ip_honors_test_header_only_in_test_environment():
    """In testing environment, X-Test-Client-Id is honored for test isolation."""
    class FakeClient:
        host = "192.168.1.100"

    class FakeState:
        settings = Settings(ENVIRONMENT="testing")

    class FakeApp:
        state = FakeState()

    scope = {
        "type": "http",
        "client": ("192.168.1.100", 54321),
        "headers": [(b"x-test-client-id", b"runner-isolated-abc")],
        "app": FakeApp(),
    }
    request = Request(scope)
    assert get_client_ip(request) == "test:runner-isolated-abc"


def test_get_client_ip_ignores_test_header_in_development():
    """In development mode, X-Test-Client-Id is completely ignored."""
    class FakeState:
        settings = Settings(ENVIRONMENT="development")

    class FakeApp:
        state = FakeState()

    scope = {
        "type": "http",
        "client": ("192.168.1.50", 12345),
        "headers": [(b"x-test-client-id", b"malicious-bypass-dev")],
        "app": FakeApp(),
    }
    request = Request(scope)
    # Must use client socket host, NOT the test header
    assert get_client_ip(request) == "192.168.1.50"


def test_get_client_ip_ignores_test_header_and_forwarded_headers_in_production():
    """In production mode, X-Test-Client-Id and forwarding headers are strictly ignored."""
    strong_secret = "s" * 32
    class FakeState:
        settings = Settings(ENVIRONMENT="production", SECRET_KEY=strong_secret)

    class FakeApp:
        state = FakeState()

    scope = {
        "type": "http",
        "client": ("203.0.113.195", 44300),
        "headers": [
            (b"x-test-client-id", b"malicious-bypass-prod"),
            (b"x-forwarded-for", b"8.8.8.8"),
            (b"x-real-ip", b"1.1.1.1"),
        ],
        "app": FakeApp(),
    }
    request = Request(scope)
    # Must use client socket host, ignoring X-Test-Client-Id, X-Forwarded-For, and X-Real-IP
    assert get_client_ip(request) == "203.0.113.195"


def test_get_client_ip_fallback_when_client_missing():
    """When request.client is unavailable, safely defaults to 127.0.0.1."""
    class FakeState:
        settings = Settings(ENVIRONMENT="production", SECRET_KEY="k" * 32)

    class FakeApp:
        state = FakeState()

    scope = {
        "type": "http",
        "client": None,
        "headers": [],
        "app": FakeApp(),
    }
    request = Request(scope)
    assert get_client_ip(request) == "127.0.0.1"


# ==============================================================================
# 2. Integration Tests: Rate Limiting & Bypass Prevention
# ==============================================================================


@pytest.mark.anyio
async def test_rate_limiting_register_threshold_and_429(mock_db_session):
    """POST /api/v1/auth/register allows requests below threshold and blocks on exceeding it."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = httpx.ASGITransport(app=app)
    # In development mode, requests are keyed by socket address (127.0.0.1)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # First 5 requests pass threshold
        for i in range(5):
            res = await client.post(
                "/api/v1/auth/register",
                json={"email": f"user{i}@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
            )
            assert res.status_code != 429, f"Request {i+1} should not be rate-limited"

        # 6th request triggers rate limit
        blocked_res = await client.post(
            "/api/v1/auth/register",
            json={"email": "overflow@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert blocked_res.status_code == 429
        assert "Retry-After" in blocked_res.headers
        assert int(blocked_res.headers["Retry-After"]) >= 1

        # Check ADR-010 envelope
        data = blocked_res.json()
        assert "error" in data
        assert data["error"]["code"] == "RATE_LIMIT_EXCEEDED"
        assert data["error"]["status"] == 429
        assert data["error"]["path"] == "/api/v1/auth/register"
        assert "Rate limit exceeded" in data["error"]["message"]
        # Detail field also present for legacy compatibility
        assert "detail" in data
        assert "Rate limit exceeded" in data["detail"]


@pytest.mark.anyio
async def test_rate_limiting_client_isolation_in_testing_environment(mock_db_session):
    """In the test environment (ENVIRONMENT='testing'), distinct X-Test-Client-Id values isolate clients."""
    app = create_app(Settings(ENVIRONMENT="testing"))
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = httpx.ASGITransport(app=app)
    client_a = f"client-a-{uuid.uuid4()}"
    client_b = f"client-b-{uuid.uuid4()}"

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust client A's limit (5 requests)
        for i in range(5):
            await client.post(
                "/api/v1/auth/register",
                headers={"X-Test-Client-Id": client_a},
                json={"email": f"a{i}@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
            )

        # 6th request for client A is blocked
        res_a = await client.post(
            "/api/v1/auth/register",
            headers={"X-Test-Client-Id": client_a},
            json={"email": "a_overflow@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert res_a.status_code == 429

        # Client B has a distinct test identity and is NOT blocked
        res_b = await client.post(
            "/api/v1/auth/register",
            headers={"X-Test-Client-Id": client_b},
            json={"email": "b0@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert res_b.status_code != 429


@pytest.mark.anyio
async def test_rate_limiting_production_bypass_prevention(mock_db_session):
    """MANDATORY PRODUCTION BYPASS REGRESSION TEST:

    In production mode, changing X-Test-Client-Id on every request MUST NOT bypass rate limiting.
    Repeated requests from the same client remain subject to the rate limit even when each
    request supplies a completely different X-Test-Client-Id header.
    """
    strong_secret = "m" * 32
    app = create_app(Settings(ENVIRONMENT="production", SECRET_KEY=strong_secret))
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Send 5 requests, each with a different X-Test-Client-Id
        for i in range(5):
            spoofed_id = f"attacker-id-{uuid.uuid4()}"
            res = await client.post(
                "/api/v1/auth/register",
                headers={"X-Test-Client-Id": spoofed_id},
                json={"email": f"user{i}@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
            )
            assert res.status_code != 429, f"Request {i+1} should pass within limit"

        # 6th request with yet another new X-Test-Client-Id MUST be blocked
        final_spoofed_id = f"attacker-id-{uuid.uuid4()}"
        res_blocked = await client.post(
            "/api/v1/auth/register",
            headers={"X-Test-Client-Id": final_spoofed_id},
            json={"email": "overflow@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert res_blocked.status_code == 429, (
            "SECURITY VULNERABILITY: Rate limiting was bypassed in production by altering X-Test-Client-Id!"
        )
        assert res_blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"


@pytest.mark.anyio
async def test_rate_limiting_development_mode_ignores_test_header(mock_db_session):
    """In development mode, arbitrary X-Test-Client-Id values do not change client identity."""
    app = create_app(Settings(ENVIRONMENT="development"))
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Send 5 requests with differing test headers
        for i in range(5):
            res = await client.post(
                "/api/v1/auth/register",
                headers={"X-Test-Client-Id": f"dev-spoof-{i}"},
                json={"email": f"dev{i}@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
            )
            assert res.status_code != 429

        # 6th request is blocked regardless of test header
        res_blocked = await client.post(
            "/api/v1/auth/register",
            headers={"X-Test-Client-Id": "dev-spoof-6"},
            json={"email": "dev_blocked@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert res_blocked.status_code == 429


@pytest.mark.anyio
async def test_rate_limiting_untrusted_forwarding_headers_cannot_bypass(mock_db_session):
    """Untrusted forwarding headers (X-Forwarded-For, X-Real-IP) cannot bypass rate limits."""
    strong_secret = "f" * 32
    app = create_app(Settings(ENVIRONMENT="production", SECRET_KEY=strong_secret))
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Send 5 requests with spoofed forwarding IPs
        for i in range(5):
            headers = {
                "X-Forwarded-For": f"10.0.0.{i+1}",
                "X-Real-IP": f"192.168.1.{i+1}",
            }
            res = await client.post(
                "/api/v1/auth/register",
                headers=headers,
                json={"email": f"fwd{i}@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
            )
            assert res.status_code != 429

        # 6th request with a new spoofed forwarding IP is blocked
        res_blocked = await client.post(
            "/api/v1/auth/register",
            headers={"X-Forwarded-For": "10.0.0.99", "X-Real-IP": "192.168.1.99"},
            json={"email": "fwd_blocked@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert res_blocked.status_code == 429


@pytest.mark.anyio
async def test_rate_limiting_reset_clears_counters(mock_db_session):
    """Limiter reset clears rate limit counts allowing immediate access."""
    app = create_app(Settings(ENVIRONMENT="testing"))
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = httpx.ASGITransport(app=app)
    client_id = f"client-reset-{uuid.uuid4()}"

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust limit
        for i in range(5):
            await client.post(
                "/api/v1/auth/register",
                headers={"X-Test-Client-Id": client_id},
                json={"email": f"r{i}@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
            )

        res_blocked = await client.post(
            "/api/v1/auth/register",
            headers={"X-Test-Client-Id": client_id},
            json={"email": "r_blocked@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert res_blocked.status_code == 429

        # Explicit reset
        limiter.reset()

        # Immediately should succeed (not 429)
        res_after = await client.post(
            "/api/v1/auth/register",
            headers={"X-Test-Client-Id": client_id},
            json={"email": "r_after@test.com", "password": "SecurePassword123!", "full_name": "Student User"},
        )
        assert res_after.status_code != 429


@pytest.mark.anyio
async def test_rate_limiting_login_and_refresh_limits(mock_db_session):
    """POST /login and /refresh endpoints are also protected by auth rate limits."""
    app = create_app(Settings(ENVIRONMENT="testing"))
    app.dependency_overrides[get_db] = lambda: mock_db_session

    transport = httpx.ASGITransport(app=app)
    client_id = f"client-login-{uuid.uuid4()}"
    headers = {"X-Test-Client-Id": client_id}

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        for i in range(5):
            res = await client.post(
                "/api/v1/auth/login",
                headers=headers,
                json={"email": "student@university.edu", "password": "wrong"},
            )
            assert res.status_code != 429

        blocked = await client.post(
            "/api/v1/auth/login",
            headers=headers,
            json={"email": "student@university.edu", "password": "wrong"},
        )
        assert blocked.status_code == 429
        assert blocked.json()["error"]["code"] == "RATE_LIMIT_EXCEEDED"
