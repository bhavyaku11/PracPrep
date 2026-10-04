"""Lab Manual Document Ingestion Router.

Provides authenticated multipart/form-data upload for laboratory manuals,
performing format/signature validation, experiment ownership verification,
secure sandboxed storage, and transactional document metadata persistence.
"""

from datetime import datetime, timezone
from typing import Annotated, Optional
import uuid

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings, settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.modules.auth.dependencies import get_current_active_user
from app.modules.auth.models import User
from app.modules.documents.extractor import (
    DocumentExtractionError,
    DocumentExtractorService,
    DocumentFileNotFoundError,
    get_extractor_service,
)
from app.modules.documents.models import UploadedDocument
from app.modules.documents.parser import (
    DocumentSectionParserService,
    get_section_parser_service,
)
from app.modules.documents.schemas import (
    DocumentExtractionResult,
    DocumentStatusEnum,
    DocumentUploadResponse,
    ManualParseRequestBody,
    ManualParseResponse,
    ManualParseStatusEnum,
)
from app.modules.documents.storage import DocumentStorageService, get_storage_service
from app.modules.experiments.models import Experiment

router = APIRouter()


@router.post(
    "/upload-manual",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload laboratory manual file",
    description=(
        "Accepts a multipart/form-data upload of a PDF or Word DOCX laboratory manual. "
        "Validates file format, structure signature, and size limit; checks experiment ownership; "
        "stores the file securely; and creates/updates document metadata."
    ),
)
@limiter.limit(get_settings().RATE_LIMIT_UPLOAD_DEFAULT)
async def upload_manual(
    request: Request,
    file: Annotated[UploadFile, File(description="Uploaded lab manual file (.pdf, .docx)")],
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[DocumentStorageService, Depends(get_storage_service)],
    experiment_id: Annotated[Optional[uuid.UUID], Form(description="Target experiment UUID")] = None,
    experimentId: Annotated[Optional[uuid.UUID], Form(description="Target experiment UUID (camelCase alias)")] = None,
) -> DocumentUploadResponse:
    """Upload and attach a laboratory manual file to an experiment workspace."""
    target_exp_id = experiment_id or experimentId
    if target_exp_id is None:
        raise HTTPException(
            status_code=422,
            detail="experiment_id is required.",
        )

    # 1. Retrieve experiment and verify ownership before doing file I/O
    query = (
        select(Experiment)
        .options(selectinload(Experiment.documents))
        .where(
            Experiment.id == target_exp_id,
            Experiment.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found or access denied.",
        )

    # 2. Record old document paths for safe cleanup after successful commit
    old_docs = list(experiment.documents) if experiment.documents else []
    old_storage_paths = [doc.storage_path for doc in old_docs if doc.storage_path]

    # 3. Stream and validate file storage safely
    try:
        stored_info = await storage.save_upload_file(
            file=file,
            user_id=current_user.id,
            experiment_id=experiment.id,
            max_size_bytes=settings.MAX_UPLOAD_SIZE_BYTES,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store uploaded file.",
        )

    # 4. Transactionally persist new document metadata and update experiment
    now = datetime.now(timezone.utc)
    new_doc = UploadedDocument(
        id=uuid.uuid4(),
        user_id=current_user.id,
        experiment_id=experiment.id,
        file_name=stored_info.original_filename,
        file_size_bytes=stored_info.file_size_bytes,
        mime_type=stored_info.mime_type,
        storage_path=stored_info.storage_path,
        status=DocumentStatusEnum.PENDING.value,
        extracted_text=None,
        extracted_data={},
        error_message=None,
        created_at=now,
        updated_at=now,
    )

    try:
        # Delete old document records for this experiment (clean replacement)
        for old_doc in old_docs:
            await db.delete(old_doc)

        db.add(new_doc)
        experiment.has_manual_file = True
        experiment.file_name = stored_info.original_filename
        experiment.updated_at = now

        await db.commit()
        await db.refresh(new_doc)
    except Exception:
        await db.rollback()
        # Clean up newly written file since DB transaction failed
        storage.delete_file(stored_info.storage_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist document metadata.",
        )

    # 5. Database commit succeeded: Clean up previously stored physical files
    for old_path in old_storage_paths:
        storage.delete_file(old_path)

    return DocumentUploadResponse(
        id=new_doc.id,
        experiment_id=new_doc.experiment_id,
        file_name=new_doc.file_name,
        mime_type=new_doc.mime_type,
        file_size_bytes=new_doc.file_size_bytes,
        status=new_doc.status,
        has_manual_file=True,
        created_at=new_doc.created_at,
        updated_at=new_doc.updated_at,
    )


@router.post(
    "/{experiment_id}/extract-text",
    response_model=DocumentExtractionResult,
    status_code=status.HTTP_200_OK,
    summary="Extract text from experiment lab manual",
    description=(
        "Retrieves the active lab manual uploaded for the specified experiment, "
        "extracts readable text using digital PDF/DOCX extractors, "
        "persists the extracted text and metadata, and returns structured extraction results."
    ),
)
async def extract_manual_text(
    experiment_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    extractor: Annotated[DocumentExtractorService, Depends(get_extractor_service)],
) -> DocumentExtractionResult:
    """Extract text from the uploaded laboratory manual for an experiment."""
    query = (
        select(Experiment)
        .options(selectinload(Experiment.documents))
        .where(
            Experiment.id == experiment_id,
            Experiment.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found or access denied.",
        )

    if not experiment.documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uploaded laboratory manual found for this experiment.",
        )

    # Pick the latest uploaded document
    active_doc = sorted(experiment.documents, key=lambda d: d.created_at, reverse=True)[0]

    try:
        extraction_result = await extractor.extract_document_and_persist(
            db=db,
            document_id=active_doc.id,
            user_id=current_user.id,
        )
    except DocumentFileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The uploaded manual file was not found in storage.",
        )
    except DocumentExtractionError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err.message,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during document text extraction.",
        )

    return extraction_result


@router.post(
    "/{experiment_id}/parse-manual",
    response_model=ManualParseResponse,
    status_code=status.HTTP_200_OK,
    summary="Parse extracted lab manual text into structured experiment sections",
    description=(
        "Retrieves the active laboratory manual uploaded for the specified experiment, "
        "processes the extracted source text through the AI section parser, "
        "and returns a structured, editable draft without modifying final experiment fields."
    ),
)
async def parse_manual_sections(
    experiment_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_active_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    parser_service: Annotated[DocumentSectionParserService, Depends(get_section_parser_service)],
    body: Optional[ManualParseRequestBody] = None,
) -> ManualParseResponse:
    """Parse extracted lab manual text into structured experiment sections using AI."""
    # 1. Verify that the experiment belongs to the authenticated user
    query = (
        select(Experiment)
        .options(selectinload(Experiment.documents))
        .where(
            Experiment.id == experiment_id,
            Experiment.user_id == current_user.id,
        )
    )
    result = await db.execute(query)
    experiment = result.scalar_one_or_none()

    if not experiment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Experiment not found or access denied.",
        )

    # 2. Check for uploaded document or direct raw_text override
    has_body_text = bool(body and body.raw_text and body.raw_text.strip())
    if not experiment.documents and not has_body_text:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No uploaded laboratory manual found for this experiment.",
        )

    active_doc = (
        sorted(experiment.documents, key=lambda d: d.created_at, reverse=True)[0]
        if experiment.documents
        else None
    )

    source_text = body.raw_text if has_body_text else (active_doc.extracted_text if active_doc else None)
    file_name = active_doc.file_name if active_doc else "manual.txt"
    doc_id = active_doc.id if active_doc else None

    # 3. Verify usable extracted text is available
    if not source_text or not source_text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Document extraction has not completed or no usable text was extracted. Please run extraction first.",
        )

    # 4. Invoke the section parser service
    parse_result = await parser_service.parse_document_text(
        text=source_text,
        file_name=file_name,
        document_id=doc_id,
        experiment_id=experiment.id,
    )

    # 5. Persist draft into document extracted_data safely (without overwriting source text or experiment)
    if active_doc and parse_result.status != ManualParseStatusEnum.FAILED:
        try:
            doc_data = dict(active_doc.extracted_data or {})
            doc_data["parsed_sections_draft"] = parse_result.model_dump(by_alias=True, mode="json")
            active_doc.extracted_data = doc_data
            active_doc.updated_at = datetime.now(timezone.utc)
            await db.commit()
        except Exception as exc:
            logger.warning("Could not persist parsed sections draft into document metadata: %s", exc)
            await db.rollback()

    return parse_result

