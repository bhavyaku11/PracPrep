"""Unit tests for Viva Voce Examination Pydantic Schemas and DTOs.

Verifies session creation validation, answer submission constraints, completion payloads,
ORM model serialization, camelCase alias conversions, score boundaries, and transcript DTOs.
"""

from datetime import datetime, timezone
from decimal import Decimal
import uuid

import pytest
from pydantic import ValidationError

from app.modules.auth.models import User  # noqa: F401
import app.modules.documents.models  # noqa: F401
import app.modules.experiments.models  # noqa: F401
import app.modules.users.models  # noqa: F401
from app.modules.viva.models import VivaAnswer, VivaSession
from app.modules.viva.schemas import (
    EvaluationVerdictEnum,
    RevisionRecommendationResponse,
    TopicPerformanceResponse,
    VivaAnswerResponse,
    VivaAnswerSubmitRequest,
    VivaDifficultyEnum,
    VivaEvaluateAnswerRequest,
    VivaEvaluationResponse,
    VivaGenerateQuestionsRequest,
    VivaProviderModeEnum,
    VivaQuestionResponse,
    VivaSessionCompleteRequest,
    VivaSessionConfigDTO,
    VivaSessionCreateRequest,
    VivaSessionListItemResponse,
    VivaSessionListResponse,
    VivaSessionResponse,
    VivaSessionStatusEnum,
    VivaTopicEnum,
    VivaTranscriptResponse,
    WorkspaceTabEnum,
)


# ==============================================================================
# 1. VivaSessionCreateRequest Tests
# ==============================================================================


def test_session_create_valid_minimal_payload() -> None:
    """Minimal create payload requires only experiment_id and sets defaults."""
    exp_id = uuid.uuid4()
    req = VivaSessionCreateRequest(experiment_id=exp_id)
    assert req.experiment_id == exp_id
    assert req.difficulty == VivaDifficultyEnum.INTERMEDIATE
    assert req.question_count == 5
    assert req.topic_focus == VivaTopicEnum.MIXED
    assert req.provider_mode == VivaProviderModeEnum.DEMONSTRATION


def test_session_create_valid_complete_payload() -> None:
    """Full create payload accepts explicit difficulty, topic focus, and question count."""
    exp_id = uuid.uuid4()
    data = {
        "experiment_id": str(exp_id),
        "difficulty": "advanced",
        "question_count": 10,
        "topic_focus": "apparatus",
        "provider_mode": "ai-live",
    }
    req = VivaSessionCreateRequest.model_validate(data)
    assert req.experiment_id == exp_id
    assert req.difficulty == VivaDifficultyEnum.ADVANCED
    assert req.question_count == 10
    assert req.topic_focus == VivaTopicEnum.APPARATUS
    assert req.provider_mode == VivaProviderModeEnum.AI_LIVE


def test_session_create_accepts_frontend_camelcase_aliases() -> None:
    """Create schema accepts frontend camelCase field names."""
    exp_id = uuid.uuid4()
    data = {
        "experimentId": str(exp_id),
        "questionCount": 15,
        "focus": "procedure",
        "providerMode": "demonstration",
    }
    req = VivaSessionCreateRequest.model_validate(data)
    assert req.experiment_id == exp_id
    assert req.question_count == 15
    assert req.topic_focus == VivaTopicEnum.PROCEDURE
    assert req.provider_mode == VivaProviderModeEnum.DEMONSTRATION


def test_session_create_missing_experiment_id_rejected() -> None:
    """Missing experiment_id must raise ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        VivaSessionCreateRequest.model_validate({})
    assert "experiment_id" in str(exc_info.value)


def test_session_create_invalid_uuid_rejected() -> None:
    """Malformed UUID string must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        VivaSessionCreateRequest.model_validate({"experiment_id": "not-a-valid-uuid"})
    assert "experiment_id" in str(exc_info.value)


def test_session_create_unsupported_difficulty_rejected() -> None:
    """Unsupported difficulty value must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        VivaSessionCreateRequest.model_validate({
            "experiment_id": str(uuid.uuid4()),
            "difficulty": "legendary",
        })
    assert "difficulty" in str(exc_info.value)


@pytest.mark.parametrize("invalid_count", [0, -1, -10, 21, 50, 100])
def test_session_create_question_count_boundaries(invalid_count: int) -> None:
    """Question count outside [1, 20] boundary must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        VivaSessionCreateRequest.model_validate({
            "experiment_id": str(uuid.uuid4()),
            "question_count": invalid_count,
        })
    assert "question_count" in str(exc_info.value)


def test_session_create_unsupported_provider_mode_rejected() -> None:
    """Unsupported provider mode must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        VivaSessionCreateRequest.model_validate({
            "experiment_id": str(uuid.uuid4()),
            "provider_mode": "chatgpt-5",
        })
    assert "provider_mode" in str(exc_info.value)


def test_session_create_unknown_fields_forbidden() -> None:
    """Unexpected/unknown keys must be rejected by extra='forbid'."""
    with pytest.raises(ValidationError) as exc_info:
        VivaSessionCreateRequest.model_validate({
            "experiment_id": str(uuid.uuid4()),
            "unknown_extra_field": "injected",
        })
    assert "extra_forbidden" in str(exc_info.value)


@pytest.mark.parametrize(
    "forbidden_payload",
    [
        {"user_id": str(uuid.uuid4())},
        {"userId": str(uuid.uuid4())},
        {"id": str(uuid.uuid4())},
        {"is_completed": True},
        {"average_score": 9.5},
        {"averageScore": 9.5},
        {"started_at": "2026-10-04T00:00:00Z"},
        {"completed_at": "2026-10-04T00:00:00Z"},
        {"total_questions": 10},
        {"questions_answered": 5},
    ],
)
def test_session_create_rejects_client_injected_server_fields(
    forbidden_payload: dict,
) -> None:
    """Clients cannot inject server-managed lifecycle, score, or identity fields."""
    payload = {"experiment_id": str(uuid.uuid4()), **forbidden_payload}
    with pytest.raises(ValidationError):
        VivaSessionCreateRequest.model_validate(payload)


# ==============================================================================
# 2. VivaAnswerSubmitRequest Tests
# ==============================================================================


def test_answer_submit_valid_minimal_payload() -> None:
    """Minimal answer submission requires question_number and student_answer."""
    req = VivaAnswerSubmitRequest(
        question_number=1,
        student_answer="Ohm's law states current is directly proportional to voltage at constant temperature.",
    )
    assert req.question_number == 1
    assert req.student_answer.startswith("Ohm's law states")
    assert req.question_id is None
    assert req.time_spent_seconds is None


def test_answer_submit_valid_complete_payload() -> None:
    """Complete answer submission with optional question context and time spent."""
    data = {
        "question_number": 2,
        "question_id": "vq-exp-123-2",
        "question_text": "What is the physical significance of the slope in V-I graph?",
        "topic": "observations",
        "difficulty": "intermediate",
        "student_answer": "The reciprocal of the slope gives the electrical resistance of the conductor.",
        "time_spent_seconds": 45,
    }
    req = VivaAnswerSubmitRequest.model_validate(data)
    assert req.question_number == 2
    assert req.question_id == "vq-exp-123-2"
    assert req.topic == VivaTopicEnum.OBSERVATIONS
    assert req.time_spent_seconds == 45


def test_answer_submit_accepts_camelcase_aliases() -> None:
    """Answer submission schema accepts frontend camelCase field names."""
    data = {
        "questionNumber": 3,
        "questionId": "vq-456",
        "questionText": "State precautions against meter damage.",
        "studentAnswer": "Always set the multimeter range higher than the expected parameter.",
        "timeSpentSeconds": 30,
    }
    req = VivaAnswerSubmitRequest.model_validate(data)
    assert req.question_number == 3
    assert req.question_id == "vq-456"
    assert req.student_answer.startswith("Always set the multimeter")
    assert req.time_spent_seconds == 30


@pytest.mark.parametrize("empty_val", ["", "   ", "\n\t  \n"])
def test_answer_submit_empty_or_whitespace_answer_rejected(empty_val: str) -> None:
    """Empty or whitespace-only answers must be rejected with 422."""
    with pytest.raises(ValidationError) as exc_info:
        VivaAnswerSubmitRequest.model_validate({
            "question_number": 1,
            "student_answer": empty_val,
        })
    assert "student_answer" in str(exc_info.value)


def test_answer_submit_null_answer_rejected() -> None:
    """Null answer must be rejected."""
    with pytest.raises(ValidationError):
        VivaAnswerSubmitRequest.model_validate({
            "question_number": 1,
            "student_answer": None,
        })


def test_answer_submit_excessively_long_answer_rejected() -> None:
    """Answers exceeding 5000 characters must be rejected."""
    with pytest.raises(ValidationError):
        VivaAnswerSubmitRequest.model_validate({
            "question_number": 1,
            "student_answer": "A" * 5001,
        })


@pytest.mark.parametrize("invalid_q_num", [0, -1, -5])
def test_answer_submit_invalid_question_number(invalid_q_num: int) -> None:
    """Question numbers <= 0 must be rejected."""
    with pytest.raises(ValidationError):
        VivaAnswerSubmitRequest.model_validate({
            "question_number": invalid_q_num,
            "student_answer": "Valid text answer",
        })


def test_answer_submit_negative_time_spent_rejected() -> None:
    """Negative time_spent_seconds must be rejected."""
    with pytest.raises(ValidationError):
        VivaAnswerSubmitRequest.model_validate({
            "question_number": 1,
            "student_answer": "Valid answer",
            "time_spent_seconds": -10,
        })


def test_answer_submit_unknown_fields_forbidden() -> None:
    """Unknown fields in answer submission must be rejected."""
    with pytest.raises(ValidationError) as exc_info:
        VivaAnswerSubmitRequest.model_validate({
            "question_number": 1,
            "student_answer": "Valid answer",
            "extra_field": "forbidden",
        })
    assert "extra_forbidden" in str(exc_info.value)


@pytest.mark.parametrize(
    "forbidden_payload",
    [
        {"score": 10},
        {"verdict": "correct"},
        {"feedback": "Great job"},
        {"expected_answer": "Model answer"},
        {"id": str(uuid.uuid4())},
        {"session_id": str(uuid.uuid4())},
        {"user_id": str(uuid.uuid4())},
        {"evaluation": {"score": 10}},
        {"key_points_covered": ["point1"]},
    ],
)
def test_answer_submit_rejects_client_injected_evaluation_fields(
    forbidden_payload: dict,
) -> None:
    """Clients cannot inject evaluation verdicts, scores, or keys."""
    payload = {
        "question_number": 1,
        "student_answer": "Valid answer",
        **forbidden_payload,
    }
    with pytest.raises(ValidationError):
        VivaAnswerSubmitRequest.model_validate(payload)


# ==============================================================================
# 3. VivaSessionCompleteRequest Tests
# ==============================================================================


def test_session_complete_empty_payload_valid() -> None:
    """Empty payload {} is completely valid for session completion."""
    req = VivaSessionCompleteRequest.model_validate({})
    assert req.notes is None


def test_session_complete_with_notes() -> None:
    """Session completion with optional student notes."""
    req = VivaSessionCompleteRequest(notes="Completed physics viva practice before lab test.")
    assert req.notes == "Completed physics viva practice before lab test."


def test_session_complete_whitespace_notes_normalized() -> None:
    """Whitespace-only notes normalize to None."""
    req = VivaSessionCompleteRequest.model_validate({"notes": "   \n\t  "})
    assert req.notes is None


def test_session_complete_rejects_excessively_long_notes() -> None:
    """Notes exceeding 1000 characters must be rejected."""
    with pytest.raises(ValidationError):
        VivaSessionCompleteRequest.model_validate({"notes": "x" * 1001})


def test_session_complete_rejects_injected_metrics() -> None:
    """Completion payload rejects client scores or calculations."""
    with pytest.raises(ValidationError):
        VivaSessionCompleteRequest.model_validate({
            "notes": "Good session",
            "average_score": 10.0,
            "is_completed": True,
        })


# ==============================================================================
# 4. Question & Evaluation DTO Tests
# ==============================================================================


def test_viva_question_response_serialization() -> None:
    """VivaQuestionResponse correctly serializes to camelCase JSON."""
    dto = VivaQuestionResponse(
        id="vq-101",
        question_number=1,
        question="What is the significance of the least count of an instrument?",
        topic=VivaTopicEnum.APPARATUS,
        difficulty="beginner",
        expected_answer="Least count is the smallest value that can be measured accurately.",
        key_points=["smallest measurable value", "determines resolution and precision"],
        grounded_source_section="Apparatus",
    )
    dumped = dto.model_dump(by_alias=True)
    assert dumped["id"] == "vq-101"
    assert dumped["questionNumber"] == 1
    assert dumped["question"] == "What is the significance of the least count of an instrument?"
    assert dumped["topic"] == "apparatus"
    assert dumped["expectedAnswer"].startswith("Least count is")
    assert len(dumped["keyPoints"]) == 2
    assert dumped["groundedSourceSection"] == "Apparatus"


def test_viva_evaluation_response_serialization() -> None:
    """VivaEvaluationResponse validates scores (0-10) and serializes camelCase."""
    dto = VivaEvaluationResponse(
        verdict=EvaluationVerdictEnum.CORRECT,
        score=9,
        what_you_got_right="Accurately explained operating principles.",
        what_was_missing="Minor note on standard temperature condition.",
        expected_answer="Model answer text.",
        improvement_tip="Specify SI units in oral responses.",
        provider_mode=VivaProviderModeEnum.DEMONSTRATION,
        key_points_covered=["operating principle", "circuit connections"],
        key_points_missed=["ambient temperature"],
    )
    dumped = dto.model_dump(by_alias=True)
    assert dumped["verdict"] == "correct"
    assert dumped["score"] == 9
    assert dumped["whatYouGotRight"].startswith("Accurately explained")
    assert dumped["whatWasMissing"].startswith("Minor note")
    assert dumped["improvementTip"] == "Specify SI units in oral responses."
    assert dumped["providerMode"] == "demonstration"
    assert dumped["keyPointsCovered"] == ["operating principle", "circuit connections"]
    assert dumped["keyPointsMissed"] == ["ambient temperature"]


@pytest.mark.parametrize("invalid_score", [-1, 11, 100])
def test_viva_evaluation_invalid_score_boundaries(invalid_score: int) -> None:
    """Score must be between 0 and 10."""
    with pytest.raises(ValidationError):
        VivaEvaluationResponse(
            verdict=EvaluationVerdictEnum.CORRECT,
            score=invalid_score,
            what_you_got_right="Good",
            what_was_missing="None",
            expected_answer="Answer",
            improvement_tip="Tip",
        )


# ==============================================================================
# 5. VivaAnswerResponse Tests & Synthesis
# ==============================================================================


def test_viva_answer_response_from_dict() -> None:
    """VivaAnswerResponse serializes correctly from dictionary."""
    ans_id = uuid.uuid4()
    sess_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    dto = VivaAnswerResponse(
        id=ans_id,
        session_id=sess_id,
        question_id="vq-01",
        question_number=1,
        question_text="State Lenz's law.",
        topic="theory",
        difficulty="intermediate",
        student_answer="The direction of induced EMF opposes the change in flux producing it.",
        score=10,
        verdict="correct",
        feedback="Flawless recitation of Lenz's law.",
        expected_answer="Induced current opposes the change in magnetic flux.",
        what_you_got_right="Exact statement of opposition to flux change.",
        what_was_missing="",
        suggested_improvement="None needed.",
        key_points_covered=["opposes flux change", "conservation of energy"],
        key_points_missed=[],
        created_at=now,
    )

    dumped = dto.model_dump(by_alias=True)
    assert dumped["id"] == ans_id
    assert dumped["sessionId"] == sess_id
    assert dumped["questionNumber"] == 1
    assert dumped["questionText"] == "State Lenz's law."
    assert dumped["studentAnswer"].startswith("The direction of induced")
    assert dumped["score"] == 10
    assert dumped["verdict"] == "correct"
    # Nested evaluation synthesized automatically
    assert dto.evaluation is not None
    assert dto.evaluation.score == 10
    assert dto.evaluation.verdict == EvaluationVerdictEnum.CORRECT
    # Millisecond timestamp computed from created_at
    assert dto.timestamp == int(now.timestamp() * 1000)


def test_viva_answer_response_from_orm_model() -> None:
    """VivaAnswerResponse serializes directly from SQLAlchemy VivaAnswer ORM model."""
    ans_id = uuid.uuid4()
    sess_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    orm_answer = VivaAnswer(
        id=ans_id,
        session_id=sess_id,
        question_id="vq-02",
        question_number=2,
        topic="apparatus",
        difficulty="beginner",
        question_text="Why is an ammeter connected in series?",
        student_answer="Because an ammeter has very low internal resistance and measures current flowing through the branch.",
        score=8,
        verdict="correct",
        feedback="Good explanation of low internal resistance.",
        expected_answer="An ammeter has low resistance so connecting it in series does not alter branch current.",
        what_you_got_right="Mentioned low internal resistance and series current measurement.",
        what_was_missing="",
        suggested_improvement="State what happens if connected in parallel (short circuit).",
        key_points_covered=["low resistance", "series placement"],
        key_points_missed=["parallel short-circuit hazard"],
        evaluation_data={},
        time_spent_seconds=28,
        created_at=now,
    )

    dto = VivaAnswerResponse.model_validate(orm_answer)
    assert dto.id == ans_id
    assert dto.session_id == sess_id
    assert dto.question_number == 2
    assert dto.score == 8
    assert dto.verdict == "correct"
    assert dto.time_spent_seconds == 28
    assert dto.evaluation is not None
    assert dto.evaluation.score == 8
    assert dto.timestamp == int(now.timestamp() * 1000)


# ==============================================================================
# 6. VivaSessionResponse Tests
# ==============================================================================


def test_viva_session_response_full_serialization() -> None:
    """VivaSessionResponse serializes complete session metrics and nested DTOs."""
    sess_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    ans_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    session_dto = VivaSessionResponse(
        id=sess_id,
        experiment_id=exp_id,
        experiment_title="Verification of Thevenin's Theorem",
        subject="Electrical Circuits",
        difficulty="intermediate",
        question_count=5,
        topic_focus="theory",
        provider_mode="demonstration",
        is_completed=True,
        started_at=now,
        completed_at=now,
        total_questions=5,
        questions_answered=5,
        correct_count=4,
        partially_correct_count=1,
        incorrect_count=0,
        average_score=8.5,
        topic_analysis={
            "theory": TopicPerformanceResponse(
                topic="theory",
                total=3,
                correct=3,
                partially_correct=0,
                incorrect=0,
                average_score=9.0,
            ),
            "procedure": TopicPerformanceResponse(
                topic="procedure",
                total=2,
                correct=1,
                partially_correct=1,
                incorrect=0,
                average_score=7.75,
            ),
        },
        weak_topics=["procedure"],
        strong_topics=["theory"],
        revision_recommendations=[
            RevisionRecommendationResponse(
                topic="Procedure Step Verification",
                reason="Minor hesitation observed on open-circuit voltage measurement.",
                suggested_action="Review step 3 in the Procedure tab.",
                workspace_tab=WorkspaceTabEnum.PROCEDURE,
            )
        ],
        answers=[
            VivaAnswerResponse(
                id=ans_id,
                session_id=sess_id,
                question_number=1,
                question_text="Define Thevenin voltage.",
                topic="theory",
                difficulty="intermediate",
                student_answer="Open-circuit voltage across load terminals.",
                score=9,
                verdict="correct",
                created_at=now,
            )
        ],
        created_at=now,
        updated_at=now,
    )

    dumped = session_dto.model_dump(by_alias=True)
    assert dumped["id"] == sess_id
    assert dumped["experimentId"] == exp_id
    assert dumped["experimentTitle"] == "Verification of Thevenin's Theorem"
    assert dumped["subject"] == "Electrical Circuits"
    assert dumped["difficulty"] == "intermediate"
    assert dumped["questionCount"] == 5
    assert dumped["topicFocus"] == "theory"
    assert dumped["isCompleted"] is True
    assert dumped["status"] == "completed"
    assert dumped["averageScore"] == 8.5
    assert "theory" in dumped["topicAnalysis"]
    assert dumped["topicAnalysis"]["theory"]["averageScore"] == 9.0
    assert dumped["revisionRecommendations"][0]["workspaceTab"] == "procedure"
    assert len(dumped["answers"]) == 1
    assert dumped["config"]["questionCount"] == 5
    assert dumped["config"]["difficulty"] == "intermediate"


def test_viva_session_response_from_orm_model() -> None:
    """VivaSessionResponse serializes from SQLAlchemy VivaSession ORM model."""
    sess_id = uuid.uuid4()
    user_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    orm_session = VivaSession(
        id=sess_id,
        user_id=user_id,
        experiment_id=exp_id,
        difficulty="advanced",
        question_count=10,
        topic_focus="mixed",
        provider_mode="demonstration",
        is_completed=False,
        started_at=now,
        completed_at=None,
        average_score=Decimal("7.65"),
        total_questions=10,
        questions_answered=3,
        correct_count=2,
        partially_correct_count=1,
        incorrect_count=0,
        topic_analysis={},
        weak_topics=[],
        strong_topics=["theory"],
        revision_recommendations=[],
        created_at=now,
        updated_at=now,
    )

    dto = VivaSessionResponse.model_validate(orm_session)
    assert dto.id == sess_id
    assert dto.experiment_id == exp_id
    assert dto.is_completed is False
    assert dto.status == "in-progress"
    assert dto.average_score == 7.65
    assert dto.config is not None
    assert dto.config.difficulty == VivaDifficultyEnum.ADVANCED
    assert dto.config.question_count == 10
    assert dto.started_at_timestamp == int(now.timestamp() * 1000)
    assert dto.completed_at_timestamp is None


def test_viva_session_response_empty_analytics_supported() -> None:
    """Session response safely supports empty analytics when no answers submitted yet."""
    sess_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    dto = VivaSessionResponse(
        id=sess_id,
        experiment_id=exp_id,
        difficulty="beginner",
        question_count=5,
        topic_focus="mixed",
        provider_mode="demonstration",
        is_completed=False,
        started_at=now,
        total_questions=5,
        created_at=now,
        updated_at=now,
    )

    assert dto.status == "in-progress"
    assert dto.questions_answered == 0
    assert dto.average_score is None
    assert dto.topic_analysis == {}
    assert dto.weak_topics == []
    assert dto.strong_topics == []
    assert dto.revision_recommendations == []
    assert dto.answers == []


# ==============================================================================
# 7. VivaTranscriptResponse Tests
# ==============================================================================


def test_viva_transcript_response_serialization() -> None:
    """VivaTranscriptResponse serializes session summary and answer transcripts."""
    sess_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    ans_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    dto = VivaTranscriptResponse(
        session_id=sess_id,
        experiment_id=exp_id,
        difficulty="intermediate",
        is_completed=True,
        total_questions=1,
        questions_answered=1,
        average_score=9.0,
        started_at=now,
        completed_at=now,
        answers=[
            VivaAnswerResponse(
                id=ans_id,
                session_id=sess_id,
                question_number=1,
                question_text="What is resonance in RLC circuits?",
                topic="theory",
                difficulty="intermediate",
                student_answer="When inductive reactance equals capacitive reactance and impedance is purely resistive.",
                score=9,
                verdict="correct",
                created_at=now,
            )
        ],
    )

    dumped = dto.model_dump(by_alias=True)
    assert dumped["sessionId"] == sess_id
    assert dumped["experimentId"] == exp_id
    assert dumped["isCompleted"] is True
    assert dumped["totalQuestions"] == 1
    assert dumped["questionsAnswered"] == 1
    assert dumped["averageScore"] == 9.0
    assert len(dumped["answers"]) == 1
    assert dumped["answers"][0]["questionNumber"] == 1


def test_viva_transcript_empty_answers_supported() -> None:
    """Empty transcript response correctly serializes with empty list."""
    sess_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    dto = VivaTranscriptResponse(
        session_id=sess_id,
        experiment_id=exp_id,
        difficulty="beginner",
        is_completed=False,
        total_questions=5,
        questions_answered=0,
        average_score=None,
        started_at=now,
        completed_at=None,
        answers=[],
    )

    assert dto.answers == []
    assert dto.is_completed is False
    assert dto.average_score is None


# ==============================================================================
# 8. VivaSessionListItemResponse & VivaSessionListResponse Tests
# ==============================================================================


def test_viva_session_list_item_and_collection() -> None:
    """VivaSessionListResponse provides pagination wrappers for viva history."""
    sess_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    item = VivaSessionListItemResponse(
        id=sess_id,
        experiment_id=exp_id,
        experiment_title="Verification of Superposition Theorem",
        subject="Electrical Networks",
        difficulty="intermediate",
        question_count=5,
        topic_focus="mixed",
        provider_mode="demonstration",
        is_completed=True,
        total_questions=5,
        questions_answered=5,
        correct_count=4,
        average_score=8.0,
        started_at=now,
        completed_at=now,
        created_at=now,
    )

    collection = VivaSessionListResponse(
        items=[item],
        total=1,
        page=1,
        page_size=20,
        total_pages=1,
    )

    dumped = collection.model_dump(by_alias=True)
    assert dumped["total"] == 1
    assert dumped["page"] == 1
    assert dumped["pageSize"] == 20
    assert dumped["totalPages"] == 1
    assert len(dumped["items"]) == 1
    assert dumped["items"][0]["experimentTitle"] == "Verification of Superposition Theorem"


# ==============================================================================
# 9. Additional AI Provider Request DTO Tests
# ==============================================================================


def test_generate_questions_request() -> None:
    """VivaGenerateQuestionsRequest validates generation parameters."""
    exp_id = uuid.uuid4()
    req = VivaGenerateQuestionsRequest(
        experiment_id=exp_id,
        question_count=10,
        difficulty=VivaDifficultyEnum.ADVANCED,
        focus=VivaTopicEnum.THEORY,
    )
    assert req.experiment_id == exp_id
    assert req.question_count == 10
    assert req.difficulty == VivaDifficultyEnum.ADVANCED
    assert req.focus == VivaTopicEnum.THEORY


def test_evaluate_answer_request() -> None:
    """VivaEvaluateAnswerRequest validates rubric evaluation payload."""
    question = VivaQuestionResponse(
        id="vq-55",
        question_number=1,
        question="What is meant by Q-factor?",
        topic=VivaTopicEnum.THEORY,
        difficulty="intermediate",
        expected_answer="Ratio of resonant frequency to bandwidth.",
    )
    req = VivaEvaluateAnswerRequest(
        question=question,
        student_answer="Q factor represents quality factor, measuring resonance sharpness.",
    )
    assert req.question.id == "vq-55"
    assert "sharpness" in req.student_answer
