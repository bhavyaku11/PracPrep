"""Central Rate Limiting Configuration.

Provides a centralized Limiter instance using slowapi with documented client IP
resolution, testing isolation, and zero external infrastructure requirements (in-memory).

Architectural Notes:
1. In-Memory Process-Local Storage:
   For the MVP single-instance container deployment, slowapi stores request counts
   in-memory. Counters are process-local and not shared across separate ASGI worker
   processes or container replicas until a distributed storage adapter (e.g., Redis)
   is introduced in a future scale-out phase.

2. Client Identification & Proxy Safety:
   The client IP resolution strategy uses direct client socket address (request.client.host).
   Forwarded headers like X-Forwarded-For are not blindly trusted to prevent IP spoofing
   bypass unless explicitly routed through a known, trusted reverse proxy.
   Test isolation is supported via the X-Test-Client-Id header.
"""

from fastapi import Request
from slowapi import Limiter
from app.core.config import get_settings


def get_client_ip(request: Request) -> str:
    """Resolve client identifier for rate limiting.

    Strategy:
    1. Test client isolation:
       ONLY when the application is explicitly running in a test environment
       (ENVIRONMENT == 'testing' or 'test'), the 'X-Test-Client-Id' header is honored.
       This enables test suites running against test-configured apps to isolate test
       runners or concurrent test cases without counter interference.

    2. Development, Staging, and Production environments:
       'X-Test-Client-Id' is strictly ignored. The client IP is resolved directly from
       the socket address (request.client.host). Arbitrary forwarding headers
       (e.g., X-Forwarded-For, X-Real-IP) are untrusted to prevent header-spoofing
       rate limit bypasses.

    3. Safe default fallback:
       Returns '127.0.0.1' if client socket details are unavailable.
    """
    settings = None
    if hasattr(request, "app") and hasattr(request.app, "state"):
        settings = getattr(request.app.state, "settings", None)
    if settings is None:
        settings = get_settings()

    is_test_env = settings.ENVIRONMENT.lower() in ("testing", "test")
    if is_test_env:
        test_id = request.headers.get("X-Test-Client-Id")
        if test_id and test_id.strip():
            return f"test:{test_id.strip()}"

    if request.client and request.client.host:
        return request.client.host

    return "127.0.0.1"


# Initialize central limiter singleton with in-memory storage and disabled automatic header injection
# (automatic header injection requires explicit response argument on endpoints; custom headers are injected in error handler)
limiter = Limiter(
    key_func=get_client_ip,
    headers_enabled=False,
    default_limits=[],
    storage_uri="memory://",
    strategy="fixed-window",
)
