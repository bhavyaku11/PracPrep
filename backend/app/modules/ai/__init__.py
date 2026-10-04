"""AI Provider Abstraction Module for PracPrep Viva Examination Engine.

Architectural Purpose:
----------------------
This module establishes a vendor-agnostic abstraction boundary between PracPrep's
viva examination workflows and external/internal intelligence engines (e.g. Google
Gemini, OpenAI, Anthropic, or deterministic offline heuristic engines).

Key Principles:
---------------
1. Dependency Inversion:
   Viva examination business logic and FastAPI endpoints MUST depend solely on
   the abstract `BaseAIProvider` interface and the strict Pydantic v2 boundary schemas
   defined here, NEVER on concrete provider implementations or external vendor SDKs.

2. Provider Contracts:
   All operations use typed request/response models (`QuestionGenerationRequest`,
   `QuestionGenerationResponse`, `AnswerEvaluationRequest`, `AnswerEvaluationResponse`)
   configured with `extra="forbid"`, ensuring no vendor-specific payload leaks across
   the application core.

3. Deterministic Demonstration Fallback:
   Offline/heuristic engines (such as `TASK-09.2`) conform to the exact same
   `BaseAIProvider` protocol, enabling zero-configuration offline student practice,
   seamless automated testing, and resilient automatic fallback when LLM API keys
   are absent or external quotas are exhausted.

4. Exception Handling Strategy:
   All provider implementations MUST catch vendor-specific exceptions (e.g., HTTP
   timeouts, HTTP 429 rate limits, malformed JSON responses) and translate them into
   the standard `AIProviderError` hierarchy defined in `app.modules.ai.exceptions`.
   Higher-level application services catch these standardized errors to implement
   fallback failover and client-friendly error messaging without leaking sensitive
   API keys, headers, or internal vendor payloads.
"""

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

__all__ = [
    "BaseAIProvider",
    "DemonstrationAIProvider",
    "GeminiAIProvider",
    "FallbackAIProvider",
    "AIProviderFactory",
    "get_ai_provider",
    "CircuitBreaker",
    "CircuitState",
    "AIProviderError",
    "AIProviderUnavailableError",
    "AIProviderTimeoutError",
    "AIProviderResponseError",
    "AIProviderRateLimitError",
    "AIProviderConfigError",
    "AIExperimentContext",
    "AIGeneratedQuestion",
    "QuestionGenerationRequest",
    "QuestionGenerationResponse",
    "AIEvaluationContextItem",
    "AnswerEvaluationRequest",
    "AnswerEvaluationResponse",
    "VivaDifficultyEnum",
    "VivaTopicEnum",
    "EvaluationVerdictEnum",
    "VivaProviderModeEnum",
]
