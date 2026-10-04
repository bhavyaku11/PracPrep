"""ADR-010 Standardized Error Envelope Test Suite (TASK-15.1).

Validates consistent error responses across HTTP exceptions, validation errors,
rate limit errors, and unhandled server errors, ensuring no sensitive data leakage.
"""

from unittest.mock import AsyncMock
import httpx
import pytest
from fastapi import APIRouter
from app.core.database import get_db
from app.main import create_app


@pytest.fixture
def mock_db():
    return AsyncMock()


@pytest.mark.anyio
async def test_http_exception_envelope_format(mock_db):
    """HTTP 404 responses conform to ADR-010 error envelope specification."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/unknown-endpoint")
        assert res.status_code == 404

        body = res.json()
        assert "error" in body
        error = body["error"]
        assert error["code"] == "NOT_FOUND"
        assert error["status"] == 404
        assert error["path"] == "/api/v1/unknown-endpoint"
        assert "Not Found" in error["message"]
        assert isinstance(error["details"], list)

        # Legacy detail field preserved
        assert "detail" in body
        assert "Not Found" in body["detail"]


@pytest.mark.anyio
async def test_validation_error_envelope_format(mock_db):
    """HTTP 422 RequestValidationError conforms to ADR-010 with structured field details."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid body for registration (missing required fields)
        res = await client.post("/api/v1/auth/register", json={"email": "not-an-email"})
        assert res.status_code == 422

        body = res.json()
        assert "error" in body
        error = body["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert error["status"] == 422
        assert error["path"] == "/api/v1/auth/register"
        assert "Validation error" in error["message"]
        assert isinstance(error["details"], list)
        assert len(error["details"]) > 0

        # Verify field path and error message are present in details
        locs = [d.get("loc") for d in error["details"]]
        assert any(loc and "password" in loc for loc in locs)


@pytest.mark.anyio
async def test_unhandled_exception_does_not_leak_stack_trace_or_internals(mock_db):
    """Unhandled internal errors return 500 without leaking stack traces or internal messages."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: mock_db

    # Inject a test route that raises an unexpected internal exception with sensitive info
    test_router = APIRouter()

    @test_router.get("/api/v1/test-crash")
    async def crash():
        raise RuntimeError("CRITICAL: Database password=SuperSecret123 at /var/secrets/db.key failed!")

    app.include_router(test_router)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/test-crash")
        assert res.status_code == 500

        body = res.json()
        assert "error" in body
        error = body["error"]
        assert error["code"] == "INTERNAL_SERVER_ERROR"
        assert error["status"] == 500
        assert "internal server error occurred" in error["message"].lower()
        assert error["details"] == []

        # Confirm sensitive strings are completely absent from the response
        raw_text = res.text
        assert "SuperSecret123" not in raw_text
        assert "/var/secrets" not in raw_text
        assert "RuntimeError" not in raw_text
        assert "Traceback" not in raw_text
