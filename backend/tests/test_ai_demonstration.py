"""Comprehensive Tests for Deterministic Demonstration Viva AI Provider.

Verifies:
1. Provider interface & metadata (BaseAIProvider conformance).
2. Question generation (determinism, duplicate prevention, count adherence, topic focus, difficulty, sparse context).
3. Answer evaluation (correct, partially correct, incorrect, very short, low-effort, irrelevant).
4. Score boundary constraints (0 <= score <= 10).
5. Deterministic reproducibility across all operations.
6. JSON serialization and deserialization integrity.
7. Zero vendor SDK dependencies.
"""

import json
import pytest
from pydantic import ValidationError

from app.modules.ai.base import BaseAIProvider
from app.modules.ai.demonstration import (
    DemonstrationAIProvider,
    extract_significant_terms,
)
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


@pytest.fixture
def provider() -> DemonstrationAIProvider:
    """Fixture providing a fresh DemonstrationAIProvider instance."""
    return DemonstrationAIProvider()


@pytest.fixture
def full_experiment_context() -> AIExperimentContext:
    """Complete, realistic engineering laboratory manual context."""
    return AIExperimentContext(
        title="Verification of Ohm's Law and Resistor I-V Characteristics",
        subject="Basic Electrical and Electronics Engineering",
        experiment_number="EXP-01",
        description="Verify the linear relationship between voltage and current across a carbon resistor and determine its resistance.",
        objective="To verify Ohm's Law by measuring current for varying voltages across a fixed resistor and plotting the I-V graph.",
        theory="Ohm's Law states that the current flowing through a conductor between two points is directly proportional to the voltage across the two points, provided physical conditions such as temperature remain constant: V = I * R.",
        apparatus="Regulated DC power supply (0-30V), DC Voltmeter (0-15V), DC Ammeter (0-500mA), 100-ohm ceramic resistor, breadboard, connecting wires.",
        procedure="1. Connect the circuit as per the schematic diagram. 2. Verify meters read zero before turning on supply. 3. Vary the DC power supply voltage in steps of 1V from 0V to 10V. 4. Record the corresponding ammeter current in milliamps. 5. Plot V versus I on a linear graph.",
        observations="Voltage V (Volts): [1.0, 2.0, 3.0, 4.0, 5.0]; Current I (mA): [10.1, 19.8, 30.2, 40.1, 49.9].",
        calculations="Slope of V-I graph = Delta V / Delta I = Resistance R = 99.8 ohms. Percentage Error = |100 - 99.8| / 100 * 100 = 0.2%.",
        precautions="1. All connections must be tight and clean. 2. Do not exceed the maximum power rating of the resistor. 3. Avoid parallax error when reading analog meters.",
    )


@pytest.fixture
def minimal_experiment_context() -> AIExperimentContext:
    """Minimal experiment context with only mandatory title and subject."""
    return AIExperimentContext(
        title="Study of Logic Gates",
        subject="Digital Electronics",
    )


# ==============================================================================
# 1. Provider Interface & Metadata Tests
# ==============================================================================


def test_provider_metadata(provider: DemonstrationAIProvider) -> None:
    """Verifies provider metadata matches architecture specifications."""
    assert provider.provider_id == "demonstration"
    assert provider.display_name == "PracPrep Demonstration Engine"
    assert provider.provider_mode == VivaProviderModeEnum.DEMONSTRATION


def test_provider_is_instance_of_base_ai_provider(provider: DemonstrationAIProvider) -> None:
    """Verifies concrete provider inherits from and implements BaseAIProvider."""
    assert isinstance(provider, BaseAIProvider)


@pytest.mark.asyncio
async def test_provider_async_methods_execute_successfully(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
) -> None:
    """Verifies both generate_questions and evaluate_answer execute cleanly."""
    gen_req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=2,
        difficulty=VivaDifficultyEnum.BEGINNER,
        topic_focus=VivaTopicEnum.THEORY,
    )
    gen_resp = await provider.generate_questions(gen_req)
    assert len(gen_resp.questions) == 2

    first_q = gen_resp.questions[0]
    eval_req = AnswerEvaluationRequest(
        question=first_q,
        student_answer="The objective is to verify Ohm's law V = I * R and determine resistance.",
        experiment=full_experiment_context,
    )
    eval_resp = await provider.evaluate_answer(eval_req)
    assert isinstance(eval_resp, AnswerEvaluationResponse)
    assert eval_resp.score >= 0


# ==============================================================================
# 2. Question Generation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_question_generation_full_experiment(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
) -> None:
    """Verifies question generation with complete experiment context."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=5,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)

    assert isinstance(resp, QuestionGenerationResponse)
    assert len(resp.questions) == 5
    assert resp.provider_id == "demonstration"
    assert resp.provider_mode == VivaProviderModeEnum.DEMONSTRATION

    for idx, q in enumerate(resp.questions, start=1):
        assert q.question_number == idx
        assert len(q.question_text) >= 10
        assert q.expected_answer is not None
        assert len(q.key_points) > 0
        assert q.grounded_source_section is not None


@pytest.mark.asyncio
@pytest.mark.parametrize("requested_count", [1, 3, 5, 8, 12, 20])
async def test_question_generation_respects_count(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
    requested_count: int,
) -> None:
    """Verifies that the requested question count is strictly honored across ranges."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=requested_count,
        difficulty=VivaDifficultyEnum.MIXED,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)
    assert len(resp.questions) == requested_count


@pytest.mark.asyncio
async def test_question_generation_is_strictly_deterministic(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
) -> None:
    """Verifies that identical input parameters produce 100% identical question sets."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=7,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.THEORY,
    )
    run1 = await provider.generate_questions(req)
    run2 = await provider.generate_questions(req)

    assert len(run1.questions) == len(run2.questions)
    for q1, q2 in zip(run1.questions, run2.questions):
        assert q1.id == q2.id
        assert q1.question_number == q2.question_number
        assert q1.question_text == q2.question_text
        assert q1.topic == q2.topic
        assert q1.difficulty == q2.difficulty
        assert q1.expected_answer == q2.expected_answer
        assert q1.key_points == q2.key_points


@pytest.mark.asyncio
async def test_question_generation_avoids_duplicate_questions(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
) -> None:
    """Verifies no duplicate questions are returned in a set, even at max question count (20)."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=20,
        difficulty=VivaDifficultyEnum.MIXED,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)
    assert len(resp.questions) == 20

    question_texts = [q.question_text for q in resp.questions]
    unique_texts = set(question_texts)
    assert len(unique_texts) == 20, "Every question in the generated set must be unique"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "difficulty",
    [
        VivaDifficultyEnum.BEGINNER,
        VivaDifficultyEnum.INTERMEDIATE,
        VivaDifficultyEnum.ADVANCED,
    ],
)
async def test_question_generation_difficulty_prioritization(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
    difficulty: VivaDifficultyEnum,
) -> None:
    """Verifies questions matching requested difficulty are prioritized first."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=4,
        difficulty=difficulty,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)
    # The first few questions should match the requested difficulty
    matched_diff_count = sum(1 for q in resp.questions if q.difficulty == difficulty)
    assert matched_diff_count >= 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "topic",
    [
        VivaTopicEnum.THEORY,
        VivaTopicEnum.APPARATUS,
        VivaTopicEnum.PROCEDURE,
        VivaTopicEnum.OBSERVATIONS,
        VivaTopicEnum.PRECAUTIONS,
    ],
)
async def test_question_generation_topic_focus(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
    topic: VivaTopicEnum,
) -> None:
    """Verifies questions matching topic_focus are selected when specified."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=5,
        difficulty=VivaDifficultyEnum.MIXED,
        topic_focus=topic,
    )
    resp = await provider.generate_questions(req)
    # All 5 questions should be from the requested topic since each topic has 8 templates
    for q in resp.questions:
        assert q.topic == topic


@pytest.mark.asyncio
async def test_question_generation_topic_distribution_accuracy(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
) -> None:
    """Verifies topic_distribution dictionary accurately mirrors the question collection."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=10,
        difficulty=VivaDifficultyEnum.MIXED,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)
    expected_dist: dict[str, int] = {}
    for q in resp.questions:
        key = q.topic.value
        expected_dist[key] = expected_dist.get(key, 0) + 1

    assert resp.topic_distribution == expected_dist


@pytest.mark.asyncio
async def test_question_generation_incomplete_context_handling(
    provider: DemonstrationAIProvider,
    minimal_experiment_context: AIExperimentContext,
) -> None:
    """Verifies question generation succeeds gracefully when experiment context is sparse."""
    req = QuestionGenerationRequest(
        experiment=minimal_experiment_context,
        question_count=5,
        difficulty=VivaDifficultyEnum.BEGINNER,
        topic_focus=VivaTopicEnum.MIXED,
    )
    resp = await provider.generate_questions(req)
    assert len(resp.questions) == 5

    # Should fall back cleanly using title and subject without throwing or fabricating fake data
    for q in resp.questions:
        assert "Study of Logic Gates" in q.question_text or "Digital Electronics" in q.question_text or "experiment" in q.question_text.lower()
        assert q.expected_answer is not None and len(q.expected_answer) > 0


@pytest.mark.asyncio
async def test_question_generation_serialization_roundtrip(
    provider: DemonstrationAIProvider,
    full_experiment_context: AIExperimentContext,
) -> None:
    """Verifies QuestionGenerationResponse serializes to JSON and deserializes cleanly."""
    req = QuestionGenerationRequest(
        experiment=full_experiment_context,
        question_count=3,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        topic_focus=VivaTopicEnum.THEORY,
    )
    resp = await provider.generate_questions(req)
    json_str = resp.model_dump_json()
    assert isinstance(json_str, str)

    raw_dict = json.loads(json_str)
    restored = QuestionGenerationResponse.model_validate(raw_dict)
    assert len(restored.questions) == 3
    assert restored.provider_id == "demonstration"


# ==============================================================================
# 3. Answer Evaluation Tests
# ==============================================================================


@pytest.fixture
def sample_question() -> AIGeneratedQuestion:
    """Standard test question for answer evaluation."""
    return AIGeneratedQuestion(
        id="vq-test-01",
        question_number=1,
        question_text="Explain the fundamental governing scientific law or principle that forms the basis of Ohm's Law.",
        topic=VivaTopicEnum.THEORY,
        difficulty=VivaDifficultyEnum.INTERMEDIATE,
        expected_answer="Ohm's Law states that current through a conductor between two points is directly proportional to the voltage across the two points, provided physical conditions such as temperature remain constant: V = I * R.",
        key_points=[
            "State the governing law or equation accurately V = I * R",
            "Define the physical terms voltage, current, and resistance",
            "Explain the key theoretical assumptions such as constant temperature",
        ],
        grounded_source_section="Theory",
    )


@pytest.mark.asyncio
async def test_evaluation_clearly_correct_answer(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies a comprehensive, accurate answer receives a high score and 'correct' verdict."""
    student_ans = (
        "Ohm's Law states that the current flowing through a metallic conductor is directly proportional "
        "to the applied potential difference across its ends, represented by the equation V = I * R. "
        "Here, V is the voltage in volts, I is the current in amperes, and R is the resistance in ohms. "
        "A critical condition is that physical parameters like temperature and material geometry must remain constant."
    )
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=student_ans,
    )
    resp = await provider.evaluate_answer(req)

    assert resp.score >= 8
    assert resp.verdict == EvaluationVerdictEnum.CORRECT
    assert len(resp.key_points_covered) >= 2
    assert "Ohm" in resp.feedback or "accurate" in resp.feedback.lower() or "comprehension" in resp.feedback.lower()
    assert resp.provider_id == "demonstration"
    assert resp.provider_mode == VivaProviderModeEnum.DEMONSTRATION


@pytest.mark.asyncio
async def test_evaluation_partially_correct_answer(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies an answer with partial coverage receives a middle score and 'partially-correct' verdict."""
    student_ans = (
        "It states that voltage equals current multiplied by resistance, so V = I * R. "
        "If you increase voltage, the current also goes up."
    )
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=student_ans,
    )
    resp = await provider.evaluate_answer(req)

    assert 4 <= resp.score <= 7
    assert resp.verdict == EvaluationVerdictEnum.PARTIALLY_CORRECT
    assert len(resp.what_was_missing) > 0


@pytest.mark.asyncio
async def test_evaluation_incorrect_answer(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies an incorrect or highly deficient answer receives a low score and 'incorrect' verdict."""
    student_ans = "The law says that electricity always flows in a circular direction when you connect wires to a battery."
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=student_ans,
    )
    resp = await provider.evaluate_answer(req)

    assert resp.score <= 3
    assert resp.verdict == EvaluationVerdictEnum.INCORRECT


def test_evaluation_empty_or_whitespace_rejected_at_schema(
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies empty or whitespace-only answers are strictly rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        AnswerEvaluationRequest(
            question=sample_question,
            student_answer="",
        )

    with pytest.raises(ValidationError):
        AnswerEvaluationRequest(
            question=sample_question,
            student_answer="     \t \n   ",
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("short_ans", ["yes", "no", "ok", "a", "Ohm"])
async def test_evaluation_very_short_answer(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
    short_ans: str,
) -> None:
    """Verifies answers under 5 characters are scored 0 and marked incorrect."""
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=short_ans,
    )
    resp = await provider.evaluate_answer(req)

    assert resp.score == 0
    assert resp.verdict == EvaluationVerdictEnum.INCORRECT
    assert "too brief" in resp.feedback.lower()
    assert len(resp.key_points_covered) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "low_effort_ans",
    ["idk", "dont know", "I don't know", "no idea", "asdf", "qwerty", "na", "nil", "dunno", "???"],
)
async def test_evaluation_low_effort_answer(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
    low_effort_ans: str,
) -> None:
    """Verifies dismissive or low-effort answers score 1 and receive appropriate guidance."""
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=low_effort_ans,
    )
    resp = await provider.evaluate_answer(req)

    assert resp.score == 1
    assert resp.verdict == EvaluationVerdictEnum.INCORRECT
    assert "not provide the required technical concepts" in resp.feedback.lower()


@pytest.mark.asyncio
async def test_evaluation_irrelevant_answer(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies completely irrelevant responses score 0 with an off-topic warning."""
    irrelevant_ans = (
        "During my weekend vacation I baked chocolate chip cookies with my family "
        "and watched the football championship game on television."
    )
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=irrelevant_ans,
    )
    resp = await provider.evaluate_answer(req)

    assert resp.score == 0
    assert resp.verdict == EvaluationVerdictEnum.INCORRECT
    assert "off-topic" in resp.feedback.lower() or "irrelevant" in resp.feedback.lower()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "answer_text",
    [
        "yes",
        "idk",
        "V = I * R is the formula",
        "Ohm's Law states that current is directly proportional to voltage at constant temperature.",
        "Completely irrelevant gibberish about pizza and movies with lots of words.",
    ],
)
async def test_score_boundary_enforcement(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
    answer_text: str,
) -> None:
    """Verifies all evaluated scores remain strictly within the range [0, 10]."""
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=answer_text,
    )
    resp = await provider.evaluate_answer(req)
    assert 0 <= resp.score <= 10


@pytest.mark.asyncio
async def test_evaluation_is_strictly_deterministic(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies identical evaluation requests return 100% identical outputs."""
    ans = "Ohm's law relates voltage, current, and resistance by the linear equation V = I * R."
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=ans,
    )
    run1 = await provider.evaluate_answer(req)
    run2 = await provider.evaluate_answer(req)

    assert run1.score == run2.score
    assert run1.verdict == run2.verdict
    assert run1.feedback == run2.feedback
    assert run1.what_you_got_right == run2.what_you_got_right
    assert run1.what_was_missing == run2.what_was_missing
    assert run1.key_points_covered == run2.key_points_covered
    assert run1.key_points_missed == run2.key_points_missed
    assert run1.improvement_tip == run2.improvement_tip


@pytest.mark.asyncio
async def test_evaluation_key_points_partition_consistency(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies key_points_covered and key_points_missed cleanly partition the original key points."""
    ans = "The law states V = I * R, where V is voltage, I is current, and R is resistance."
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=ans,
    )
    resp = await provider.evaluate_answer(req)

    all_returned = set(resp.key_points_covered) | set(resp.key_points_missed)
    original_points = set(sample_question.key_points)
    assert all_returned == original_points
    assert len(set(resp.key_points_covered) & set(resp.key_points_missed)) == 0


@pytest.mark.asyncio
async def test_evaluation_serialization_roundtrip(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies AnswerEvaluationResponse serializes to JSON and deserializes cleanly."""
    ans = "V = I * R at constant temperature."
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer=ans,
    )
    resp = await provider.evaluate_answer(req)
    json_str = resp.model_dump_json()
    assert isinstance(json_str, str)

    raw_dict = json.loads(json_str)
    restored = AnswerEvaluationResponse.model_validate(raw_dict)
    assert restored.score == resp.score
    assert restored.verdict == resp.verdict


@pytest.mark.asyncio
async def test_evaluation_with_multi_turn_previous_answers(
    provider: DemonstrationAIProvider,
    sample_question: AIGeneratedQuestion,
) -> None:
    """Verifies evaluation succeeds when multi-turn session context is provided."""
    previous_item = AIEvaluationContextItem(
        question_number=1,
        question_text="What is the objective of this experiment?",
        student_answer="To verify Ohm's law.",
        verdict=EvaluationVerdictEnum.CORRECT,
        score=9,
    )
    req = AnswerEvaluationRequest(
        question=sample_question,
        student_answer="Ohm's law gives V = I * R.",
        previous_answers=[previous_item],
    )
    resp = await provider.evaluate_answer(req)
    assert isinstance(resp, AnswerEvaluationResponse)
    assert resp.score >= 0


def test_no_vendor_sdk_dependencies() -> None:
    """Verifies demonstration.py does not import external AI vendor SDKs or FastAPI."""
    import inspect
    import app.modules.ai.demonstration as demo_module

    forbidden_patterns = [
        "google.genai",
        "google.generativeai",
        "openai",
        "anthropic",
        "fastapi",
        "sqlalchemy",
    ]

    source_code = inspect.getsource(demo_module)
    for pattern in forbidden_patterns:
        assert f"import {pattern}" not in source_code, f"Forbidden import '{pattern}' found in demonstration.py!"
        assert f"from {pattern}" not in source_code, f"Forbidden from-import '{pattern}' found in demonstration.py!"
