"""Unit and integration tests for Viva Voce AI practice endpoints.

Verifies POST /api/v1/viva/generate-questions and POST /api/v1/viva/evaluate-answer
for authentication, request mapping, provider metadata preservation, strict schema validation,
statelessness (zero DB persistence), error mapping, and exception sanitization.
"""

import asyncio
from datetime import datetime, timezone
import math
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock
import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.modules.ai.base import BaseAIProvider
from app.modules.ai.exceptions import (
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.modules.ai.schemas import (
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
from app.modules.auth.models import User
import app.modules.documents.models  # noqa: F401
from app.modules.experiments.models import Experiment, PreparationChecklist
import app.modules.users.models  # noqa: F401
from app.modules.viva.models import VivaSession
from app.modules.viva.router import get_viva_ai_provider


# ==============================================================================
# Test Fixtures & Helpers
# ==============================================================================


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def other_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_user(sample_user_id: uuid.UUID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=sample_user_id,
        email="viva_student@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        full_name="Viva Student",
        university="Engineering University",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def auth_token(sample_user_id: uuid.UUID) -> str:
    return create_access_token(sample_user_id)


@pytest.fixture
def auth_headers(auth_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {auth_token}"}


def create_sample_experiment(
    user_id: uuid.UUID,
    exp_id: Optional[uuid.UUID] = None,
    title: str = "Ohm's Law Verification",
    subject: str = "Physics",
) -> Experiment:
    """Helper to instantiate an Experiment ORM model."""
    now = datetime.now(timezone.utc)
    actual_exp_id = exp_id or uuid.uuid4()
    exp = Experiment(
        id=actual_exp_id,
        user_id=user_id,
        title=title,
        subject=subject,
        experiment_number="EXP-01",
        course_semester="Semester 1",
        creation_method="manual",
        has_manual_file=False,
        file_name=None,
        status="ready",
        description="Verification of V=IR relationship.",
        objective="Determine resistance using Ohm's Law.",
        theory="Current is directly proportional to voltage at constant temperature.",
        apparatus="Voltmeter, Ammeter, Resistor, DC Power Supply.",
        procedure="1. Connect circuit. 2. Vary voltage. 3. Record current.",
        observations="V vs I table.",
        calculations="Slope = Resistance (R = V/I).",
        precautions="Do not exceed current limits. Check for loose connections.",
        created_at=now,
        updated_at=now,
    )
    chk = PreparationChecklist(
        id=uuid.uuid4(),
        experiment_id=actual_exp_id,
        items={"objective": True, "theory": True, "apparatus": True, "procedure": True, "precautions": True},
        created_at=now,
        updated_at=now,
        experiment=exp,
    )
    exp.checklist = chk
    return exp


def create_sample_ai_questions(count: int = 5, difficulty: VivaDifficultyEnum = VivaDifficultyEnum.INTERMEDIATE) -> list[AIGeneratedQuestion]:
    """Helper to generate mock AIGeneratedQuestion items."""
    topics = [VivaTopicEnum.THEORY, VivaTopicEnum.PROCEDURE, VivaTopicEnum.APPARATUS, VivaTopicEnum.OBSERVATIONS, VivaTopicEnum.PRECAUTIONS]
    questions = []
    for i in range(1, count + 1):
        topic = topics[(i - 1) % len(topics)]
        questions.append(
            AIGeneratedQuestion(
                id=f"q-{i}",
                question_number=i,
                question_text=f"Test question {i} regarding {topic.value} concepts?",
                topic=topic,
                difficulty=difficulty,
                expected_answer=f"Expected detailed answer for question {i}.",
                key_points=[f"key point {i}a", f"key point {i}b"],
                grounded_source_section=topic.value.capitalize(),
            )
        )
    return questions


class MockAIProvider(BaseAIProvider):
    """Configurable mock AI provider for testing endpoint orchestration."""

    def __init__(
        self,
        provider_id: str = "mock-provider",
        provider_mode: VivaProviderModeEnum = VivaProviderModeEnum.DEMONSTRATION,
    ) -> None:
        self._provider_id = provider_id
        self._provider_mode = provider_mode
        self.generate_questions_mock = AsyncMock()
        self.evaluate_answer_mock = AsyncMock()

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def display_name(self) -> str:
        return "Mock AI Provider"

    @property
    def provider_mode(self) -> VivaProviderModeEnum:
        return self._provider_mode

    async def generate_questions(self, request: QuestionGenerationRequest) -> QuestionGenerationResponse:
        return await self.generate_questions_mock(request)

    async def evaluate_answer(self, request: AnswerEvaluationRequest) -> AnswerEvaluationResponse:
        return await self.evaluate_answer_mock(request)


def build_test_client(
    sample_user: User,
    experiment: Optional[Experiment] = None,
    mock_provider: Optional[BaseAIProvider] = None,
) -> tuple[httpx.AsyncClient, AsyncMock]:
    """Build test client with overridden DB session and optional AI provider dependency."""
    db_session = AsyncMock(spec=AsyncSession)
    db_session.add = MagicMock()
    db_session.delete = AsyncMock()
    db_session.commit = AsyncMock()
    db_session.rollback = AsyncMock()

    async def fake_execute(statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        res = MagicMock()

        if "from users" in stmt_str:
            res.scalar_one_or_none.return_value = sample_user
        elif "from experiments" in stmt_str:
            res.scalar_one_or_none.return_value = experiment
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []

        return res

    db_session.execute = AsyncMock(side_effect=fake_execute)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    if mock_provider is not None:
        app.dependency_overrides[get_viva_ai_provider] = lambda: mock_provider

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return client, db_session


# ==============================================================================
# 1. Question Generation Endpoint Tests (POST /api/v1/viva/generate-questions)
# ==============================================================================


@pytest.mark.asyncio
async def test_generate_questions_authenticated_success_with_experiment_id(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Authenticated request with valid experiment_id resolves DB model, calls provider, and returns questions."""
    exp = create_sample_experiment(sample_user.id)
    mock_questions = create_sample_ai_questions(count=5)

    mock_provider = MockAIProvider(provider_id="gemini", provider_mode=VivaProviderModeEnum.AI_LIVE)
    mock_provider.generate_questions_mock.return_value = QuestionGenerationResponse(
        questions=mock_questions,
        provider_mode=VivaProviderModeEnum.AI_LIVE,
        provider_id="gemini",
        metadata={"model": "gemini-2.5-flash"},
    )

    client, db_session = build_test_client(sample_user, experiment=exp, mock_provider=mock_provider)

    payload = {
        "experimentId": str(exp.id),
        "questionCount": 5,
        "difficulty": "intermediate",
        "topicFocus": "mixed",
    }

    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert "questions" in data
    assert len(data["questions"]) == 5
    assert data["providerMode"] == "ai-live"
    assert data["providerId"] == "gemini"
    assert data["totalCount"] == 5

    first_q = data["questions"][0]
    assert first_q["id"] == "q-1"
    assert first_q["questionNumber"] == 1
    assert "Test question 1" in first_q["question"]
    assert first_q["topic"] == "theory"
    assert first_q["difficulty"] == "intermediate"
    assert first_q["expectedAnswer"] == "Expected detailed answer for question 1."
    assert first_q["keyPoints"] == ["key point 1a", "key point 1b"]
    assert first_q["groundedSourceSection"] == "Theory"

    # Verify provider was called with properly mapped QuestionGenerationRequest
    mock_provider.generate_questions_mock.assert_awaited_once()
    called_req: QuestionGenerationRequest = mock_provider.generate_questions_mock.call_args[0][0]
    assert called_req.experiment.title == exp.title
    assert called_req.experiment.subject == exp.subject
    assert called_req.question_count == 5
    assert called_req.difficulty == VivaDifficultyEnum.INTERMEDIATE
    assert called_req.topic_focus == VivaTopicEnum.MIXED

    # Verify statelessness: DB was never written to
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_generate_questions_authenticated_success_with_direct_context(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Authenticated request with direct experimentContext does not require database lookup."""
    mock_questions = create_sample_ai_questions(count=3, difficulty=VivaDifficultyEnum.ADVANCED)
    mock_provider = MockAIProvider(provider_id="demonstration", provider_mode=VivaProviderModeEnum.DEMONSTRATION)
    mock_provider.generate_questions_mock.return_value = QuestionGenerationResponse(
        questions=mock_questions,
        provider_mode=VivaProviderModeEnum.DEMONSTRATION,
        provider_id="demonstration",
        metadata={},
    )

    client, db_session = build_test_client(sample_user, experiment=None, mock_provider=mock_provider)

    payload = {
        "experimentContext": {
            "title": "Boyle's Law Experiment",
            "subject": "Chemistry",
            "theory": "Pressure is inversely proportional to volume.",
            "procedure": "Compress gas in cylinder and measure pressure.",
        },
        "questionCount": 3,
        "difficulty": "advanced",
        "focus": "theory",
    }

    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert len(data["questions"]) == 3
    assert data["providerMode"] == "demonstration"
    assert data["providerId"] == "demonstration"
    assert data["totalCount"] == 3

    # Provider request should reflect the direct context
    called_req: QuestionGenerationRequest = mock_provider.generate_questions_mock.call_args[0][0]
    assert called_req.experiment.title == "Boyle's Law Experiment"
    assert called_req.experiment.subject == "Chemistry"
    assert called_req.question_count == 3
    assert called_req.difficulty == VivaDifficultyEnum.ADVANCED
    assert called_req.topic_focus == VivaTopicEnum.THEORY

    # DB was never written to
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_generate_questions_unauthenticated_returns_401(sample_user: User) -> None:
    """Unauthenticated request without Authorization header returns HTTP 401."""
    client, _ = build_test_client(sample_user)
    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}, "questionCount": 5}
    resp = await client.post("/api/v1/viva/generate-questions", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_questions_invalid_token_returns_401(sample_user: User) -> None:
    """Request with invalid bearer token returns HTTP 401."""
    client, _ = build_test_client(sample_user)
    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}, "questionCount": 5}
    resp = await client.post(
        "/api/v1/viva/generate-questions",
        json=payload,
        headers={"Authorization": "Bearer invalid_malformed_token"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_generate_questions_experiment_not_found_returns_404(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Request with non-existent or unowned experiment_id returns HTTP 404."""
    client, _ = build_test_client(sample_user, experiment=None)
    payload = {
        "experimentId": str(uuid.uuid4()),
        "questionCount": 5,
    }
    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 404
    assert "Experiment not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_generate_questions_invalid_payload_returns_422(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Invalid payloads return HTTP 422: missing context/id, count out of bounds, extra fields."""
    client, _ = build_test_client(sample_user)

    # 1. Missing both experiment_id and experiment_context
    resp1 = await client.post(
        "/api/v1/viva/generate-questions",
        json={"questionCount": 5},
        headers=auth_headers,
    )
    assert resp1.status_code == 422

    # 2. Question count < 1
    resp2 = await client.post(
        "/api/v1/viva/generate-questions",
        json={"experimentContext": {"title": "T", "subject": "S"}, "questionCount": 0},
        headers=auth_headers,
    )
    assert resp2.status_code == 422

    # 3. Question count > 20
    resp3 = await client.post(
        "/api/v1/viva/generate-questions",
        json={"experimentContext": {"title": "T", "subject": "S"}, "questionCount": 25},
        headers=auth_headers,
    )
    assert resp3.status_code == 422

    # 4. Injected unknown field (extra="forbid")
    resp4 = await client.post(
        "/api/v1/viva/generate-questions",
        json={"experimentContext": {"title": "T", "subject": "S"}, "injectedField": "malicious"},
        headers=auth_headers,
    )
    assert resp4.status_code == 422


@pytest.mark.asyncio
async def test_generate_questions_provider_timeout_maps_to_504(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """AI provider timeout maps to HTTP 504 Gateway Timeout."""
    mock_provider = MockAIProvider()
    mock_provider.generate_questions_mock.side_effect = AIProviderTimeoutError(
        message="Gemini upstream timed out", provider_id="gemini"
    )
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}}
    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 504
    assert "timed out" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_questions_provider_unavailable_maps_to_503(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """AI provider unavailability maps to HTTP 503 Service Unavailable."""
    mock_provider = MockAIProvider()
    mock_provider.generate_questions_mock.side_effect = AIProviderUnavailableError(
        message="Gemini service 503", provider_id="gemini"
    )
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}}
    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 503
    assert "unavailable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_questions_provider_rate_limit_maps_to_429(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """AI provider rate limit maps to HTTP 429 Too Many Requests with Retry-After header."""
    mock_provider = MockAIProvider()
    mock_provider.generate_questions_mock.side_effect = AIProviderRateLimitError(
        message="Quota exceeded", provider_id="gemini", retry_after_seconds=45.0
    )
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}}
    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "45"
    assert "rate limit" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_questions_provider_response_error_maps_to_502(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """AI provider malformed/unparseable response maps to HTTP 502 Bad Gateway."""
    mock_provider = MockAIProvider()
    mock_provider.generate_questions_mock.side_effect = AIProviderResponseError(
        message="Unparseable JSON", provider_id="gemini", raw_response="{invalid"
    )
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}}
    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 502
    assert "invalid or unparseable" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_generate_questions_provider_config_error_maps_to_500(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """AI provider configuration error maps to HTTP 500 without leaking credentials."""
    mock_provider = MockAIProvider()
    mock_provider.generate_questions_mock.side_effect = AIProviderConfigError(
        message="API key configuration failure: AIzaSySecret12345", provider_id="gemini"
    )
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}}
    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 500
    detail = resp.json()["detail"]
    assert "AIzaSySecret12345" not in detail


# ==============================================================================
# 2. Answer Evaluation Endpoint Tests (POST /api/v1/viva/evaluate-answer)
# ==============================================================================


@pytest.mark.asyncio
async def test_evaluate_answer_authenticated_success(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Authenticated answer evaluation maps input to provider, validates score and verdict, and returns result."""
    mock_provider = MockAIProvider(provider_id="gemini", provider_mode=VivaProviderModeEnum.AI_LIVE)
    mock_provider.evaluate_answer_mock.return_value = AnswerEvaluationResponse(
        verdict=EvaluationVerdictEnum.CORRECT,
        score=9,
        feedback="Excellent conceptual clarity on Ohm's Law.",
        what_you_got_right="Correctly stated V=IR proportionality and constant temperature constraint.",
        what_was_missing="Could have mentioned non-ohmic conductor exceptions.",
        expected_answer="Current through a conductor between two points is directly proportional to voltage across the two points, provided temperature remains constant.",
        improvement_tip="Specify SI units (Amperes, Volts, Ohms) when reciting formulas orally.",
        key_points_covered=["proportionality", "temperature constraint"],
        key_points_missed=["non-ohmic exceptions"],
        provider_mode=VivaProviderModeEnum.AI_LIVE,
        provider_id="gemini",
        metadata={"latencyMs": 420},
    )

    client, db_session = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {
        "question": {
            "id": "q-viva-1",
            "questionNumber": 1,
            "question": "State Ohm's Law and its necessary physical condition.",
            "topic": "theory",
            "difficulty": "intermediate",
            "expectedAnswer": "V is proportional to I at constant temperature.",
            "keyPoints": ["V is proportional to I", "temperature remains constant"],
            "groundedSourceSection": "Theory",
        },
        "studentAnswer": "Ohm's law states that current is directly proportional to voltage across a conductor provided temperature is constant.",
    }

    resp = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["verdict"] == "correct"
    assert data["score"] == 9
    assert data["whatYouGotRight"].startswith("Correctly stated")
    assert data["whatWasMissing"].startswith("Could have mentioned")
    assert data["expectedAnswer"].startswith("Current through a conductor")
    assert data["improvementTip"].startswith("Specify SI units")
    assert data["providerMode"] == "ai-live"
    assert data["providerId"] == "gemini"
    assert data["keyPointsCovered"] == ["proportionality", "temperature constraint"]
    assert data["keyPointsMissed"] == ["non-ohmic exceptions"]

    # Verify provider call arguments
    mock_provider.evaluate_answer_mock.assert_awaited_once()
    called_req: AnswerEvaluationRequest = mock_provider.evaluate_answer_mock.call_args[0][0]
    assert called_req.question.id == "q-viva-1"
    assert called_req.question.question_text == "State Ohm's Law and its necessary physical condition."
    assert called_req.question.topic == VivaTopicEnum.THEORY
    assert called_req.question.difficulty == VivaDifficultyEnum.INTERMEDIATE
    assert "current is directly proportional" in called_req.student_answer

    # Verify statelessness: zero DB calls
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_evaluate_answer_demonstration_fallback_metadata_preserved(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """When fallback provider is used, evaluation retains demonstration mode and ID."""
    mock_provider = MockAIProvider(provider_id="demonstration", provider_mode=VivaProviderModeEnum.DEMONSTRATION)
    mock_provider.evaluate_answer_mock.return_value = AnswerEvaluationResponse(
        verdict=EvaluationVerdictEnum.PARTIALLY_CORRECT,
        score=6,
        feedback="Partial explanation provided.",
        what_you_got_right="Stated basic relationship.",
        what_was_missing="Missed temperature constancy.",
        expected_answer="V=IR at constant temperature.",
        improvement_tip="Include all physical conditions.",
        key_points_covered=["proportionality"],
        key_points_missed=["temperature"],
        provider_mode=VivaProviderModeEnum.DEMONSTRATION,
        provider_id="demonstration",
    )

    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {
        "question": {
            "id": "q-2",
            "questionNumber": 2,
            "question": "What is the relationship between current and voltage?",
            "topic": "theory",
            "difficulty": "beginner",
        },
        "studentAnswer": "Voltage and current are proportional to each other.",
    }

    resp = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp.status_code == 200

    data = resp.json()
    assert data["verdict"] == "partially-correct"
    assert data["score"] == 6
    assert data["providerMode"] == "demonstration"
    assert data["providerId"] == "demonstration"


@pytest.mark.asyncio
async def test_evaluate_answer_unauthenticated_returns_401(sample_user: User) -> None:
    """Unauthenticated answer evaluation returns HTTP 401."""
    client, _ = build_test_client(sample_user)
    payload = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "Some student answer.",
    }
    resp = await client.post("/api/v1/viva/evaluate-answer", json=payload)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_evaluate_answer_client_injected_score_or_verdict_rejected(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Client-supplied score or verdict is strictly rejected with HTTP 422 (extra='forbid')."""
    client, _ = build_test_client(sample_user)

    payload_with_score = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "My honest answer.",
        "score": 10,
    }
    resp = await client.post("/api/v1/viva/evaluate-answer", json=payload_with_score, headers=auth_headers)
    assert resp.status_code == 422

    payload_with_verdict = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "My honest answer.",
        "verdict": "correct",
    }
    resp2 = await client.post("/api/v1/viva/evaluate-answer", json=payload_with_verdict, headers=auth_headers)
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_evaluate_answer_empty_or_whitespace_answer_rejected(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Empty or whitespace-only student answer is rejected with HTTP 422."""
    client, _ = build_test_client(sample_user)

    payload_whitespace = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "   \n\t  ",
    }
    resp = await client.post("/api/v1/viva/evaluate-answer", json=payload_whitespace, headers=auth_headers)
    assert resp.status_code == 422

    payload_empty = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "",
    }
    resp2 = await client.post("/api/v1/viva/evaluate-answer", json=payload_empty, headers=auth_headers)
    assert resp2.status_code == 422


@pytest.mark.asyncio
async def test_evaluate_answer_provider_errors_mapped_correctly(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Provider exceptions during evaluation map to appropriate HTTP status codes."""
    mock_provider = MockAIProvider()
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "Valid student answer.",
    }

    # 1. Timeout -> 504
    mock_provider.evaluate_answer_mock.side_effect = AIProviderTimeoutError(provider_id="gemini")
    resp_504 = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp_504.status_code == 504

    # 2. Unavailable -> 503
    mock_provider.evaluate_answer_mock.side_effect = AIProviderUnavailableError(provider_id="gemini")
    resp_503 = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp_503.status_code == 503

    # 3. Rate limit -> 429
    mock_provider.evaluate_answer_mock.side_effect = AIProviderRateLimitError(
        provider_id="gemini", retry_after_seconds=20.0
    )
    resp_429 = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp_429.status_code == 429
    assert resp_429.headers.get("Retry-After") == "20"

    # 4. Response error -> 502
    mock_provider.evaluate_answer_mock.side_effect = AIProviderResponseError(provider_id="gemini")
    resp_502 = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp_502.status_code == 502

    # 5. Generic provider error -> 500
    mock_provider.evaluate_answer_mock.side_effect = AIProviderError(provider_id="gemini")
    resp_500 = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp_500.status_code == 500


# ==============================================================================
# 3. Cross-Cutting & Security Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_end_to_end_demonstration_mode_without_mock_provider(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Verifies that without mock overrides, the factory resolves DemonstrationAIProvider offline with 0 network calls."""
    # Do NOT override get_viva_ai_provider, allowing get_ai_provider() default resolution
    client, _ = build_test_client(sample_user, mock_provider=None)

    # 1. Generate questions
    gen_payload = {
        "experimentContext": {
            "title": "Verification of Ohm's Law",
            "subject": "Physics",
            "theory": "Ohm's Law states that current is directly proportional to potential difference.",
            "procedure": "Connect circuit with ammeter and voltmeter. Take readings.",
        },
        "questionCount": 3,
        "difficulty": "intermediate",
        "focus": "theory",
    }

    gen_resp = await client.post("/api/v1/viva/generate-questions", json=gen_payload, headers=auth_headers)
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert len(gen_data["questions"]) == 3
    assert gen_data["providerMode"] == "demonstration"
    assert gen_data["providerId"] == "demonstration"

    first_question = gen_data["questions"][0]

    # 2. Evaluate answer
    eval_payload = {
        "question": first_question,
        "studentAnswer": "Current is directly proportional to potential difference across a conductor if temperature remains unchanged.",
    }

    eval_resp = await client.post("/api/v1/viva/evaluate-answer", json=eval_payload, headers=auth_headers)
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["verdict"] in ["correct", "partially-correct", "incorrect"]
    assert 0 <= eval_data["score"] <= 10
    assert eval_data["providerMode"] == "demonstration"
    assert eval_data["providerId"] == "demonstration"


@pytest.mark.asyncio
async def test_cancellation_propagates_without_suppression(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """asyncio.CancelledError must not be caught and masked as HTTP 500."""
    mock_provider = MockAIProvider()
    mock_provider.generate_questions_mock.side_effect = asyncio.CancelledError()
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}}
    with pytest.raises(asyncio.CancelledError):
        await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)


@pytest.mark.asyncio
async def test_existing_viva_sessions_unaffected(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Existing viva session CRUD routes continue to function normally alongside new AI endpoints."""
    exp = create_sample_experiment(sample_user.id)
    client, _ = build_test_client(sample_user, experiment=exp)

    payload = {
        "experimentId": str(exp.id),
        "difficulty": "intermediate",
        "questionCount": 5,
        "topicFocus": "theory",
        "providerMode": "demonstration",
    }
    resp = await client.post("/api/v1/viva/sessions", json=payload, headers=auth_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["experimentId"] == str(exp.id)


@pytest.mark.asyncio
async def test_generate_questions_empty_questions_from_provider_returns_502(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """When provider returns an empty questions list, endpoint returns HTTP 502 instead of false success."""
    mock_provider = MockAIProvider()
    # Bypass Pydantic validation on QuestionGenerationResponse by constructing a MagicMock response
    empty_res = MagicMock()
    empty_res.questions = []
    mock_provider.generate_questions_mock.return_value = empty_res

    client, _ = build_test_client(sample_user, mock_provider=mock_provider)
    payload = {"experimentContext": {"title": "Title", "subject": "Subject"}}
    resp = await client.post("/api/v1/viva/generate-questions", json=payload, headers=auth_headers)
    assert resp.status_code == 502
    assert "no questions" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_evaluate_answer_cancellation_propagates_without_suppression(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """asyncio.CancelledError during answer evaluation must propagate directly."""
    mock_provider = MockAIProvider()
    mock_provider.evaluate_answer_mock.side_effect = asyncio.CancelledError()
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "Valid student answer.",
    }
    with pytest.raises(asyncio.CancelledError):
        await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)


@pytest.mark.asyncio
async def test_no_api_credentials_leak_in_evaluation_errors(
    sample_user: User, auth_headers: dict[str, str]
) -> None:
    """Evaluation errors do not leak credentials in response detail."""
    mock_provider = MockAIProvider()
    mock_provider.evaluate_answer_mock.side_effect = AIProviderError(
        message="Critical failure involving key AIzaSySuperSecretKey999", provider_id="gemini"
    )
    client, _ = build_test_client(sample_user, mock_provider=mock_provider)

    payload = {
        "question": {
            "id": "q-1",
            "questionNumber": 1,
            "question": "Sample question text?",
            "topic": "theory",
        },
        "studentAnswer": "Valid student answer.",
    }
    resp = await client.post("/api/v1/viva/evaluate-answer", json=payload, headers=auth_headers)
    assert resp.status_code == 500
    assert "AIzaSySuperSecretKey999" not in resp.json()["detail"]

