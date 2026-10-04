"""Document Ingestion & Processing Pydantic Schemas.

Defines request and response schemas for lab manual file upload,
metadata tracking, and processing pipeline state.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class DocumentStatusEnum(str, Enum):
    """Processing lifecycle status of uploaded document."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentUploadResponse(BaseModel):
    """Structured response for uploaded lab manual document."""

    id: uuid.UUID = Field(description="Unique document identifier")
    experiment_id: uuid.UUID = Field(
        serialization_alias="experimentId",
        description="Associated experiment identifier",
    )
    file_name: str = Field(
        serialization_alias="fileName",
        description="Original uploaded manual filename",
    )
    mime_type: str = Field(
        serialization_alias="mimeType",
        description="MIME type of the uploaded file",
    )
    file_size_bytes: int = Field(
        serialization_alias="fileSizeBytes",
        description="File size in bytes",
    )
    status: str = Field(
        default=DocumentStatusEnum.PENDING.value,
        description="Processing status (e.g. 'pending', 'processing', 'completed', 'failed')",
    )
    has_manual_file: bool = Field(
        default=True,
        serialization_alias="hasManualFile",
        description="Whether manual file is attached to the experiment",
    )
    created_at: datetime = Field(
        serialization_alias="createdAt",
        description="Upload creation timestamp in UTC",
    )
    updated_at: datetime = Field(
        serialization_alias="updatedAt",
        description="Last update timestamp in UTC",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExtractionStatusEnum(str, Enum):
    """Granular extraction result status."""

    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    NO_TEXT_FOUND = "no_text_found"
    CORRUPTED = "corrupted"
    ENCRYPTED = "encrypted"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class ExtractedPage(BaseModel):
    """Per-page structural text representation."""

    page_number: int = Field(serialization_alias="pageNumber", description="1-based page number")
    text: str = Field(description="Extracted and normalized text on this page")
    character_count: int = Field(serialization_alias="characterCount", description="Character count on this page")
    has_text: bool = Field(serialization_alias="hasText", description="Whether extractable text was found")
    ocr_applied: bool = Field(
        default=False,
        serialization_alias="ocrApplied",
        description="Whether OCR was used to extract text for this page",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class DocumentExtractionResult(BaseModel):
    """Structured result returned by digital text extraction pipeline."""

    document_id: Optional[uuid.UUID] = Field(
        default=None,
        serialization_alias="documentId",
        description="Uploaded document UUID if associated",
    )
    experiment_id: Optional[uuid.UUID] = Field(
        default=None,
        serialization_alias="experimentId",
        description="Associated experiment UUID if applicable",
    )
    source_file_type: str = Field(
        serialization_alias="sourceFileType",
        description="Detected file type ('pdf', 'docx')",
    )
    extracted_text: str = Field(
        serialization_alias="extractedText",
        description="Complete normalized extracted text",
    )
    page_count: int = Field(
        serialization_alias="pageCount",
        description="Total page or structural block count",
    )
    character_count: int = Field(
        serialization_alias="characterCount",
        description="Total extracted character count",
    )
    status: ExtractionStatusEnum = Field(
        description="Detailed extraction status",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal extraction warnings",
    )
    failure_reason: Optional[str] = Field(
        default=None,
        serialization_alias="failureReason",
        description="Detailed failure reason when extraction cannot complete",
    )
    pages: list[ExtractedPage] = Field(
        default_factory=list,
        description="Per-page or per-block text breakdown",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional extraction metadata and structural details",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


from app.modules.ai.schemas import ParsedExperimentSections


class ManualParseStatusEnum(str, Enum):
    """Execution status for document LLM section parsing."""

    SUCCESS = "success"
    SUCCESS_WITH_WARNINGS = "success_with_warnings"
    FAILED = "failed"


class ManualParseRequestBody(BaseModel):
    """Optional request payload for manual text parsing."""

    raw_text: Optional[str] = Field(
        default=None,
        description="Optional manual text override for direct parsing without uploaded document",
    )

    model_config = ConfigDict(extra="forbid")


class ManualParseResponse(BaseModel):
    """Structured response container for AI-parsed laboratory manual sections."""

    document_id: Optional[uuid.UUID] = Field(
        default=None,
        serialization_alias="documentId",
        description="Associated uploaded document UUID if present",
    )
    experiment_id: uuid.UUID = Field(
        serialization_alias="experimentId",
        description="Target experiment UUID",
    )
    status: ManualParseStatusEnum = Field(
        description="Parsing execution status",
    )
    sections: ParsedExperimentSections = Field(
        description="Structured experiment sections draft",
    )
    confidence_score: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        serialization_alias="confidenceScore",
        description="Estimated parsing quality and completeness confidence score",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Diagnostic warnings, uncertain fields, or review notices",
    )
    missing_sections: list[str] = Field(
        default_factory=list,
        serialization_alias="missingSections",
        description="Standard lab manual sections that were absent from the source text",
    )
    provider_mode: str = Field(
        default="ai-live",
        serialization_alias="providerMode",
        description="AI provider execution mode ('ai-live' or 'demonstration')",
    )
    provider_id: str = Field(
        default="gemini",
        serialization_alias="providerId",
        description="AI provider identifier",
    )
    raw_character_count: int = Field(
        serialization_alias="rawCharacterCount",
        description="Character count of source text processed",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        serialization_alias="createdAt",
        description="Timestamp when parsing was performed",
    )

    model_config = ConfigDict(populate_by_name=True)

