"""Standardized Error Envelope and Exception Handlers (ADR-010).

Provides centralized, predictable JSON error responses across the FastAPI application
while preserving top-level detail compatibility for existing API clients and test suites.

ADR-010 Envelope Specification:
{
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "Human readable explanation.",
    "status": 400,
    "path": "/api/v1/...",
    "details": []
  },
  "detail": "Human readable explanation or validation error list"
}
"""

import logging
from typing import Any, Dict, List, Union
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import JSONResponse

logger = logging.getLogger("app.core.errors")

# Map of HTTP status codes to standardized machine-readable error codes
HTTP_STATUS_CODE_MAP: Dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "UNPROCESSABLE_ENTITY",
    429: "RATE_LIMIT_EXCEEDED",
    500: "INTERNAL_SERVER_ERROR",
    502: "BAD_GATEWAY",
    503: "SERVICE_UNAVAILABLE",
    504: "GATEWAY_TIMEOUT",
}


def register_error_handlers(app: FastAPI) -> None:
    """Register centralized exception handlers for standardizing API error responses."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Standardize HTTP exceptions while preserving custom status, headers, and detail."""
        code = HTTP_STATUS_CODE_MAP.get(exc.status_code, "HTTP_ERROR")

        # Determine message and structured details
        if isinstance(exc.detail, str):
            message = exc.detail
            details: List[Any] = []
        elif isinstance(exc.detail, dict):
            message = str(exc.detail.get("message") or exc.detail.get("detail") or "Request failed")
            code = str(exc.detail.get("code") or code)
            details = [exc.detail]
        elif isinstance(exc.detail, list):
            message = "One or more request errors occurred."
            details = exc.detail
        else:
            message = "An error occurred processing the request."
            details = []

        payload = {
            "error": {
                "code": code,
                "message": message,
                "status": exc.status_code,
                "path": request.url.path,
                "details": details,
            },
            "detail": exc.detail,
        }

        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Standardize Pydantic validation errors into structured field issues."""
        structured_details: List[Dict[str, Any]] = []

        for err in exc.errors():
            raw_loc = list(err.get("loc", []))
            field_path = ".".join(str(loc) for loc in raw_loc)
            structured_details.append(
                {
                    "field": field_path or "body",
                    "issue": err.get("msg", "Invalid value"),
                    "type": err.get("type", "validation_error"),
                    "loc": raw_loc,
                    "msg": err.get("msg", "Invalid value"),
                }
            )

        if structured_details:
            formatted_issues = "; ".join(
                f"{d['field']}: {d['issue']}" for d in structured_details
            )
            summary_message = f"Validation error: {formatted_issues}"
        else:
            summary_message = "Validation error: Invalid request parameters."

        payload = {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": summary_message,
                "status": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "path": request.url.path,
                "details": structured_details,
            },
            "detail": jsonable_encoder(exc.errors()),
        }

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=payload,
        )

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(
        request: Request, exc: RateLimitExceeded
    ) -> JSONResponse:
        """Standardize slowapi RateLimitExceeded errors with Retry-After header."""
        limit_desc = str(getattr(exc, "detail", "limit exceeded"))
        message = f"Rate limit exceeded: {limit_desc}. Please try again later."

        headers = {"Retry-After": "60"}

        payload = {
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": message,
                "status": status.HTTP_429_TOO_MANY_REQUESTS,
                "path": request.url.path,
                "details": [{"limit": limit_desc, "retry_after": "60"}],
            },
            "detail": message,
        }

        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content=payload,
            headers=headers,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all handler for unhandled internal exceptions preventing stack trace leaks."""
        logger.exception("Unhandled internal exception on %s: %s", request.url.path, exc)

        payload = {
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected internal server error occurred.",
                "status": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "path": request.url.path,
                "details": [],
            },
            "detail": "An unexpected internal server error occurred.",
        }

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload,
        )
