"""Experiment and Preparation Checklist Pydantic Schemas.

Defines request and response data transfer objects for laboratory experiment
management, lifecycle tracking, preparation checklists, and listings.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
import uuid

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.modules.experiments.models import default_preparation_checklist_items


# ==============================================================================
# Enumerations & Constants
# ==============================================================================


class CreationMethodEnum(str, Enum):
    """Supported creation mechanisms for experiments."""

    MANUAL = "manual"
    UPLOAD = "upload"


class ExperimentStatusEnum(str, Enum):
    """Lifecycle statuses for experiments."""

    DRAFT = "draft"
    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    READY = "ready"
    ANALYZING = "analyzing"


SUPPORTED_CHECKLIST_SECTIONS: tuple[str, ...] = (
    "objective",
    "theory",
    "apparatus",
    "procedure",
    "precautions",
)


# ==============================================================================
# Preparation Checklist Schemas
# ==============================================================================


class PreparationChecklistItemResponse(BaseModel):
    """Detailed metadata and state for a single checklist item."""

    id: str = Field(description="Standard checklist section identifier")
    label: str = Field(description="Human-readable title for the checklist item")
    description: str = Field(description="Guidance on verifying this section")
    completed: bool = Field(default=False, description="Verification status")
    tab_target: Optional[str] = Field(
        default=None,
        serialization_alias="tabTarget",
        description="Associated workspace tab",
    )

    model_config = ConfigDict(populate_by_name=True)


class PreparationChecklistResponse(BaseModel):
    """Preparation checklist response mirroring the 1-to-1 database entity."""

    id: uuid.UUID
    experiment_id: uuid.UUID = Field(serialization_alias="experimentId")
    items: dict[str, bool] = Field(
        default_factory=default_preparation_checklist_items,
        description="Dictionary mapping section keys to completion booleans",
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class PreparationChecklistUpdateRequest(BaseModel):
    """Payload to batch update checklist item states."""

    model_config = ConfigDict(extra="forbid")

    items: dict[str, bool] = Field(
        ...,
        description="Dictionary mapping section keys ('objective', 'theory', 'apparatus', 'procedure', 'precautions') to booleans",
        examples=[{"objective": True, "theory": True}],
    )

    @field_validator("items")
    @classmethod
    def validate_items(cls, v: dict[str, bool]) -> dict[str, bool]:
        if not v:
            raise ValueError("Checklist items mapping cannot be empty")
        valid_sections = set(SUPPORTED_CHECKLIST_SECTIONS)
        for key, val in v.items():
            if key not in valid_sections:
                raise ValueError(
                    f"Invalid checklist section key: '{key}'. Supported sections are: {sorted(valid_sections)}"
                )
            if not isinstance(val, bool):
                raise ValueError(f"Value for '{key}' must be a boolean (True or False)")
        return v


class PreparationChecklistItemToggleRequest(BaseModel):
    """Payload to toggle a single checklist item."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(
        ...,
        validation_alias=AliasChoices("item_id", "itemId"),
        description="Checklist item section key (e.g. 'objective', 'procedure')",
    )
    completed: bool = Field(
        ...,
        description="Target completion boolean state",
    )

    @field_validator("item_id")
    @classmethod
    def validate_item_id(cls, v: str) -> str:
        if not isinstance(v, str):
            raise ValueError("Item ID must be a string")
        stripped = v.strip().lower()
        if stripped not in SUPPORTED_CHECKLIST_SECTIONS:
            raise ValueError(
                f"Invalid checklist item '{stripped}'. Supported items are: {sorted(SUPPORTED_CHECKLIST_SECTIONS)}"
            )
        return stripped


class ChecklistUpdateRequest(BaseModel):
    """Payload to update one or multiple checklist items directly.

    Expected structure:
    {
        "objective": true,
        "theory": false,
        "apparatus": true
    }
    """

    model_config = ConfigDict(extra="forbid")

    objective: Optional[bool] = None
    theory: Optional[bool] = None
    apparatus: Optional[bool] = None
    procedure: Optional[bool] = None
    precautions: Optional[bool] = None

    @field_validator(
        "objective",
        "theory",
        "apparatus",
        "procedure",
        "precautions",
        mode="before",
    )
    @classmethod
    def validate_strict_boolean(cls, v: Any, info: Any) -> bool:
        fname = info.field_name
        if v is None:
            raise ValueError(f"Value for '{fname}' cannot be null")
        if not isinstance(v, bool):
            raise ValueError(f"Value for '{fname}' must be a boolean (True or False)")
        return v

    @model_validator(mode="after")
    def validate_not_empty(self) -> "ChecklistUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one checklist item must be provided")
        return self


# ==============================================================================
# Experiment CRUD Request Schemas
# ==============================================================================


class ExperimentCreateRequest(BaseModel):
    """Payload for creating a new laboratory experiment workspace."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Title of the experiment",
        examples=["Determination of Planck's Constant"],
    )
    subject: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Academic subject or lab title",
        examples=["Physics"],
    )
    experiment_number: Optional[str] = Field(
        default=None,
        max_length=50,
        validation_alias=AliasChoices("experiment_number", "experimentNumber"),
        description="Optional laboratory experiment number or code",
        examples=["EXP-01"],
    )
    course_semester: Optional[str] = Field(
        default=None,
        max_length=50,
        validation_alias=AliasChoices("course_semester", "courseSemester"),
        description="Optional course code and semester",
        examples=["B.Tech Physics - Semester 1"],
    )
    creation_method: CreationMethodEnum = Field(
        default=CreationMethodEnum.MANUAL,
        validation_alias=AliasChoices("creation_method", "method"),
        description="Creation method: 'manual' or 'upload'",
    )
    has_manual_file: bool = Field(
        default=False,
        validation_alias=AliasChoices("has_manual_file", "hasManualFile"),
        description="Flag indicating whether an uploaded file is associated",
    )
    file_name: Optional[str] = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("file_name", "fileName"),
        description="Original manual filename if created via upload",
    )
    status: ExperimentStatusEnum = Field(
        default=ExperimentStatusEnum.READY,
        description="Initial experiment lifecycle status",
    )

    # Content sections: overview and 6 standard lab manual sections
    description: Optional[str] = Field(
        default=None,
        description="General experiment overview or introduction",
    )
    objective: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("objective", "aim"),
        description="Core experimental aim or objective",
    )
    theory: Optional[str] = Field(
        default=None,
        description="Theoretical background, governing equations, and physics/circuit principles",
    )
    apparatus: Optional[str] = Field(
        default=None,
        description="List of required equipment, components, ratings, and tools",
    )
    procedure: Optional[str] = Field(
        default=None,
        description="Step-by-step experimental steps and precautions",
    )
    observations: Optional[str] = Field(
        default=None,
        description="Observation tables, measurement values, and readings",
    )
    calculations: Optional[str] = Field(
        default=None,
        description="Calculations, formulas, error analysis, and derivations",
    )
    precautions: Optional[str] = Field(
        default=None,
        description="Safety precautions, handling limits, and hazard warnings",
    )

    @field_validator("title", "subject", mode="before")
    @classmethod
    def validate_required_text(cls, v: Any, info: Any) -> str:
        fname = info.field_name.replace("_", " ").capitalize()
        if not isinstance(v, str):
            raise ValueError(f"{fname} must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError(f"{fname} cannot be blank")
        return stripped

    @field_validator(
        "experiment_number",
        "course_semester",
        "file_name",
        "description",
        "objective",
        "theory",
        "apparatus",
        "procedure",
        "observations",
        "calculations",
        "precautions",
        mode="before",
    )
    @classmethod
    def validate_optional_text(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v


class ExperimentUpdateRequest(BaseModel):
    """Payload for updating an existing experiment workspace.

    Supports partial updates. Unset fields remain unchanged.
    Protected fields (e.g. id, user_id, timestamps) are strictly forbidden.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated experiment title",
    )
    subject: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated academic subject or course",
    )
    experiment_number: Optional[str] = Field(
        default=None,
        max_length=50,
        validation_alias=AliasChoices("experiment_number", "experimentNumber"),
        description="Updated experiment number",
    )
    course_semester: Optional[str] = Field(
        default=None,
        max_length=50,
        validation_alias=AliasChoices("course_semester", "courseSemester"),
        description="Updated semester or course affiliation",
    )
    creation_method: Optional[CreationMethodEnum] = Field(
        default=None,
        validation_alias=AliasChoices("creation_method", "method"),
        description="Updated creation method",
    )
    has_manual_file: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("has_manual_file", "hasManualFile"),
        description="Updated manual file attachment flag",
    )
    file_name: Optional[str] = Field(
        default=None,
        max_length=255,
        validation_alias=AliasChoices("file_name", "fileName"),
        description="Updated file name",
    )
    status: Optional[ExperimentStatusEnum] = Field(
        default=None,
        description="Updated lifecycle status",
    )

    # Content sections
    description: Optional[str] = Field(default=None)
    objective: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("objective", "aim"),
    )
    theory: Optional[str] = Field(default=None)
    apparatus: Optional[str] = Field(default=None)
    procedure: Optional[str] = Field(default=None)
    observations: Optional[str] = Field(default=None)
    calculations: Optional[str] = Field(default=None)
    precautions: Optional[str] = Field(default=None)

    @field_validator("title", "subject", mode="before")
    @classmethod
    def validate_non_nullable_text(cls, v: Any, info: Any) -> Optional[str]:
        fname = info.field_name.replace("_", " ").capitalize()
        if v is None:
            raise ValueError(f"{fname} cannot be null")
        if not isinstance(v, str):
            raise ValueError(f"{fname} must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError(f"{fname} cannot be blank")
        return stripped

    @field_validator("creation_method", "status", "has_manual_file", mode="before")
    @classmethod
    def validate_non_nullable_fields(cls, v: Any, info: Any) -> Any:
        fname = info.field_name.replace("_", " ").capitalize()
        if v is None:
            raise ValueError(f"{fname} cannot be null")
        return v

    @field_validator(
        "experiment_number",
        "course_semester",
        "file_name",
        "description",
        "objective",
        "theory",
        "apparatus",
        "procedure",
        "observations",
        "calculations",
        "precautions",
        mode="before",
    )
    @classmethod
    def normalize_optional_update_text(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v

    @model_validator(mode="after")
    def check_at_least_one_field_supplied(self) -> "ExperimentUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one experiment field must be provided for update")
        return self


# ==============================================================================
# Experiment Response Schemas
# ==============================================================================


class ExperimentListItemResponse(BaseModel):
    """Lightweight summary schema for experiment cards, grids, and table listings."""

    id: uuid.UUID
    title: str
    subject: str
    experiment_number: Optional[str] = Field(
        default=None,
        serialization_alias="experimentNumber",
    )
    course_semester: Optional[str] = Field(
        default=None,
        serialization_alias="courseSemester",
    )
    creation_method: str = Field(
        default="manual",
        serialization_alias="creationMethod",
    )
    has_manual_file: bool = Field(
        default=False,
        serialization_alias="hasManualFile",
    )
    file_name: Optional[str] = Field(
        default=None,
        serialization_alias="fileName",
    )
    status: str
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ExperimentResponse(BaseModel):
    """Comprehensive experiment detail representation for the workspace."""

    id: uuid.UUID
    title: str
    subject: str
    experiment_number: Optional[str] = Field(
        default=None,
        serialization_alias="experimentNumber",
    )
    course_semester: Optional[str] = Field(
        default=None,
        serialization_alias="courseSemester",
    )
    creation_method: str = Field(
        default="manual",
        serialization_alias="creationMethod",
    )
    has_manual_file: bool = Field(
        default=False,
        serialization_alias="hasManualFile",
    )
    file_name: Optional[str] = Field(
        default=None,
        serialization_alias="fileName",
    )
    status: str
    description: Optional[str] = None
    objective: Optional[str] = None
    theory: Optional[str] = None
    apparatus: Optional[str] = None
    procedure: Optional[str] = None
    observations: Optional[str] = None
    calculations: Optional[str] = None
    precautions: Optional[str] = None

    # Relational preparation checklist DTO
    checklist: Optional[PreparationChecklistResponse] = None

    # Flat dictionary representation matching frontend ExperimentRecord.preparationChecklist
    preparation_checklist: Optional[dict[str, bool]] = Field(
        default=None,
        serialization_alias="preparationChecklist",
    )

    # Viva question counter matching frontend ExperimentRecord.vivaQuestionsCount
    viva_questions_count: int = Field(
        default=0,
        serialization_alias="vivaQuestionsCount",
    )

    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_preparation_checklist(self) -> "ExperimentResponse":
        """Sync flat preparation_checklist dictionary from nested checklist if present."""
        if self.checklist and self.checklist.items and self.preparation_checklist is None:
            self.preparation_checklist = self.checklist.items
        return self


class ExperimentListResponse(BaseModel):
    """Paginated collection response for experiment listings."""

    items: list[ExperimentListItemResponse] = Field(
        default_factory=list,
        description="Collection of experiment summary records",
    )
    total: int = Field(
        ge=0,
        description="Total number of experiments matching query criteria",
    )
    page: int = Field(
        ge=1,
        default=1,
        description="Current page index (1-indexed)",
    )
    page_size: int = Field(
        ge=1,
        default=20,
        serialization_alias="pageSize",
        description="Maximum items per page",
    )
    total_pages: int = Field(
        ge=0,
        default=1,
        serialization_alias="totalPages",
        description="Total page count",
    )

    model_config = ConfigDict(populate_by_name=True)
