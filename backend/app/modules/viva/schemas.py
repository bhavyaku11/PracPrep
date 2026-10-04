"""Viva Voce Examination Pydantic Schemas and DTOs.

Defines request and response data transfer objects for AI viva sessions,
question generation, student answer submission, evaluations, transcripts,
and performance analytics.
"""

from datetime import datetime
from decimal import Decimal
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


# ==============================================================================
# Enumerations
# ==============================================================================


class VivaDifficultyEnum(str, Enum):
    """Supported difficulty levels for viva sessions and questions."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    MIXED = "mixed"


class VivaTopicEnum(str, Enum):
    """Supported topic focus areas for viva voce practice."""

    THEORY = "theory"
    PROCEDURE = "procedure"
    APPARATUS = "apparatus"
    OBSERVATIONS = "observations"
    PRECAUTIONS = "precautions"
    MIXED = "mixed"


class EvaluationVerdictEnum(str, Enum):
    """Evaluation verdict classifications for student answers."""

    CORRECT = "correct"
    PARTIALLY_CORRECT = "partially-correct"
    INCORRECT = "incorrect"


class VivaProviderModeEnum(str, Enum):
    """Operational mode of the AI viva evaluation engine."""

    DEMONSTRATION = "demonstration"
    AI_LIVE = "ai-live"


class VivaSessionStatusEnum(str, Enum):
    """Lifecycle statuses for viva sessions."""

    IN_PROGRESS = "in-progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class WorkspaceTabEnum(str, Enum):
    """Experiment workspace tab targets for revision recommendations."""

    OVERVIEW = "overview"
    THEORY = "theory"
    APPARATUS = "apparatus"
    PROCEDURE = "procedure"
    OBSERVATIONS = "observations"
    PRECAUTIONS = "precautions"
    CHECKLIST = "checklist"


# ==============================================================================
# Nested Analytics & Configuration DTOs
# ==============================================================================


class VivaSessionConfigDTO(BaseModel):
    """Configuration settings for a viva practice session."""

    question_count: int = Field(
        default=5,
        ge=1,
        le=20,
        serialization_alias="questionCount",
        description="Target question count (5, 10, or 15)",
    )
    difficulty: VivaDifficultyEnum = Field(
        default=VivaDifficultyEnum.INTERMEDIATE,
        description="Session difficulty level ('beginner', 'intermediate', 'advanced', 'mixed')",
    )
    focus: VivaTopicEnum = Field(
        default=VivaTopicEnum.MIXED,
        description="Specific topic focus area or 'mixed'",
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class TopicPerformanceResponse(BaseModel):
    """Aggregated performance metrics for a specific topic."""

    topic: str = Field(description="Subject topic name (e.g. 'theory', 'procedure')")
    total: int = Field(ge=0, description="Total questions for this topic")
    correct: int = Field(ge=0, default=0, description="Questions scored as correct")
    partially_correct: int = Field(
        ge=0,
        default=0,
        validation_alias=AliasChoices("partially_correct", "partiallyCorrect"),
        serialization_alias="partiallyCorrect",
        description="Questions scored as partially correct",
    )
    incorrect: int = Field(ge=0, default=0, description="Questions scored as incorrect")
    average_score: float = Field(
        ge=0.0,
        le=10.0,
        default=0.0,
        validation_alias=AliasChoices("average_score", "averageScore"),
        serialization_alias="averageScore",
        description="Average score on 0-10 scale for this topic",
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class RevisionRecommendationResponse(BaseModel):
    """Targeted revision guidance linked to an experiment workspace tab."""

    topic: str = Field(description="Subject topic requiring revision")
    reason: str = Field(description="Specific analytical reason for recommendation")
    suggested_action: str = Field(
        ...,
        validation_alias=AliasChoices("suggested_action", "suggestedAction"),
        serialization_alias="suggestedAction",
        description="Actionable study or lab preparation step",
    )
    workspace_tab: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("workspace_tab", "workspaceTab"),
        serialization_alias="workspaceTab",
        description="Linked workspace tab for revision (e.g. 'theory', 'procedure')",
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# ==============================================================================
# Question & Evaluation DTOs
# ==============================================================================


class VivaQuestionResponse(BaseModel):
    """Question item presented to the student during viva examination."""

    id: str = Field(description="Unique question identifier")
    question_number: int = Field(
        ge=1,
        validation_alias=AliasChoices("question_number", "questionNumber"),
        serialization_alias="questionNumber",
        description="1-based sequence index",
    )
    question: str = Field(
        ...,
        validation_alias=AliasChoices("question", "question_text", "questionText"),
        description="The oral examination question text",
    )
    topic: VivaTopicEnum = Field(description="Question topic area")
    difficulty: str = Field(
        default="intermediate",
        description="Question difficulty rating ('beginner', 'intermediate', 'advanced')",
    )
    expected_answer: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("expected_answer", "expectedAnswer"),
        serialization_alias="expectedAnswer",
        description="Model academic answer text",
    )
    key_points: list[str] = Field(
        default_factory=list,
        validation_alias=AliasChoices("key_points", "keyPoints"),
        serialization_alias="keyPoints",
        description="Key conceptual elements required for full score",
    )
    grounded_source_section: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("grounded_source_section", "groundedSourceSection"),
        serialization_alias="groundedSourceSection",
        description="Lab manual source section (e.g. 'Theory', 'Procedure')",
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class VivaGenerateQuestionsResponse(BaseModel):
    """Response collection for generated viva examination questions."""

    questions: list[VivaQuestionResponse] = Field(
        min_length=1,
        description="Ordered list of generated viva examination questions",
    )
    provider_mode: VivaProviderModeEnum = Field(
        default=VivaProviderModeEnum.DEMONSTRATION,
        serialization_alias="providerMode",
        description="Generating provider mode: 'demonstration' or 'ai-live'",
    )
    provider_id: str = Field(
        default="demonstration",
        serialization_alias="providerId",
        description="Generating provider machine identifier (e.g. 'gemini', 'demonstration')",
    )
    total_count: int = Field(
        default=0,
        serialization_alias="totalCount",
        description="Total number of generated questions",
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


class VivaEvaluationResponse(BaseModel):
    """Evaluation result for an individual student oral answer."""

    verdict: EvaluationVerdictEnum = Field(
        description="Classification verdict: 'correct', 'partially-correct', 'incorrect'"
    )
    score: int = Field(
        ge=0,
        le=10,
        description="Rubric score on a 0-10 scale",
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Summary evaluation feedback",
    )
    what_you_got_right: str = Field(
        default="",
        serialization_alias="whatYouGotRight",
        description="Specific concepts or terminology the student correctly explained",
    )
    what_was_missing: str = Field(
        default="",
        serialization_alias="whatWasMissing",
        description="Important concepts, equations, or details omitted from answer",
    )
    expected_answer: str = Field(
        default="",
        serialization_alias="expectedAnswer",
        description="Authoritative model answer for student review",
    )
    improvement_tip: str = Field(
        default="",
        serialization_alias="improvementTip",
        description="Actionable viva tip for future oral examinations",
    )
    provider_mode: VivaProviderModeEnum = Field(
        default=VivaProviderModeEnum.DEMONSTRATION,
        serialization_alias="providerMode",
        description="Evaluation provider: 'demonstration' or 'ai-live'",
    )
    provider_id: str = Field(
        default="demonstration",
        serialization_alias="providerId",
        description="Machine identifier of evaluating provider (e.g. 'gemini', 'demonstration')",
    )
    key_points_covered: list[str] = Field(
        default_factory=list,
        serialization_alias="keyPointsCovered",
        description="Key points matched in student's response",
    )
    key_points_missed: list[str] = Field(
        default_factory=list,
        serialization_alias="keyPointsMissed",
        description="Key points omitted in student's response",
    )

    model_config = ConfigDict(populate_by_name=True, from_attributes=True)


# ==============================================================================
# Request Schemas
# ==============================================================================


class VivaSessionCreateRequest(BaseModel):
    """Payload to initiate a new viva examination practice session."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    experiment_id: uuid.UUID = Field(
        ...,
        validation_alias=AliasChoices("experiment_id", "experimentId"),
        description="Unique identifier of the experiment to practice viva for",
    )
    difficulty: VivaDifficultyEnum = Field(
        default=VivaDifficultyEnum.INTERMEDIATE,
        description="Difficulty setting: 'beginner', 'intermediate', 'advanced', or 'mixed'",
    )
    question_count: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias=AliasChoices("question_count", "questionCount"),
        description="Target question count (5, 10, or 15)",
    )
    topic_focus: VivaTopicEnum = Field(
        default=VivaTopicEnum.MIXED,
        validation_alias=AliasChoices("topic_focus", "topicFocus", "focus"),
        description="Topic area focus or 'mixed'",
    )
    provider_mode: VivaProviderModeEnum = Field(
        default=VivaProviderModeEnum.DEMONSTRATION,
        validation_alias=AliasChoices("provider_mode", "providerMode"),
        description="Evaluation engine mode: 'demonstration' or 'ai-live'",
    )


class VivaAnswerSubmitRequest(BaseModel):
    """Payload to submit a student response for evaluation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    question_number: int = Field(
        ...,
        ge=1,
        validation_alias=AliasChoices("question_number", "questionNumber"),
        description="1-based sequence index of the question being answered",
    )
    question_id: Optional[str] = Field(
        default=None,
        max_length=100,
        validation_alias=AliasChoices("question_id", "questionId"),
        description="Question identifier if generated by question pool",
    )
    question_text: Optional[str] = Field(
        default=None,
        max_length=2000,
        validation_alias=AliasChoices("question_text", "questionText", "question"),
        description="Optional text of the question asked",
    )
    topic: Optional[VivaTopicEnum] = Field(
        default=None,
        description="Optional topic of the question",
    )
    difficulty: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Optional difficulty of the question",
    )
    student_answer: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("student_answer", "studentAnswer", "answer"),
        description="Student's verbal or typed response",
    )
    time_spent_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        validation_alias=AliasChoices("time_spent_seconds", "timeSpentSeconds"),
        description="Optional duration spent answering in seconds",
    )

    @field_validator("student_answer", mode="before")
    @classmethod
    def validate_student_answer_non_empty(cls, v: Any) -> str:
        if v is None:
            raise ValueError("Student answer cannot be null")
        if not isinstance(v, str):
            raise ValueError("Student answer must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Student answer cannot be empty or whitespace-only")
        return stripped


class VivaSessionCompleteRequest(BaseModel):
    """Payload to complete an active viva examination session.

    All score calculations, topic analytics, and revision recommendations
    are determined and persisted strictly server-side. Optional student notes
    may be supplied, but client-manipulated scores or verdicts are forbidden.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional student notes or reflection upon completing the session",
    )

    @field_validator("notes", mode="before")
    @classmethod
    def normalize_notes(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        if isinstance(v, str):
            stripped = v.strip()
            return stripped if stripped else None
        return v


class VivaGenerateQuestionsRequest(BaseModel):
    """Payload to request viva questions generation for an experiment."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    experiment_id: Optional[uuid.UUID] = Field(
        default=None,
        validation_alias=AliasChoices("experiment_id", "experimentId"),
        description="Experiment to generate questions for",
    )
    experiment_context: Optional[dict[str, Any]] = Field(
        default=None,
        validation_alias=AliasChoices("experiment_context", "experimentContext", "experiment"),
        description="Optional direct experiment context object",
    )
    question_count: int = Field(
        default=5,
        ge=1,
        le=20,
        validation_alias=AliasChoices("question_count", "questionCount"),
        description="Target question count",
    )
    difficulty: VivaDifficultyEnum = Field(
        default=VivaDifficultyEnum.INTERMEDIATE,
        description="Question difficulty",
    )
    focus: VivaTopicEnum = Field(
        default=VivaTopicEnum.MIXED,
        validation_alias=AliasChoices("focus", "topic_focus", "topicFocus"),
        description="Question focus topic or 'mixed'",
    )

    @model_validator(mode="after")
    def validate_experiment_source(self) -> "VivaGenerateQuestionsRequest":
        if self.experiment_id is None and self.experiment_context is None:
            raise ValueError("Either experiment_id or experiment_context must be provided")
        return self


class VivaEvaluateAnswerRequest(BaseModel):
    """Payload to evaluate an individual student response against a question rubric."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    question: VivaQuestionResponse = Field(description="Question being evaluated")
    student_answer: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        validation_alias=AliasChoices("student_answer", "studentAnswer"),
        description="Student's response text",
    )

    @field_validator("student_answer", mode="before")
    @classmethod
    def validate_student_answer_non_empty(cls, v: Any) -> str:
        if v is None:
            raise ValueError("Student answer cannot be null")
        if not isinstance(v, str):
            raise ValueError("Student answer must be a string")
        stripped = v.strip()
        if not stripped:
            raise ValueError("Student answer cannot be empty or whitespace-only")
        return stripped


# ==============================================================================
# Response Schemas
# ==============================================================================


class VivaAnswerResponse(BaseModel):
    """Detailed record of a single question-and-answer interaction."""

    id: uuid.UUID
    session_id: uuid.UUID = Field(serialization_alias="sessionId")
    question_id: Optional[str] = Field(
        default=None,
        serialization_alias="questionId",
        description="Original question ID if available",
    )
    question_number: int = Field(
        ge=1,
        serialization_alias="questionNumber",
        description="1-based question number in session",
    )
    question_text: str = Field(
        serialization_alias="questionText",
        description="Text of the question asked",
    )
    topic: str = Field(description="Topic category of the question")
    difficulty: str = Field(description="Difficulty level")
    student_answer: str = Field(
        serialization_alias="studentAnswer",
        description="Student submitted response",
    )
    score: Optional[int] = Field(
        default=None,
        ge=0,
        le=10,
        description="Evaluated score (0-10) or None if unevaluated",
    )
    verdict: Optional[str] = Field(
        default=None,
        description="Evaluated verdict ('correct', 'partially-correct', 'incorrect')",
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Summary evaluation feedback",
    )
    expected_answer: Optional[str] = Field(
        default=None,
        serialization_alias="expectedAnswer",
    )
    what_you_got_right: Optional[str] = Field(
        default=None,
        serialization_alias="whatYouGotRight",
    )
    what_was_missing: Optional[str] = Field(
        default=None,
        serialization_alias="whatWasMissing",
    )
    suggested_improvement: Optional[str] = Field(
        default=None,
        serialization_alias="suggestedImprovement",
    )
    key_points_covered: list[str] = Field(
        default_factory=list,
        serialization_alias="keyPointsCovered",
    )
    key_points_missed: list[str] = Field(
        default_factory=list,
        serialization_alias="keyPointsMissed",
    )
    evaluation: Optional[VivaEvaluationResponse] = Field(
        default=None,
        description="Nested evaluation DTO matching frontend VivaEvaluation contract",
    )
    time_spent_seconds: Optional[int] = Field(
        default=None,
        ge=0,
        serialization_alias="timeSpentSeconds",
        description="Seconds spent by student answering",
    )
    created_at: datetime = Field(serialization_alias="createdAt")
    timestamp: Optional[int] = Field(
        default=None,
        description="Unix timestamp (milliseconds) for frontend VivaAnswerRecord compatibility",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @model_validator(mode="after")
    def synthesize_evaluation_and_timestamp(self) -> "VivaAnswerResponse":
        """Compute timestamp and synthesize evaluation DTO if absent."""
        if self.created_at and self.timestamp is None:
            self.timestamp = int(self.created_at.timestamp() * 1000)

        # Synthesize evaluation object from flat ORM attributes if evaluation is None
        if self.evaluation is None and (self.verdict is not None or self.score is not None):
            try:
                verdict_enum = (
                    EvaluationVerdictEnum(self.verdict)
                    if self.verdict
                    else EvaluationVerdictEnum.INCORRECT
                )
            except ValueError:
                verdict_enum = EvaluationVerdictEnum.INCORRECT

            self.evaluation = VivaEvaluationResponse(
                verdict=verdict_enum,
                score=self.score if self.score is not None else 0,
                what_you_got_right=self.what_you_got_right or "",
                what_was_missing=self.what_was_missing or "",
                expected_answer=self.expected_answer or "",
                improvement_tip=self.suggested_improvement or self.feedback or "",
                key_points_covered=self.key_points_covered,
                key_points_missed=self.key_points_missed,
            )
        return self


class VivaSessionResponse(BaseModel):
    """Complete viva examination practice session representation."""

    id: uuid.UUID
    experiment_id: uuid.UUID = Field(serialization_alias="experimentId")
    experiment_title: Optional[str] = Field(
        default="",
        serialization_alias="experimentTitle",
        description="Associated experiment title",
    )
    subject: Optional[str] = Field(
        default="",
        description="Associated experiment subject",
    )
    difficulty: str
    question_count: int = Field(serialization_alias="questionCount")
    topic_focus: str = Field(serialization_alias="topicFocus")
    provider_mode: str = Field(serialization_alias="providerMode")
    is_completed: bool = Field(serialization_alias="isCompleted")
    status: str = Field(
        default="in-progress",
        description="'completed' if completed, else 'in-progress'",
    )
    config: Optional[VivaSessionConfigDTO] = None
    started_at: datetime = Field(serialization_alias="startedAt")
    completed_at: Optional[datetime] = Field(
        default=None,
        serialization_alias="completedAt",
    )
    started_at_timestamp: Optional[int] = Field(
        default=None,
        serialization_alias="startedAtTimestamp",
    )
    completed_at_timestamp: Optional[int] = Field(
        default=None,
        serialization_alias="completedAtTimestamp",
    )
    total_questions: int = Field(serialization_alias="totalQuestions")
    questions_answered: int = Field(
        default=0,
        serialization_alias="questionsAnswered",
    )
    correct_count: int = Field(
        default=0,
        serialization_alias="correctCount",
    )
    partially_correct_count: int = Field(
        default=0,
        serialization_alias="partiallyCorrectCount",
    )
    incorrect_count: int = Field(
        default=0,
        serialization_alias="incorrectCount",
    )
    average_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=10.0,
        serialization_alias="averageScore",
        description="Average score across evaluated answers (0-10)",
    )
    topic_analysis: dict[str, TopicPerformanceResponse] = Field(
        default_factory=dict,
        serialization_alias="topicAnalysis",
    )
    weak_topics: list[str] = Field(
        default_factory=list,
        serialization_alias="weakTopics",
    )
    strong_topics: list[str] = Field(
        default_factory=list,
        serialization_alias="strongTopics",
    )
    revision_recommendations: list[RevisionRecommendationResponse] = Field(
        default_factory=list,
        serialization_alias="revisionRecommendations",
    )
    answers: list[VivaAnswerResponse] = Field(default_factory=list)
    created_at: datetime = Field(serialization_alias="createdAt")
    updated_at: datetime = Field(serialization_alias="updatedAt")

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
    def synthesize_session_details(self) -> "VivaSessionResponse":
        """Compute status, config DTO, and millisecond timestamps."""
        # Synchronize lifecycle status
        self.status = "completed" if self.is_completed else "in-progress"

        # Populate config object if absent
        if self.config is None:
            try:
                diff_enum = VivaDifficultyEnum(self.difficulty)
            except ValueError:
                diff_enum = VivaDifficultyEnum.INTERMEDIATE
            try:
                topic_enum = VivaTopicEnum(self.topic_focus)
            except ValueError:
                topic_enum = VivaTopicEnum.MIXED

            self.config = VivaSessionConfigDTO(
                question_count=self.question_count,
                difficulty=diff_enum,
                focus=topic_enum,
            )

        # Populate millisecond timestamps for frontend compatibility
        if self.started_at and self.started_at_timestamp is None:
            self.started_at_timestamp = int(self.started_at.timestamp() * 1000)
        if self.completed_at and self.completed_at_timestamp is None:
            self.completed_at_timestamp = int(self.completed_at.timestamp() * 1000)

        return self


class VivaSessionListItemResponse(BaseModel):
    """Summary representation of a viva session for history tables and dashboard cards."""

    id: uuid.UUID
    experiment_id: uuid.UUID = Field(serialization_alias="experimentId")
    experiment_title: Optional[str] = Field(
        default="",
        serialization_alias="experimentTitle",
    )
    subject: Optional[str] = Field(default="")
    difficulty: str
    question_count: int = Field(serialization_alias="questionCount")
    topic_focus: str = Field(serialization_alias="topicFocus")
    provider_mode: str = Field(serialization_alias="providerMode")
    is_completed: bool = Field(serialization_alias="isCompleted")
    total_questions: int = Field(serialization_alias="totalQuestions")
    questions_answered: int = Field(serialization_alias="questionsAnswered")
    correct_count: int = Field(default=0, serialization_alias="correctCount")
    average_score: Optional[float] = Field(
        default=None,
        serialization_alias="averageScore",
    )
    started_at: datetime = Field(serialization_alias="startedAt")
    completed_at: Optional[datetime] = Field(
        default=None,
        serialization_alias="completedAt",
    )
    created_at: datetime = Field(serialization_alias="createdAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("average_score", mode="before")
    @classmethod
    def convert_decimal_to_float(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (Decimal, int, float, str)):
            return round(float(v), 2)
        return v


class VivaSessionListResponse(BaseModel):
    """Paginated collection response for viva session listings."""

    items: list[VivaSessionListItemResponse] = Field(
        default_factory=list,
        description="Collection of viva session summary records",
    )
    total: int = Field(
        ge=0,
        description="Total number of sessions matching query criteria",
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
        description="Total calculated page count",
    )

    model_config = ConfigDict(populate_by_name=True)


class VivaTranscriptResponse(BaseModel):
    """Full transcript of an active or completed viva examination session."""

    session_id: uuid.UUID = Field(serialization_alias="sessionId")
    experiment_id: uuid.UUID = Field(serialization_alias="experimentId")
    difficulty: str
    is_completed: bool = Field(serialization_alias="isCompleted")
    total_questions: int = Field(serialization_alias="totalQuestions")
    questions_answered: int = Field(serialization_alias="questionsAnswered")
    average_score: Optional[float] = Field(
        default=None,
        serialization_alias="averageScore",
    )
    started_at: datetime = Field(serialization_alias="startedAt")
    completed_at: Optional[datetime] = Field(
        default=None,
        serialization_alias="completedAt",
    )
    answers: list[VivaAnswerResponse] = Field(
        default_factory=list,
        description="Chronologically ordered student answer and evaluation records",
    )

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    @field_validator("average_score", mode="before")
    @classmethod
    def convert_decimal_to_float(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        if isinstance(v, (Decimal, int, float, str)):
            return round(float(v), 2)
        return v
