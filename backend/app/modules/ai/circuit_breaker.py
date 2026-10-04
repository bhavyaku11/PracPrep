"""AI Provider Circuit Breaker.

Implements an asynchronous, in-process three-state circuit breaker to protect the
application from cascading failures during external LLM outages, rate limiting,
or persistent network instability.

State Machine:
--------------
1. CLOSED:
   - Normal operating state.
   - All requests are dispatched to the primary live AI provider (Google Gemini).
   - Tracks consecutive qualifying provider availability failures.
   - If failures reach or exceed `failure_threshold`, transitions to OPEN.
   - Any successful provider execution resets the consecutive failure counter to 0.

2. OPEN:
   - Outage / trip state.
   - Calls to the primary live provider are blocked immediately.
   - Operations automatically bypass the primary provider and delegate to the
     deterministic fallback provider without incurring network latency or quota.
   - Once `recovery_timeout` seconds have elapsed since the last failure,
     transitions to HALF_OPEN.

3. HALF_OPEN:
   - Recovery trial state.
   - Permits exactly ONE trial probe request to test live provider health.
   - Any concurrent requests arriving while the probe is active are redirected
     to the fallback provider without waiting or blocking.
   - If the trial probe succeeds:
     The circuit closes (CLOSED), resetting the failure counter to 0.
   - If the trial probe fails with a qualifying availability failure:
     The circuit immediately trips back to OPEN, resetting the recovery cooldown.
   - If the trial probe is cancelled or raises a non-availability error:
     The trial probe slot is released without tripping the circuit.

Concurrency Strategy:
---------------------
- State transitions and counter updates are guarded by an asynchronous lock (`asyncio.Lock`).
- Non-blocking monotonic clocks (`time.monotonic`) are used for elapsed time measurements.
- Thread/task safe; prevents race conditions during concurrent trial requests.
"""

from enum import Enum
import logging
import time
from typing import Callable, Optional

from app.modules.ai.exceptions import (
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)

import re

logger = logging.getLogger(__name__)

# Regex to detect potential Google API keys and Bearer tokens for log redaction
_API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z-_]{20,50}")
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)


def _sanitize_message(message: str) -> str:
    """Redact API keys and bearer tokens from error messages and log outputs."""
    sanitized = _API_KEY_PATTERN.sub("[REDACTED_API_KEY]", message)
    sanitized = _BEARER_PATTERN.sub("Bearer [REDACTED_TOKEN]", sanitized)
    return sanitized


class CircuitState(str, Enum):
    """Explicit operational states of the AI provider circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """In-process asynchronous circuit breaker for AI provider resilience.

    Protects against downstream LLM outages by monitoring consecutive qualifying
    failures and shedding load to the deterministic demonstration engine.
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        time_func: Optional[Callable[[], float]] = None,
    ) -> None:
        """Initialize the circuit breaker.

        Args:
            failure_threshold: Number of consecutive qualifying failures before tripping OPEN.
            recovery_timeout: Cooldown duration in seconds before attempting HALF_OPEN recovery.
            time_func: Monotonic time callable, injectible for deterministic unit testing.
        """
        if failure_threshold < 1:
            raise ValueError(f"failure_threshold must be >= 1, got {failure_threshold}")
        if recovery_timeout <= 0.0:
            raise ValueError(f"recovery_timeout must be > 0.0, got {recovery_timeout}")

        self._failure_threshold = failure_threshold
        self._recovery_timeout = float(recovery_timeout)
        self._time_func = time_func or time.monotonic

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._trial_in_progress = False
        self._lock: Optional[any] = None

    @property
    def _async_lock(self):
        """Lazily initialize the asyncio Lock to ensure attachment to the active event loop."""
        import asyncio
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    @property
    def failure_threshold(self) -> int:
        """Configured failure threshold before tripping OPEN."""
        return self._failure_threshold

    @property
    def recovery_timeout(self) -> float:
        """Configured recovery timeout in seconds."""
        return self._recovery_timeout

    @property
    def failure_count(self) -> int:
        """Current consecutive qualifying failure count."""
        return self._failure_count

    @property
    def trial_in_progress(self) -> bool:
        """Whether a recovery trial probe is currently in-flight in HALF_OPEN state."""
        return self._trial_in_progress

    @property
    def last_failure_time(self) -> float:
        """Monotonic timestamp of the most recent qualifying failure."""
        return self._last_failure_time

    @property
    def state(self) -> CircuitState:
        """Current operational state, evaluating cooldown expiry dynamically."""
        if self._state == CircuitState.OPEN:
            if self._time_func() - self._last_failure_time >= self._recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    def is_qualifying_failure(self, exception: Exception) -> bool:
        """Determine whether an exception indicates a provider availability outage.

        Qualifying failures:
        - AIProviderUnavailableError (HTTP 5xx, network reachability, service outage)
        - AIProviderTimeoutError (latency exceeding SLA threshold)
        - AIProviderRateLimitError (HTTP 429 quota exhaustion)
        - Any retryable AIProviderError
        - Low-level network/socket/connection/timeout errors

        Non-qualifying failures (do NOT trip the breaker):
        - AIProviderResponseError (malformed model response, validation failure)
        - AIProviderConfigError (misconfiguration / missing keys)
        - pydantic.ValidationError (schema or boundary mismatch)
        - Standard application/programming errors (ValueError, TypeError, KeyError)
        - asyncio.CancelledError (must be propagated immediately)
        """
        if isinstance(
            exception,
            (AIProviderUnavailableError, AIProviderTimeoutError, AIProviderRateLimitError),
        ):
            return True

        if isinstance(exception, AIProviderError) and exception.retryable:
            return True

        if isinstance(exception, (TimeoutError, ConnectionError, OSError)):
            return True

        return False

    async def can_attempt(self) -> bool:
        """Check whether an execution against the primary live provider is permitted.

        Returns:
            True if the circuit is CLOSED or if the current request is the designated
            HALF_OPEN trial probe. Returns False if the circuit is OPEN or if another
            probe is already in-flight in HALF_OPEN.
        """
        async with self._async_lock:
            now = self._time_func()

            # Check if OPEN cooldown has expired
            if self._state == CircuitState.OPEN:
                if now - self._last_failure_time >= self._recovery_timeout:
                    logger.info(
                        "Circuit breaker cooldown (%ss) elapsed; transitioning OPEN -> HALF_OPEN.",
                        self._recovery_timeout,
                    )
                    self._state = CircuitState.HALF_OPEN
                    self._trial_in_progress = False

            # CLOSED allows all traffic
            if self._state == CircuitState.CLOSED:
                return True

            # HALF_OPEN permits exactly ONE probe trial
            if self._state == CircuitState.HALF_OPEN:
                if not self._trial_in_progress:
                    self._trial_in_progress = True
                    logger.info("Circuit breaker permitting single trial probe in HALF_OPEN state.")
                    return True
                return False

            # OPEN blocks traffic
            return False

    async def record_success(self) -> None:
        """Record a successful execution against the primary provider.

        Resets consecutive failure counts to 0 and restores the circuit to CLOSED.
        """
        async with self._async_lock:
            if self._state != CircuitState.CLOSED or self._failure_count > 0:
                logger.info(
                    "Primary AI provider call succeeded; resetting failure count and closing circuit (%s -> CLOSED).",
                    self._state.value,
                )
            self._failure_count = 0
            self._trial_in_progress = False
            self._state = CircuitState.CLOSED

    async def record_failure(self, exception: Optional[Exception] = None) -> None:
        """Record a failure from the primary provider.

        Only qualifying availability failures (timeouts, rate limits, network outages)
        increment the failure count or cause state transitions.

        Args:
            exception: The exception raised by the provider call.
        """
        async with self._async_lock:
            if exception is not None and not self.is_qualifying_failure(exception):
                # Non-qualifying exception (e.g. response schema or bad request).
                # Release trial slot if one was active so it does not block future trials.
                self._trial_in_progress = False
                return

            now = self._time_func()
            self._last_failure_time = now
            self._trial_in_progress = False

            if self._state == CircuitState.HALF_OPEN:
                logger.warning(
                    "Trial probe failed in HALF_OPEN; reopening circuit for %ss cooldown.",
                    self._recovery_timeout,
                )
                self._state = CircuitState.OPEN
            elif self._state == CircuitState.CLOSED:
                self._failure_count += 1
                logger.warning(
                    "Circuit breaker recorded qualifying failure (%d/%d): %s",
                    self._failure_count,
                    self._failure_threshold,
                    _sanitize_message(str(exception)),
                )
                if self._failure_count >= self._failure_threshold:
                    logger.error(
                        "Circuit breaker threshold reached (%d failures); tripping circuit CLOSED -> OPEN for %ss cooldown.",
                        self._failure_count,
                        self._recovery_timeout,
                    )
                    self._state = CircuitState.OPEN

    async def record_cancellation(self) -> None:
        """Record an in-flight request cancellation.

        Ensures that if an active trial probe was cancelled, the probe slot is
        safely freed without penalizing the provider or altering the state.
        """
        async with self._async_lock:
            self._trial_in_progress = False

    async def reset(self) -> None:
        """Force reset the circuit breaker to its initial CLOSED state."""
        async with self._async_lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0
            self._trial_in_progress = False
