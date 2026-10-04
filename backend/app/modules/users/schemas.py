"""User Profile and Settings Pydantic Schemas.

Defines request and response data transfer objects for retrieving and updating
student profiles and study preferences in the PracPrep platform.
"""

from datetime import datetime, timezone
from decimal import Decimal
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


# Canonical study preferences values
CANONICAL_DIFFICULTIES = {"beginner", "intermediate", "advanced", "mixed"}
CANONICAL_QUESTION_COUNTS = {5, 10, 15}
CANONICAL_FOCUS_AREAS = {
    "theory",
    "procedure",
    "apparatus",
    "observations",
    "precautions",
    "mixed",
}


class UserProfileResponse(BaseModel):
    """Safe user profile response excluding sensitive security fields."""

    id: uuid.UUID
    email: str
    full_name: str
    university: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdateRequest(BaseModel):
    """Payload for updating user profile fields.

    Supports partial updates with strict field allowlist and validation.
    Protected fields (e.g. email, password, is_active, id) are forbidden.
    """

    model_config = ConfigDict(extra="forbid")

    full_name: Optional[str] = Field(
        default=None,
        description="Updated full name of student",
        examples=["Alex Johnson"],
    )
    university: Optional[str] = Field(
        default=None,
        description="Updated university or institution affiliation",
        examples=["State University"],
    )

    @field_validator("full_name", mode="before")
    @classmethod
    def validate_full_name(cls, v: Any) -> str:
        """Strip whitespace and enforce minimum length on full_name."""
        if v is None:
            raise ValueError("Full name cannot be null")
        if not isinstance(v, str):
            raise ValueError("Full name must be a string")
        stripped = v.strip()
        if len(stripped) < 2:
            raise ValueError("Full name must contain at least 2 non-whitespace characters")
        return stripped

    @field_validator("university", mode="before")
    @classmethod
    def validate_university(cls, v: Any) -> str:
        """Strip whitespace and reject blank or null university."""
        if v is None:
            raise ValueError("University cannot be null")
        if not isinstance(v, str):
            raise ValueError("University must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("University cannot be blank")
        return stripped

    @model_validator(mode="after")
    def check_at_least_one_field_supplied(self) -> "UserProfileUpdateRequest":
        """Ensure the payload contains at least one field to update."""
        if not self.model_fields_set:
            raise ValueError("At least one profile field must be provided for update")
        return self

    def __repr__(self) -> str:
        return f"<UserProfileUpdateRequest fields={list(self.model_fields_set)}>"


class UserSettingsResponse(BaseModel):
    """User study preferences response matching frontend camelCase contract."""

    id: uuid.UUID
    user_id: uuid.UUID = Field(..., serialization_alias="userId")
    default_difficulty: str = Field(..., serialization_alias="defaultDifficulty")
    default_question_count: int = Field(..., serialization_alias="defaultQuestionCount")
    preferred_focus: str = Field(..., serialization_alias="preferredFocus")
    created_at: datetime = Field(..., serialization_alias="createdAt")
    updated_at: datetime = Field(..., serialization_alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("default_difficulty", mode="before")
    @classmethod
    def normalize_difficulty(cls, v: Any) -> str:
        """Normalize legacy values such as 'medium' to canonical 'intermediate'."""
        if isinstance(v, str):
            val = v.strip().lower()
            if val == "medium":
                return "intermediate"
            return val
        return v

    @field_validator("preferred_focus", mode="before")
    @classmethod
    def normalize_preferred_focus(cls, v: Any) -> str:
        """Normalize legacy values such as 'all' to canonical 'mixed'."""
        if isinstance(v, str):
            val = v.strip().lower()
            if val == "all":
                return "mixed"
            return val
        return v


class UserSettingsUpdateRequest(BaseModel):
    """Payload for updating user study preferences.

    Supports partial updates with strict field allowlist and validation.
    Forbidden/unknown fields, ID fields, timestamps, and display preferences are rejected.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    default_difficulty: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("defaultDifficulty", "default_difficulty"),
        description="Default viva difficulty level ('beginner', 'intermediate', 'advanced', 'mixed')",
    )
    default_question_count: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("defaultQuestionCount", "default_question_count"),
        description="Default number of questions per session (5, 10, or 15)",
    )
    preferred_focus: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("preferredFocus", "preferred_focus"),
        description="Preferred viva focus area ('theory', 'procedure', 'apparatus', 'observations', 'precautions', 'mixed')",
    )

    @field_validator("default_difficulty", mode="before")
    @classmethod
    def validate_difficulty(cls, v: Any) -> Optional[str]:
        """Validate and normalize difficulty level."""
        if v is None:
            raise ValueError("defaultDifficulty cannot be null")
        if not isinstance(v, str):
            raise ValueError("defaultDifficulty must be a string")
        val = v.strip().lower()
        if val == "medium":
            val = "intermediate"
        if val not in CANONICAL_DIFFICULTIES:
            raise ValueError(
                f"Invalid difficulty '{v}'. Must be one of: {', '.join(sorted(CANONICAL_DIFFICULTIES))}"
            )
        return val

    @field_validator("default_question_count", mode="before")
    @classmethod
    def validate_question_count(cls, v: Any) -> Optional[int]:
        """Validate question count against canonical allowed values."""
        if v is None:
            raise ValueError("defaultQuestionCount cannot be null")
        if isinstance(v, bool):
            raise ValueError("defaultQuestionCount cannot be a boolean")
        if isinstance(v, int):
            count = v
        elif isinstance(v, str) and v.isdigit():
            count = int(v)
        else:
            raise ValueError("defaultQuestionCount must be an integer (5, 10, or 15)")
        if count not in CANONICAL_QUESTION_COUNTS:
            raise ValueError(
                f"Invalid question count '{v}'. Must be one of: {', '.join(str(c) for c in sorted(CANONICAL_QUESTION_COUNTS))}"
            )
        return count

    @field_validator("preferred_focus", mode="before")
    @classmethod
    def validate_preferred_focus(cls, v: Any) -> Optional[str]:
        """Validate and normalize topic focus area."""
        if v is None:
            raise ValueError("preferredFocus cannot be null")
        if not isinstance(v, str):
            raise ValueError("preferredFocus must be a string")
        val = v.strip().lower()
        if val == "all":
            val = "mixed"
        if val not in CANONICAL_FOCUS_AREAS:
            raise ValueError(
                f"Invalid preferred focus '{v}'. Must be one of: {', '.join(sorted(CANONICAL_FOCUS_AREAS))}"
            )
        return val

    @model_validator(mode="after")
    def check_at_least_one_field_supplied(self) -> "UserSettingsUpdateRequest":
        """Ensure the payload contains at least one study preference field to update."""
        if not self.model_fields_set:
            raise ValueError("At least one study preference field must be provided for update")
        return self

    def __repr__(self) -> str:
        return f"<UserSettingsUpdateRequest fields={list(self.model_fields_set)}>"


# ==============================================================================
# Full Account Data Export Schemas (TASK-13.1)
# ==============================================================================


class UserExportProfile(BaseModel):
    """User account profile for data export (strictly excludes password_hash and secrets)."""

    id: uuid.UUID
    email: str
    full_name: str
    fullName: Optional[str] = None
    university: Optional[str] = None
    is_active: bool
    isActive: Optional[bool] = None
    auth_provider: Optional[str] = "local"
    authProvider: Optional[str] = None
    created_at: datetime
    createdAt: Optional[datetime] = None
    updated_at: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "UserExportProfile":
        if self.auth_provider is None:
            self.auth_provider = "local"
        if self.fullName is None:
            self.fullName = self.full_name
        if self.isActive is None:
            self.isActive = self.is_active
        if self.authProvider is None:
            self.authProvider = self.auth_provider
        if self.createdAt is None:
            self.createdAt = self.created_at
        if self.updatedAt is None:
            self.updatedAt = self.updated_at
        return self


class UserSettingsExport(BaseModel):
    """User study preferences entity representation for data export."""

    id: uuid.UUID
    user_id: uuid.UUID
    userId: Optional[uuid.UUID] = None
    default_difficulty: str
    defaultDifficulty: Optional[str] = None
    default_question_count: int
    defaultQuestionCount: Optional[int] = None
    preferred_focus: str
    preferredFocus: Optional[str] = None
    created_at: datetime
    createdAt: Optional[datetime] = None
    updated_at: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("default_difficulty", mode="before")
    @classmethod
    def normalize_difficulty(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower()
            if val == "medium":
                return "intermediate"
            return val
        return v

    @field_validator("preferred_focus", mode="before")
    @classmethod
    def normalize_preferred_focus(cls, v: Any) -> str:
        if isinstance(v, str):
            val = v.strip().lower()
            if val == "all":
                return "mixed"
            return val
        return v

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "UserSettingsExport":
        if self.userId is None:
            self.userId = self.user_id
        if self.defaultDifficulty is None:
            self.defaultDifficulty = self.default_difficulty
        if self.defaultQuestionCount is None:
            self.defaultQuestionCount = self.default_question_count
        if self.preferredFocus is None:
            self.preferredFocus = self.preferred_focus
        if self.createdAt is None:
            self.createdAt = self.created_at
        if self.updatedAt is None:
            self.updatedAt = self.updated_at
        return self


class PreparationChecklistExportItem(BaseModel):
    """Preparation checklist state linked to an experiment."""

    id: uuid.UUID
    experiment_id: uuid.UUID
    experimentId: Optional[uuid.UUID] = None
    items: dict[str, bool] = Field(default_factory=dict)
    created_at: datetime
    createdAt: Optional[datetime] = None
    updated_at: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "PreparationChecklistExportItem":
        if self.experimentId is None:
            self.experimentId = self.experiment_id
        if self.createdAt is None:
            self.createdAt = self.created_at
        if self.updatedAt is None:
            self.updatedAt = self.updated_at
        return self


class ExperimentExportItem(BaseModel):
    """Laboratory experiment record for data export."""

    id: uuid.UUID
    user_id: uuid.UUID
    userId: Optional[uuid.UUID] = None
    title: str
    subject: str
    experiment_number: Optional[str] = None
    experimentNumber: Optional[str] = None
    course_semester: Optional[str] = None
    courseSemester: Optional[str] = None
    creation_method: str = "manual"
    creationMethod: Optional[str] = None
    has_manual_file: bool = False
    hasManualFile: Optional[bool] = None
    file_name: Optional[str] = None
    fileName: Optional[str] = None
    status: str = "ready"
    description: Optional[str] = None
    objective: Optional[str] = None
    theory: Optional[str] = None
    apparatus: Optional[str] = None
    procedure: Optional[str] = None
    observations: Optional[str] = None
    calculations: Optional[str] = None
    precautions: Optional[str] = None
    checklist: Optional[PreparationChecklistExportItem] = None
    preparation_checklist: Optional[dict[str, bool]] = None
    preparationChecklist: Optional[dict[str, bool]] = None
    created_at: datetime
    createdAt: Optional[datetime] = None
    updated_at: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "ExperimentExportItem":
        if self.userId is None:
            self.userId = self.user_id
        if self.experimentNumber is None:
            self.experimentNumber = self.experiment_number
        if self.courseSemester is None:
            self.courseSemester = self.course_semester
        if self.creationMethod is None:
            self.creationMethod = self.creation_method
        if self.hasManualFile is None:
            self.hasManualFile = self.has_manual_file
        if self.fileName is None:
            self.fileName = self.file_name
        if self.createdAt is None:
            self.createdAt = self.created_at
        if self.updatedAt is None:
            self.updatedAt = self.updated_at
        if self.checklist and self.checklist.items:
            if self.preparation_checklist is None:
                self.preparation_checklist = self.checklist.items
            if self.preparationChecklist is None:
                self.preparationChecklist = self.checklist.items
        return self


class VivaAnswerExportItem(BaseModel):
    """Question and response record within a viva session for data export."""

    id: uuid.UUID
    session_id: uuid.UUID
    sessionId: Optional[uuid.UUID] = None
    question_id: Optional[str] = None
    questionId: Optional[str] = None
    question_number: int = 1
    questionNumber: Optional[int] = None
    topic: str
    difficulty: str
    question_text: str
    questionText: Optional[str] = None
    student_answer: str
    studentAnswer: Optional[str] = None
    score: Optional[int] = None
    verdict: Optional[str] = None
    feedback: Optional[str] = None
    expected_answer: Optional[str] = None
    expectedAnswer: Optional[str] = None
    what_you_got_right: Optional[str] = None
    whatYouGotRight: Optional[str] = None
    what_was_missing: Optional[str] = None
    whatWasMissing: Optional[str] = None
    suggested_improvement: Optional[str] = None
    suggestedImprovement: Optional[str] = None
    key_points_covered: list[str] = Field(default_factory=list)
    keyPointsCovered: Optional[list[str]] = None
    key_points_missed: list[str] = Field(default_factory=list)
    keyPointsMissed: Optional[list[str]] = None
    evaluation_data: dict[str, Any] = Field(default_factory=dict)
    evaluationData: Optional[dict[str, Any]] = None
    time_spent_seconds: Optional[int] = None
    timeSpentSeconds: Optional[int] = None
    created_at: datetime
    createdAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "VivaAnswerExportItem":
        if self.sessionId is None:
            self.sessionId = self.session_id
        if self.questionId is None:
            self.questionId = self.question_id
        if self.questionNumber is None:
            self.questionNumber = self.question_number
        if self.questionText is None:
            self.questionText = self.question_text
        if self.studentAnswer is None:
            self.studentAnswer = self.student_answer
        if self.expectedAnswer is None:
            self.expectedAnswer = self.expected_answer
        if self.whatYouGotRight is None:
            self.whatYouGotRight = self.what_you_got_right
        if self.whatWasMissing is None:
            self.whatWasMissing = self.what_was_missing
        if self.suggestedImprovement is None:
            self.suggestedImprovement = self.suggested_improvement
        if self.keyPointsCovered is None:
            self.keyPointsCovered = self.key_points_covered
        if self.keyPointsMissed is None:
            self.keyPointsMissed = self.key_points_missed
        if self.evaluationData is None:
            self.evaluationData = self.evaluation_data
        if self.timeSpentSeconds is None:
            self.timeSpentSeconds = self.time_spent_seconds
        if self.createdAt is None:
            self.createdAt = self.created_at
        return self


class VivaSessionExportItem(BaseModel):
    """Complete viva examination practice session representation for data export."""

    id: uuid.UUID
    user_id: uuid.UUID
    userId: Optional[uuid.UUID] = None
    experiment_id: uuid.UUID
    experimentId: Optional[uuid.UUID] = None
    difficulty: str
    question_count: int
    questionCount: Optional[int] = None
    topic_focus: str
    topicFocus: Optional[str] = None
    provider_mode: str = "demonstration"
    providerMode: Optional[str] = None
    is_completed: bool = False
    isCompleted: Optional[bool] = None
    started_at: datetime
    startedAt: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completedAt: Optional[datetime] = None
    average_score: Optional[float] = None
    averageScore: Optional[float] = None
    total_questions: int = 5
    totalQuestions: Optional[int] = None
    questions_answered: int = 0
    questionsAnswered: Optional[int] = None
    correct_count: int = 0
    correctCount: Optional[int] = None
    partially_correct_count: int = 0
    partiallyCorrectCount: Optional[int] = None
    incorrect_count: int = 0
    incorrectCount: Optional[int] = None
    topic_analysis: dict[str, Any] = Field(default_factory=dict)
    topicAnalysis: Optional[dict[str, Any]] = None
    weak_topics: list[str] = Field(default_factory=list)
    weakTopics: Optional[list[str]] = None
    strong_topics: list[str] = Field(default_factory=list)
    strongTopics: Optional[list[str]] = None
    revision_recommendations: list[dict[str, Any]] = Field(default_factory=list)
    revisionRecommendations: Optional[list[dict[str, Any]]] = None
    answers: list[VivaAnswerExportItem] = Field(default_factory=list)
    created_at: datetime
    createdAt: Optional[datetime] = None
    updated_at: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("average_score", mode="before")
    @classmethod
    def convert_decimal_to_float(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (Decimal, int, float, str)):
            return round(float(v), 2)
        return v

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "VivaSessionExportItem":
        if self.userId is None:
            self.userId = self.user_id
        if self.experimentId is None:
            self.experimentId = self.experiment_id
        if self.questionCount is None:
            self.questionCount = self.question_count
        if self.topicFocus is None:
            self.topicFocus = self.topic_focus
        if self.providerMode is None:
            self.providerMode = self.provider_mode
        if self.isCompleted is None:
            self.isCompleted = self.is_completed
        if self.startedAt is None:
            self.startedAt = self.started_at
        if self.completedAt is None:
            self.completedAt = self.completed_at
        if self.averageScore is None:
            self.averageScore = self.average_score
        if self.totalQuestions is None:
            self.totalQuestions = self.total_questions
        if self.questionsAnswered is None:
            self.questionsAnswered = self.questions_answered
        if self.correctCount is None:
            self.correctCount = self.correct_count
        if self.partiallyCorrectCount is None:
            self.partiallyCorrectCount = self.partially_correct_count
        if self.incorrectCount is None:
            self.incorrectCount = self.incorrect_count
        if self.topicAnalysis is None:
            self.topicAnalysis = self.topic_analysis
        if self.weakTopics is None:
            self.weakTopics = self.weak_topics
        if self.strongTopics is None:
            self.strongTopics = self.strong_topics
        if self.revisionRecommendations is None:
            self.revisionRecommendations = self.revision_recommendations
        if self.createdAt is None:
            self.createdAt = self.created_at
        if self.updatedAt is None:
            self.updatedAt = self.updated_at
        return self


class DocumentExportItem(BaseModel):
    """Uploaded manual document record for data export (strictly excludes storage_path)."""

    id: uuid.UUID
    user_id: uuid.UUID
    userId: Optional[uuid.UUID] = None
    experiment_id: Optional[uuid.UUID] = None
    experimentId: Optional[uuid.UUID] = None
    file_name: str
    fileName: Optional[str] = None
    file_size_bytes: int
    fileSizeBytes: Optional[int] = None
    mime_type: str
    mimeType: Optional[str] = None
    status: str
    extracted_text: Optional[str] = None
    extractedText: Optional[str] = None
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    extractedData: Optional[dict[str, Any]] = None
    error_message: Optional[str] = None
    errorMessage: Optional[str] = None
    created_at: datetime
    createdAt: Optional[datetime] = None
    updated_at: datetime
    updatedAt: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "DocumentExportItem":
        if self.userId is None:
            self.userId = self.user_id
        if self.experimentId is None:
            self.experimentId = self.experiment_id
        if self.fileName is None:
            self.fileName = self.file_name
        if self.fileSizeBytes is None:
            self.fileSizeBytes = self.file_size_bytes
        if self.mimeType is None:
            self.mimeType = self.mime_type
        if self.extractedText is None:
            self.extractedText = self.extracted_text
        if self.extractedData is None:
            self.extractedData = self.extracted_data
        if self.errorMessage is None:
            self.errorMessage = self.error_message
        if self.createdAt is None:
            self.createdAt = self.created_at
        if self.updatedAt is None:
            self.updatedAt = self.updated_at
        return self


class ExportSummaryDTO(BaseModel):
    """Summary record counts for the data export package."""

    experiments_count: int = 0
    experimentsCount: Optional[int] = None
    viva_sessions_count: int = 0
    vivaSessionsCount: Optional[int] = None
    documents_count: int = 0
    documentsCount: Optional[int] = None

    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="after")
    def populate_camel_aliases(self) -> "ExportSummaryDTO":
        if self.experimentsCount is None:
            self.experimentsCount = self.experiments_count
        if self.vivaSessionsCount is None:
            self.vivaSessionsCount = self.viva_sessions_count
        if self.documentsCount is None:
            self.documentsCount = self.documents_count
        return self


class UserDataExportResponse(BaseModel):
    """Complete user account data export container."""

    export_version: str = "1.0"
    exportVersion: Optional[str] = None
    export_timestamp: int = Field(
        default_factory=lambda: int(datetime.now(timezone.utc).timestamp() * 1000)
    )
    exportTimestamp: Optional[int] = None
    exported_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    exportedAt: Optional[datetime] = None

    user: UserExportProfile
    profile: Optional[UserExportProfile] = None
    settings: Optional[UserSettingsExport] = None

    experiments: list[ExperimentExportItem] = Field(default_factory=list)
    viva_sessions: list[VivaSessionExportItem] = Field(default_factory=list)
    vivaSessions: Optional[list[VivaSessionExportItem]] = None
    documents: list[DocumentExportItem] = Field(default_factory=list)

    experiments_count: int = 0
    experimentsCount: Optional[int] = None
    viva_sessions_count: int = 0
    vivaSessionsCount: Optional[int] = None
    documents_count: int = 0
    documentsCount: Optional[int] = None

    summary: ExportSummaryDTO = Field(default_factory=ExportSummaryDTO)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def populate_aliases_and_counts(self) -> "UserDataExportResponse":
        if self.exportVersion is None:
            self.exportVersion = self.export_version
        if self.exportTimestamp is None:
            self.exportTimestamp = self.export_timestamp
        if self.exportedAt is None:
            self.exportedAt = self.exported_at
        if self.profile is None:
            self.profile = self.user
        if self.vivaSessions is None:
            self.vivaSessions = self.viva_sessions

        exp_count = len(self.experiments)
        viva_count = len(self.viva_sessions)
        doc_count = len(self.documents)

        self.experiments_count = exp_count
        self.experimentsCount = exp_count
        self.viva_sessions_count = viva_count
        self.vivaSessionsCount = viva_count
        self.documents_count = doc_count
        self.documentsCount = doc_count

        self.summary.experiments_count = exp_count
        self.summary.experimentsCount = exp_count
        self.summary.viva_sessions_count = viva_count
        self.summary.vivaSessionsCount = viva_count
        self.summary.documents_count = doc_count
        self.summary.documentsCount = doc_count

        return self


class AccountDeletionResponse(BaseModel):
    """Documented response for successful account deletion."""

    message: str = Field(
        default="Account and all associated data deleted successfully.",
        description="Human-readable success confirmation message",
    )
    deleted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when account deletion was executed",
    )
    user_id: uuid.UUID = Field(
        description="UUID of the deleted user account",
    )

    model_config = ConfigDict(from_attributes=True)


class UserDataPurgeResponse(BaseModel):
    """Documented response for purging all user experiments and viva sessions."""

    message: str = Field(
        default="All user data cleared successfully.",
        description="Human-readable success confirmation message",
    )
    purged_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when data purge was executed",
    )
    experiments_deleted: int = Field(
        default=0,
        description="Number of experiments deleted",
    )
    viva_sessions_deleted: int = Field(
        default=0,
        description="Number of viva sessions deleted",
    )
    documents_deleted: int = Field(
        default=0,
        description="Number of documents deleted",
    )

    model_config = ConfigDict(from_attributes=True)


# ==============================================================================
# Guest Data Batch Migration Schemas (TASK-13.3)
# ==============================================================================


def _parse_flexible_datetime(v: Any) -> Optional[datetime]:
    """Helper to convert epoch ms/sec, numeric strings, or ISO strings to datetime."""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, (int, float)):
        ts = v / 1000.0 if v > 1e11 else float(v)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    if isinstance(v, str):
        stripped = v.strip()
        if not stripped:
            return None
        try:
            if stripped.isdigit():
                num = float(stripped)
                ts = num / 1000.0 if num > 1e11 else num
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            # Try float string (e.g. "1728000000000.0")
            try:
                num = float(stripped)
                ts = num / 1000.0 if num > 1e11 else num
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except ValueError:
                pass
            return datetime.fromisoformat(stripped)
        except Exception:
            return None
    return None


class GuestExperimentMigrationItem(BaseModel):
    """Guest experiment payload for batch account migration."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    client_id: str = Field(
        ...,
        validation_alias=AliasChoices("clientId", "client_id", "id"),
        description="Client-side identifier used for relational mapping",
    )
    title: str = Field(..., min_length=1, max_length=255)
    subject: str = Field(..., min_length=1, max_length=255)
    experiment_number: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("experimentNumber", "experiment_number"),
        max_length=50,
    )
    course_semester: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("courseSemester", "course_semester"),
        max_length=50,
    )
    creation_method: str = Field(
        default="manual",
        validation_alias=AliasChoices("creationMethod", "creation_method", "method"),
        max_length=50,
    )
    status: str = Field(default="ready", max_length=50)
    description: Optional[str] = None
    objective: Optional[str] = None
    theory: Optional[str] = None
    apparatus: Optional[str] = None
    procedure: Optional[str] = None
    observations: Optional[str] = None
    calculations: Optional[str] = None
    precautions: Optional[str] = None
    checklist: Optional[dict[str, bool]] = Field(
        default=None,
        validation_alias=AliasChoices("preparationChecklist", "preparation_checklist", "checklist"),
    )
    created_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("createdAt", "created_at", "createdAtTimestamp"),
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("updatedAt", "updated_at", "updatedAtTimestamp"),
    )

    @field_validator("created_at", "updated_at", mode="before")
    @classmethod
    def validate_datetime(cls, v: Any) -> Optional[datetime]:
        return _parse_flexible_datetime(v)


class GuestVivaAnswerMigrationItem(BaseModel):
    """Guest viva answer payload for batch account migration."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    question_id: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("questionId", "question_id"),
        max_length=100,
    )
    question_number: int = Field(
        default=1,
        validation_alias=AliasChoices("questionNumber", "question_number"),
        ge=1,
        le=50,
    )
    topic: str = Field(default="theory", max_length=50)
    difficulty: str = Field(default="intermediate", max_length=50)
    question_text: str = Field(
        ...,
        validation_alias=AliasChoices("questionText", "question_text", "question"),
        min_length=1,
    )
    student_answer: str = Field(
        ...,
        validation_alias=AliasChoices("studentAnswer", "student_answer"),
    )
    score: Optional[int] = Field(default=None, ge=0, le=10)
    verdict: Optional[str] = Field(default=None, max_length=50)
    feedback: Optional[str] = None
    expected_answer: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("expectedAnswer", "expected_answer"),
    )
    what_you_got_right: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("whatYouGotRight", "what_you_got_right"),
    )
    what_was_missing: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("whatWasMissing", "what_was_missing"),
    )
    suggested_improvement: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "suggestedImprovement", "suggested_improvement", "improvementTip"
        ),
    )
    key_points_covered: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("keyPointsCovered", "key_points_covered"),
    )
    key_points_missed: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("keyPointsMissed", "key_points_missed"),
    )
    evaluation_data: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("evaluationData", "evaluation_data"),
    )
    time_spent_seconds: Optional[int] = Field(
        default=None,
        validation_alias=AliasChoices("timeSpentSeconds", "time_spent_seconds"),
    )
    created_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("createdAt", "created_at", "timestamp"),
    )

    @model_validator(mode="before")
    @classmethod
    def unpack_nested_evaluation(cls, data: Any) -> Any:
        if isinstance(data, dict):
            eval_obj = data.get("evaluation")
            if isinstance(eval_obj, dict):
                if not data.get("verdict") and eval_obj.get("verdict"):
                    data["verdict"] = eval_obj.get("verdict")
                if data.get("score") is None and eval_obj.get("score") is not None:
                    data["score"] = eval_obj.get("score")
                if (
                    not data.get("what_you_got_right")
                    and not data.get("whatYouGotRight")
                    and eval_obj.get("whatYouGotRight")
                ):
                    data["what_you_got_right"] = eval_obj.get("whatYouGotRight")
                if (
                    not data.get("what_was_missing")
                    and not data.get("whatWasMissing")
                    and eval_obj.get("whatWasMissing")
                ):
                    data["what_was_missing"] = eval_obj.get("whatWasMissing")
                if (
                    not data.get("expected_answer")
                    and not data.get("expectedAnswer")
                    and eval_obj.get("expectedAnswer")
                ):
                    data["expected_answer"] = eval_obj.get("expectedAnswer")
                if (
                    not data.get("suggested_improvement")
                    and not data.get("suggestedImprovement")
                    and eval_obj.get("improvementTip")
                ):
                    data["suggested_improvement"] = eval_obj.get("improvementTip")
                if (
                    not data.get("key_points_covered")
                    and not data.get("keyPointsCovered")
                    and eval_obj.get("keyPointsCovered")
                ):
                    data["key_points_covered"] = eval_obj.get("keyPointsCovered")
                if (
                    not data.get("key_points_missed")
                    and not data.get("keyPointsMissed")
                    and eval_obj.get("keyPointsMissed")
                ):
                    data["key_points_missed"] = eval_obj.get("keyPointsMissed")
                if not data.get("evaluation_data") and not data.get("evaluationData"):
                    data["evaluation_data"] = eval_obj
        return data

    @field_validator("created_at", mode="before")
    @classmethod
    def validate_datetime(cls, v: Any) -> Optional[datetime]:
        return _parse_flexible_datetime(v)


class GuestVivaSessionMigrationItem(BaseModel):
    """Guest viva session payload for batch account migration."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    client_id: str = Field(
        ...,
        validation_alias=AliasChoices("clientId", "client_id", "id"),
        description="Client-side identifier for session",
    )
    client_experiment_id: str = Field(
        ...,
        validation_alias=AliasChoices("clientExperimentId", "client_experiment_id", "experimentId"),
        description="Client-side identifier or UUID of referenced experiment",
    )
    difficulty: str = Field(default="intermediate", max_length=50)
    question_count: int = Field(
        default=5,
        validation_alias=AliasChoices("questionCount", "question_count"),
        ge=1,
        le=50,
    )
    topic_focus: str = Field(
        default="mixed",
        validation_alias=AliasChoices("topicFocus", "topic_focus", "focus"),
        max_length=50,
    )
    provider_mode: str = Field(
        default="demonstration",
        validation_alias=AliasChoices("providerMode", "provider_mode"),
        max_length=50,
    )
    is_completed: bool = Field(
        default=False,
        validation_alias=AliasChoices("isCompleted", "is_completed"),
    )
    started_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("startedAt", "started_at"),
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        validation_alias=AliasChoices("completedAt", "completed_at"),
    )
    average_score: Optional[Decimal] = Field(
        default=None,
        validation_alias=AliasChoices("averageScore", "average_score"),
    )
    total_questions: int = Field(
        default=5,
        validation_alias=AliasChoices("totalQuestions", "total_questions"),
    )
    questions_answered: int = Field(
        default=0,
        validation_alias=AliasChoices("questionsAnswered", "questions_answered"),
    )
    correct_count: int = Field(
        default=0,
        validation_alias=AliasChoices("correctCount", "correct_count"),
    )
    partially_correct_count: int = Field(
        default=0,
        validation_alias=AliasChoices("partiallyCorrectCount", "partially_correct_count"),
    )
    incorrect_count: int = Field(
        default=0,
        validation_alias=AliasChoices("incorrectCount", "incorrect_count"),
    )
    topic_analysis: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("topicAnalysis", "topic_analysis"),
    )
    weak_topics: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("weakTopics", "weak_topics"),
    )
    strong_topics: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("strongTopics", "strong_topics"),
    )
    revision_recommendations: list[dict[str, Any]] = Field(
        default_factory=list,
        validation_alias=AliasChoices("revisionRecommendations", "revision_recommendations"),
    )
    answers: list[GuestVivaAnswerMigrationItem] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def unpack_nested_config(cls, data: Any) -> Any:
        if isinstance(data, dict):
            config = data.get("config")
            if isinstance(config, dict):
                if "questionCount" in config and "question_count" not in data and "questionCount" not in data:
                    data["question_count"] = config["questionCount"]
                if "difficulty" in config and "difficulty" not in data:
                    data["difficulty"] = config["difficulty"]
                if "focus" in config and "topic_focus" not in data and "topicFocus" not in data:
                    data["topic_focus"] = config["focus"]
        return data

    @field_validator("started_at", "completed_at", mode="before")
    @classmethod
    def validate_datetime(cls, v: Any) -> Optional[datetime]:
        return _parse_flexible_datetime(v)


class GuestDataMigrationRequest(BaseModel):
    """Payload for migrating guest data to the authenticated user's account."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    idempotency_key: str = Field(
        ...,
        validation_alias=AliasChoices("idempotencyKey", "idempotency_key"),
        min_length=1,
        max_length=100,
        description="Client-generated unique key to ensure migration idempotency",
    )
    experiments: list[GuestExperimentMigrationItem] = Field(
        default_factory=list,
        max_length=100,
        description="Guest experiment records to transfer",
    )
    viva_sessions: list[GuestVivaSessionMigrationItem] = Field(
        default_factory=list,
        validation_alias=AliasChoices("vivaSessions", "viva_sessions"),
        max_length=200,
        description="Guest viva examination sessions to transfer",
    )


class GuestDataMigrationResponse(BaseModel):
    """Confirmation response after guest data batch migration."""

    model_config = ConfigDict(populate_by_name=True)

    message: str = Field(
        default="Guest data migrated successfully.",
        description="Human-readable success confirmation",
    )
    idempotency_key: str = Field(
        ...,
        serialization_alias="idempotencyKey",
    )
    is_idempotent_replay: bool = Field(
        default=False,
        serialization_alias="isIdempotentReplay",
        description="True if this request was previously processed and results were replayed",
    )
    experiments_migrated: int = Field(
        default=0,
        serialization_alias="experimentsMigrated",
    )
    viva_sessions_migrated: int = Field(
        default=0,
        serialization_alias="vivaSessionsMigrated",
    )
    viva_answers_migrated: int = Field(
        default=0,
        serialization_alias="vivaAnswersMigrated",
    )
    migrated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        serialization_alias="migratedAt",
    )


