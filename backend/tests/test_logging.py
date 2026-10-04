"""Automated Test Suite for Centralized Logging & Observability (TASK-15.4).

Validates structured JSON formatting, development console formatting, log level configuration,
request ID correlation, log injection prevention, concurrent task isolation, sensitive data redaction,
and idempotent handler initialization.
"""

import asyncio
import json
import logging
from unittest.mock import MagicMock
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.core.logging import (
    DevelopmentLogFormatter,
    JSONLogFormatter,
    get_request_id,
    reset_request_id,
    sanitize_log_message,
    set_request_id,
    setup_logging,
    validate_or_generate_request_id,
)
from app.main import create_app


def test_json_log_formatter_outputs_valid_json_with_required_fields():
    """Verify JSONLogFormatter outputs valid JSON containing timestamp, level, logger, and message."""
    formatter = JSONLogFormatter()
    record = logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Student completed experiment %s",
        args=("Young's Modulus",),
        exc_info=None,
    )
    record.request_id = "req-12345"

    output = formatter.format(record)
    data = json.loads(output)

    assert data["level"] == "INFO"
    assert data["logger"] == "app.test"
    assert data["message"] == "Student completed experiment Young's Modulus"
    assert data["request_id"] == "req-12345"
    assert "timestamp" in data


def test_json_log_formatter_captures_exception_traceback():
    """Verify JSONLogFormatter serializes exception tracebacks into the exc_info field."""
    formatter = JSONLogFormatter()
    try:
        raise ValueError("Diagnostic test error")
    except ValueError:
        import sys
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=20,
            msg="Operation failed",
            args=(),
            exc_info=sys.exc_info(),
        )

    output = formatter.format(record)
    data = json.loads(output)

    assert data["level"] == "ERROR"
    assert "exc_info" in data
    assert "ValueError: Diagnostic test error" in data["exc_info"]


def test_development_log_formatter_outputs_human_readable_text():
    """Verify DevelopmentLogFormatter produces structured human-readable text."""
    formatter = DevelopmentLogFormatter()
    record = logging.LogRecord(
        name="app.core.auth",
        level=logging.WARNING,
        pathname="auth.py",
        lineno=42,
        msg="Failed login attempt for user %s",
        args=("student@test.edu",),
        exc_info=None,
    )
    record.request_id = "req-dev-01"

    output = formatter.format(record)
    assert "[WARNING]" in output
    assert "[app.core.auth]" in output
    assert "[req-dev-01]" in output
    assert "Failed login attempt for user student@test.edu" in output


def test_log_level_configuration_filters_messages():
    """Verify setup_logging configures root and app logger levels correctly."""
    setup_logging(log_level="WARNING", log_format="console")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.WARNING

    setup_logging(log_level="DEBUG", log_format="json")
    assert root_logger.level == logging.DEBUG

    # Reset to INFO
    setup_logging(log_level="INFO", log_format="console")
    assert root_logger.level == logging.INFO


def test_validate_or_generate_request_id_valid_and_invalid():
    """Verify validation allows safe IDs and sanitizes log injection attempts."""
    # Valid IDs
    assert validate_or_generate_request_id("safe-client-id-123") == "safe-client-id-123"
    assert validate_or_generate_request_id("REQ_abc_99") == "REQ_abc_99"

    # None or empty string -> generated hex ID
    gen1 = validate_or_generate_request_id(None)
    assert len(gen1) == 32
    gen2 = validate_or_generate_request_id("")
    assert len(gen2) == 32

    # Log injection attempts (newlines, carriage returns, spaces, control characters)
    injected_1 = "id\n[CRITICAL] Admin login bypassed"
    sanitized_1 = validate_or_generate_request_id(injected_1)
    assert sanitized_1 != injected_1
    assert "\n" not in sanitized_1

    # Overly long ID (> 64 characters)
    long_id = "a" * 100
    sanitized_long = validate_or_generate_request_id(long_id)
    assert sanitized_long != long_id
    assert len(sanitized_long) == 32


@pytest.mark.asyncio
async def test_concurrent_request_id_context_isolation():
    """Verify asynchronous tasks maintain strictly isolated request IDs via ContextVars."""
    results = {}

    async def worker(task_name: str, req_id: str):
        token = set_request_id(req_id)
        try:
            # Yield to event loop to simulate concurrent task interleaving
            await asyncio.sleep(0.01)
            results[task_name] = get_request_id()
        finally:
            reset_request_id(token)

    await asyncio.gather(
        worker("task_a", "id-alpha-111"),
        worker("task_b", "id-beta-222"),
        worker("task_c", "id-gamma-333"),
    )

    assert results["task_a"] == "id-alpha-111"
    assert results["task_b"] == "id-beta-222"
    assert results["task_c"] == "id-gamma-333"
    # Ensure context was reset cleanly after execution
    assert get_request_id() is None


def test_sensitive_data_redaction():
    """Verify tokens, authorization headers, passwords, and API keys are redacted from logs."""
    # Bearer token redaction
    msg1 = "Received authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.secret"
    sanitized1 = sanitize_log_message(msg1)
    assert "Bearer [REDACTED]" in sanitized1
    assert "eyJhbGciOiJIUzI1Ni" not in sanitized1

    # Password assignment redaction
    msg2 = "User payload password='super_secret_password_123' university=MIT"
    sanitized2 = sanitize_log_message(msg2)
    assert "password=[REDACTED]" in sanitized2
    assert "super_secret_password_123" not in sanitized2

    # API key in JSON-like structure
    msg3 = 'Calling Gemini with api_key="AIzaSyDummyKeyForGoogle" and model=gemini'
    sanitized3 = sanitize_log_message(msg3)
    assert "api_key=[REDACTED]" in sanitized3 or '"api_key": "[REDACTED]"' in sanitized3
    assert "AIzaSyDummyKeyForGoogle" not in sanitized3


def test_idempotent_handler_initialization():
    """Verify repeated calls to setup_logging or create_app do not duplicate handlers."""
    root_logger = logging.getLogger()

    initial_count = len(root_logger.handlers)
    setup_logging(log_level="INFO", log_format="console")
    assert len(root_logger.handlers) == 1

    setup_logging(log_level="INFO", log_format="json")
    assert len(root_logger.handlers) == 1

    create_app()
    assert len(root_logger.handlers) == 1


@pytest.mark.asyncio
async def test_request_id_in_response_header_and_propagation():
    """Verify incoming X-Request-ID is echoed back and generated if absent."""
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Case 1: Client supplies valid X-Request-ID
        res1 = await client.get("/health", headers={"X-Request-ID": "trace-client-42"})
        assert res1.status_code == 200
        assert res1.headers.get("x-request-id") == "trace-client-42"

        # Case 2: Client supplies no request ID
        res2 = await client.get("/health")
        assert res2.status_code == 200
        gen_id = res2.headers.get("x-request-id")
        assert gen_id is not None
        assert len(gen_id) == 32

        # Case 3: Client supplies invalid/malicious request ID
        res3 = await client.get("/health", headers={"X-Request-ID": "bad\nid\nwith\nnewlines"})
        assert res3.status_code == 200
        safe_id = res3.headers.get("x-request-id")
        assert safe_id is not None
        assert "\n" not in safe_id
        assert len(safe_id) == 32
