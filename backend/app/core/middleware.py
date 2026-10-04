import logging
import time
from typing import Any, Callable, Dict, List, Set, Tuple

from app.core.logging import reset_request_id, set_request_id, validate_or_generate_request_id

access_logger = logging.getLogger("app.access")


class RequestCorrelationMiddleware:
    """ASGI middleware managing request correlation IDs and concise HTTP access logging."""

    def __init__(self, app: Any):
        self.app = app

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract and validate incoming correlation ID
        headers: List[Tuple[bytes, bytes]] = list(scope.get("headers", []))
        incoming_id = None
        for name, val in headers:
            if name.lower() in (b"x-request-id", b"x-correlation-id"):
                try:
                    incoming_id = val.decode("latin1")
                    break
                except Exception:
                    pass

        request_id = validate_or_generate_request_id(incoming_id)
        token = set_request_id(request_id)
        start_time = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: Dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 200)
                res_headers: List[Tuple[bytes, bytes]] = list(message.get("headers", []))
                res_headers.append((b"x-request-id", request_id.encode("latin1")))
                message["headers"] = res_headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            method = scope.get("method", "GET")
            path = scope.get("path", "/")

            # Suppress log noise for successful health probes
            if path in ("/health", "/health/live", "/health/ready") and status_code < 400:
                access_logger.debug(
                    "HTTP %s %s %d in %.2fms",
                    method,
                    path,
                    status_code,
                    duration_ms,
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
            else:
                access_logger.info(
                    "HTTP %s %s %d in %.2fms",
                    method,
                    path,
                    status_code,
                    duration_ms,
                    extra={
                        "method": method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": round(duration_ms, 2),
                    },
                )
            reset_request_id(token)


class SecurityHeadersMiddleware:
    """Pure ASGI middleware injecting defensive security headers into all HTTP responses.

    Configured Headers:
    - X-Content-Type-Options: nosniff (Prevents MIME-type sniffing)
    - X-Frame-Options: DENY (Prevents clickjacking via iframe embedding)
    - Referrer-Policy: strict-origin-when-cross-origin (Protects path leakage in referrers)
    - Permissions-Policy: geolocation=(), camera=(), microphone=(), payment=() (Restricts unneeded hardware APIs)
    - Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' ws: wss:; font-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';
    - Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
      (Enforced ONLY in production environments over HTTPS; omitted on plain HTTP local development)
    """

    def __init__(self, app: Any, is_production: bool = False):
        self.app = app
        self.is_production = is_production

    async def __call__(
        self,
        scope: Dict[str, Any],
        receive: Callable[..., Any],
        send: Callable[..., Any],
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers: List[Tuple[bytes, bytes]] = list(message.get("headers", []))
                existing_names: Set[str] = {
                    k.decode("latin1").lower() for k, _ in headers
                }

                def add_header(name: str, value: str) -> None:
                    if name.lower() not in existing_names:
                        headers.append((name.encode("latin1"), value.encode("latin1")))
                        existing_names.add(name.lower())

                # Mandatory security headers for all environments
                add_header("X-Content-Type-Options", "nosniff")
                add_header("X-Frame-Options", "DENY")
                add_header("Referrer-Policy", "strict-origin-when-cross-origin")
                add_header(
                    "Permissions-Policy",
                    "geolocation=(), camera=(), microphone=(), payment=()",
                )
                add_header(
                    "Content-Security-Policy",
                    "default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' ws: wss:; font-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self';",
                )

                # Strict-Transport-Security (HSTS) only on HTTPS in production
                is_https = scope.get("scheme") == "https"
                if not is_https:
                    # Check X-Forwarded-Proto if behind SSL terminating reverse proxy
                    for header_name, header_val in headers:
                        if header_name.lower() == b"x-forwarded-proto" and b"https" in header_val.lower():
                            is_https = True
                            break

                if self.is_production and is_https:
                    add_header(
                        "Strict-Transport-Security",
                        "max-age=31536000; includeSubDomains; preload",
                    )

                message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_with_security_headers)
