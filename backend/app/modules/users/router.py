"""Users API Router.

Provides profile retrieval, profile update, and study preferences endpoints for authenticated students.
"""

from datetime import datetime, timezone
import logging
from typing import Annotated
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.modules.auth.dependencies import get_current_active_user
from app.modules.auth.models import User
from app.modules.documents.models import UploadedDocument
from app.modules.documents.storage import (
    DocumentStorageService,
    get_storage_service,
)
from app.modules.experiments.models import (
    Experiment,
    PreparationChecklist,
    default_preparation_checklist_items,
)
from app.modules.users.models import GuestMigration, UserSettings
from app.modules.users.schemas import (
    AccountDeletionResponse,
    DocumentExportItem,
    ExperimentExportItem,
    GuestDataMigrationRequest,
    GuestDataMigrationResponse,
    UserDataExportResponse,
    UserDataPurgeResponse,
    UserExportProfile,
    UserProfileResponse,
    UserProfileUpdateRequest,
    UserSettingsExport,
    UserSettingsResponse,
    UserSettingsUpdateRequest,
    VivaSessionExportItem,
)
from app.modules.viva.models import VivaAnswer, VivaSession

logger = logging.getLogger(__name__)

router = APIRouter()

# Approved profile fields allowed to be mutated via PATCH /me
ALLOWED_PROFILE_FIELDS = {"full_name", "university"}

# Approved settings fields allowed to be mutated via PATCH /me/settings
ALLOWED_SETTINGS_FIELDS = {
    "default_difficulty",
    "default_question_count",
    "preferred_focus",
}


async def get_or_create_user_settings(
    user: User,
    db: AsyncSession,
) -> UserSettings:
    """Retrieve existing UserSettings for user or provision a default record atomically.

    Guarantees lazy provisioning for both GET and PATCH if a settings record does
    not yet exist for the student.
    """
    settings = getattr(user, "settings", None)
    if settings is not None:
        return settings

    stmt = select(UserSettings).where(UserSettings.user_id == user.id)
    result = await db.execute(stmt)
    settings = result.scalar_one_or_none()

    if settings is None:
        now = datetime.now(timezone.utc)
        settings = UserSettings(
            id=uuid.uuid4(),
            user_id=user.id,
            default_difficulty="intermediate",
            default_question_count=5,
            preferred_focus="mixed",
            created_at=now,
            updated_at=now,
        )
        db.add(settings)
        try:
            await db.commit()
            await db.refresh(settings)
            user.settings = settings
        except Exception:
            await db.rollback()
            # If concurrent insertion occurred, attempt to re-select
            stmt = select(UserSettings).where(UserSettings.user_id == user.id)
            result = await db.execute(stmt)
            settings = result.scalar_one_or_none()
            if settings is None:
                raise
            user.settings = settings

    return settings


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile information for the authenticated active user.",
)
async def get_current_user_profile(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserProfileResponse:
    """Retrieve the authenticated user's profile.

    Does not execute redundant database queries since the get_current_active_user
    dependency already resolves the User entity from the Bearer token.
    """
    return UserProfileResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    description="Updates approved profile fields for the authenticated active user.",
)
async def update_current_user_profile(
    payload: UserProfileUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserProfileResponse:
    """Update profile fields for the authenticated active user.

    Applies partial updates using an explicit field allowlist. Unsupplied fields
    remain unchanged. Commits changes to the database and returns the refreshed profile.
    """
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field in ALLOWED_PROFILE_FIELDS:
            setattr(current_user, field, value)

    db.add(current_user)

    try:
        await db.commit()
        await db.refresh(current_user)
    except Exception:
        await db.rollback()
        raise

    return UserProfileResponse.model_validate(current_user)


@router.get(
    "/me/settings",
    response_model=UserSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user study preferences",
    description="Returns the study preferences for the authenticated active user. Automatically provisions default settings if absent.",
)
async def get_current_user_settings(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    """Retrieve the authenticated user's study preferences.

    If settings do not exist yet, provisions default preferences automatically.
    """
    settings = await get_or_create_user_settings(current_user, db)
    return UserSettingsResponse.model_validate(settings)


@router.patch(
    "/me/settings",
    response_model=UserSettingsResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user study preferences",
    description="Updates approved study preference fields for the authenticated active user.",
)
async def update_current_user_settings(
    payload: UserSettingsUpdateRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserSettingsResponse:
    """Update study preferences for the authenticated active user.

    Applies partial updates using an explicit field allowlist. Unsupplied fields
    remain unchanged. Commits changes to the database and returns the refreshed settings.
    """
    settings = await get_or_create_user_settings(current_user, db)

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if field in ALLOWED_SETTINGS_FIELDS:
            setattr(settings, field, value)

    settings.updated_at = datetime.now(timezone.utc)
    db.add(settings)

    try:
        await db.commit()
        await db.refresh(settings)
    except Exception:
        await db.rollback()
        raise

    return UserSettingsResponse.model_validate(settings)


@router.get(
    "/me/export",
    response_model=UserDataExportResponse,
    status_code=status.HTTP_200_OK,
    summary="Export complete user account data",
    description="Returns a complete, structured JSON export of all account data belonging to the authenticated user.",
)
async def export_current_user_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserDataExportResponse:
    """Export all user-owned data including profile, settings, experiments, checklists, viva sessions, and documents.

    Strictly scoped to current_user.id.
    Executes read-only queries with selectinload to prevent N+1 query patterns.
    Does not modify or delete any database records.
    """
    # 1. User profile (excludes password_hash and secrets)
    user_profile = UserExportProfile.model_validate(current_user)

    # 2. Settings (read-only; does not write or provision to the database)
    settings_record = getattr(current_user, "settings", None)
    if settings_record is None:
        stmt = select(UserSettings).where(UserSettings.user_id == current_user.id)
        res = await db.execute(stmt)
        settings_record = res.scalar_one_or_none()

    if settings_record is not None:
        settings_export = UserSettingsExport.model_validate(settings_record)
    else:
        # Non-persisted default export object so settings is populated without modifying DB
        now = datetime.now(timezone.utc)
        settings_export = UserSettingsExport(
            id=uuid.uuid4(),
            user_id=current_user.id,
            default_difficulty="intermediate",
            default_question_count=5,
            preferred_focus="mixed",
            created_at=current_user.created_at or now,
            updated_at=current_user.updated_at or now,
        )

    # 3. Experiments with checklists (single query + selectinload)
    exp_stmt = (
        select(Experiment)
        .where(Experiment.user_id == current_user.id)
        .options(selectinload(Experiment.checklist))
        .order_by(Experiment.created_at.asc())
    )
    exp_res = await db.execute(exp_stmt)
    exp_records = exp_res.scalars().all()
    experiments_export = [
        ExperimentExportItem.model_validate(exp) for exp in exp_records
    ]

    # 4. Viva sessions with answers (single query + selectinload)
    viva_stmt = (
        select(VivaSession)
        .where(VivaSession.user_id == current_user.id)
        .options(selectinload(VivaSession.answers))
        .order_by(VivaSession.created_at.asc())
    )
    viva_res = await db.execute(viva_stmt)
    viva_records = viva_res.scalars().all()
    viva_export = [
        VivaSessionExportItem.model_validate(sess) for sess in viva_records
    ]

    # 5. Uploaded documents (single query, excluding local server storage_path)
    doc_stmt = (
        select(UploadedDocument)
        .where(UploadedDocument.user_id == current_user.id)
        .order_by(UploadedDocument.created_at.asc())
    )
    doc_res = await db.execute(doc_stmt)
    doc_records = doc_res.scalars().all()
    documents_export = [
        DocumentExportItem.model_validate(doc) for doc in doc_records
    ]

    now = datetime.now(timezone.utc)
    return UserDataExportResponse(
        export_version="1.0",
        export_timestamp=int(now.timestamp() * 1000),
        exported_at=now,
        user=user_profile,
        profile=user_profile,
        settings=settings_export,
        experiments=experiments_export,
        viva_sessions=viva_export,
        documents=documents_export,
    )


@router.delete(
    "/me/data",
    response_model=UserDataPurgeResponse,
    status_code=status.HTTP_200_OK,
    summary="Purge all user experiments, viva sessions, and documents",
    description="Permanently wipes all experiments, preparation checklists, viva sessions, viva answers, document metadata, and physical manual files while keeping the user account and study preferences intact.",
)
async def purge_current_user_data(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[DocumentStorageService, Depends(get_storage_service)],
) -> UserDataPurgeResponse:
    """Purge all experiment and examination records while preserving the user account.

    Derives user exclusively from token. Never accepts user ID in params or body.
    Cleans up associated physical manual files before database deletion.
    Leaves user profile and UserSettings intact.
    """
    user_id = current_user.id
    now = datetime.now(timezone.utc)

    # 1. Identify user documents and gather storage paths
    doc_stmt = select(UploadedDocument).where(UploadedDocument.user_id == user_id)
    doc_res = await db.execute(doc_stmt)
    user_docs = doc_res.scalars().all()
    storage_paths = [doc.storage_path for doc in user_docs if doc.storage_path]
    doc_count = len(user_docs)

    # 2. Identify user experiments
    exp_stmt = select(Experiment).where(Experiment.user_id == user_id)
    exp_res = await db.execute(exp_stmt)
    user_exps = exp_res.scalars().all()
    exp_count = len(user_exps)

    # 3. Identify user viva sessions
    viva_stmt = select(VivaSession).where(VivaSession.user_id == user_id)
    viva_res = await db.execute(viva_stmt)
    user_vivas = viva_res.scalars().all()
    viva_count = len(user_vivas)

    # 4. Clean up physical files in sandbox
    try:
        storage.cleanup_user_files(user_id=user_id, storage_paths=storage_paths)
    except (PermissionError, OSError) as fs_err:
        logger.error(
            "Filesystem cleanup failed during data purge for user %s: %s",
            user_id,
            type(fs_err).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely remove stored files during data purge. Operation aborted.",
        ) from fs_err

    # 5. Delete database records in controlled transactional sequence
    try:
        for doc in user_docs:
            await db.delete(doc)
        for exp in user_exps:
            await db.delete(exp)
        for viva in user_vivas:
            await db.delete(viva)

        mig_stmt = select(GuestMigration).where(GuestMigration.user_id == user_id)
        mig_res = await db.execute(mig_stmt)
        user_migs = mig_res.scalars().all()
        for mig in user_migs:
            await db.delete(mig)

        await db.commit()
    except Exception as db_err:
        await db.rollback()
        logger.error(
            "Database error during data purge for user %s: %s",
            user_id,
            type(db_err).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to clear user data from database.",
        ) from db_err

    return UserDataPurgeResponse(
        message="All user data cleared successfully.",
        purged_at=now,
        experiments_deleted=exp_count,
        viva_sessions_deleted=viva_count,
        documents_deleted=doc_count,
    )


@router.delete(
    "/me",
    response_model=AccountDeletionResponse,
    status_code=status.HTTP_200_OK,
    summary="Permanently delete user account and all associated data",
    description="Permanently deletes the authenticated user account, associated settings, experiments, checklists, viva sessions, viva answers, documents, and physical lab manual files from storage.",
)
async def delete_current_user_account(
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[DocumentStorageService, Depends(get_storage_service)],
) -> AccountDeletionResponse:
    """Permanently delete authenticated user and all associated data with cascading cleanup.

    Order of operations:
    1. Identify all physical files belonging to the account using database metadata.
    2. Securely remove physical files from the storage sandbox before committing database changes.
       If filesystem cleanup encounters permission/IO failures, the operation is aborted and the
       database transaction is rolled back, preventing orphaned files or inconsistent state.
    3. Delete the User entity in PostgreSQL. All dependent rows (settings, experiments, checklists,
       viva sessions, answers, documents) are cascaded atomically in the transaction.
    4. Return confirmed deletion response. Subsequent requests with the same token will predictably
       fail with HTTP 401 Unauthorized because the user record no longer exists.
    """
    user_id = current_user.id
    now = datetime.now(timezone.utc)

    # 1. Gather all document records belonging to this user
    doc_stmt = select(UploadedDocument).where(UploadedDocument.user_id == user_id)
    doc_res = await db.execute(doc_stmt)
    user_docs = doc_res.scalars().all()
    storage_paths = [doc.storage_path for doc in user_docs if doc.storage_path]

    # 2. Cleanup physical manual files on disk
    try:
        storage.cleanup_user_files(user_id=user_id, storage_paths=storage_paths)
    except (PermissionError, OSError) as fs_err:
        logger.error(
            "Filesystem cleanup failed during account deletion for user %s: %s",
            user_id,
            type(fs_err).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to securely remove stored files during account deletion. Operation aborted.",
        ) from fs_err

    # 3. Delete user account and cascade in database
    try:
        await db.delete(current_user)
        await db.commit()
    except Exception as db_err:
        await db.rollback()
        logger.error(
            "Database error during account deletion for user %s: %s",
            user_id,
            type(db_err).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account from database.",
        ) from db_err

    return AccountDeletionResponse(
        message="Account and all associated data deleted successfully.",
        deleted_at=now,
        user_id=user_id,
    )


@router.post(
    "/me/migrate-guest-data",
    response_model=GuestDataMigrationResponse,
    status_code=status.HTTP_200_OK,
    summary="Migrate guest experiments and viva sessions to authenticated account",
    description="Batch transfers local guest experiments, checklists, viva practice sessions, and evaluation answers to the authenticated user account with guaranteed atomicity and idempotency.",
)
async def migrate_guest_data(
    payload: GuestDataMigrationRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> GuestDataMigrationResponse:
    """Migrate guest experiments and viva sessions into the authenticated user's account.

    Guarantees:
    - User identity derived strictly from Bearer token (never from payload).
    - Idempotency via unique idempotency_key per user: repeated requests replay original results
      without duplicating data.
    - Full transaction atomicity: either all entities and relationships succeed, or none are stored.
    - Server-generated UUIDs for all newly created records.
    - Relational integrity: client-side experiment IDs in viva sessions are resolved to the new
      server UUIDs, or matched to existing user-owned experiments.
    """
    user_id = current_user.id
    now = datetime.now(timezone.utc)

    # 1. Idempotency Check
    stmt = select(GuestMigration).where(
        GuestMigration.user_id == user_id,
        GuestMigration.idempotency_key == payload.idempotency_key,
    )
    res = await db.execute(stmt)
    existing_migration = res.scalar_one_or_none()
    if existing_migration:
        logger.info(
            "Idempotent replay of guest migration for user %s with key %s",
            user_id,
            payload.idempotency_key,
        )
        return GuestDataMigrationResponse(
            message="Guest data already migrated (idempotent replay).",
            idempotency_key=payload.idempotency_key,
            is_idempotent_replay=True,
            experiments_migrated=existing_migration.experiments_migrated,
            viva_sessions_migrated=existing_migration.viva_sessions_migrated,
            viva_answers_migrated=existing_migration.viva_answers_migrated,
            migrated_at=existing_migration.created_at,
        )

    # 2. Pre-validate client_id uniqueness within payload
    batch_client_exp_ids = {exp.client_id for exp in payload.experiments}
    if len(batch_client_exp_ids) < len(payload.experiments):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate client_id found in experiments payload.",
        )

    batch_client_sess_ids = {sess.client_id for sess in payload.viva_sessions}
    if len(batch_client_sess_ids) < len(payload.viva_sessions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate client_id found in viva_sessions payload.",
        )

    # 3. Pre-validate viva session relationships to experiments
    for sess in payload.viva_sessions:
        if sess.client_experiment_id not in batch_client_exp_ids:
            # Must reference an existing experiment owned by this user
            try:
                existing_uuid = uuid.UUID(sess.client_experiment_id)
            except (ValueError, TypeError, AttributeError):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Viva session '{sess.client_id}' references unknown experiment '{sess.client_experiment_id}'.",
                )
            exp_exists_stmt = select(Experiment.id).where(
                Experiment.id == existing_uuid,
                Experiment.user_id == user_id,
            )
            exp_exists_res = await db.execute(exp_exists_stmt)
            if not exp_exists_res.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Viva session '{sess.client_id}' references experiment '{sess.client_experiment_id}' which does not exist or does not belong to the authenticated user.",
                )

    # 4. Atomic batch insertion
    created_experiments_map: dict[str, Experiment] = {}
    total_answers_migrated = 0

    try:
        # A. Insert experiments and checklists
        for exp_item in payload.experiments:
            new_exp_id = uuid.uuid4()
            exp_created_at = exp_item.created_at or now
            exp_updated_at = exp_item.updated_at or exp_created_at

            exp = Experiment(
                id=new_exp_id,
                user_id=user_id,
                title=exp_item.title,
                subject=exp_item.subject,
                experiment_number=exp_item.experiment_number,
                course_semester=exp_item.course_semester,
                creation_method=exp_item.creation_method or "manual",
                has_manual_file=False,
                file_name=None,
                status=exp_item.status or "ready",
                description=exp_item.description,
                objective=exp_item.objective,
                theory=exp_item.theory,
                apparatus=exp_item.apparatus,
                procedure=exp_item.procedure,
                observations=exp_item.observations,
                calculations=exp_item.calculations,
                precautions=exp_item.precautions,
                created_at=exp_created_at,
                updated_at=exp_updated_at,
            )

            # Checklists
            chk_items = default_preparation_checklist_items()
            if exp_item.checklist:
                chk_items.update(exp_item.checklist)

            checklist = PreparationChecklist(
                id=uuid.uuid4(),
                experiment_id=new_exp_id,
                items=chk_items,
                created_at=exp_created_at,
                updated_at=exp_updated_at,
            )
            exp.checklist = checklist

            db.add(exp)
            created_experiments_map[exp_item.client_id] = exp

        # B. Insert viva sessions and answers
        for sess_item in payload.viva_sessions:
            if sess_item.client_experiment_id in created_experiments_map:
                target_exp_id = created_experiments_map[sess_item.client_experiment_id].id
            else:
                target_exp_id = uuid.UUID(sess_item.client_experiment_id)

            new_sess_id = uuid.uuid4()
            sess_started_at = sess_item.started_at or now
            sess_completed_at = sess_item.completed_at

            sess = VivaSession(
                id=new_sess_id,
                user_id=user_id,
                experiment_id=target_exp_id,
                difficulty=sess_item.difficulty or "intermediate",
                question_count=sess_item.question_count or 5,
                topic_focus=sess_item.topic_focus or "mixed",
                provider_mode=sess_item.provider_mode or "demonstration",
                is_completed=sess_item.is_completed,
                started_at=sess_started_at,
                completed_at=sess_completed_at,
                average_score=sess_item.average_score,
                total_questions=sess_item.total_questions,
                questions_answered=sess_item.questions_answered,
                correct_count=sess_item.correct_count,
                partially_correct_count=sess_item.partially_correct_count,
                incorrect_count=sess_item.incorrect_count,
                topic_analysis=sess_item.topic_analysis or {},
                weak_topics=sess_item.weak_topics or [],
                strong_topics=sess_item.strong_topics or [],
                revision_recommendations=sess_item.revision_recommendations or [],
                created_at=sess_started_at,
                updated_at=sess_completed_at or sess_started_at,
            )

            for ans_item in sess_item.answers:
                ans_created_at = ans_item.created_at or sess_started_at
                ans = VivaAnswer(
                    id=uuid.uuid4(),
                    session_id=new_sess_id,
                    question_id=ans_item.question_id,
                    question_number=ans_item.question_number,
                    topic=ans_item.topic or "theory",
                    difficulty=ans_item.difficulty or "intermediate",
                    question_text=ans_item.question_text,
                    student_answer=ans_item.student_answer,
                    score=ans_item.score,
                    verdict=ans_item.verdict,
                    feedback=ans_item.feedback,
                    expected_answer=ans_item.expected_answer,
                    what_you_got_right=ans_item.what_you_got_right,
                    what_was_missing=ans_item.what_was_missing,
                    suggested_improvement=ans_item.suggested_improvement,
                    key_points_covered=ans_item.key_points_covered or [],
                    key_points_missed=ans_item.key_points_missed or [],
                    evaluation_data=ans_item.evaluation_data or {},
                    time_spent_seconds=ans_item.time_spent_seconds,
                    created_at=ans_created_at,
                )
                sess.answers.append(ans)
                total_answers_migrated += 1

            db.add(sess)

        # C. Record idempotency record
        mig_record = GuestMigration(
            id=uuid.uuid4(),
            user_id=user_id,
            idempotency_key=payload.idempotency_key,
            status="completed",
            experiments_migrated=len(payload.experiments),
            viva_sessions_migrated=len(payload.viva_sessions),
            viva_answers_migrated=total_answers_migrated,
            created_at=now,
        )
        db.add(mig_record)

        await db.commit()

    except IntegrityError as ie:
        await db.rollback()
        # Check if concurrent duplicate request committed
        stmt = select(GuestMigration).where(
            GuestMigration.user_id == user_id,
            GuestMigration.idempotency_key == payload.idempotency_key,
        )
        res = await db.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            return GuestDataMigrationResponse(
                message="Guest data already migrated (idempotent replay).",
                idempotency_key=payload.idempotency_key,
                is_idempotent_replay=True,
                experiments_migrated=existing.experiments_migrated,
                viva_sessions_migrated=existing.viva_sessions_migrated,
                viva_answers_migrated=existing.viva_answers_migrated,
                migrated_at=existing.created_at,
            )
        logger.error("Integrity error during guest data migration for user %s: %s", user_id, ie)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A conflicting record or duplicate migration was detected.",
        ) from ie

    except Exception as err:
        await db.rollback()
        logger.error("Database error during guest data migration for user %s: %s", user_id, err)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist migrated records to database. Operation rolled back.",
        ) from err

    return GuestDataMigrationResponse(
        message="Guest data migrated successfully.",
        idempotency_key=payload.idempotency_key,
        is_idempotent_replay=False,
        experiments_migrated=len(payload.experiments),
        viva_sessions_migrated=len(payload.viva_sessions),
        viva_answers_migrated=total_answers_migrated,
        migrated_at=now,
    )




