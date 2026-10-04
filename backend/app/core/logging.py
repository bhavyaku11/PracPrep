"""Centralized Structured Logging Module.

Provides production-ready JSON and development console logging, request correlation tracking
via ContextVars, sensitive data redaction, and log injection prevention.
"""

from contextvars import ContextVar, Token
from datetime import datetime, timezone
import json
import logging
import re
import sys
from typing import Any, Optional
import uuid

# Context variable for storing the correlation ID for the active async task/request
request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Regular expression validating incoming correlation IDs to prevent log injection
VALID_REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")

# Patterns for redacting sensitive values from log output
SENSITIVE_PATTERNS = [
    (re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]+"), r"\1[REDACTED]"),
    (
        re.compile(
            r'(?i)(password|secret|api_key|token|access_token|refresh_token)\s*[:=]\s*["\']?[^\s,"\'\}]+'
        ),
        r"\1=[REDACTED]",
    ),
    (
        re.compile(r'(?i)("password"|"secret"|"api_key"|"token")\s*:\s*"[^"]+"'),
        r'\1: "[REDACTED]"',
    ),
]


def sanitize_log_message(msg: str) -> str:
    """Sanitize message by redacting sensitive data such as tokens and passwords."""
    if not isinstance(msg, str):
        msg = str(msg)
    for pattern, replacement in SENSITIVE_PATTERNS:
        msg = pattern.sub(replacement, msg)
    return msg


def get_request_id() -> Optional[str]:
    """Retrieve the current request correlation ID from task context."""
    return request_id_ctx_var.get()


def set_request_id(req_id: Optional[str]) -> Token:
    """Set the correlation ID in task context, returning the reset token."""
    return request_id_ctx_var.set(req_id)


def reset_request_id(token: Token) -> None:
    """Reset the correlation ID context to its prior state."""
    request_id_ctx_var.reset(token)


def validate_or_generate_request_id(incoming_id: Optional[str]) -> str:
    """Validate incoming request ID or generate a cryptographically safe fallback.

    Rejects incoming IDs containing invalid characters (newlines, control codes,
    unreasonable length) to prevent log injection or header manipulation.
    """
    if incoming_id and VALID_REQUEST_ID_REGEX.match(incoming_id.strip()):
        return incoming_id.strip()
    return uuid.uuid4().hex


class CorrelationIdFilter(logging.Filter):
    """Logging filter that injects the active request_id into every LogRecord."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JSONLogFormatter(logging.Formatter):
    """Structured JSON formatter for production log ingestion and observability."""

    def format(self, record: logging.LogRecord) -> str:
        # Standard structured fields
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": sanitize_log_message(record.getMessage()),
        }

        # Include request_id if present and active
        request_id = getattr(record, "request_id", None)
        if request_id and request_id != "-":
            log_entry["request_id"] = request_id

        # Include structured HTTP context if attached to record
        for attr in ("method", "path", "status_code", "duration_ms", "client_ip"):
            val = getattr(record, attr, None)
            if val is not None:
                log_entry[attr] = val

        # Include exception information if available
        if record.exc_info:
            log_entry["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


class DevelopmentLogFormatter(logging.Formatter):
    """Readable color-free console formatter for local development and debugging."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        request_id = getattr(record, "request_id", "-")
        req_str = f" [{request_id}]" if request_id != "-" else ""
        message = sanitize_log_message(record.getMessage())
        base = f"[{timestamp}] [{record.levelname:<7}] [{record.name}]{req_str} {message}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "auto",
    environment: str = "development",
) -> None:
    """Configure application logging idempotently without duplicating handlers.

    Args:
        log_level: Desired minimum log level (e.g. 'DEBUG', 'INFO', 'WARNING').
        log_format: Format selector ('auto', 'json', 'console').
        environment: Current runtime environment ('development', 'production', etc.).
    """
    resolved_level = getattr(logging, log_level.upper(), logging.INFO)

    # Determine whether to use JSON or human-readable console formatter
    use_json = False
    if log_format.lower() == "json":
        use_json = True
    elif log_format.lower() == "console":
        use_json = False
    else:  # auto
        use_json = environment.lower() == "production"

    formatter = JSONLogFormatter() if use_json else DevelopmentLogFormatter()
    correlation_filter = CorrelationIdFilter()

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    # Remove existing StreamHandlers to avoid duplicate log emission on re-initialization
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(resolved_level)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(correlation_filter)
    root_logger.addHandler(stream_handler)

    # Configure app logger explicitly
    app_logger = logging.getLogger("app")
    app_logger.setLevel(resolved_level)
    for handler in list(app_logger.handlers):
        app_logger.removeHandler(handler)
    app_logger.propagate = True
