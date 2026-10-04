"""AI Provider Factory & Orchestration Layer.

Provides centralized resolution, initialization, and resilient automatic fallback
orchestration for AI viva examination providers (Google Gemini and deterministic demonstration).
"""

import asyncio
import logging
from typing import Any, Optional

from app.core.config import Settings, get_settings
from app.modules.ai.base import BaseAIProvider
from app.modules.ai.circuit_breaker import CircuitBreaker
from app.modules.ai.demonstration import DemonstrationAIProvider
from app.modules.ai.exceptions import (
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.modules.ai.gemini import GeminiAIProvider
from app.modules.ai.schemas import (
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    VivaProviderModeEnum,
    ParsedExperimentSections,
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


# ==============================================================================
# Fallback AI Provider Orchestration
# ==============================================================================


class FallbackAIProvider(BaseAIProvider):
    """Resilient AI Provider Orchestrator with Circuit Breaker and Demonstration Fallback.

    Delegates question generation and answer evaluation requests to a primary live
    provider (e.g. Google Gemini) when healthy. When the primary provider is unconfigured,
    tripped by the circuit breaker, or experiences qualifying availability failures,
    the orchestrator transparently fails over to the deterministic DemonstrationAIProvider.
    """

    def __init__(
        self,
        primary_provider: Optional[BaseAIProvider] = None,
        fallback_provider: Optional[BaseAIProvider] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ) -> None:
        """Initialize the fallback provider orchestrator.

        Args:
            primary_provider: Primary live AI provider (e.g. GeminiAIProvider).
            fallback_provider: Secondary fallback provider (defaults to DemonstrationAIProvider).
            circuit_breaker: Circuit breaker instance managing availability state.
        """
        self._primary_provider = primary_provider
        self._fallback_provider = fallback_provider or DemonstrationAIProvider()
        self._circuit_breaker = circuit_breaker or CircuitBreaker()

    @property
    def primary_provider(self) -> Optional[BaseAIProvider]:
        """Configured primary live provider."""
        return self._primary_provider

    @property
    def fallback_provider(self) -> BaseAIProvider:
        """Configured fallback provider."""
        return self._fallback_provider

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        """Attached circuit breaker."""
        return self._circuit_breaker

    @property
    def provider_id(self) -> str:
        """Provider machine identifier, reflecting the primary provider if configured."""
        if self._primary_provider:
            return self._primary_provider.provider_id
        return self._fallback_provider.provider_id

    @property
    def display_name(self) -> str:
        """Human-readable display name, reflecting the primary provider if configured."""
        if self._primary_provider:
            return self._primary_provider.display_name
        return self._fallback_provider.display_name

    @property
    def provider_mode(self) -> VivaProviderModeEnum:
        """Operational category, reflecting the primary provider if configured."""
        if self._primary_provider:
            return self._primary_provider.provider_mode
        return self._fallback_provider.provider_mode

    async def generate_questions(
        self,
        request: QuestionGenerationRequest,
    ) -> QuestionGenerationResponse:
        """Generate viva questions with automatic circuit-breaker fallback.

        1. If primary provider is unconfigured, delegates directly to fallback.
        2. If circuit breaker blocks traffic (OPEN), delegates directly to fallback.
        3. If circuit breaker permits attempt (CLOSED or HALF_OPEN trial), calls primary.
        4. If primary succeeds: records success on breaker and returns result.
        5. If primary fails with a qualifying availability failure (5xx, timeout, rate limit):
           records failure on breaker and transparently returns fallback response.
        6. Non-availability exceptions (schema violations, user errors) are re-raised.
        7. asyncio.CancelledError is never swallowed and propagates immediately.
        """
        if self._primary_provider is None:
            logger.info("Primary AI provider not configured; delegating generate_questions to demonstration provider.")
            return await self._fallback_provider.generate_questions(request)

        can_attempt = await self._circuit_breaker.can_attempt()
        if not can_attempt:
            logger.warning(
                "Circuit breaker [%s] is blocking calls to primary provider; delegating generate_questions to demonstration provider.",
                self._circuit_breaker.state.value,
            )
            return await self._fallback_provider.generate_questions(request)

        try:
            response = await self._primary_provider.generate_questions(request)
            await self._circuit_breaker.record_success()
            return response
        except asyncio.CancelledError:
            await self._circuit_breaker.record_cancellation()
            raise
        except Exception as exc:
            is_qualifying = self._circuit_breaker.is_qualifying_failure(exc)
            await self._circuit_breaker.record_failure(exc)

            if is_qualifying:
                logger.warning(
                    "Primary AI provider failed with %s: %s; falling back to demonstration provider for generate_questions.",
                    exc.__class__.__name__,
                    _sanitize_message(str(exc)),
                )
                return await self._fallback_provider.generate_questions(request)
            else:
                logger.error(
                    "Primary AI provider encountered non-availability error during generate_questions: %s; re-raising without fallback.",
                    _sanitize_message(str(exc)),
                )
                raise

    async def evaluate_answer(
        self,
        request: AnswerEvaluationRequest,
    ) -> AnswerEvaluationResponse:
        """Evaluate student viva answer with automatic circuit-breaker fallback.

        Follows identical resilience semantics to generate_questions.
        """
        if self._primary_provider is None:
            logger.info("Primary AI provider not configured; delegating evaluate_answer to demonstration provider.")
            return await self._fallback_provider.evaluate_answer(request)

        can_attempt = await self._circuit_breaker.can_attempt()
        if not can_attempt:
            logger.warning(
                "Circuit breaker [%s] is blocking calls to primary provider; delegating evaluate_answer to demonstration provider.",
                self._circuit_breaker.state.value,
            )
            return await self._fallback_provider.evaluate_answer(request)

        try:
            response = await self._primary_provider.evaluate_answer(request)
            await self._circuit_breaker.record_success()
            return response
        except asyncio.CancelledError:
            await self._circuit_breaker.record_cancellation()
            raise
        except Exception as exc:
            is_qualifying = self._circuit_breaker.is_qualifying_failure(exc)
            await self._circuit_breaker.record_failure(exc)

            if is_qualifying:
                logger.warning(
                    "Primary AI provider failed with %s: %s; falling back to demonstration provider for evaluate_answer.",
                    exc.__class__.__name__,
                    _sanitize_message(str(exc)),
                )
                return await self._fallback_provider.evaluate_answer(request)
            else:
                logger.error(
                    "Primary AI provider encountered non-availability error during evaluate_answer: %s; re-raising without fallback.",
                    _sanitize_message(str(exc)),
                )
                raise

    async def parse_manual_sections(
        self,
        raw_text: str,
        file_name: Optional[str] = None,
    ) -> ParsedExperimentSections:
        """Parse manual sections with primary live provider and automatic demonstration fallback."""
        if not self._primary_provider:
            return await self._fallback_provider.parse_manual_sections(raw_text, file_name)

        if not self._circuit_breaker.can_execute():
            logger.warning(
                "Circuit breaker is OPEN for primary AI provider; falling back to DemonstrationAIProvider for section parsing."
            )
            return await self._fallback_provider.parse_manual_sections(raw_text, file_name)

        try:
            result = await self._primary_provider.parse_manual_sections(raw_text, file_name)
            await self._circuit_breaker.record_success()
            return result
        except Exception as exc:
            if self._is_qualifying_availability_failure(exc):
                await self._circuit_breaker.record_failure()
                logger.warning(
                    "Primary AI provider failed with %s during parse_manual_sections (%s); falling back to DemonstrationAIProvider.",
                    exc.__class__.__name__,
                    _sanitize_message(str(exc)),
                )
                return await self._fallback_provider.parse_manual_sections(raw_text, file_name)
            else:
                logger.error(
                    "Primary AI provider encountered non-availability error during parse_manual_sections: %s; re-raising without fallback.",
                    _sanitize_message(str(exc)),
                )
                raise


# ==============================================================================
# AI Provider Factory
# ==============================================================================


class AIProviderFactory:
    """Central factory for resolving and instantiating AI examination providers."""

    @classmethod
    def create_provider(
        cls,
        provider_name: Optional[str] = None,
        settings: Optional[Settings] = None,
        with_fallback: bool = True,
        circuit_breaker: Optional[CircuitBreaker] = None,
        gemini_client: Optional[Any] = None,
    ) -> BaseAIProvider:
        """Instantiate and configure an AI viva provider based on application settings.

        Args:
            provider_name: Explicit provider name override ('gemini', 'demonstration').
            settings: Optional Settings instance (uses singleton get_settings() if omitted).
            with_fallback: If True, wraps live providers in FallbackAIProvider with circuit breaker.
            circuit_breaker: Optional existing CircuitBreaker instance.
            gemini_client: Optional injected SDK client for Gemini (useful for testing).

        Returns:
            An object conforming to BaseAIProvider.

        Raises:
            AIProviderConfigError: If an unsupported provider name is specified.
        """
        active_settings = settings or get_settings()

        # Determine target provider:
        # 1. Explicit override if provided.
        # 2. If DEFAULT_AI_PROVIDER is 'gemini', target is 'gemini'.
        # 3. If GEMINI_API_KEY is configured or gemini_client is supplied, target is 'gemini'.
        # 4. Otherwise, use DEFAULT_AI_PROVIDER.
        if provider_name is not None:
            target = provider_name.strip().lower()
        elif active_settings.DEFAULT_AI_PROVIDER.strip().lower() == "gemini":
            target = "gemini"
        elif active_settings.GEMINI_API_KEY is not None and bool(active_settings.GEMINI_API_KEY.get_secret_value().strip()):
            target = "gemini"
        elif gemini_client is not None:
            target = "gemini"
        else:
            target = active_settings.DEFAULT_AI_PROVIDER.strip().lower()

        if target == "demonstration":
            return DemonstrationAIProvider()

        if target == "gemini":
            has_credentials = (
                active_settings.GEMINI_API_KEY is not None
                and bool(active_settings.GEMINI_API_KEY.get_secret_value().strip())
            ) or (gemini_client is not None)

            if not has_credentials:
                logger.warning(
                    "Google Gemini API key is missing or not configured; "
                    "falling back to DemonstrationAIProvider."
                )
                return DemonstrationAIProvider()

            try:
                gemini_provider = GeminiAIProvider(
                    model_name=active_settings.GEMINI_MODEL,
                    timeout_seconds=active_settings.GEMINI_TIMEOUT_SECONDS,
                    max_retries=active_settings.GEMINI_MAX_RETRIES,
                    client=gemini_client,
                )
            except AIProviderConfigError as exc:
                logger.warning(
                    "Failed to configure GeminiAIProvider (%s); falling back to DemonstrationAIProvider.",
                    exc,
                )
                return DemonstrationAIProvider()

            if not with_fallback:
                return gemini_provider

            cb = circuit_breaker or CircuitBreaker(
                failure_threshold=active_settings.AI_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
                recovery_timeout=active_settings.AI_CIRCUIT_BREAKER_RECOVERY_SECONDS,
            )
            return FallbackAIProvider(
                primary_provider=gemini_provider,
                fallback_provider=DemonstrationAIProvider(),
                circuit_breaker=cb,
            )

        if target == "openai":
            has_openai_credentials = (
                active_settings.OPENAI_API_KEY is not None
                and bool(active_settings.OPENAI_API_KEY.get_secret_value().strip())
            )
            if not has_openai_credentials:
                logger.warning(
                    "OpenAI API key is missing or not configured; "
                    "falling back to DemonstrationAIProvider."
                )
                return DemonstrationAIProvider()
            raise AIProviderConfigError(
                "OpenAI provider integration is scheduled for a future milestone.",
                provider_id="openai",
            )

        raise AIProviderConfigError(
            f"Unsupported AI viva provider: {target!r}. Supported providers: 'gemini', 'demonstration'.",
            provider_id=target,
        )


def get_ai_provider(
    provider_name: Optional[str] = None,
    settings: Optional[Settings] = None,
    with_fallback: bool = True,
    circuit_breaker: Optional[CircuitBreaker] = None,
    gemini_client: Optional[Any] = None,
) -> BaseAIProvider:
    """Convenience function to obtain the configured BaseAIProvider instance.

    Args:
        provider_name: Optional explicit provider identifier override ('gemini', 'demonstration').
        settings: Optional Settings instance (uses singleton get_settings() if omitted).
        with_fallback: Whether to wrap with FallbackAIProvider and CircuitBreaker.
        circuit_breaker: Optional existing CircuitBreaker instance.
        gemini_client: Optional mock SDK client for testing.

    Returns:
        An instance implementing BaseAIProvider.
    """
    return AIProviderFactory.create_provider(
        provider_name=provider_name,
        settings=settings,
        with_fallback=with_fallback,
        circuit_breaker=circuit_breaker,
        gemini_client=gemini_client,
    )
