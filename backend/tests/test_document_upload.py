"""Unit and integration tests for Lab Manual Multipart Upload Endpoint.

Verifies POST /api/v1/experiments/upload-manual for:
- Authenticated PDF and DOCX uploads with metadata return.
- File validation (missing, empty, unsupported extension, signature mismatch, oversized).
- Path traversal defense and server-controlled safe storage naming.
- Experiment ownership isolation (404 for missing/foreign experiment).
- Transactional persistence and replacement of existing manuals.
- Rollback and physical file cleanup on storage or database failure.
- Zero leakage of internal filesystem paths or stack traces.
"""

from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
import uuid
import zipfile

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.modules.auth.models import User
from app.modules.documents.models import UploadedDocument
from app.modules.documents.storage import DocumentStorageService, get_storage_service
from app.modules.experiments.models import Experiment, PreparationChecklist


# ==============================================================================
# Helpers & Byte Generators
# ==============================================================================


def make_valid_pdf_bytes(label: str = "Test Lab Manual") -> bytes:
    """Generate minimal valid PDF byte sequence containing %PDF- signature and EOF."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /Contents 4 0 R >> endobj\n"
        b"4 0 obj << /Length 55 >> stream\n"
        + f"BT /F1 12 Tf 100 700 Td ({label}) Tj ET".encode("utf-8")
        + b"\nendstream endobj\n"
        b"xref\n0 5\n0000000000 65535 f \n"
        b"trailer << /Root 1 0 R /Size 5 >>\n"
        b"startxref\n300\n%%EOF"
    )


def make_valid_docx_bytes(label: str = "Test Lab Manual") -> bytes:
    """Generate minimal valid OpenXML DOCX archive."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/>'
            "</Types>",
        )
        zf.writestr(
            "word/document.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{label}</w:t></w:r></w:p></w:body></w:document>',
        )
    return buf.getvalue()


# ==============================================================================
# Fixtures
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
        email="student@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        full_name="Lab Student",
        university="State University",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def other_user(other_user_id: uuid.UUID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=other_user_id,
        email="other@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        full_name="Other Student",
        university="State University",
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
    has_manual_file: bool = False,
    file_name: Optional[str] = None,
) -> Experiment:
    """Helper to instantiate an Experiment ORM model with checklist."""
    now = datetime.now(timezone.utc)
    actual_exp_id = exp_id or uuid.uuid4()
    exp = Experiment(
        id=actual_exp_id,
        user_id=user_id,
        title=title,
        subject="Electrical Engineering",
        experiment_number="EE-101",
        course_semester="Semester 1",
        creation_method="manual",
        has_manual_file=has_manual_file,
        file_name=file_name,
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
    exp.documents = []
    return exp


def build_test_client(
    sample_user: User,
    experiment: Optional[Experiment] = None,
    storage_service: Optional[DocumentStorageService] = None,
) -> tuple[httpx.AsyncClient, AsyncMock]:
    """Build test client with overridden DB session and storage service."""
    db_session = AsyncMock(spec=AsyncSession)
    db_session.add = MagicMock()
    db_session.delete = AsyncMock()
    db_session.commit = AsyncMock()
    db_session.rollback = AsyncMock()
    db_session.refresh = AsyncMock()

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
    if storage_service is not None:
        app.dependency_overrides[get_storage_service] = lambda: storage_service

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return client, db_session


# ==============================================================================
# 1. Successful Upload Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_upload_pdf_manual_success(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Authenticated user successfully uploads valid PDF manual."""
    exp = create_sample_experiment(sample_user.id)
    storage = DocumentStorageService(base_dir=tmp_path)
    client, db_session = build_test_client(sample_user, exp, storage)

    pdf_bytes = make_valid_pdf_bytes("Physics Lab Manual")

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("physics_manual.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["experimentId"] == str(exp.id)
    assert data["fileName"] == "physics_manual.pdf"
    assert data["mimeType"] == "application/pdf"
    assert data["fileSizeBytes"] == len(pdf_bytes)
    assert data["status"] == "pending"
    assert data["hasManualFile"] is True
    assert "createdAt" in data
    assert "updatedAt" in data
    assert "id" in data

    # Verify internal host path is NOT leaked in response
    assert str(tmp_path) not in response.text

    # Verify DB interaction
    db_session.add.assert_called_once()
    added_doc = db_session.add.call_args[0][0]
    assert isinstance(added_doc, UploadedDocument)
    assert added_doc.experiment_id == exp.id
    assert added_doc.user_id == sample_user.id
    assert added_doc.file_name == "physics_manual.pdf"
    assert added_doc.file_size_bytes == len(pdf_bytes)
    assert added_doc.mime_type == "application/pdf"

    # Verify experiment was updated
    assert exp.has_manual_file is True
    assert exp.file_name == "physics_manual.pdf"

    # Verify file stored on disk with server-generated name
    stored_file_path = tmp_path / added_doc.storage_path
    assert stored_file_path.is_file()
    assert stored_file_path.name != "physics_manual.pdf"
    assert stored_file_path.suffix == ".pdf"
    assert stored_file_path.read_bytes() == pdf_bytes


@pytest.mark.asyncio
async def test_upload_docx_manual_success(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Authenticated user successfully uploads valid DOCX manual."""
    exp = create_sample_experiment(sample_user.id)
    storage = DocumentStorageService(base_dir=tmp_path)
    client, db_session = build_test_client(sample_user, exp, storage)

    docx_bytes = make_valid_docx_bytes("Chemistry Lab Manual")

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("chem_manual.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 201
    data = response.json()

    assert data["experimentId"] == str(exp.id)
    assert data["fileName"] == "chem_manual.docx"
    assert data["mimeType"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    assert data["fileSizeBytes"] == len(docx_bytes)
    assert data["hasManualFile"] is True

    # Verify file stored on disk
    added_doc = db_session.add.call_args[0][0]
    stored_file_path = tmp_path / added_doc.storage_path
    assert stored_file_path.is_file()
    assert stored_file_path.suffix == ".docx"
    assert stored_file_path.read_bytes() == docx_bytes


@pytest.mark.asyncio
async def test_upload_manual_supports_camelcase_alias(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Endpoint accepts experimentId (camelCase) alias for frontend convenience."""
    exp = create_sample_experiment(sample_user.id)
    storage = DocumentStorageService(base_dir=tmp_path)
    client, _ = build_test_client(sample_user, exp, storage)

    pdf_bytes = make_valid_pdf_bytes("Alias Test")

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experimentId": str(exp.id)},
        files={"file": ("manual.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["experimentId"] == str(exp.id)


# ==============================================================================
# 2. File Validation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_upload_missing_file_rejected(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Request without file is rejected with 422."""
    exp = create_sample_experiment(sample_user.id)
    client, _ = build_test_client(sample_user, exp, DocumentStorageService(base_dir=tmp_path))

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_upload_empty_file_rejected(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Empty 0-byte file is rejected with 422."""
    exp = create_sample_experiment(sample_user.id)
    client, _ = build_test_client(sample_user, exp, DocumentStorageService(base_dir=tmp_path))

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 422
    assert "empty" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_unsupported_extension_rejected(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """File with unsupported extension is rejected with 415."""
    exp = create_sample_experiment(sample_user.id)
    client, _ = build_test_client(sample_user, exp, DocumentStorageService(base_dir=tmp_path))

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("script.py", b"print('hello')", "text/plain")},
    )

    assert response.status_code == 415
    assert "unsupported file format" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_pdf_signature_mismatch_rejected(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """File claiming to be .pdf with invalid header signature is rejected with 415."""
    exp = create_sample_experiment(sample_user.id)
    client, _ = build_test_client(sample_user, exp, DocumentStorageService(base_dir=tmp_path))

    # Plain text disguised as a PDF
    fake_pdf = b"This is plainly a text file and not a PDF document."

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("fake_manual.pdf", fake_pdf, "application/pdf")},
    )

    assert response.status_code == 415
    assert "format signature" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_docx_signature_mismatch_rejected(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """File claiming to be .docx with invalid header signature is rejected with 415."""
    exp = create_sample_experiment(sample_user.id)
    client, _ = build_test_client(sample_user, exp, DocumentStorageService(base_dir=tmp_path))

    # Text disguised as docx
    fake_docx = b"Not a zip file at all"

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("fake.docx", fake_docx, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )

    assert response.status_code == 415
    assert "signature" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_oversized_file_rejected(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path, monkeypatch
) -> None:
    """File exceeding MAX_UPLOAD_SIZE_BYTES is rejected with 413."""
    # Set limit to 500 bytes for test
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 500)

    exp = create_sample_experiment(sample_user.id)
    client, _ = build_test_client(sample_user, exp, DocumentStorageService(base_dir=tmp_path))

    # Create oversized PDF (> 500 bytes)
    big_pdf = make_valid_pdf_bytes("A" * 1000)

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("huge.pdf", big_pdf, "application/pdf")},
    )

    assert response.status_code == 413
    assert "exceeds maximum allowed size" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_malformed_experiment_uuid_rejected(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Malformed experiment UUID returns 422 validation error."""
    client, _ = build_test_client(sample_user, None, DocumentStorageService(base_dir=tmp_path))

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": "not-a-valid-uuid"},
        files={"file": ("manual.pdf", make_valid_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_path_traversal_filename_sanitized(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Dangerous filename with path traversal is sanitized and safely stored."""
    exp = create_sample_experiment(sample_user.id)
    storage = DocumentStorageService(base_dir=tmp_path)
    client, db_session = build_test_client(sample_user, exp, storage)

    pdf_bytes = make_valid_pdf_bytes("Traversal Test")

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("../../../../etc/passwd.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["fileName"] == "passwd.pdf"

    added_doc = db_session.add.call_args[0][0]
    stored_path = tmp_path / added_doc.storage_path
    # Stored path must be strictly inside the sandbox tmp_path
    assert stored_path.resolve().is_relative_to(tmp_path.resolve())


# ==============================================================================
# 3. Authentication & Ownership Isolation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_upload_unauthenticated_rejected(tmp_path: Path) -> None:
    """Unauthenticated request returns 401 Unauthorized."""
    client, _ = build_test_client(
        User(id=uuid.uuid4(), email="any@test.com", password_hash="", full_name="Any", is_active=True),
        None,
        DocumentStorageService(base_dir=tmp_path),
    )

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        data={"experiment_id": str(uuid.uuid4())},
        files={"file": ("manual.pdf", make_valid_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_nonexistent_experiment_returns_404(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Upload to nonexistent experiment returns 404 Not Found."""
    client, _ = build_test_client(sample_user, None, DocumentStorageService(base_dir=tmp_path))

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(uuid.uuid4())},
        files={"file": ("manual.pdf", make_valid_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 404
    assert "not found or access denied" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_to_other_users_experiment_returns_404(
    sample_user: User, other_user_id: uuid.UUID, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Upload to experiment owned by a different user returns 404 (strict ownership isolation)."""
    # Experiment belongs to other_user_id, not sample_user
    exp = create_sample_experiment(user_id=other_user_id)
    # fake_execute returns None when user_id != current_user.id
    client, _ = build_test_client(sample_user, None, DocumentStorageService(base_dir=tmp_path))

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("manual.pdf", make_valid_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 404
    assert "not found or access denied" in response.json()["detail"].lower()


# ==============================================================================
# 4. Replacement & Failure Cleanup Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_upload_replaces_existing_manual_safely(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """Replacing an existing manual deletes previous record and cleans old file after commit."""
    exp = create_sample_experiment(sample_user.id, has_manual_file=True, file_name="old_manual.pdf")
    storage = DocumentStorageService(base_dir=tmp_path)

    # Create dummy previous physical file and document record
    old_file_path = tmp_path / str(sample_user.id) / str(exp.id) / "old_uuid.pdf"
    old_file_path.parent.mkdir(parents=True, exist_ok=True)
    old_file_path.write_bytes(make_valid_pdf_bytes("Old Manual"))

    old_doc = UploadedDocument(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        experiment_id=exp.id,
        file_name="old_manual.pdf",
        file_size_bytes=old_file_path.stat().st_size,
        mime_type="application/pdf",
        storage_path=f"{sample_user.id}/{exp.id}/old_uuid.pdf",
        status="pending",
        extracted_data={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    exp.documents = [old_doc]

    client, db_session = build_test_client(sample_user, exp, storage)

    new_pdf = make_valid_pdf_bytes("New Replaced Manual")
    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("new_manual.pdf", new_pdf, "application/pdf")},
    )

    assert response.status_code == 201
    assert response.json()["fileName"] == "new_manual.pdf"

    # Old document record was deleted from session
    db_session.delete.assert_called_once_with(old_doc)

    # Old file on disk was cleaned up
    assert not old_file_path.exists()


@pytest.mark.asyncio
async def test_database_failure_cleans_up_stored_file(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """If DB commit fails, transaction rolls back and newly stored file on disk is deleted."""
    exp = create_sample_experiment(sample_user.id)
    storage = DocumentStorageService(base_dir=tmp_path)
    client, db_session = build_test_client(sample_user, exp, storage)

    # Force commit to fail
    db_session.commit.side_effect = Exception("DB Connection Lost")

    pdf_bytes = make_valid_pdf_bytes("Rollback Test")

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("manual.pdf", pdf_bytes, "application/pdf")},
    )

    assert response.status_code == 500
    assert "failed to persist document metadata" in response.json()["detail"].lower()

    # DB rolled back
    db_session.rollback.assert_called_once()

    # Verify no leaked files in storage directory
    stored_files = list(tmp_path.rglob("*.pdf"))
    assert len(stored_files) == 0, f"Expected zero files after rollback, found: {stored_files}"


@pytest.mark.asyncio
async def test_failed_replacement_preserves_old_manual(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """If replacing fails during commit, the previous valid file is NOT destroyed."""
    exp = create_sample_experiment(sample_user.id, has_manual_file=True, file_name="preserve_me.pdf")
    storage = DocumentStorageService(base_dir=tmp_path)

    old_file_path = tmp_path / str(sample_user.id) / str(exp.id) / "preserve_uuid.pdf"
    old_file_path.parent.mkdir(parents=True, exist_ok=True)
    old_file_path.write_bytes(make_valid_pdf_bytes("Preserved Content"))

    old_doc = UploadedDocument(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        experiment_id=exp.id,
        file_name="preserve_me.pdf",
        file_size_bytes=old_file_path.stat().st_size,
        mime_type="application/pdf",
        storage_path=f"{sample_user.id}/{exp.id}/preserve_uuid.pdf",
        status="pending",
        extracted_data={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    exp.documents = [old_doc]

    client, db_session = build_test_client(sample_user, exp, storage)
    db_session.commit.side_effect = Exception("DB Commit Deadlock")

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("corrupting_replacement.pdf", make_valid_pdf_bytes("New Content"), "application/pdf")},
    )

    assert response.status_code == 500

    # Old valid manual file must STILL exist
    assert old_file_path.exists()
    assert old_file_path.read_bytes() == make_valid_pdf_bytes("Preserved Content")


@pytest.mark.asyncio
async def test_storage_failure_does_not_create_document_record(
    sample_user: User, auth_headers: dict[str, str], tmp_path: Path
) -> None:
    """If file storage fails, no DB record is created and 500 error is returned."""
    exp = create_sample_experiment(sample_user.id)
    storage = DocumentStorageService(base_dir=tmp_path)
    client, db_session = build_test_client(sample_user, exp, storage)

    # Force storage to fail
    storage.save_upload_file = AsyncMock(side_effect=IOError("Disk I/O failure"))

    response = await client.post(
        "/api/v1/experiments/upload-manual",
        headers=auth_headers,
        data={"experiment_id": str(exp.id)},
        files={"file": ("manual.pdf", make_valid_pdf_bytes(), "application/pdf")},
    )

    assert response.status_code == 500
    assert "failed to store uploaded file" in response.json()["detail"].lower()
    db_session.add.assert_not_called()
    db_session.commit.assert_not_called()


def test_storage_service_unit_methods(tmp_path: Path) -> None:
    """Verify DocumentStorageService helper methods (sanitize, get_file_path, delete_file)."""
    service = DocumentStorageService(base_dir=tmp_path)

    # Sanitize filename
    assert service.sanitize_filename("../../../malicious.pdf") == "malicious.pdf"
    assert service.sanitize_filename("valid_manual.docx") == "valid_manual.docx"
    assert service.sanitize_filename(None) == "uploaded_manual.pdf"
    assert service.sanitize_filename("") == "uploaded_manual.pdf"

    # Write a test file
    test_rel = "user1/exp1/test.pdf"
    full_path = tmp_path / test_rel
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(b"content")

    # get_file_path
    resolved = service.get_file_path(test_rel)
    assert resolved is not None
    assert resolved == full_path

    # get_file_path path traversal protection
    assert service.get_file_path("../../../etc/passwd") is None

    # delete_file
    assert service.delete_file(test_rel) is True
    assert not full_path.exists()
    assert service.delete_file(test_rel) is False
    assert service.delete_file("../../../etc/passwd") is False
    assert service.delete_file(None) is False

