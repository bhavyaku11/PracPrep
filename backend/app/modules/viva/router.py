"""Viva Voce Examination API Router.

Provides authenticated endpoints for creating, listing, retrieving, and deleting
viva practice sessions with strict multi-tenant ownership isolation.
"""

import asyncio
from datetime import datetime, timezone
import math
from typing import Annotated, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.modules.ai.base import BaseAIProvider
from app.modules.ai.exceptions import (
    AIProviderConfigError,
    AIProviderError,
    AIProviderRateLimitError,
    AIProviderResponseError,
    AIProviderTimeoutError,
    AIProviderUnavailableError,
)
from app.modules.ai.factory import get_ai_provider
from app.modules.ai.schemas import (
    AIGeneratedQuestion,
    AIExperimentContext,
    AnswerEvaluationRequest,
    QuestionGenerationRequest,
)
from app.modules.auth.dependencies import get_current_active_user
from app.modules.auth.models import User
from app.modules.experiments.models import Experiment
from app.modules.viva.models import VivaSession
from app.modules.viva.schemas import (
    VivaDifficultyEnum,
    VivaEvaluateAnswerRequest,
    VivaEvaluationResponse,
    VivaGenerateQuestionsRequest,
    VivaGenerateQuestionsResponse,
    VivaQuestionResponse,
    VivaSessionCreateRequest,
    VivaSessionListItemResponse,
    VivaSessionListResponse,
    VivaSessionResponse,
    VivaSessionStatusEnum,
)


router = APIRouter()


def get_viva_ai_provider() -> BaseAIProvider:
    """Dependency resolver returning the configured BaseAIProvider instance."""
    return get_ai_provider()


def _handle_ai_error(exc: Exception) -> None:
    """Translate provider exceptions into appropriate HTTP exceptions."""
    if isinstance(exc, asyncio.CancelledError):
        raise exc
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, AIProviderRateLimitError):
        headers = {}
        if exc.retry_after_seconds is not None:
            headers["Retry-After"] = str(int(math.ceil(exc.retry_after_seconds)))
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate limit or quota exceeded. Please try again later.",
            headers=headers,
        ) from exc
    if isinstance(exc, AIProviderTimeoutError):
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI provider request timed out.",
        ) from exc
    if isinstance(exc, AIProviderUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider is temporarily unavailable.",
        ) from exc
    if isinstance(exc, AIProviderResponseError):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned an invalid or unparseable response.",
        ) from exc
    if isinstance(exc, (AIProviderConfigError, AIProviderError)):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI provider encountered an internal error.",
        ) from exc
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred during AI processing.",
    ) from exc


def _serialize_viva_session(session: VivaSession) -> VivaSessionResponse:
    """Helper to serialize VivaSession ORM model to VivaSessionResponse DTO with experiment metadata."""
    dto = VivaSessionResponse.model_validate(session)
    if hasattr(session, "experiment") and session.experiment is not None:
        dto.experiment_title = session.experiment.title
        dto.subject = session.experiment.subject
    return dto


def _serialize_viva_session_list_item(session: VivaSession) -> VivaSessionListItemResponse:
    """Helper to serialize VivaSession ORM model to VivaSessionListItemResponse DTO with experiment metadata."""
    dto = VivaSessionListItemResponse.model_validate(session)
    if hasattr(session, "experiment") and session.experiment is not None:
        dto.experiment_title = session.experiment.title
        dto.subject = session.experiment.subject
    return dto


@router.post(
    "/sessions",
    response_model=VivaSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new viva examination session",
    description="Initiates an interactive viva voce practice session for a verified user-owned experiment.",
)
async def create_viva_session(
    payload: VivaSessionCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VivaSessionResponse:
    """Create a new viva practice session with strict experiment ownership verification."""
    # 1. Verify referenced experiment exists and is owned by authenticated user
    exp_stmt = select(Experiment).where(
        Experiment.id == payload.experiment_id,
        Experiment.user_id == current_user.id,
    )
    exp_result = await db.execute(exp_stmt)
    experiment = exp_result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    # 2. Instantiate VivaSession with established defaults and requested config
    now = datetime.now(timezone.utc)
    new_session = VivaSession(
        id=uuid.uuid4(),
        user_id=current_user.id,
        experiment_id=experiment.id,
        difficulty=payload.difficulty.value,
        question_count=payload.question_count,
        topic_focus=payload.topic_focus.value,
        provider_mode=payload.provider_mode.value,
        is_completed=False,
        started_at=now,
        completed_at=None,
        total_questions=payload.question_count,
        questions_answered=0,
        correct_count=0,
        partially_correct_count=0,
        incorrect_count=0,
        average_score=None,
        topic_analysis={},
        weak_topics=[],
        strong_topics=[],
        revision_recommendations=[],
        created_at=now,
        updated_at=now,
    )

    db.add(new_session)

    try:
        await db.commit()
        await db.refresh(new_session)
    except Exception:
        await db.rollback()
        raise

    # Attach verified experiment relationship for serialization
    new_session.experiment = experiment
    return _serialize_viva_session(new_session)


@router.get(
    "/sessions",
    response_model=VivaSessionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List viva examination sessions",
    description="Returns a paginated list of viva practice sessions owned by the authenticated user.",
)
async def list_viva_sessions(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1, description="Page index (1-indexed)"),
    page_size: Optional[int] = Query(
        default=None, ge=1, le=100, description="Page size limit (1-100)"
    ),
    pageSize: Optional[int] = Query(
        default=None, ge=1, le=100, description="Page size limit (camelCase alias)"
    ),
    experiment_id: Optional[uuid.UUID] = Query(
        default=None, description="Filter by experiment UUID"
    ),
    experimentId: Optional[uuid.UUID] = Query(
        default=None, description="Filter by experiment UUID (camelCase alias)"
    ),
    status_filter: Optional[VivaSessionStatusEnum] = Query(
        default=None, alias="status", description="Filter by status ('in-progress', 'completed')"
    ),
    difficulty: Optional[VivaDifficultyEnum] = Query(
        default=None, description="Filter by session difficulty level"
    ),
) -> VivaSessionListResponse:
    """Retrieve a paginated collection of viva sessions with ownership isolation and optional filters."""
    actual_page_size = pageSize if pageSize is not None else (page_size if page_size is not None else 10)
    target_experiment_id = experimentId or experiment_id

    # 1. Base query strictly scoped to authenticated user
    base_query = select(VivaSession).where(VivaSession.user_id == current_user.id)

    # 2. Optional experiment ID filter
    if target_experiment_id is not None:
        base_query = base_query.where(VivaSession.experiment_id == target_experiment_id)

    # 3. Optional status filter
    if status_filter is not None:
        if status_filter == VivaSessionStatusEnum.COMPLETED:
            base_query = base_query.where(VivaSession.is_completed.is_(True))
        elif status_filter == VivaSessionStatusEnum.IN_PROGRESS:
            base_query = base_query.where(VivaSession.is_completed.is_(False))

    # 4. Optional difficulty filter
    if difficulty is not None:
        base_query = base_query.where(VivaSession.difficulty == difficulty.value)

    # 5. Compute total matching records before pagination
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # 6. Apply deterministic sorting (newest started_at first, then ID) and pagination
    # Eager-load experiment for metadata without loading full answer transcripts
    offset = (page - 1) * actual_page_size
    ordered_query = (
        base_query.options(selectinload(VivaSession.experiment))
        .order_by(VivaSession.started_at.desc(), VivaSession.id.desc())
        .offset(offset)
        .limit(actual_page_size)
    )

    result = await db.execute(ordered_query)
    sessions = result.scalars().all()

    # 7. Compute total pages and construct summary response
    total_pages = math.ceil(total / actual_page_size) if total > 0 else 0
    items = [_serialize_viva_session_list_item(s) for s in sessions]

    return VivaSessionListResponse(
        items=items,
        total=total,
        page=page,
        page_size=actual_page_size,
        total_pages=total_pages,
    )


@router.get(
    "/sessions/{session_id}",
    response_model=VivaSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get viva examination session details",
    description="Retrieves a full viva practice session and its answer evaluations for the authenticated user.",
)
async def get_viva_session(
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VivaSessionResponse:
    """Retrieve full details of an individual viva session owned by the authenticated user."""
    stmt = (
        select(VivaSession)
        .options(
            selectinload(VivaSession.experiment),
            selectinload(VivaSession.answers),
        )
        .where(
            VivaSession.id == session_id,
            VivaSession.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Viva session not found",
        )

    return _serialize_viva_session(session)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete viva examination session",
    description="Deletes a viva session owned by the authenticated user, cascading to associated answers.",
)
async def delete_viva_session(
    session_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete a viva session owned by the authenticated user with cascade cleanup."""
    stmt = select(VivaSession).where(
        VivaSession.id == session_id,
        VivaSession.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Viva session not found",
        )

    await db.delete(session)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==============================================================================
# AI Viva Practice Endpoints (Stateless)
# ==============================================================================


@router.post(
    "/generate-questions",
    response_model=VivaGenerateQuestionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate viva examination questions",
    description="Generates grounded viva examination questions based on experiment context or experiment ID using configured AI provider.",
)
@limiter.limit(get_settings().RATE_LIMIT_AI_DEFAULT)
async def generate_viva_questions(
    request: Request,
    payload: VivaGenerateQuestionsRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    provider: Annotated[BaseAIProvider, Depends(get_viva_ai_provider)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VivaGenerateQuestionsResponse:
    """Generate viva questions grounded in experiment context.

    Stateless endpoint: Does not persist questions or sessions.
    """
    # 1. Resolve experiment context
    if payload.experiment_id is not None:
        exp_stmt = select(Experiment).where(
            Experiment.id == payload.experiment_id,
            Experiment.user_id == current_user.id,
        )
        exp_result = await db.execute(exp_stmt)
        experiment = exp_result.scalar_one_or_none()

        if experiment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Experiment not found",
            )

        exp_context = AIExperimentContext(
            title=experiment.title,
            subject=experiment.subject,
            experiment_number=experiment.experiment_number,
            description=experiment.description,
            objective=experiment.objective,
            theory=experiment.theory,
            apparatus=experiment.apparatus,
            procedure=experiment.procedure,
            observations=experiment.observations,
            calculations=experiment.calculations,
            precautions=experiment.precautions,
        )
    elif payload.experiment_context is not None:
        try:
            exp_context = AIExperimentContext.model_validate(payload.experiment_context)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid experiment context: {exc}",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either experiment_id or experiment_context must be provided.",
        )

    # 2. Build provider request
    req = QuestionGenerationRequest(
        experiment=exp_context,
        question_count=payload.question_count,
        difficulty=payload.difficulty,
        topic_focus=payload.focus,
        constraints=[],
    )

    # 3. Call AI provider with mapped error handling
    try:
        res = await provider.generate_questions(req)
    except Exception as exc:
        _handle_ai_error(exc)

    if not res.questions:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned no questions.",
        )

    # 4. Map provider questions to API response schema
    mapped_questions = [
        VivaQuestionResponse(
            id=q.id,
            question_number=q.question_number,
            question=q.question_text,
            topic=q.topic,
            difficulty=q.difficulty.value if hasattr(q.difficulty, "value") else str(q.difficulty),
            expected_answer=q.expected_answer,
            key_points=q.key_points,
            grounded_source_section=q.grounded_source_section,
        )
        for q in res.questions
    ]

    return VivaGenerateQuestionsResponse(
        questions=mapped_questions,
        provider_mode=res.provider_mode,
        provider_id=res.provider_id,
        total_count=len(mapped_questions),
    )


@router.post(
    "/evaluate-answer",
    response_model=VivaEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate student viva answer",
    description="Evaluates a student viva voce answer against question rubric and context using configured AI provider.",
)
@limiter.limit(get_settings().RATE_LIMIT_AI_DEFAULT)
async def evaluate_viva_answer(
    request: Request,
    payload: VivaEvaluateAnswerRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    provider: Annotated[BaseAIProvider, Depends(get_viva_ai_provider)],
) -> VivaEvaluationResponse:
    """Evaluate a single viva question answer.

    Stateless endpoint: Does not persist answer records or modify session states.
    """
    # 1. Map incoming question to AIGeneratedQuestion
    try:
        diff_enum = VivaDifficultyEnum(payload.question.difficulty.lower())
    except (ValueError, AttributeError):
        diff_enum = VivaDifficultyEnum.INTERMEDIATE

    try:
        ai_question = AIGeneratedQuestion(
            id=payload.question.id,
            question_number=payload.question.question_number,
            question_text=payload.question.question,
            topic=payload.question.topic,
            difficulty=diff_enum,
            expected_answer=payload.question.expected_answer,
            key_points=payload.question.key_points,
            grounded_source_section=payload.question.grounded_source_section,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid question payload: {exc}",
        )

    # 2. Build provider request
    req = AnswerEvaluationRequest(
        question=ai_question,
        student_answer=payload.student_answer,
    )

    # 3. Call AI provider with error handling
    try:
        eval_res = await provider.evaluate_answer(req)
    except Exception as exc:
        _handle_ai_error(exc)

    # 4. Map provider response to VivaEvaluationResponse
    return VivaEvaluationResponse(
        verdict=eval_res.verdict,
        score=eval_res.score,
        feedback=eval_res.feedback,
        what_you_got_right=eval_res.what_you_got_right,
        what_was_missing=eval_res.what_was_missing,
        expected_answer=eval_res.expected_answer,
        improvement_tip=eval_res.improvement_tip,
        provider_mode=eval_res.provider_mode,
        provider_id=eval_res.provider_id,
        key_points_covered=eval_res.key_points_covered,
        key_points_missed=eval_res.key_points_missed,
    )

