"""Unit Tests for AI Provider Circuit Breaker.

Tests the asynchronous three-state (CLOSED, OPEN, HALF_OPEN) circuit breaker
concurrency control, timeout-driven state transitions, qualifying failure filters,
and cancellation safety. Zero network calls or external quota consumed.
"""

import asyncio
from unittest.mock import MagicMock
import pytest
from pydantic import ValidationError

from app.modules.ai.circuit_breaker import CircuitBreaker, CircuitState
from app.modules.ai.exceptions import (
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)


class MockClock:
    """Deterministic simulated clock for circuit breaker cooldown testing."""

    def __init__(self, start_time: float = 1000.0) -> None:
        self._time = start_time

    def now(self) -> float:
        return self._time

    def advance(self, seconds: float) -> None:
        self._time += seconds


class TestCircuitBreakerStateTransitions:
    """Test standard state machine transitions and threshold tracking."""

    @pytest.mark.asyncio
    async def test_initial_state_is_closed(self) -> None:
        """Circuit breaker must start in CLOSED state with 0 failures."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.failure_threshold == 3
        assert cb.recovery_timeout == 30.0
        assert await cb.can_attempt() is True

    @pytest.mark.asyncio
    async def test_invalid_parameters_raise_value_error(self) -> None:
        """Invalid threshold or timeout values must be rejected."""
        with pytest.raises(ValueError, match="failure_threshold must be >= 1"):
            CircuitBreaker(failure_threshold=0)

        with pytest.raises(ValueError, match="recovery_timeout must be > 0.0"):
            CircuitBreaker(failure_threshold=3, recovery_timeout=0.0)

        with pytest.raises(ValueError, match="recovery_timeout must be > 0.0"):
            CircuitBreaker(failure_threshold=3, recovery_timeout=-5.0)

    @pytest.mark.asyncio
    async def test_opens_after_configured_qualifying_failures(self) -> None:
        """Circuit breaker trips to OPEN upon reaching failure threshold."""
        clock = MockClock()
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30.0, time_func=clock.now)

        # 1st failure: remains CLOSED
        await cb.record_failure(AIProviderUnavailableError("503 Service Unavailable"))
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 1
        assert await cb.can_attempt() is True

        # 2nd failure: remains CLOSED
        await cb.record_failure(AIProviderTimeoutError("Request timed out"))
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2
        assert await cb.can_attempt() is True

        # 3rd failure: trips to OPEN
        await cb.record_failure(AIProviderRateLimitError("429 Too Many Requests"))
        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3
        assert await cb.can_attempt() is False

    @pytest.mark.asyncio
    async def test_remains_open_before_recovery_timeout(self) -> None:
        """Circuit breaker must block attempts while recovery cooldown is active."""
        clock = MockClock(100.0)
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, time_func=clock.now)

        await cb.record_failure(AIProviderUnavailableError("500 Server Error"))
        await cb.record_failure(AIProviderUnavailableError("500 Server Error"))
        assert cb.state == CircuitState.OPEN

        # Advance 15s (timeout is 30s)
        clock.advance(15.0)
        assert cb.state == CircuitState.OPEN
        assert await cb.can_attempt() is False

        # Advance another 14s (total 29s elapsed)
        clock.advance(14.0)
        assert cb.state == CircuitState.OPEN
        assert await cb.can_attempt() is False

    @pytest.mark.asyncio
    async def test_transitions_to_half_open_after_recovery_timeout(self) -> None:
        """Circuit transitions to HALF_OPEN when recovery timeout elapses."""
        clock = MockClock(100.0)
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, time_func=clock.now)

        await cb.record_failure(AIProviderUnavailableError("500"))
        await cb.record_failure(AIProviderUnavailableError("500"))
        assert cb.state == CircuitState.OPEN

        # Exactly 30s elapsed
        clock.advance(30.0)
        assert cb.state == CircuitState.HALF_OPEN

        # First request should be allowed as trial probe
        assert await cb.can_attempt() is True
        assert cb.trial_in_progress is True

        # Second request while trial is in progress must be blocked
        assert await cb.can_attempt() is False

    @pytest.mark.asyncio
    async def test_successful_trial_closes_circuit(self) -> None:
        """Successful trial probe restores breaker to CLOSED and resets failure count."""
        clock = MockClock(100.0)
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, time_func=clock.now)

        await cb.record_failure(AIProviderUnavailableError("500"))
        await cb.record_failure(AIProviderUnavailableError("500"))
        assert cb.state == CircuitState.OPEN

        clock.advance(35.0)
        assert await cb.can_attempt() is True  # Probe dispatched

        # Trial succeeds
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.trial_in_progress is False
        assert await cb.can_attempt() is True

    @pytest.mark.asyncio
    async def test_failed_trial_reopens_circuit(self) -> None:
        """Failed trial probe in HALF_OPEN immediately trips circuit back to OPEN."""
        clock = MockClock(100.0)
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=30.0, time_func=clock.now)

        await cb.record_failure(AIProviderUnavailableError("500"))
        await cb.record_failure(AIProviderUnavailableError("500"))
        assert cb.state == CircuitState.OPEN

        clock.advance(30.0)
        assert await cb.can_attempt() is True  # Enter HALF_OPEN, trial active

        # Trial probe fails at t=130
        await cb.record_failure(AIProviderUnavailableError("503 Backend down"))
        assert cb.state == CircuitState.OPEN
        assert cb.trial_in_progress is False
        assert await cb.can_attempt() is False

        # Must wait another 30s from t=130
        clock.advance(20.0)  # t=150
        assert cb.state == CircuitState.OPEN
        assert await cb.can_attempt() is False

        clock.advance(11.0)  # t=161 (31s after second failure)
        assert cb.state == CircuitState.HALF_OPEN
        assert await cb.can_attempt() is True

    @pytest.mark.asyncio
    async def test_success_in_closed_state_resets_failures(self) -> None:
        """Intermittent success resets consecutive failure count before threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        await cb.record_failure(AIProviderUnavailableError("fail 1"))
        await cb.record_failure(AIProviderUnavailableError("fail 2"))
        assert cb.failure_count == 2
        assert cb.state == CircuitState.CLOSED

        # Success occurs
        await cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

        # New failure starts from count 1
        await cb.record_failure(AIProviderUnavailableError("fail 3"))
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_manual_reset(self) -> None:
        """Manual reset forces CLOSED state and clears all failure counters."""
        cb = CircuitBreaker(failure_threshold=1)
        await cb.record_failure(AIProviderUnavailableError("trip"))
        assert cb.state == CircuitState.OPEN

        await cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.trial_in_progress is False
        assert await cb.can_attempt() is True


class TestQualifyingFailures:
    """Verify that only provider availability failures increment failure counts."""

    @pytest.mark.asyncio
    async def test_qualifying_exceptions(self) -> None:
        """Unavailable, Timeout, RateLimit, and network errors are qualifying."""
        cb = CircuitBreaker(failure_threshold=10)

        qualifying = [
            AIProviderUnavailableError("503"),
            AIProviderTimeoutError("Timeout"),
            AIProviderRateLimitError("429"),
            AIProviderError("Generic retryable", retryable=True),
            TimeoutError("System timeout"),
            ConnectionError("Connection refused"),
            OSError("Network down"),
        ]

        for exc in qualifying:
            assert cb.is_qualifying_failure(exc) is True
            count_before = cb.failure_count
            await cb.record_failure(exc)
            assert cb.failure_count == count_before + 1

    @pytest.mark.asyncio
    async def test_non_qualifying_exceptions_do_not_increment_counter(self) -> None:
        """Malformed outputs, client errors, validation errors, and programming errors do not trip."""
        cb = CircuitBreaker(failure_threshold=3)

        non_qualifying = [
            AIProviderResponseError("Malformed JSON response"),
            AIProviderConfigError("Missing key"),
            ValueError("Bad argument"),
            TypeError("Type mismatch"),
            KeyError("missing_field"),
            RuntimeError("Arbitrary runtime error"),
        ]

        for exc in non_qualifying:
            assert cb.is_qualifying_failure(exc) is False
            await cb.record_failure(exc)
            assert cb.failure_count == 0
            assert cb.state == CircuitState.CLOSED


class TestConcurrencyAndCancellation:
    """Test async task safety and cancellation recovery."""

    @pytest.mark.asyncio
    async def test_concurrent_probes_in_half_open(self) -> None:
        """Only exactly ONE concurrent task receives permission to probe in HALF_OPEN."""
        clock = MockClock(100.0)
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0, time_func=clock.now)

        await cb.record_failure(AIProviderUnavailableError("trip"))
        assert cb.state == CircuitState.OPEN

        clock.advance(35.0)
        assert cb.state == CircuitState.HALF_OPEN

        # Launch 25 concurrent tasks competing for the trial probe
        results = await asyncio.gather(*(cb.can_attempt() for _ in range(25)))

        # Exactly one task should succeed; all 24 others must be rejected
        assert results.count(True) == 1
        assert results.count(False) == 24
        assert cb.trial_in_progress is True

    @pytest.mark.asyncio
    async def test_cancellation_releases_trial_probe(self) -> None:
        """Cancelling a trial probe in HALF_OPEN frees the slot without tripping circuit."""
        clock = MockClock(100.0)
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=30.0, time_func=clock.now)

        await cb.record_failure(AIProviderUnavailableError("trip"))
        clock.advance(35.0)

        # Grab probe
        assert await cb.can_attempt() is True
        assert cb.trial_in_progress is True

        # Probe cancelled
        await cb.record_cancellation()
        assert cb.trial_in_progress is False

        # Next caller can attempt the probe again
        assert await cb.can_attempt() is True
