"""AI Provider Exception Hierarchy.

Defines standardized, provider-agnostic exceptions for LLM and demonstration
viva engine failures, ensuring sensitive credentials or raw payloads are never
leaked to higher layers or API responses.
"""

from typing import Optional


class AIProviderError(Exception):
    """Base exception for all AI provider operations."""

    def __init__(
        self,
        message: str = "An unexpected error occurred in the AI evaluation engine",
        provider_id: str = "unknown",
        retryable: bool = False,
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.provider_id = provider_id
        self.retryable = retryable
        self.original_error = original_error

    def __str__(self) -> str:
        return f"[{self.provider_id}] {self.message}"

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"provider_id={self.provider_id!r}, "
            f"retryable={self.retryable!r})"
        )


class AIProviderUnavailableError(AIProviderError):
    """Raised when an AI provider endpoint or service is unreachable or offline."""

    def __init__(
        self,
        message: str = "The AI evaluation service is currently unavailable",
        provider_id: str = "unknown",
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message=message, provider_id=provider_id, retryable=True, original_error=original_error)


class AIProviderTimeoutError(AIProviderError):
    """Raised when an AI provider call exceeds the configured latency threshold."""

    def __init__(
        self,
        message: str = "The AI provider request timed out",
        provider_id: str = "unknown",
        timeout_seconds: Optional[float] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message=message, provider_id=provider_id, retryable=True, original_error=original_error)
        self.timeout_seconds = timeout_seconds


class AIProviderResponseError(AIProviderError):
    """Raised when an AI provider returns malformed, unparseable, or schema-violating output."""

    def __init__(
        self,
        message: str = "The AI provider returned an invalid or unparseable response",
        provider_id: str = "unknown",
        raw_response: Optional[str] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message=message, provider_id=provider_id, retryable=False, original_error=original_error)
        self.raw_response = raw_response


class AIProviderRateLimitError(AIProviderError):
    """Raised when external provider quotas or rate limits are exceeded (e.g. HTTP 429)."""

    def __init__(
        self,
        message: str = "AI provider rate limit or quota exceeded",
        provider_id: str = "unknown",
        retry_after_seconds: Optional[float] = None,
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message=message, provider_id=provider_id, retryable=True, original_error=original_error)
        self.retry_after_seconds = retry_after_seconds


class AIProviderConfigError(AIProviderError):
    """Raised when an AI provider is misconfigured (e.g. missing required model identifier)."""

    def __init__(
        self,
        message: str = "The AI provider configuration is invalid",
        provider_id: str = "unknown",
        original_error: Optional[Exception] = None,
    ) -> None:
        super().__init__(message=message, provider_id=provider_id, retryable=False, original_error=original_error)
