"""Laboratory Experiment API Router.

Provides experiment creation with automatic preparation checklist provisioning,
paginated listing with ownership isolation, search, filtering, and individual
experiment retrieval, partial update, and deletion endpoints.
"""

from datetime import datetime, timezone
import math
from typing import Annotated, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_active_user
from app.modules.auth.models import User
from app.modules.experiments.models import (
    Experiment,
    PreparationChecklist,
    default_preparation_checklist_items,
)
from app.modules.experiments.schemas import (
    ChecklistUpdateRequest,
    ExperimentCreateRequest,
    ExperimentListItemResponse,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentStatusEnum,
    ExperimentUpdateRequest,
    PreparationChecklistResponse,
)


router = APIRouter()


@router.post(
    "",
    response_model=ExperimentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new experiment",
    description="Creates a laboratory experiment workspace and automatically provisions its preparation checklist.",
)
async def create_experiment(
    payload: ExperimentCreateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExperimentResponse:
    """Create a new experiment assigned to the authenticated user and initialize its checklist."""
    now = datetime.now(timezone.utc)
    exp_id = uuid.uuid4()
    chk_id = uuid.uuid4()

    new_experiment = Experiment(
        id=exp_id,
        user_id=current_user.id,
        title=payload.title,
        subject=payload.subject,
        experiment_number=payload.experiment_number,
        course_semester=payload.course_semester,
        creation_method=payload.creation_method.value,
        has_manual_file=payload.has_manual_file,
        file_name=payload.file_name,
        status=payload.status.value,
        description=payload.description,
        objective=payload.objective,
        theory=payload.theory,
        apparatus=payload.apparatus,
        procedure=payload.procedure,
        observations=payload.observations,
        calculations=payload.calculations,
        precautions=payload.precautions,
        created_at=now,
        updated_at=now,
    )

    new_checklist = PreparationChecklist(
        id=chk_id,
        experiment_id=exp_id,
        items=default_preparation_checklist_items(),
        created_at=now,
        updated_at=now,
        experiment=new_experiment,
    )

    new_experiment.checklist = new_checklist

    db.add(new_experiment)
    db.add(new_checklist)

    try:
        await db.commit()
        await db.refresh(new_experiment)
        await db.refresh(new_checklist)
    except Exception:
        await db.rollback()
        raise

    # Ensure checklist reference is attached for response serialization
    new_experiment.checklist = new_checklist
    return ExperimentResponse.model_validate(new_experiment)


@router.get(
    "",
    response_model=ExperimentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List user experiments",
    description="Returns a paginated list of experiments belonging exclusively to the authenticated user.",
)
async def list_experiments(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(default=1, ge=1, description="Page index (1-indexed)"),
    page_size: Optional[int] = Query(
        default=None, ge=1, le=100, description="Page size limit (1-100)"
    ),
    pageSize: Optional[int] = Query(
        default=None, ge=1, le=100, description="Page size limit (camelCase alias)"
    ),
    subject: Optional[str] = Query(
        default=None, description="Filter by exact subject name"
    ),
    status_filter: Optional[ExperimentStatusEnum] = Query(
        default=None, alias="status", description="Filter by experiment lifecycle status"
    ),
    search: Optional[str] = Query(
        default=None, description="Case-insensitive search over title, subject, and description"
    ),
) -> ExperimentListResponse:
    """Retrieve a paginated list of experiments with ownership isolation and optional filters."""
    actual_page_size = pageSize if pageSize is not None else (page_size if page_size is not None else 10)

    # 1. Base query strictly scoped to authenticated user
    base_query = select(Experiment).where(Experiment.user_id == current_user.id)

    # 2. Optional subject filter
    if subject is not None and subject.strip():
        base_query = base_query.where(Experiment.subject == subject.strip())

    # 3. Optional status filter
    if status_filter is not None:
        base_query = base_query.where(Experiment.status == status_filter.value)

    # 4. Optional case-insensitive text search across title, subject, description, and experiment number
    if search is not None and search.strip():
        search_pattern = f"%{search.strip()}%"
        search_condition = or_(
            Experiment.title.ilike(search_pattern),
            Experiment.subject.ilike(search_pattern),
            Experiment.description.ilike(search_pattern),
            Experiment.experiment_number.ilike(search_pattern),
        )
        base_query = base_query.where(search_condition)

    # 5. Compute total matching records before pagination
    count_query = select(func.count()).select_from(base_query.subquery())
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # 6. Apply deterministic sorting and pagination
    offset = (page - 1) * actual_page_size
    ordered_query = (
        base_query.order_by(Experiment.updated_at.desc(), Experiment.id.desc())
        .offset(offset)
        .limit(actual_page_size)
    )

    result = await db.execute(ordered_query)
    experiments = result.scalars().all()

    # 7. Compute total pages and construct lightweight response items
    total_pages = math.ceil(total / actual_page_size) if total > 0 else 0
    items = [ExperimentListItemResponse.model_validate(exp) for exp in experiments]

    return ExperimentListResponse(
        items=items,
        total=total,
        page=page,
        page_size=actual_page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get experiment by ID",
    description="Retrieves a single experiment and its preparation checklist for the authenticated user.",
)
async def get_experiment(
    experiment_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExperimentResponse:
    """Retrieve an individual experiment owned by the authenticated user."""
    stmt = (
        select(Experiment)
        .options(selectinload(Experiment.checklist))
        .where(
            Experiment.id == experiment_id,
            Experiment.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    return ExperimentResponse.model_validate(experiment)


@router.patch(
    "/{experiment_id}",
    response_model=ExperimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update experiment by ID",
    description="Partially updates metadata or content sections of an experiment owned by the authenticated user.",
)
async def update_experiment(
    experiment_id: uuid.UUID,
    payload: ExperimentUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExperimentResponse:
    """Partially update an experiment owned by the authenticated user."""
    stmt = (
        select(Experiment)
        .options(selectinload(Experiment.checklist))
        .where(
            Experiment.id == experiment_id,
            Experiment.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Disallow tampering with protected internal fields (defensive check)
    protected_fields = {
        "id",
        "user_id",
        "created_at",
        "updated_at",
        "checklist",
        "preparation_checklist",
        "viva_sessions",
        "documents",
    }
    for field in protected_fields:
        update_data.pop(field, None)

    for field, value in update_data.items():
        if hasattr(value, "value"):
            value = value.value
        setattr(experiment, field, value)

    experiment.updated_at = datetime.now(timezone.utc)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    # Reload with selectinload to ensure clean async serialization of all attributes
    reload_stmt = (
        select(Experiment)
        .options(selectinload(Experiment.checklist))
        .where(
            Experiment.id == experiment_id,
            Experiment.user_id == current_user.id,
        )
    )
    reload_result = await db.execute(reload_stmt)
    refreshed_experiment = reload_result.scalar_one()

    return ExperimentResponse.model_validate(refreshed_experiment)


@router.delete(
    "/{experiment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete experiment by ID",
    description="Deletes an experiment owned by the authenticated user, cascading to associated checklists and viva sessions.",
)
async def delete_experiment(
    experiment_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """Delete an experiment owned by the authenticated user."""
    stmt = select(Experiment).where(
        Experiment.id == experiment_id,
        Experiment.user_id == current_user.id,
    )
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    try:
        await db.delete(experiment)
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{experiment_id}/checklist",
    response_model=PreparationChecklistResponse,
    status_code=status.HTTP_200_OK,
    summary="Update experiment preparation checklist",
    description="Updates one or more preparation checklist item completion states for an experiment owned by the authenticated user.",
)
async def update_experiment_checklist(
    experiment_id: uuid.UUID,
    payload: ChecklistUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PreparationChecklistResponse:
    """Update preparation checklist item states for an experiment owned by the authenticated user."""
    # 1. Scoped query verifying experiment ownership
    stmt = (
        select(Experiment)
        .options(selectinload(Experiment.checklist))
        .where(
            Experiment.id == experiment_id,
            Experiment.user_id == current_user.id,
        )
    )
    result = await db.execute(stmt)
    experiment = result.scalar_one_or_none()

    # Conceal existence of foreign-owned or nonexistent experiments
    if experiment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found",
        )

    # 2. Safely resolve or instantiate checklist without creating duplicates
    checklist = experiment.checklist
    now = datetime.now(timezone.utc)
    if checklist is None:
        chk_stmt = select(PreparationChecklist).where(
            PreparationChecklist.experiment_id == experiment.id
        )
        chk_res = await db.execute(chk_stmt)
        checklist = chk_res.scalar_one_or_none()

        if checklist is None:
            checklist = PreparationChecklist(
                id=uuid.uuid4(),
                experiment_id=experiment.id,
                items=default_preparation_checklist_items(),
                created_at=now,
                updated_at=now,
                experiment=experiment,
            )
            db.add(checklist)
            experiment.checklist = checklist

    # 3. Merge supplied checklist items while preserving unsupplied items
    current_items = (
        dict(checklist.items)
        if checklist.items
        else default_preparation_checklist_items()
    )
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        current_items[key] = value

    checklist.items = current_items
    flag_modified(checklist, "items")
    checklist.updated_at = now

    # 4. Atomically commit updates
    try:
        await db.commit()
        await db.refresh(checklist)
    except Exception:
        await db.rollback()
        raise

    return PreparationChecklistResponse.model_validate(checklist)


