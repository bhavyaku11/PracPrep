"""Comprehensive Unit and Mock Integration Tests for GeminiAIProvider.

Verifies:
1. Provider interface & metadata (BaseAIProvider conformance).
2. Question generation (prompt construction, structured schema parsing, duplicate handling, malformed JSON, missing text).
3. Answer evaluation (prompt construction, structured schema parsing, score/verdict validation, context propagation).
4. Error translation & resilience (API key missing, rate limits, timeouts, client errors, network errors).
5. Retry backoff behavior and cancellation propagation.
6. Absolute secret sanitization (no API key leakage).
7. Zero real external network calls.
"""

import asyncio
import json
from typing import Any, Callable, Optional
import pytest
from google.genai import errors

from app.core.config import Settings
from app.modules.ai.base import BaseAIProvider
from app.modules.ai.exceptions import (
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.modules.ai.gemini import GeminiAIProvider, _clean_json_text, _sanitize_message
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
# Mock SDK Client Infrastructure
# ==============================================================================


class MockResponse:
    """Mock of GenerateContentResponse from Google GenAI SDK."""

    def __init__(self, text: Optional[str]) -> None:
        self.text = text


class MockModels:
    """Mock of client.aio.models namespace."""

    def __init__(self, client: "MockGeminiClient") -> None:
        self.client = client

    async def generate_content(self, model: str, contents: str, config: Any) -> MockResponse:
        self.client.calls.append({
            "model": model,
            "contents": contents,
            "config": config,
        })
        if self.client.side_effect:
            if callable(self.client.side_effect):
                res = self.client.side_effect()
                if isinstance(res, Exception):
                    raise res
                return res
            raise self.client.side_effect
        return MockResponse(self.client.response_text)


class MockAio:
    """Mock of client.aio namespace."""

    def __init__(self, client: "MockGeminiClient") -> None:
        self.models = MockModels(client)


class MockGeminiClient:
    """Self-contained mock Google GenAI SDK client for testing."""

    def __init__(
        self,
        response_text: Optional[str] = None,
        side_effect: Optional[Any] = None,
    ) -> None:
        self.response_text = response_text
        self.side_effect = side_effect
        self.calls: list[dict[str, Any]] = []
        self.aio = MockAio(self)


# ==============================================================================
# Common Test Fixtures
# ==============================================================================


@pytest.fixture
def sample_experiment() -> AIExperimentContext:
    """Realistic laboratory experiment context for question generation."""
    return AIExperimentContext(
        title="Verification of Thevenin's Theorem",
        subject="Network Analysis & Circuit Theory",
        experiment_number="EXP-03",
        objective="To determine the Thevenin equivalent voltage (Vth) and Thevenin resistance (Rth) across load terminals.",
        theory="Thevenin's theorem states that any linear active bilateral network can be replaced across its load terminals by an equivalent voltage source Vth in series with resistance Rth.",
        apparatus="DC Power Supply (0-30V), Digital Multimeter, decade resistance box, connecting wires.",
        procedure="1. Remove the load resistor and measure open-circuit voltage Vth. 2. Deactivate all independent sources and measure Rth. 3. Connect the equivalent circuit and verify load current.",
        observations="Open circuit voltage Vth = 6.2V. Rth = 150 ohms. Load current IL = 18.2mA.",
        calculations="Calculated IL = Vth / (Rth + RL) = 6.2 / (150 + 190) = 18.23mA. Error = 0.16%.",
        precautions="Ensure all independent voltage sources are short-circuited when measuring internal resistance Rth.",
    )


@pytest.fixture
def sample_question() -> AIGeneratedQuestion:
    """Sample generated question for evaluation testing."""
    return AIGeneratedQuestion(
        id="vq-gemini-test-01",
        question_number=1,
        question_text="How do you determine the Thevenin equivalent resistance Rth experimentally?",
        topic=VivaTopicEnum.PROCEDURE,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        expected_answer="Remove the load resistance, replace all independent voltage sources with short circuits and current sources with open circuits, and measure the resistance looking into the load terminals.",
        key_points=[
            "Remove the load resistor across the output terminals",
            "Deactivate all independent sources: short-circuit voltage sources, open-circuit current sources",
            "Measure or calculate the equivalent resistance looking back into the open terminals",
        ],
        grounded_source_section="Procedure",
    )


# ==============================================================================
# 1. Provider Interface & Metadata Tests
# ==============================================================================


def test_gemini_provider_metadata() -> None:
    """Verifies Gemini provider metadata matches architectural requirements."""
    mock_client = MockGeminiClient(response_text="{}")
    provider = GeminiAIProvider(
        api_key="fake-test-key",
        client=mock_client,
    )
    assert provider.provider_id == "gemini"
    assert provider.display_name == "Google Gemini"
    assert provider.provider_mode == VivaProviderModeEnum.AI_LIVE


def test_gemini_provider_is_instance_of_base_ai_provider() -> None:
    """Verifies GeminiAIProvider implements BaseAIProvider abstract base class."""
    mock_client = MockGeminiClient(response_text="{}")
    provider = GeminiAIProvider(
        api_key="fake-test-key",
        client=mock_client,
    )
    assert isinstance(provider, BaseAIProvider)


@pytest.mark.asyncio
async def test_successful_async_method_invocation(
    sample_experiment: AIExperimentContext,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies both generate_questions and evaluate_answer execute successfully with a mock client."""
    mock_gen_payload = {
        "questions": [
            {
                "question_text": "What is the primary significance of Thevenin equivalent voltage?",
                "topic": "theory",
                "difficulty": "intermediate",
                "expected_answer": "Vth represents the open-circuit voltage across load terminals.",
                "key_points": ["Open-circuit voltage", "Across load terminals"],
                "grounded_source_section": "Theory",
            }
        ]
    }
    mock_eval_payload = {
        "verdict": "correct",
        "score": 9,
        "feedback": "Outstanding answer demonstrating clear knowledge of source deactivation.",
        "what_you_got_right": "Accurately stated to short voltage sources and remove load.",
        "what_was_missing": "Mentioned open-circuiting current sources as an edge case.",
        "expected_answer": "Remove load, short voltage sources, measure resistance across terminals.",
        "improvement_tip": "Always state SI units when quoting measured resistance.",
        "key_points_covered": ["Remove load", "Short voltage sources"],
        "key_points_missed": [],
    }

    mock_client = MockGeminiClient()

    def _mock_router() -> MockResponse:
        call_count = len(mock_client.calls)
        if call_count == 1:
            return MockResponse(json.dumps(mock_gen_payload))
        return MockResponse(json.dumps(mock_eval_payload))

    mock_client.side_effect = _mock_router
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    gen_req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=1,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.THEORY,
    )
    gen_resp = await provider.generate_questions(gen_req)
    assert len(gen_resp.questions) == 1
    assert gen_resp.questions[0].topic == VivaTopicEnum.THEORY

    eval_req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Remove the load and replace voltage sources with short circuits.",
    )
    eval_resp = await provider.evaluate_answer(eval_req)
    assert eval_resp.score == 9
    assert eval_resp.verdict == EvaluationVerdictEnum.CORRECT


# ==============================================================================
# 2. Question Generation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_question_generation_structured_parsing(
    sample_experiment: AIExperimentContext,
) -> None:
    """Verifies valid structured JSON from Gemini is parsed into domain models."""
    mock_payload = {
        "questions": [
            {
                "question_text": "Define Thevenin's theorem in your own words.",
                "topic": "theory",
                "difficulty": "beginner",
                "expected_answer": "Any linear bilateral network can be replaced by Vth and Rth.",
                "key_points": ["Linear bilateral network", "Equivalent Vth and Rth"],
                "grounded_source_section": "Theory",
            },
            {
                "question_text": "What steps are required to calculate Rth experimentally?",
                "topic": "procedure",
                "difficulty": "intermediate",
                "expected_answer": "Deactivate sources and measure looking into open terminals.",
                "key_points": ["Deactivate sources", "Look into open terminals"],
                "grounded_source_section": "Procedure",
            },
        ]
    }
    mock_client = MockGeminiClient(response_text=json.dumps(mock_payload))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=2,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)

    assert isinstance(resp, QuestionGenerationResponse)
    assert len(resp.questions) == 2
    assert resp.questions[0].question_number == 1
    assert resp.questions[1].question_number == 2
    assert resp.questions[0].topic == VivaTopicEnum.THEORY
    assert resp.questions[1].topic == VivaTopicEnum.PROCEDURE
    assert resp.provider_id == "gemini"
    assert resp.provider_mode == VivaProviderModeEnum.AI_LIVE


@pytest.mark.asyncio
async def test_question_generation_count_and_ordering(
    sample_experiment: AIExperimentContext,
) -> None:
    """Verifies requested question count and sequence indexing are strictly respected."""
    mock_payload = {
        "questions": [
            {
                "question_text": f"Question number {i} regarding circuit theory?",
                "topic": "theory",
                "difficulty": "intermediate",
                "expected_answer": f"Expected answer for {i}",
                "key_points": [f"Point {i}"],
                "grounded_source_section": "Theory",
            }
            for i in range(1, 6)
        ]
    }
    mock_client = MockGeminiClient(response_text=json.dumps(mock_payload))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=3,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.THEORY,
    )
    resp = await provider.generate_questions(req)
    assert len(resp.questions) == 3
    assert [q.question_number for q in resp.questions] == [1, 2, 3]


@pytest.mark.asyncio
async def test_question_generation_prompt_contains_context(
    sample_experiment: AIExperimentContext,
) -> None:
    """Verifies that the prompt sent to Gemini includes all relevant experiment fields."""
    mock_payload = {
        "questions": [
            {
                "question_text": "What is the calculated value of Rth in this experiment?",
                "topic": "observations",
                "difficulty": "intermediate",
                "expected_answer": "150 ohms.",
                "key_points": ["150 ohms"],
                "grounded_source_section": "Observations",
            }
        ]
    }
    mock_client = MockGeminiClient(response_text=json.dumps(mock_payload))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=1,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.OBSERVATIONS,
    )
    await provider.generate_questions(req)

    assert len(mock_client.calls) == 1
    call_content = mock_client.calls[0]["contents"]
    assert sample_experiment.title in call_content
    assert sample_experiment.subject in call_content
    assert sample_experiment.objective in call_content
    assert sample_experiment.theory in call_content
    assert sample_experiment.apparatus in call_content
    assert sample_experiment.procedure in call_content


@pytest.mark.asyncio
async def test_question_generation_duplicate_handling(
    sample_experiment: AIExperimentContext,
) -> None:
    """Verifies duplicate questions from model are filtered, and fails if count is deficient."""
    duplicate_payload = {
        "questions": [
            {
                "question_text": "Explain Thevenin's theorem.",
                "topic": "theory",
                "difficulty": "beginner",
                "expected_answer": "Answer 1",
                "key_points": ["Point 1"],
            },
            {
                "question_text": "Explain Thevenin's theorem.",  # Duplicate!
                "topic": "theory",
                "difficulty": "beginner",
                "expected_answer": "Answer 1",
                "key_points": ["Point 1"],
            },
        ]
    }
    mock_client = MockGeminiClient(response_text=json.dumps(duplicate_payload))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=2,  # Requests 2, but only 1 unique exists
        difficulty=VivaDifficultyEnum.BEGINNER,
        topic_focus=VivaTopicEnum.THEORY,
    )
    with pytest.raises(AIProviderResponseError) as exc_info:
        await provider.generate_questions(req)

    assert "unique questions" in str(exc_info.value)
    assert exc_info.value.provider_id == "gemini"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_response",
    [
        "This is not JSON text at all",
        "{'invalid': 'single quotes'}",
        "```json\n{\"broken\": [unclosed\n```",
    ],
)
async def test_question_generation_malformed_json_handling(
    sample_experiment: AIExperimentContext,
    bad_response: str,
) -> None:
    """Verifies unparseable JSON from model raises AIProviderResponseError."""
    mock_client = MockGeminiClient(response_text=bad_response)
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=1,
    )
    with pytest.raises(AIProviderResponseError) as exc_info:
        await provider.generate_questions(req)

    assert "JSON" in str(exc_info.value) or "decoded" in str(exc_info.value)


@pytest.mark.asyncio
async def test_question_generation_schema_violation_handling(
    sample_experiment: AIExperimentContext,
) -> None:
    """Verifies JSON that violates Pydantic schema contracts raises AIProviderResponseError."""
    # Missing required 'expected_answer' and 'key_points'
    invalid_schema_json = json.dumps({
        "questions": [
            {
                "question_text": "Valid text?",
                "topic": "invalid_topic",  # Invalid enum
                "difficulty": "intermediate",
            }
        ]
    })
    mock_client = MockGeminiClient(response_text=invalid_schema_json)
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=1,
    )
    with pytest.raises(AIProviderResponseError) as exc_info:
        await provider.generate_questions(req)

    assert "schema" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_question_generation_missing_response_text(
    sample_experiment: AIExperimentContext,
) -> None:
    """Verifies empty or None response text raises AIProviderResponseError."""
    mock_client = MockGeminiClient(response_text="")
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=1,
    )
    with pytest.raises(AIProviderResponseError) as exc_info:
        await provider.generate_questions(req)

    assert "empty or null" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_question_generation_topic_distribution(
    sample_experiment: AIExperimentContext,
) -> None:
    """Verifies topic_distribution dictionary accurately mirrors returned questions."""
    mock_payload = {
        "questions": [
            {
                "question_text": "Theory question?",
                "topic": "theory",
                "difficulty": "beginner",
                "expected_answer": "Theory answer",
                "key_points": ["Point 1"],
            },
            {
                "question_text": "Apparatus question?",
                "topic": "apparatus",
                "difficulty": "beginner",
                "expected_answer": "Apparatus answer",
                "key_points": ["Point 2"],
            },
            {
                "question_text": "Procedure question?",
                "topic": "procedure",
                "difficulty": "intermediate",
                "expected_answer": "Procedure answer",
                "key_points": ["Point 3"],
            },
        ]
    }
    mock_client = MockGeminiClient(response_text=json.dumps(mock_payload))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = QuestionGenerationRequest(
        experiment=sample_experiment,
        question_count=3,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)
    assert resp.topic_distribution == {"theory": 1, "apparatus": 1, "procedure": 1}


# ==============================================================================
# 3. Answer Evaluation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_evaluation_valid_response_parsing(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies valid evaluation JSON from Gemini is parsed into AnswerEvaluationResponse."""
    mock_eval = {
        "verdict": "correct",
        "score": 9,
        "feedback": "Excellent procedural explanation of Thevenin resistance determination.",
        "what_you_got_right": "Correctly identified deactivating all independent voltage sources and measuring across open terminals.",
        "what_was_missing": "Did not specify that current sources must be open-circuited.",
        "expected_answer": "Deactivate all sources (short voltage, open current) and measure looking back into the open circuit.",
        "improvement_tip": "Remember to explicitly mention current sources when generalizing the theorem.",
        "key_points_covered": [
            "Remove the load resistor across the output terminals",
            "Deactivate all independent sources: short-circuit voltage sources, open-circuit current sources",
        ],
        "key_points_missed": [
            "Measure or calculate the equivalent resistance looking back into the open terminals",
        ],
    }
    mock_client = MockGeminiClient(response_text=json.dumps(mock_eval))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="To find Rth, short circuit all the voltage sources and open the current sources, then measure across the terminals where the load was.",
    )
    resp = await provider.evaluate_answer(req)

    assert isinstance(resp, AnswerEvaluationResponse)
    assert resp.verdict == EvaluationVerdictEnum.CORRECT
    assert resp.score == 9
    assert len(resp.key_points_covered) == 2
    assert len(resp.key_points_missed) == 1
    assert resp.provider_id == "gemini"
    assert resp.provider_mode == VivaProviderModeEnum.AI_LIVE


@pytest.mark.asyncio
async def test_evaluation_context_and_transcript_propagation(
    sample_experiment: AIExperimentContext,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies previous answers and experiment context are formatted into evaluation prompt."""
    mock_eval = {
        "verdict": "partially-correct",
        "score": 6,
        "feedback": "Good answer but missing details.",
        "what_you_got_right": "Understood the basic idea.",
        "what_was_missing": "Missed source deactivation.",
        "expected_answer": "Deactivate sources and measure looking in.",
        "improvement_tip": "Review circuit analysis procedures.",
        "key_points_covered": [],
        "key_points_missed": [],
    }
    mock_client = MockGeminiClient(response_text=json.dumps(mock_eval))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    prev_answer = AIEvaluationContextItem(
        question_number=1,
        question_text="What is Thevenin's theorem?",
        student_answer="A circuit replacement theorem.",
        verdict=EvaluationVerdictEnum.CORRECT,
        score=8,
    )
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Turn off the power and check the resistance.",
        experiment=sample_experiment,
        previous_answers=[prev_answer],
    )
    await provider.evaluate_answer(req)

    prompt = mock_client.calls[0]["contents"]
    assert sample_experiment.title in prompt
    assert "A circuit replacement theorem." in prompt
    assert sample_question.question_text in prompt
    assert "Turn off the power and check the resistance." in prompt


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_eval_data",
    [
        {"verdict": "correct", "score": 99},  # Score out of bounds (> 10)
        {"verdict": "invalid_verdict", "score": 5},  # Invalid verdict enum
        {"verdict": "correct"},  # Missing score and feedback
    ],
)
async def test_evaluation_invalid_schema_handling(
    sample_question: AIGeneratedQuestion,
    invalid_eval_data: dict[str, Any],
) -> None:
    """Verifies schema violations in evaluation output raise AIProviderResponseError."""
    mock_client = MockGeminiClient(response_text=json.dumps(invalid_eval_data))
    provider = GeminiAIProvider(api_key="test-key", client=mock_client)

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Some student response.",
    )
    with pytest.raises(AIProviderResponseError) as exc_info:
        await provider.evaluate_answer(req)

    assert "schema" in str(exc_info.value).lower()


# ==============================================================================
# 4. Errors & Resilience Tests
# ==============================================================================


def test_missing_api_key_configuration_raises_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifies instantiating GeminiAIProvider without an API key raises AIProviderConfigError."""
    # Force settings to have no GEMINI_API_KEY
    import app.core.config as config_mod
    config_mod.get_settings.cache_clear()
    monkeypatch.setenv("GEMINI_API_KEY", "")

    with pytest.raises(AIProviderConfigError) as exc_info:
        GeminiAIProvider()

    assert "API key is missing" in str(exc_info.value)
    assert exc_info.value.provider_id == "gemini"
    config_mod.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_rate_limit_translation_and_retry(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies HTTP 429 rate limit error translates to AIProviderRateLimitError."""
    rate_limit_err = errors.APIError(429, "Resource has been exhausted (e.g. check quota).")
    mock_client = MockGeminiClient(side_effect=rate_limit_err)
    provider = GeminiAIProvider(
        api_key="test-key",
        client=mock_client,
        max_retries=1,  # Short retry limit for test
    )

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Student answer.",
    )
    with pytest.raises(AIProviderRateLimitError) as exc_info:
        await provider.evaluate_answer(req)

    assert "rate limit" in str(exc_info.value).lower() or "quota" in str(exc_info.value).lower()
    assert exc_info.value.provider_id == "gemini"
    assert exc_info.value.retryable is True
    # Initial attempt + 1 retry = 2 calls
    assert len(mock_client.calls) == 2


@pytest.mark.asyncio
async def test_timeout_translation_and_retry(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies timeout exception translates to AIProviderTimeoutError."""
    mock_client = MockGeminiClient(side_effect=asyncio.TimeoutError())
    provider = GeminiAIProvider(
        api_key="test-key",
        client=mock_client,
        timeout_seconds=0.5,
        max_retries=1,
    )

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Student answer.",
    )
    with pytest.raises(AIProviderTimeoutError) as exc_info:
        await provider.evaluate_answer(req)

    assert "timed out" in str(exc_info.value).lower()
    assert exc_info.value.provider_id == "gemini"
    assert exc_info.value.timeout_seconds == 0.5
    assert len(mock_client.calls) == 2


@pytest.mark.asyncio
async def test_transient_server_error_retry_success(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies provider successfully recovers on retry after transient HTTP 503 error."""
    mock_eval = {
        "verdict": "correct",
        "score": 10,
        "feedback": "Perfect answer after retry.",
        "what_you_got_right": "Everything.",
        "what_was_missing": "None.",
        "expected_answer": "Complete answer.",
        "improvement_tip": "None.",
        "key_points_covered": ["All"],
        "key_points_missed": [],
    }
    call_count = 0

    def _side_effect() -> MockResponse:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise errors.APIError(503, "The service is temporarily unavailable.")
        return MockResponse(json.dumps(mock_eval))

    mock_client = MockGeminiClient(side_effect=_side_effect)
    provider = GeminiAIProvider(
        api_key="test-key",
        client=mock_client,
        max_retries=2,
    )

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Student answer.",
    )
    resp = await provider.evaluate_answer(req)
    assert resp.score == 10
    assert call_count == 2


@pytest.mark.asyncio
async def test_no_retry_for_permanent_client_error(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies HTTP 400 Bad Request fails immediately without retry."""
    bad_req_err = errors.APIError(400, "Invalid argument: Bad request payload.")
    mock_client = MockGeminiClient(side_effect=bad_req_err)
    provider = GeminiAIProvider(
        api_key="test-key",
        client=mock_client,
        max_retries=3,
    )

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Student answer.",
    )
    with pytest.raises(AIProviderError) as exc_info:
        await provider.evaluate_answer(req)

    # Must NOT retry client errors!
    assert len(mock_client.calls) == 1
    assert "400" in str(exc_info.value)


@pytest.mark.asyncio
async def test_auth_error_translates_to_config_error(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies HTTP 401 or 403 API error translates to AIProviderConfigError."""
    auth_err = errors.APIError(401, "API key not valid. Please pass a valid API key.")
    mock_client = MockGeminiClient(side_effect=auth_err)
    provider = GeminiAIProvider(
        api_key="invalid-key",
        client=mock_client,
        max_retries=2,
    )

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Student answer.",
    )
    with pytest.raises(AIProviderConfigError) as exc_info:
        await provider.evaluate_answer(req)

    assert "authentication failed" in str(exc_info.value).lower()
    # Must NOT retry auth failures!
    assert len(mock_client.calls) == 1


def test_secret_sanitization() -> None:
    """Verifies that API keys and bearer tokens are strictly redacted from messages."""
    leaked_msg = "Error communicating with endpoint https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSyA1234567890123456789012345678901 with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    sanitized = _sanitize_message(leaked_msg)
    assert "AIzaSy" not in sanitized
    assert "eyJhbGci" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized
    assert "[REDACTED_TOKEN]" in sanitized


def test_clean_json_text_helper() -> None:
    """Verifies code fences are cleanly stripped from model output."""
    raw = "```json\n{\"test\": 123}\n```"
    assert _clean_json_text(raw) == '{"test": 123}'

    raw2 = "```\n{\"test\": 456}\n```"
    assert _clean_json_text(raw2) == '{"test": 456}'

    raw3 = "  {\"test\": 789}  "
    assert _clean_json_text(raw3) == '{"test": 789}'


@pytest.mark.asyncio
async def test_cancellation_propagation(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies asyncio.CancelledError is never swallowed by retry handlers."""
    mock_client = MockGeminiClient(side_effect=asyncio.CancelledError())
    provider = GeminiAIProvider(
        api_key="test-key",
        client=mock_client,
    )

    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Student answer.",
    )
    with pytest.raises(asyncio.CancelledError):
        await provider.evaluate_answer(req)


def test_zero_real_network_calls_guaranteed() -> None:
    """Verifies that running mock tests requires no internet connection or real keys."""
    client = MockGeminiClient(response_text="{}")
    provider = GeminiAIProvider(api_key="dummy-test-key", client=client)
    assert provider._client is client
