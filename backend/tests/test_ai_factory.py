"""Unit Tests for AI Provider Factory & Resilient Fallback Orchestrator.

Tests factory provider resolution, credential-checking fallback, circuit breaker
orchestration for generate_questions and evaluate_answer, cancellation propagation,
and error handling. Uses mocked providers with zero real network calls or paid quota.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import SecretStr

from app.core.config import Settings
from app.modules.ai.base import BaseAIProvider
from app.modules.ai.circuit_breaker import CircuitBreaker, CircuitState
from app.modules.ai.demonstration import DemonstrationAIProvider
from app.modules.ai.exceptions import (
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.modules.ai.factory import AIProviderFactory, FallbackAIProvider, get_ai_provider
from app.modules.ai.gemini import GeminiAIProvider
from app.modules.ai.schemas import (
    AIEvaluationContextItem,
    AIExperimentContext,
    AIGeneratedQuestion,
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    EvaluationVerdictEnum,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    VivaDifficultyEnum,
    VivaProviderModeEnum,
    VivaTopicEnum,
)


# ==============================================================================
# Helpers & Test Fixtures
# ==============================================================================


def sample_experiment_context() -> AIExperimentContext:
    return AIExperimentContext(
        title="Ohm's Law Verification",
        subject="Electrical Science",
        objective="Verify V = IR across standard resistive loads",
        theory="Current through a conductor is proportional to voltage across it",
        apparatus="Ammeter, Voltmeter, Rheostat, DC Power Supply",
        procedure="1. Connect circuit in series. 2. Vary rheostat. 3. Record V and I.",
        precautions="Avoid overheating the wire. Zero meters before reading.",
    )


def sample_generation_request() -> QuestionGenerationRequest:
    return QuestionGenerationRequest(
        experiment=sample_experiment_context(),
        question_count=2,
        difficulty=VivaDifficultyEnum.BEGINNER,
        topic_focus=VivaTopicEnum.THEORY,
    )


def sample_evaluation_request() -> AnswerEvaluationRequest:
    return AnswerEvaluationRequest(
        question=AIGeneratedQuestion(
            id="q-eval-1",
            question_number=1,
            question_text="What is the primary scientific aim of Ohm's Law Verification?",
            expected_answer="To verify the linear relationship between voltage and current across a conductor.",
            difficulty=VivaDifficultyEnum.BEGINNER,
            topic=VivaTopicEnum.THEORY,
            key_points=["proportional", "temperature"],
        ),
        student_answer="To prove that voltage and current are directly proportional when temperature is constant.",
        experiment=sample_experiment_context(),
    )


def make_mock_gemini_provider() -> MagicMock:
    """Create a mock provider conforming to BaseAIProvider representing healthy Gemini."""
    mock = MagicMock(spec=BaseAIProvider)
    mock.provider_id = "gemini"
    mock.display_name = "Google Gemini"
    mock.provider_mode = VivaProviderModeEnum.AI_LIVE

    mock.generate_questions = AsyncMock(
        return_value=QuestionGenerationResponse(
            questions=[
                AIGeneratedQuestion(
                    id="gemini-q1",
                    question_number=1,
                    question_text="State Ohm's Law and its mathematical formula.",
                    expected_answer="V = IR at constant temperature.",
                    topic=VivaTopicEnum.THEORY,
                    difficulty=VivaDifficultyEnum.BEGINNER,
                    key_points=["V=IR", "temperature constant"],
                ),
                AIGeneratedQuestion(
                    id="gemini-q2",
                    question_number=2,
                    question_text="What instruments measure voltage and current?",
                    expected_answer="Voltmeter and ammeter respectively.",
                    topic=VivaTopicEnum.APPARATUS,
                    difficulty=VivaDifficultyEnum.BEGINNER,
                    key_points=["voltmeter", "ammeter"],
                ),
            ],
            provider_id="gemini",
            provider_mode=VivaProviderModeEnum.AI_LIVE,
            metadata={"model_name": "gemini-2.5-flash"},
        )
    )

    mock.evaluate_answer = AsyncMock(
        return_value=AnswerEvaluationResponse(
            score=9.0,
            verdict=EvaluationVerdictEnum.CORRECT,
            feedback="Accurate statement of Ohm's Law and its temperature condition.",
            what_you_got_right="Ohm's Law formula and temperature condition.",
            what_was_missing="",
            expected_answer="To verify that V is proportional to I.",
            improvement_tip="Always specify SI units during viva voce.",
            key_points_covered=["proportional", "temperature"],
            key_points_missed=[],
            provider_id="gemini",
            provider_mode=VivaProviderModeEnum.AI_LIVE,
            metadata={"model_name": "gemini-2.5-flash"},
        )
    )

    return mock


# ==============================================================================
# Factory Resolution Tests
# ==============================================================================


class TestAIProviderFactoryResolution:
    """Test resolution logic, configuration handling, and provider instantiation."""

    def test_factory_returns_base_ai_provider(self) -> None:
        """Any provider returned by the factory must implement BaseAIProvider."""
        provider = get_ai_provider("demonstration")
        assert isinstance(provider, BaseAIProvider)
        assert provider.provider_id == "demonstration"
        assert provider.provider_mode == VivaProviderModeEnum.DEMONSTRATION

    def test_explicit_demonstration_provider_selection(self) -> None:
        """Explicitly requesting 'demonstration' returns DemonstrationAIProvider directly."""
        provider = AIProviderFactory.create_provider(provider_name="demonstration")
        assert isinstance(provider, DemonstrationAIProvider)
        assert provider.provider_id == "demonstration"

    def test_gemini_selected_when_configured(self) -> None:
        """When Gemini API key is configured, factory selects Gemini with FallbackAIProvider."""
        custom_settings = Settings(
            GEMINI_API_KEY=SecretStr("AIzaSyFakeKeyForUnitTestingPurposesOnly12345"),
            DEFAULT_AI_PROVIDER="gemini",
        )
        fake_client = MagicMock()
        provider = get_ai_provider(settings=custom_settings, gemini_client=fake_client)

        assert isinstance(provider, FallbackAIProvider)
        assert provider.provider_id == "gemini"
        assert provider.display_name == "Google Gemini"
        assert provider.provider_mode == VivaProviderModeEnum.AI_LIVE
        assert isinstance(provider.primary_provider, GeminiAIProvider)
        assert isinstance(provider.fallback_provider, DemonstrationAIProvider)
        assert isinstance(provider.circuit_breaker, CircuitBreaker)

    def test_gemini_without_fallback_returns_raw_provider(self) -> None:
        """When with_fallback=False is passed, raw GeminiAIProvider is returned."""
        custom_settings = Settings(
            GEMINI_API_KEY=SecretStr("AIzaSyFakeKeyForUnitTestingPurposesOnly12345"),
            DEFAULT_AI_PROVIDER="gemini",
        )
        fake_client = MagicMock()
        provider = get_ai_provider(
            settings=custom_settings,
            with_fallback=False,
            gemini_client=fake_client,
        )

        assert isinstance(provider, GeminiAIProvider)
        assert provider.provider_id == "gemini"

    def test_demonstration_selected_when_gemini_credentials_missing(self) -> None:
        """When Gemini is requested but credentials are absent, demonstration provider is selected."""
        # Configured to prefer Gemini, but GEMINI_API_KEY is empty/None
        custom_settings = Settings(
            GEMINI_API_KEY=None,
            DEFAULT_AI_PROVIDER="gemini",
        )
        provider = get_ai_provider(settings=custom_settings)

        # Must fall back gracefully to demonstration provider without crashing
        assert isinstance(provider, DemonstrationAIProvider)
        assert provider.provider_id == "demonstration"
        assert provider.provider_mode == VivaProviderModeEnum.DEMONSTRATION

    def test_demonstration_selected_when_gemini_key_is_empty_string(self) -> None:
        """Whitespace or empty API key triggers automatic demonstration fallback."""
        custom_settings = Settings(
            GEMINI_API_KEY=SecretStr("   "),
            DEFAULT_AI_PROVIDER="gemini",
        )
        provider = get_ai_provider(settings=custom_settings)
        assert isinstance(provider, DemonstrationAIProvider)

    def test_unsupported_provider_raises_config_error(self) -> None:
        """Unsupported provider names must raise AIProviderConfigError."""
        with pytest.raises(AIProviderConfigError, match="Unsupported AI viva provider"):
            get_ai_provider("anthropic_claude")

        custom_settings = Settings(DEFAULT_AI_PROVIDER="nonexistent_provider")
        with pytest.raises(AIProviderConfigError, match="Unsupported AI viva provider"):
            get_ai_provider(settings=custom_settings)

    def test_unexpected_gemini_initialization_error_is_not_swallowed(self) -> None:
        """Unexpected programming/runtime errors during Gemini setup must propagate."""
        custom_settings = Settings(
            GEMINI_API_KEY=SecretStr("AIzaSyFakeKey"),
            DEFAULT_AI_PROVIDER="gemini",
        )
        with patch("app.modules.ai.factory.GeminiAIProvider", side_effect=TypeError("Unexpected init crash")):
            with pytest.raises(TypeError, match="Unexpected init crash"):
                get_ai_provider(settings=custom_settings)


# ==============================================================================
# Fallback AI Provider Orchestration Tests
# ==============================================================================


class TestFallbackAIProviderOrchestration:
    """Test runtime fallback behavior, circuit breaker coordination, and error translation."""

    @pytest.mark.asyncio
    async def test_unconfigured_primary_uses_fallback_directly(self) -> None:
        """When primary provider is None, fallback provider is executed directly."""
        fallback = DemonstrationAIProvider()
        orchestrator = FallbackAIProvider(primary_provider=None, fallback_provider=fallback)

        assert orchestrator.provider_id == "demonstration"
        assert orchestrator.provider_mode == VivaProviderModeEnum.DEMONSTRATION

        resp = await orchestrator.generate_questions(sample_generation_request())
        assert resp.provider_id == "demonstration"
        assert len(resp.questions) == 2

    @pytest.mark.asyncio
    async def test_gemini_success_returns_original_response(self) -> None:
        """When primary provider succeeds, its response is returned without fallback intervention."""
        mock_gemini = make_mock_gemini_provider()
        mock_fallback = MagicMock(spec=BaseAIProvider)
        mock_fallback.generate_questions = AsyncMock()
        cb = CircuitBreaker()

        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=mock_fallback,
            circuit_breaker=cb,
        )

        resp = await orchestrator.generate_questions(sample_generation_request())

        assert resp.provider_id == "gemini"
        assert resp.metadata.get("model_name") == "gemini-2.5-flash"
        assert resp.provider_mode == VivaProviderModeEnum.AI_LIVE
        assert mock_gemini.generate_questions.await_count == 1
        assert mock_fallback.generate_questions.await_count == 0
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_gemini_unavailable_triggers_demonstration_fallback_questions(self) -> None:
        """Qualifying availability error during question generation triggers demonstration fallback."""
        mock_gemini = make_mock_gemini_provider()
        mock_gemini.generate_questions.side_effect = AIProviderUnavailableError("503 Service Unavailable")

        fallback = DemonstrationAIProvider()
        cb = CircuitBreaker(failure_threshold=3)

        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=fallback,
            circuit_breaker=cb,
        )

        resp = await orchestrator.generate_questions(sample_generation_request())

        # Returned response is cleanly from the demonstration engine
        assert resp.provider_id == "demonstration"
        assert resp.provider_mode == VivaProviderModeEnum.DEMONSTRATION
        assert resp.metadata.get("engine") == "deterministic_demonstration_v1"
        assert len(resp.questions) == 2
        # Circuit breaker recorded 1 qualifying failure
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_gemini_timeout_triggers_demonstration_fallback_evaluation(self) -> None:
        """Qualifying timeout error during answer evaluation triggers demonstration fallback."""
        mock_gemini = make_mock_gemini_provider()
        mock_gemini.evaluate_answer.side_effect = AIProviderTimeoutError("Gemini timed out after 10.0s")

        fallback = DemonstrationAIProvider()
        cb = CircuitBreaker(failure_threshold=2)

        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=fallback,
            circuit_breaker=cb,
        )

        resp = await orchestrator.evaluate_answer(sample_evaluation_request())

        assert resp.provider_id == "demonstration"
        assert resp.provider_mode == VivaProviderModeEnum.DEMONSTRATION
        assert resp.score > 0.0
        assert cb.failure_count == 1

    @pytest.mark.asyncio
    async def test_open_circuit_skips_primary_provider(self) -> None:
        """When circuit is OPEN, primary provider is bypassed without network attempt."""
        mock_gemini = make_mock_gemini_provider()
        fallback = DemonstrationAIProvider()
        cb = CircuitBreaker(failure_threshold=1)

        # Force circuit OPEN
        await cb.record_failure(AIProviderUnavailableError("outage"))
        assert cb.state == CircuitState.OPEN

        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=fallback,
            circuit_breaker=cb,
        )

        resp = await orchestrator.generate_questions(sample_generation_request())

        assert resp.provider_id == "demonstration"
        # Primary provider was NOT invoked
        assert mock_gemini.generate_questions.await_count == 0

    @pytest.mark.asyncio
    async def test_half_open_allows_recovery_trial_success(self) -> None:
        """HALF_OPEN permits a trial probe; successful probe closes circuit and returns Gemini."""
        mock_gemini = make_mock_gemini_provider()
        fallback = DemonstrationAIProvider()

        # Custom clock to simulate timeout expiration
        current_time = [1000.0]
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=30.0,
            time_func=lambda: current_time[0],
        )

        await cb.record_failure(AIProviderUnavailableError("outage"))
        assert cb.state == CircuitState.OPEN

        # Advance time past recovery cooldown
        current_time[0] += 35.0
        assert cb.state == CircuitState.HALF_OPEN

        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=fallback,
            circuit_breaker=cb,
        )

        # Trial probe dispatched to primary provider
        resp = await orchestrator.generate_questions(sample_generation_request())

        assert resp.provider_id == "gemini"
        assert mock_gemini.generate_questions.await_count == 1
        # Circuit is restored to CLOSED
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_trial_failure_reopens_circuit(self) -> None:
        """HALF_OPEN trial probe failure returns demonstration response and reopens circuit."""
        mock_gemini = make_mock_gemini_provider()
        mock_gemini.generate_questions.side_effect = AIProviderUnavailableError("Trial failed")
        fallback = DemonstrationAIProvider()

        current_time = [1000.0]
        cb = CircuitBreaker(
            failure_threshold=1,
            recovery_timeout=30.0,
            time_func=lambda: current_time[0],
        )

        await cb.record_failure(AIProviderUnavailableError("outage"))
        assert cb.state == CircuitState.OPEN

        current_time[0] += 35.0
        assert cb.state == CircuitState.HALF_OPEN

        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=fallback,
            circuit_breaker=cb,
        )

        resp = await orchestrator.generate_questions(sample_generation_request())

        assert resp.provider_id == "demonstration"
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_cancellation_propagates_without_fallback(self) -> None:
        """asyncio.CancelledError must never be swallowed or converted into fallback."""
        mock_gemini = make_mock_gemini_provider()
        mock_gemini.generate_questions.side_effect = asyncio.CancelledError()
        mock_fallback = MagicMock(spec=BaseAIProvider)
        mock_fallback.generate_questions = AsyncMock()

        cb = CircuitBreaker()
        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=mock_fallback,
            circuit_breaker=cb,
        )

        with pytest.raises(asyncio.CancelledError):
            await orchestrator.generate_questions(sample_generation_request())

        # Fallback provider must NOT have been called
        assert mock_fallback.generate_questions.await_count == 0
        # Failure count not incremented on cancellation
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_unexpected_exceptions_re_raised_without_fallback(self) -> None:
        """Programming bugs and schema response errors are re-raised without triggering fallback."""
        mock_gemini = make_mock_gemini_provider()
        mock_gemini.generate_questions.side_effect = AIProviderResponseError("Malformed JSON payload")
        mock_fallback = MagicMock(spec=BaseAIProvider)
        mock_fallback.generate_questions = AsyncMock()

        cb = CircuitBreaker(failure_threshold=3)
        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=mock_fallback,
            circuit_breaker=cb,
        )

        with pytest.raises(AIProviderResponseError, match="Malformed JSON payload"):
            await orchestrator.generate_questions(sample_generation_request())

        assert mock_fallback.generate_questions.await_count == 0
        # Non-availability exception does not increment breaker failure count
        assert cb.failure_count == 0

    @pytest.mark.asyncio
    async def test_no_secret_leakage_in_fallback_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """Fallback logging must not expose API keys or authorization headers."""
        mock_gemini = make_mock_gemini_provider()
        fake_key = "AIzaSySecretApiKeyThatMustNeverBeLogged12345"
        mock_gemini.generate_questions.side_effect = AIProviderUnavailableError(
            f"Service failed for key {fake_key}"
        )

        fallback = DemonstrationAIProvider()
        orchestrator = FallbackAIProvider(
            primary_provider=mock_gemini,
            fallback_provider=fallback,
            circuit_breaker=CircuitBreaker(),
        )

        with caplog.at_level(logging.WARNING):
            resp = await orchestrator.generate_questions(sample_generation_request())

        assert resp.provider_id == "demonstration"
        assert fake_key not in caplog.text
