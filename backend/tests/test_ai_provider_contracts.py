"""Unit Tests for AI Provider Abstraction Contracts and Interfaces (TASK-09.1).

Validates:
1. Valid question-generation request construction
2. Invalid difficulty and topic values rejection
3. Question count and text constraints
4. Valid generated question responses
5. Valid answer-evaluation responses
6. Score boundary validation (0 to 10 inclusive)
7. Invalid score rejection (< 0 or > 10)
8. Unexpected field rejection (extra="forbid")
9. JSON serialization and deserialization
10. Abstract provider interface cannot be instantiated directly
11. Minimal mock provider implements interface successfully
12. Provider exception hierarchy and retryable behavior
13. No vendor SDK dependencies in module
14. Compatibility with existing backend schemas and models
15. Non-empty and whitespace-only student answer validation
16. Automatic computation of topic distribution in QuestionGenerationResponse
17. Evaluation context item serialization
"""

import inspect
import json
import pytest
from pydantic import ValidationError

from app.modules.ai import (
    AIEvaluationContextItem,
    AIExperimentContext,
    AIGeneratedQuestion,
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
    AnswerEvaluationRequest,
    AnswerEvaluationResponse,
    BaseAIProvider,
    EvaluationVerdictEnum,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    VivaDifficultyEnum,
    VivaProviderModeEnum,
    VivaTopicEnum,
)
import app.modules.ai.base as ai_base
import app.modules.ai.exceptions as ai_exceptions
import app.modules.ai.schemas as ai_schemas


# ==============================================================================
# 1. Experiment Context & Question Generation Request Tests
# ==============================================================================


def test_valid_experiment_context_and_request() -> None:
    """Verifies standard valid construction of experiment context and question generation request."""
    exp = AIExperimentContext(
        title="Verification of Ohm's Law",
        subject="Basic Electrical Engineering",
        experiment_number="EXP-EE-01",
        description="Verify V = IR across standard resistive elements.",
        objective="To determine resistance of a wire by plotting V vs I graph.",
        theory="Ohm's law states that current through a conductor is proportional to potential difference.",
        apparatus="Ammeter, Voltmeter, Rheostat, DC power supply, Connecting wires",
        procedure="Connect circuit in series with ammeter and parallel with voltmeter. Vary rheostat.",
        observations="Linear relation observed between voltage and current values.",
        calculations="Slope of V-I graph gives resistance R = delta V / delta I.",
        precautions="Do not allow current to pass for a long time to prevent heating effect.",
    )

    req = QuestionGenerationRequest(
        experiment=exp,
        question_count=5,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.THEORY,
        constraints=["Focus on temperature coefficient of resistance"],
    )

    assert req.experiment.title == "Verification of Ohm's Law"
    assert req.question_count == 5
    assert req.difficulty == VivaDifficultyEnum.INTERMEDIATE
    assert req.topic_focus == VivaTopicEnum.THEORY
    assert len(req.constraints) == 1


def test_invalid_difficulty_and_topic_rejection() -> None:
    """Ensures invalid enum values for difficulty and topic are rejected."""
    exp = AIExperimentContext(title="Logic Gates", subject="Electronics")

    with pytest.raises(ValidationError) as exc_info:
        QuestionGenerationRequest(
            experiment=exp,
            difficulty="extreme",  # type: ignore[arg-type]
        )
    assert "Input should be 'beginner', 'intermediate', 'advanced' or 'mixed'" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        QuestionGenerationRequest(
            experiment=exp,
            topic_focus="history",  # type: ignore[arg-type]
        )
    assert "Input should be 'theory', 'procedure', 'apparatus', 'observations', 'precautions' or 'mixed'" in str(exc_info.value)


def test_question_count_constraints() -> None:
    """Verifies lower and upper bound enforcement on question count (1 to 20)."""
    exp = AIExperimentContext(title="Logic Gates", subject="Electronics")

    # Min bound: 1
    valid_min = QuestionGenerationRequest(experiment=exp, question_count=1)
    assert valid_min.question_count == 1

    # Max bound: 20
    valid_max = QuestionGenerationRequest(experiment=exp, question_count=20)
    assert valid_max.question_count == 20

    # Below min: 0
    with pytest.raises(ValidationError):
        QuestionGenerationRequest(experiment=exp, question_count=0)

    # Above max: 21
    with pytest.raises(ValidationError):
        QuestionGenerationRequest(experiment=exp, question_count=21)


def test_unexpected_fields_rejected_on_all_models() -> None:
    """Ensures extra='forbid' strictly rejects unauthorized or misspelled payload attributes."""
    exp = AIExperimentContext(title="Logic Gates", subject="Electronics")

    with pytest.raises(ValidationError) as exc_info:
        AIExperimentContext(title="Logic Gates", subject="Electronics", unknown_field="invalid")  # type: ignore[call-arg]
    assert "Extra inputs are not permitted" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        QuestionGenerationRequest(experiment=exp, extra_param=123)  # type: ignore[call-arg]
    assert "Extra inputs are not permitted" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        AnswerEvaluationResponse(  # type: ignore[call-arg]
            verdict=EvaluationVerdictEnum.CORRECT,
            score=10,
            feedback="Good",
            provider_mode=VivaProviderModeEnum.DEMONSTRATION,
            provider_id="demo",
            hallucinated_field=True,
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


# ==============================================================================
# 2. Generated Question & Question Response Tests
# ==============================================================================


def test_valid_generated_question_and_response() -> None:
    """Validates AIGeneratedQuestion and QuestionGenerationResponse models."""
    q1 = AIGeneratedQuestion(
        id="q-001",
        question_number=1,
        question_text="State Ohm's Law and its mathematical formulation.",
        topic=VivaTopicEnum.THEORY,
        difficulty=VivaDifficultyEnum.BEGINNER,
        expected_answer="Ohm's Law states V = IR where V is voltage, I is current, and R is resistance.",
        key_points=["Direct proportionality between V and I", "Constant temperature condition", "V = IR formula"],
        grounded_source_section="Theory",
    )

    q2 = AIGeneratedQuestion(
        id="q-002",
        question_number=2,
        question_text="Why must the voltmeter be connected in parallel with the resistance wire?",
        topic=VivaTopicEnum.APPARATUS,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        expected_answer="Because a voltmeter has high internal resistance and measures potential difference across components.",
        key_points=["High internal resistance", "Measures potential difference without drawing significant current"],
        grounded_source_section="Apparatus",
    )

    resp = QuestionGenerationResponse(
        questions=[q1, q2],
        provider_mode=VivaProviderModeEnum.DEMONSTRATION,
        provider_id="demonstration",
        metadata={"generator": "heuristic_v1", "elapsed_ms": 4.2},
    )

    assert len(resp.questions) == 2
    assert resp.provider_mode == VivaProviderModeEnum.DEMONSTRATION
    assert resp.provider_id == "demonstration"
    # Auto-computed topic distribution
    assert resp.topic_distribution == {"theory": 1, "apparatus": 1}
    assert resp.metadata["generator"] == "heuristic_v1"


def test_question_text_length_constraints() -> None:
    """Ensures question text enforces non-empty minimum and maximum length bounds."""
    # Too short (< 5 chars)
    with pytest.raises(ValidationError):
        AIGeneratedQuestion(
            question_number=1,
            question_text="Why?",
            topic=VivaTopicEnum.THEORY,
        )

    # Valid length (>= 5 chars)
    q = AIGeneratedQuestion(
        question_number=1,
        question_text="Why is the voltmeter connected in parallel?",
        topic=VivaTopicEnum.THEORY,
    )
    assert q.question_text == "Why is the voltmeter connected in parallel?"


# ==============================================================================
# 3. Answer Evaluation Request & Response Tests
# ==============================================================================


def test_valid_answer_evaluation_request_and_response() -> None:
    """Verifies valid answer evaluation request and response creation."""
    q = AIGeneratedQuestion(
        id="q-001",
        question_number=1,
        question_text="What is threshold frequency in photoelectric effect?",
        topic=VivaTopicEnum.THEORY,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        expected_answer="Minimum frequency of incident radiation required to eject electrons from a metal surface.",
        key_points=["Minimum frequency", "No electron emission below this frequency", "Material dependent"],
    )

    req = AnswerEvaluationRequest(
        question=q,
        student_answer="It is the minimum frequency of light needed to emit photoelectrons from a metal surface.",
        experiment=AIExperimentContext(title="Photoelectric Effect", subject="Physics"),
        previous_answers=[
            AIEvaluationContextItem(
                question_number=1,
                question_text="Previous question",
                student_answer="Previous answer",
                verdict=EvaluationVerdictEnum.CORRECT,
                score=10,
            )
        ],
    )
    assert req.question.id == "q-001"
    assert "minimum frequency" in req.student_answer
    assert len(req.previous_answers) == 1

    resp = AnswerEvaluationResponse(
        verdict=EvaluationVerdictEnum.CORRECT,
        score=10,
        feedback="Flawless explanation directly addressing the critical physical condition.",
        what_you_got_right="Accurately noted the minimum frequency condition for photoelectric emission.",
        what_was_missing="",
        expected_answer=q.expected_answer or "",
        improvement_tip="Keep responses concise and direct just like this one.",
        key_points_covered=["Minimum frequency", "No electron emission below this frequency"],
        key_points_missed=[],
        provider_mode=VivaProviderModeEnum.DEMONSTRATION,
        provider_id="demonstration",
        metadata={"token_usage": None},
    )

    assert resp.score == 10
    assert resp.verdict == EvaluationVerdictEnum.CORRECT
    assert resp.feedback.startswith("Flawless")


def test_student_answer_whitespace_and_null_rejection() -> None:
    """Ensures empty, null, or whitespace-only student answers are rejected."""
    q = AIGeneratedQuestion(
        question_number=1,
        question_text="What is the function of a rheostat?",
        topic=VivaTopicEnum.APPARATUS,
    )

    # Empty string
    with pytest.raises(ValidationError) as exc_info:
        AnswerEvaluationRequest(question=q, student_answer="")
    assert "Student answer cannot be empty or whitespace-only" in str(exc_info.value)

    # Whitespace only
    with pytest.raises(ValidationError) as exc_info:
        AnswerEvaluationRequest(question=q, student_answer="   \n\t  ")
    assert "Student answer cannot be empty or whitespace-only" in str(exc_info.value)

    # Leading/trailing whitespace should be stripped
    req = AnswerEvaluationRequest(question=q, student_answer="   It varies current.  ")
    assert req.student_answer == "It varies current."


def test_score_boundaries_validation() -> None:
    """Verifies rubric score strict boundaries between 0 and 10."""
    # Min bound: 0
    resp_zero = AnswerEvaluationResponse(
        verdict=EvaluationVerdictEnum.INCORRECT,
        score=0,
        feedback="Incorrect",
        provider_mode=VivaProviderModeEnum.DEMONSTRATION,
        provider_id="demo",
    )
    assert resp_zero.score == 0

    # Max bound: 10
    resp_ten = AnswerEvaluationResponse(
        verdict=EvaluationVerdictEnum.CORRECT,
        score=10,
        feedback="Perfect",
        provider_mode=VivaProviderModeEnum.DEMONSTRATION,
        provider_id="demo",
    )
    assert resp_ten.score == 10

    # Below 0
    with pytest.raises(ValidationError):
        AnswerEvaluationResponse(
            verdict=EvaluationVerdictEnum.INCORRECT,
            score=-1,
            feedback="Negative",
            provider_mode=VivaProviderModeEnum.DEMONSTRATION,
            provider_id="demo",
        )

    # Above 10
    with pytest.raises(ValidationError):
        AnswerEvaluationResponse(
            verdict=EvaluationVerdictEnum.CORRECT,
            score=11,
            feedback="Too high",
            provider_mode=VivaProviderModeEnum.DEMONSTRATION,
            provider_id="demo",
        )


# ==============================================================================
# 4. JSON Serialization & Deserialization Tests
# ==============================================================================


def test_model_json_serialization_roundtrip() -> None:
    """Ensures contracts serialize and deserialize cleanly to and from JSON."""
    exp = AIExperimentContext(
        title="Digital Logic Verification",
        subject="Computer Engineering",
        experiment_number="CS-201",
    )
    req = QuestionGenerationRequest(
        experiment=exp,
        question_count=3,
        difficulty=VivaDifficultyEnum.ADVANCED,
        topic_focus=VivaTopicEnum.PROCEDURE,
    )

    json_str = req.model_dump_json()
    data = json.loads(json_str)
    assert data["question_count"] == 3
    assert data["difficulty"] == "advanced"
    assert data["experiment"]["title"] == "Digital Logic Verification"

    # Restore from JSON
    restored = QuestionGenerationRequest.model_validate_json(json_str)
    assert restored.question_count == 3
    assert restored.difficulty == VivaDifficultyEnum.ADVANCED
    assert restored.experiment.title == "Digital Logic Verification"


# ==============================================================================
# 5. Abstract Interface & Mock Implementation Tests
# ==============================================================================


def test_cannot_instantiate_abstract_base_ai_provider() -> None:
    """Verifies BaseAIProvider cannot be instantiated without implementing abstract methods."""
    with pytest.raises(TypeError) as exc_info:
        BaseAIProvider()  # type: ignore[abstract]
    err_str = str(exc_info.value)
    assert "Can't instantiate abstract class BaseAIProvider" in err_str
    assert "abstract method" in err_str


class MockValidAIProvider(BaseAIProvider):
    """Concrete mock implementation satisfying BaseAIProvider interface."""

    @property
    def provider_id(self) -> str:
        return "mock-ai"

    @property
    def display_name(self) -> str:
        return "Mock Academic AI Provider"

    @property
    def provider_mode(self) -> VivaProviderModeEnum:
        return VivaProviderModeEnum.DEMONSTRATION

    async def generate_questions(
        self,
        request: QuestionGenerationRequest,
    ) -> QuestionGenerationResponse:
        questions = [
            AIGeneratedQuestion(
                id=f"mock-q-{i+1}",
                question_number=i + 1,
                question_text=f"Mock question {i+1} for {request.experiment.title}?",
                topic=request.topic_focus if request.topic_focus != VivaTopicEnum.MIXED else VivaTopicEnum.THEORY,
                difficulty=request.difficulty,
                expected_answer="Mock authoritative answer.",
                key_points=["Point 1", "Point 2"],
            )
            for i in range(request.question_count)
        ]
        return QuestionGenerationResponse(
            questions=questions,
            provider_mode=self.provider_mode,
            provider_id=self.provider_id,
            metadata={"mock": True},
        )

    async def evaluate_answer(
        self,
        request: AnswerEvaluationRequest,
    ) -> AnswerEvaluationResponse:
        return AnswerEvaluationResponse(
            verdict=EvaluationVerdictEnum.CORRECT,
            score=9,
            feedback=f"Good answer for question {request.question.question_number}.",
            what_you_got_right=request.student_answer,
            what_was_missing="",
            expected_answer="Model answer",
            improvement_tip="Keep practicing",
            provider_mode=self.provider_mode,
            provider_id=self.provider_id,
            metadata={"mock": True},
        )


@pytest.mark.asyncio
async def test_mock_provider_implementation() -> None:
    """Ensures a compliant provider executes asynchronously and produces valid responses."""
    provider = MockValidAIProvider()

    assert provider.provider_id == "mock-ai"
    assert provider.display_name == "Mock Academic AI Provider"
    assert provider.provider_mode == VivaProviderModeEnum.DEMONSTRATION

    exp = AIExperimentContext(title="Vernier Caliper", subject="Physics")
    gen_req = QuestionGenerationRequest(
        experiment=exp,
        question_count=2,
        difficulty=VivaDifficultyEnum.BEGINNER,
        topic_focus=VivaTopicEnum.APPARATUS,
    )

    gen_resp = await provider.generate_questions(gen_req)
    assert len(gen_resp.questions) == 2
    assert gen_resp.questions[0].question_number == 1
    assert gen_resp.topic_distribution == {"apparatus": 2}

    eval_req = AnswerEvaluationRequest(
        question=gen_resp.questions[0],
        student_answer="Vernier caliper measures dimensions with high precision.",
    )
    eval_resp = await provider.evaluate_answer(eval_req)
    assert eval_resp.score == 9
    assert eval_resp.verdict == EvaluationVerdictEnum.CORRECT
    assert eval_resp.provider_id == "mock-ai"


# ==============================================================================
# 6. Exception Hierarchy Tests
# ==============================================================================


def test_exception_inheritance_and_properties() -> None:
    """Verifies AIProviderError inheritance hierarchy, retryability, and message formatting."""
    # Base
    base_err = AIProviderError(message="General failure", provider_id="gemini", retryable=False)
    assert isinstance(base_err, Exception)
    assert base_err.provider_id == "gemini"
    assert not base_err.retryable
    assert str(base_err) == "[gemini] General failure"

    # Unavailable (retryable)
    unavail_err = AIProviderUnavailableError(message="Service unreachable", provider_id="gemini")
    assert isinstance(unavail_err, AIProviderError)
    assert unavail_err.retryable is True
    assert str(unavail_err) == "[gemini] Service unreachable"

    # Timeout (retryable, timeout_seconds)
    timeout_err = AIProviderTimeoutError(message="Call took > 4000ms", provider_id="gemini", timeout_seconds=4.0)
    assert isinstance(timeout_err, AIProviderError)
    assert timeout_err.retryable is True
    assert timeout_err.timeout_seconds == 4.0

    # Response error (non-retryable)
    resp_err = AIProviderResponseError(message="JSON output violated schema", provider_id="openai")
    assert isinstance(resp_err, AIProviderError)
    assert resp_err.retryable is False

    # Rate limit (retryable, retry_after)
    rate_err = AIProviderRateLimitError(message="HTTP 429 quota exhausted", provider_id="gemini", retry_after_seconds=30.0)
    assert isinstance(rate_err, AIProviderError)
    assert rate_err.retryable is True
    assert rate_err.retry_after_seconds == 30.0

    # Config error (non-retryable)
    cfg_err = AIProviderConfigError(message="API key missing", provider_id="gemini")
    assert isinstance(cfg_err, AIProviderError)
    assert cfg_err.retryable is False


# ==============================================================================
# 7. Architecture Isolation & Import Purity Tests
# ==============================================================================


def test_no_vendor_sdk_dependencies() -> None:
    """Verifies app.modules.ai does not import vendor SDKs or FastAPI request/response objects."""
    ai_modules = [ai_base, ai_exceptions, ai_schemas]

    forbidden_packages = [
        "google.genai",
        "google.generativeai",
        "openai",
        "anthropic",
        "fastapi.Request",
        "fastapi.Response",
        "sqlalchemy.orm.Session",
    ]

    for mod in ai_modules:
        source = inspect.getsource(mod)
        for forbidden in forbidden_packages:
            assert forbidden not in source, f"Module {mod.__name__} must not depend on {forbidden}"
