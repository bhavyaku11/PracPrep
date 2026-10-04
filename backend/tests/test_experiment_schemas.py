"""Unit tests for Experiment and Preparation Checklist Pydantic Schemas.

Verifies creation validation, update partial contracts, protected field rejection,
SQLAlchemy ORM serialization, pagination wrappers, checklist DTOs, and immutable defaults.
"""

from datetime import datetime, timezone
import uuid

import pytest
from pydantic import ValidationError

from app.modules.auth.models import User  # noqa: F401
import app.modules.users.models  # noqa: F401
import app.modules.viva.models  # noqa: F401
import app.modules.documents.models  # noqa: F401
from app.modules.experiments.models import (
    Experiment,
    PreparationChecklist,
    default_preparation_checklist_items,
)
from app.modules.experiments.schemas import (
    CreationMethodEnum,
    ExperimentCreateRequest,
    ExperimentListItemResponse,
    ExperimentListResponse,
    ExperimentResponse,
    ExperimentStatusEnum,
    ExperimentUpdateRequest,
    PreparationChecklistItemResponse,
    PreparationChecklistItemToggleRequest,
    PreparationChecklistResponse,
    PreparationChecklistUpdateRequest,
    SUPPORTED_CHECKLIST_SECTIONS,
)


# ==============================================================================
# 1. ExperimentCreateRequest Tests
# ==============================================================================


def test_create_valid_minimal_payload() -> None:
    """Minimal create payload requires only title and subject and sets defaults."""
    req = ExperimentCreateRequest(
        title="Ohm's Law Verification",
        subject="Physics",
    )
    assert req.title == "Ohm's Law Verification"
    assert req.subject == "Physics"
    assert req.creation_method == CreationMethodEnum.MANUAL
    assert req.status == ExperimentStatusEnum.READY
    assert req.has_manual_file is False
    assert req.experiment_number is None
    assert req.course_semester is None
    assert req.description is None
    assert req.objective is None
    assert req.theory is None
    assert req.apparatus is None
    assert req.procedure is None
    assert req.observations is None
    assert req.calculations is None
    assert req.precautions is None


def test_create_valid_complete_payload() -> None:
    """Full create payload accepts all optional content and metadata sections."""
    data = {
        "title": "BJT Common Emitter Characteristics",
        "subject": "Electronic Devices & Circuits",
        "experiment_number": "EXP-04",
        "course_semester": "Semester 3",
        "creation_method": "manual",
        "has_manual_file": False,
        "file_name": None,
        "status": "ready",
        "description": "Study of input and output curves of an NPN transistor.",
        "objective": "Plot input and output characteristics and calculate beta.",
        "theory": "In common emitter configuration, the emitter is common to input and output.",
        "apparatus": "NPN Transistor (BC547), DC Power Supply, Ammeters, Voltmeters.",
        "procedure": "1. Connect circuit as shown. 2. Vary Vbe and record Ib.",
        "observations": "Table of Vbe vs Ib at constant Vce.",
        "calculations": "beta = Delta Ic / Delta Ib at constant Vce.",
        "precautions": "Do not exceed maximum transistor power ratings.",
    }
    req = ExperimentCreateRequest.model_validate(data)
    assert req.title == "BJT Common Emitter Characteristics"
    assert req.experiment_number == "EXP-04"
    assert req.procedure.startswith("1. Connect circuit")
    assert req.precautions == "Do not exceed maximum transistor power ratings."


def test_create_accepts_frontend_camelcase_and_aliases() -> None:
    """Create schema accepts frontend camelCase field names and aliases."""
    data = {
        "title": "Photoelectric Effect",
        "subject": "Modern Physics",
        "experimentNumber": "EXP-08",
        "courseSemester": "Semester 2",
        "method": "upload",
        "hasManualFile": True,
        "fileName": "photoelectric_lab.pdf",
        "aim": "Determine Planck's constant using phototube.",
    }
    req = ExperimentCreateRequest.model_validate(data)
    assert req.experiment_number == "EXP-08"
    assert req.course_semester == "Semester 2"
    assert req.creation_method == CreationMethodEnum.UPLOAD
    assert req.has_manual_file is True
    assert req.file_name == "photoelectric_lab.pdf"
    assert req.objective == "Determine Planck's constant using phototube."


def test_create_missing_required_fields_rejected() -> None:
    """Omitting title or subject raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest.model_validate({"subject": "Physics"})
    assert "title" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest.model_validate({"title": "Physics Lab"})
    assert "subject" in str(exc_info.value)


def test_create_blank_required_fields_rejected() -> None:
    """Whitespace-only title or subject is rejected with a clear validation error."""
    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest(title="   ", subject="Physics")
    assert "Title cannot be blank" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest(title="Valid Title", subject="   ")
    assert "Subject cannot be blank" in str(exc_info.value)


def test_create_whitespace_trimming() -> None:
    """Leading and trailing whitespace is trimmed from text inputs."""
    req = ExperimentCreateRequest(
        title="   Newton's Rings   ",
        subject="   Optics   ",
        experiment_number="   EXP-02   ",
        description="   Interference fringes   ",
    )
    assert req.title == "Newton's Rings"
    assert req.subject == "Optics"
    assert req.experiment_number == "EXP-02"
    assert req.description == "Interference fringes"


def test_create_invalid_creation_method_rejected() -> None:
    """Unrecognized creation method raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest(
            title="Title",
            subject="Subject",
            creation_method="telepathy",  # type: ignore
        )
    assert "Input should be 'manual' or 'upload'" in str(exc_info.value)


def test_create_invalid_status_rejected() -> None:
    """Unrecognized experiment status raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest(
            title="Title",
            subject="Subject",
            status="destroyed",  # type: ignore
        )
    assert "Input should be 'draft', 'in-progress', 'completed', 'ready' or 'analyzing'" in str(
        exc_info.value
    )


def test_create_length_constraints() -> None:
    """String fields exceeding maximum database column lengths are rejected."""
    with pytest.raises(ValidationError):
        ExperimentCreateRequest(
            title="A" * 256,
            subject="Physics",
        )

    with pytest.raises(ValidationError):
        ExperimentCreateRequest(
            title="Title",
            subject="B" * 256,
        )

    with pytest.raises(ValidationError):
        ExperimentCreateRequest(
            title="Title",
            subject="Physics",
            experiment_number="C" * 51,
        )


def test_create_rejects_protected_and_unknown_fields() -> None:
    """Protected server-managed fields like id, user_id, timestamps are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest.model_validate(
            {
                "title": "Title",
                "subject": "Subject",
                "id": str(uuid.uuid4()),
            }
        )
    assert "extra_forbidden" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest.model_validate(
            {
                "title": "Title",
                "subject": "Subject",
                "user_id": str(uuid.uuid4()),
            }
        )
    assert "extra_forbidden" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ExperimentCreateRequest.model_validate(
            {
                "title": "Title",
                "subject": "Subject",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_create_optional_empty_strings_normalized_to_none() -> None:
    """Empty strings in optional content fields are normalized to None."""
    req = ExperimentCreateRequest(
        title="Title",
        subject="Subject",
        experiment_number="   ",
        course_semester="",
        description="   ",
        apparatus="",
    )
    assert req.experiment_number is None
    assert req.course_semester is None
    assert req.description is None
    assert req.apparatus is None


# ==============================================================================
# 2. ExperimentUpdateRequest Tests
# ==============================================================================


def test_update_valid_single_field() -> None:
    """Single-field partial update operates cleanly."""
    update = ExperimentUpdateRequest(title="Updated Title")
    assert update.title == "Updated Title"
    assert update.model_dump(exclude_unset=True) == {"title": "Updated Title"}


def test_update_valid_multi_field_with_aliases() -> None:
    """Multi-field partial update with camelCase aliases."""
    update = ExperimentUpdateRequest.model_validate(
        {
            "experimentNumber": "EXP-05-REV",
            "apparatus": "Oscilloscope, Function Generator",
            "status": "in-progress",
            "aim": "Calibrate frequency generator",
        }
    )
    dumped = update.model_dump(exclude_unset=True)
    assert dumped["experiment_number"] == "EXP-05-REV"
    assert dumped["apparatus"] == "Oscilloscope, Function Generator"
    assert dumped["status"] == ExperimentStatusEnum.IN_PROGRESS
    assert dumped["objective"] == "Calibrate frequency generator"


def test_update_omitted_fields_distinguishable_from_supplied() -> None:
    """Fields not provided are not present in model_dump(exclude_unset=True)."""
    update = ExperimentUpdateRequest(subject="Advanced Chemistry")
    unset_dump = update.model_dump(exclude_unset=True)
    assert unset_dump == {"subject": "Advanced Chemistry"}
    assert "title" not in unset_dump
    assert "procedure" not in unset_dump


def test_update_empty_payload_rejected() -> None:
    """Empty update payload raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        ExperimentUpdateRequest.model_validate({})
    assert "At least one experiment field must be provided for update" in str(
        exc_info.value
    )


def test_update_explicit_null_for_non_clearable_fields_rejected() -> None:
    """Non-clearable fields (title, subject, status, creation_method, has_manual_file) reject null."""
    for field in ["title", "subject", "status", "creation_method", "has_manual_file"]:
        with pytest.raises(ValidationError) as exc_info:
            ExperimentUpdateRequest.model_validate({field: None})
        assert "cannot be null" in str(exc_info.value)


def test_update_blank_title_or_subject_rejected() -> None:
    """Whitespace-only title or subject in update is rejected."""
    with pytest.raises(ValidationError) as exc_info:
        ExperimentUpdateRequest.model_validate({"title": "   "})
    assert "Title cannot be blank" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ExperimentUpdateRequest.model_validate({"subject": "   "})
    assert "Subject cannot be blank" in str(exc_info.value)


def test_update_protected_fields_rejected() -> None:
    """Attempting to update id, user_id, timestamps or unknown fields raises extra_forbidden."""
    protected_payloads = [
        {"id": str(uuid.uuid4())},
        {"user_id": str(uuid.uuid4())},
        {"created_at": datetime.now(timezone.utc).isoformat()},
        {"updated_at": datetime.now(timezone.utc).isoformat()},
        {"unknown_random_key": "hacker_payload"},
    ]
    for payload in protected_payloads:
        with pytest.raises(ValidationError) as exc_info:
            ExperimentUpdateRequest.model_validate(payload)
        assert "extra_forbidden" in str(exc_info.value)


def test_update_whitespace_normalization() -> None:
    """Whitespace is trimmed on update fields."""
    update = ExperimentUpdateRequest(
        title="   New Trimmed Title   ",
        subject="   New Trimmed Subject   ",
    )
    assert update.title == "New Trimmed Title"
    assert update.subject == "New Trimmed Subject"


# ==============================================================================
# 3. ExperimentResponse & Serialization Tests
# ==============================================================================


@pytest.fixture
def orm_experiment() -> Experiment:
    """Create a populated Experiment SQLAlchemy ORM model instance with checklist."""
    now = datetime.now(timezone.utc)
    exp_id = uuid.uuid4()
    user_id = uuid.uuid4()
    checklist_id = uuid.uuid4()

    checklist = PreparationChecklist(
        id=checklist_id,
        experiment_id=exp_id,
        items={
            "objective": True,
            "theory": True,
            "apparatus": False,
            "procedure": False,
            "precautions": False,
        },
        created_at=now,
        updated_at=now,
    )

    exp = Experiment(
        id=exp_id,
        user_id=user_id,
        title="Vernier Caliper Measurement",
        subject="Physics",
        experiment_number="EXP-01",
        course_semester="Semester 1",
        creation_method="manual",
        has_manual_file=False,
        file_name=None,
        status="ready",
        description="Basic measurement of dimensions.",
        objective="Measure diameter of a cylinder.",
        theory="Least count = 1 MSD - 1 VSD.",
        apparatus="Vernier Caliper, Solid Cylinder.",
        procedure="1. Determine least count. 2. Measure diameter.",
        observations="Main scale and Vernier readings recorded.",
        calculations="Calculated volume = pi * r^2 * h.",
        precautions="Avoid parallax error and excessive screw pressure.",
        created_at=now,
        updated_at=now,
        checklist=checklist,
    )
    return exp


def test_response_serialization_from_orm_model(orm_experiment: Experiment) -> None:
    """ExperimentResponse accurately serializes from a SQLAlchemy ORM model instance."""
    resp = ExperimentResponse.model_validate(orm_experiment)

    assert resp.id == orm_experiment.id
    assert resp.title == "Vernier Caliper Measurement"
    assert resp.subject == "Physics"
    assert resp.experiment_number == "EXP-01"
    assert resp.course_semester == "Semester 1"
    assert resp.creation_method == "manual"
    assert resp.has_manual_file is False
    assert resp.status == "ready"
    assert resp.description == "Basic measurement of dimensions."
    assert resp.objective == "Measure diameter of a cylinder."
    assert resp.procedure == "1. Determine least count. 2. Measure diameter."
    assert resp.created_at == orm_experiment.created_at
    assert resp.updated_at == orm_experiment.updated_at

    # Relational checklist serialization
    assert resp.checklist is not None
    assert resp.checklist.id == orm_experiment.checklist.id
    assert resp.checklist.items["objective"] is True
    assert resp.checklist.items["apparatus"] is False

    # Flat preparationChecklist dictionary sync
    assert resp.preparation_checklist is not None
    assert resp.preparation_checklist["objective"] is True
    assert resp.preparation_checklist["theory"] is True
    assert resp.preparation_checklist["apparatus"] is False


def test_response_serialization_aliases_match_frontend() -> None:
    """ExperimentResponse serializes with camelCase aliases matching frontend ExperimentRecord."""
    now = datetime.now(timezone.utc)
    exp = Experiment(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Hooke's Law",
        subject="Mechanics",
        experiment_number="EXP-03",
        course_semester="Sem 1",
        creation_method="manual",
        has_manual_file=True,
        file_name="hooke.pdf",
        status="ready",
        created_at=now,
        updated_at=now,
    )
    resp = ExperimentResponse.model_validate(exp)
    dumped = resp.model_dump(by_alias=True)

    assert "experimentNumber" in dumped
    assert dumped["experimentNumber"] == "EXP-03"
    assert "courseSemester" in dumped
    assert dumped["courseSemester"] == "Sem 1"
    assert "creationMethod" in dumped
    assert "hasManualFile" in dumped
    assert dumped["hasManualFile"] is True
    assert "fileName" in dumped
    assert dumped["fileName"] == "hooke.pdf"
    assert "createdAt" in dumped
    assert "updatedAt" in dumped
    assert "vivaQuestionsCount" in dumped
    assert dumped["vivaQuestionsCount"] == 0


def test_response_excludes_user_id_and_internal_secrets(orm_experiment: Experiment) -> None:
    """Internal user_id, password hashes, and database internals are never serialized."""
    resp = ExperimentResponse.model_validate(orm_experiment)
    dumped = resp.model_dump()

    assert "user_id" not in dumped
    assert "userId" not in dumped
    assert "password_hash" not in dumped


# ==============================================================================
# 4. ExperimentListItemResponse & List Wrapper Tests
# ==============================================================================


def test_list_item_response_is_lightweight(orm_experiment: Experiment) -> None:
    """ExperimentListItemResponse contains only essential card metadata without heavy text."""
    item = ExperimentListItemResponse.model_validate(orm_experiment)

    assert item.id == orm_experiment.id
    assert item.title == orm_experiment.title
    assert item.subject == orm_experiment.subject
    assert item.experiment_number == orm_experiment.experiment_number
    assert item.status == orm_experiment.status
    assert item.created_at == orm_experiment.created_at
    assert item.updated_at == orm_experiment.updated_at

    dumped = item.model_dump()
    # Confirm large text sections are not present
    assert "theory" not in dumped
    assert "procedure" not in dumped
    assert "observations" not in dumped
    assert "calculations" not in dumped
    assert "precautions" not in dumped
    assert "apparatus" not in dumped
    assert "description" not in dumped


def test_list_response_pagination_wrapper(orm_experiment: Experiment) -> None:
    """ExperimentListResponse encapsulates items list and pagination metadata."""
    item = ExperimentListItemResponse.model_validate(orm_experiment)
    list_resp = ExperimentListResponse(
        items=[item],
        total=1,
        page=1,
        page_size=20,
        total_pages=1,
    )
    assert len(list_resp.items) == 1
    assert list_resp.total == 1
    assert list_resp.page == 1
    assert list_resp.page_size == 20
    assert list_resp.total_pages == 1

    dumped = list_resp.model_dump(by_alias=True)
    assert "pageSize" in dumped
    assert "totalPages" in dumped


# ==============================================================================
# 5. Preparation Checklist DTO Tests
# ==============================================================================


def test_preparation_checklist_response_structure() -> None:
    """PreparationChecklistResponse matches the database model structure."""
    chk_id = uuid.uuid4()
    exp_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    resp = PreparationChecklistResponse(
        id=chk_id,
        experiment_id=exp_id,
        items=default_preparation_checklist_items(),
        created_at=now,
        updated_at=now,
    )
    assert resp.id == chk_id
    assert resp.experiment_id == exp_id
    assert len(resp.items) == 5
    assert all(val is False for val in resp.items.values())


def test_checklist_batch_update_request_validation() -> None:
    """PreparationChecklistUpdateRequest validates section keys and booleans."""
    valid_req = PreparationChecklistUpdateRequest(
        items={"objective": True, "theory": True}
    )
    assert valid_req.items["objective"] is True

    # Empty dictionary rejected
    with pytest.raises(ValidationError) as exc_info:
        PreparationChecklistUpdateRequest.model_validate({"items": {}})
    assert "Checklist items mapping cannot be empty" in str(exc_info.value)

    # Invalid section key rejected
    with pytest.raises(ValidationError) as exc_info:
        PreparationChecklistUpdateRequest(
            items={"non_existent_section": True}  # type: ignore
        )
    assert "Invalid checklist section key" in str(exc_info.value)


def test_checklist_single_item_toggle_request() -> None:
    """PreparationChecklistItemToggleRequest validates item key and boolean status."""
    toggle = PreparationChecklistItemToggleRequest(
        item_id="procedure",
        completed=True,
    )
    assert toggle.item_id == "procedure"
    assert toggle.completed is True

    # Accepts camelCase alias itemId
    toggle_alias = PreparationChecklistItemToggleRequest.model_validate(
        {"itemId": "theory", "completed": False}
    )
    assert toggle_alias.item_id == "theory"
    assert toggle_alias.completed is False

    # Invalid item rejected
    with pytest.raises(ValidationError) as exc_info:
        PreparationChecklistItemToggleRequest(
            item_id="invalid_section",
            completed=True,
        )
    assert "Invalid checklist item 'invalid_section'" in str(exc_info.value)


def test_checklist_item_response_metadata() -> None:
    """PreparationChecklistItemResponse defines item guidance and target tab."""
    item = PreparationChecklistItemResponse(
        id="theory",
        label="Understand the underlying theory.",
        description="Review physical laws and circuit principles.",
        completed=True,
        tab_target="theory",
    )
    assert item.id == "theory"
    assert item.completed is True
    assert item.model_dump(by_alias=True)["tabTarget"] == "theory"


# ==============================================================================
# 6. Immutable Defaults & Isolation Tests
# ==============================================================================


def test_mutable_defaults_are_isolated_instances() -> None:
    """Verify default_factory ensures collections are not shared across instances."""
    resp1 = ExperimentListResponse(total=0)
    resp2 = ExperimentListResponse(total=0)

    assert resp1.items is not resp2.items

    chk1 = PreparationChecklistResponse(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    chk2 = PreparationChecklistResponse(
        id=uuid.uuid4(),
        experiment_id=uuid.uuid4(),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    assert chk1.items is not chk2.items
    chk1.items["objective"] = True
    assert chk2.items["objective"] is False
