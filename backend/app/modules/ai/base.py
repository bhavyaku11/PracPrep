"""Abstract Base AI Provider Interface.

Defines the pluggable contract for AI viva examination providers (Google Gemini,
OpenAI, and heuristic demonstration engines).
"""

from abc import ABC, abstractmethod
from typing import Optional

from app.modules.ai.schemas import (
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    VivaProviderModeEnum,
    ParsedExperimentSections,
)


class BaseAIProvider(ABC):
    """Standardized abstract base class for viva AI examination engines.

    Implementations must provide asynchronous question generation and answer evaluation
    conforming strictly to the provider boundary Pydantic contracts.
    """

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique machine identifier for this provider (e.g., 'gemini', 'demonstration')."""
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable display title for student UI presentation."""
        pass

    @property
    @abstractmethod
    def provider_mode(self) -> VivaProviderModeEnum:
        """Operational category: 'demonstration' (heuristic/offline) or 'ai-live' (LLM)."""
        pass

    @abstractmethod
    async def generate_questions(
        self,
        request: QuestionGenerationRequest,
    ) -> QuestionGenerationResponse:
        """Generate viva examination questions grounded in experiment context.

        Args:
            request: Standardized question generation parameters including experiment
                manual content, difficulty, question count, and topic focus.

        Returns:
            QuestionGenerationResponse containing the ordered collection of questions.

        Raises:
            AIProviderUnavailableError: If provider service is unreachable.
            AIProviderTimeoutError: If generation exceeds latency threshold.
            AIProviderRateLimitError: If provider rate limits are exhausted.
            AIProviderResponseError: If output violates schema contracts.
            AIProviderError: For any other unhandled provider failure.
        """
        pass

    @abstractmethod
    async def evaluate_answer(
        self,
        request: AnswerEvaluationRequest,
    ) -> AnswerEvaluationResponse:
        """Evaluate a student's oral or written response against a question rubric.

        Args:
            request: Standardized answer evaluation parameters including original
                question, student answer, and optional experiment grounding context.

        Returns:
            AnswerEvaluationResponse containing rubric score, verdict, feedback, and tips.

        Raises:
            AIProviderUnavailableError: If provider service is unreachable.
            AIProviderTimeoutError: If evaluation exceeds latency threshold.
            AIProviderRateLimitError: If provider rate limits are exhausted.
            AIProviderResponseError: If output violates schema contracts.
            AIProviderError: For any other unhandled provider failure.
        """
        pass

    async def parse_manual_sections(
        self,
        raw_text: str,
        file_name: Optional[str] = None,
    ) -> ParsedExperimentSections:
        """Parse extracted laboratory manual text into structured experiment sections.

        Args:
            raw_text: Extracted and normalized source text from manual.
            file_name: Optional original document filename for context.

        Returns:
            ParsedExperimentSections populated with structured domain sections.

        Raises:
            AIProviderUnavailableError: If provider service is unreachable.
            AIProviderTimeoutError: If parsing exceeds latency threshold.
            AIProviderRateLimitError: If provider rate limits are exhausted.
            AIProviderResponseError: If output violates schema contracts.
            AIProviderError: For any other unhandled provider failure.
        """
        raise NotImplementedError(
            f"Provider '{self.provider_id}' does not implement parse_manual_sections."
        )
