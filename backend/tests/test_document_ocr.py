"""Unit and integration tests for Scanned Lab Manual OCR Fallback (TASK-11.3).

Verifies:
- OCR availability detection and graceful handling when native binaries are absent.
- Conservative image preprocessing (grayscale, contrast normalization).
- Digital PDF extraction priority (zero OCR overhead for digital manuals).
- OCR fallback for scanned/image-based PDFs.
- Mixed-document extraction: digital text preserved on text pages, OCR invoked only for textless pages.
- Resource safety: page limits, timeout handling, and temporary resource cleanup.
- Error reporting: explicit warnings without application crashes or fabricated text.
- Transactional persistence and API endpoint integration.
"""

from datetime import datetime, timezone
import io
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import httpx
from PIL import Image, ImageDraw
import pypdf
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import create_app
from app.modules.auth.models import User
from app.modules.documents.extractor import (
    DocumentExtractorService,
    ExtractionStatusEnum,
    get_extractor_service,
)
from app.modules.documents.models import UploadedDocument
from app.modules.documents.ocr import (
    MockOCREngine,
    OCREngineUnavailableError,
    OCRProcessingError,
    OCRService,
    OCRTimeoutError,
    TesseractOCREngine,
    get_ocr_service,
)
from app.modules.documents.schemas import DocumentStatusEnum
from app.modules.documents.storage import DocumentStorageService, get_storage_service
from app.modules.experiments.models import Experiment, PreparationChecklist


# ---------------------------------------------------------------------------
# Synthetic Test Fixtures Generators
# ---------------------------------------------------------------------------


def make_synthetic_pdf(
    page_texts: list[str],
    encrypted: bool = False,
    password: str = "secret123",
) -> bytes:
    """Create a valid in-memory PDF with the provided page texts."""
    writer = pypdf.PdfWriter()
    for text in page_texts:
        if not text:
            # Blank page simulating scanned image without text layer
            writer.add_blank_page(width=612, height=792)
            continue

        clean_text = text.replace("(", "").replace(")", "")
        stream_str = f"BT /F1 12 Tf 72 712 Td ({clean_text}) Tj ET"
        stream_bytes = stream_str.encode("latin-1", errors="replace")
        length = len(stream_bytes)
        raw_pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
            + f"4 0 obj << /Length {length} >> stream\n".encode("latin-1")
            + stream_bytes
            + b"\nendstream\nendobj\n"
            b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
            b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
            b"0000000115 00000 n \n0000000266 00000 n \n0000000360 00000 n \n"
            b"trailer << /Size 6 /Root 1 0 R >>\nstartxref\n441\n%%EOF\n"
        )
        r = pypdf.PdfReader(io.BytesIO(raw_pdf))
        writer.add_page(r.pages[0])

    if encrypted:
        writer.encrypt(password)

    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sample_user(sample_user_id: uuid.UUID) -> User:
    now = datetime.now(timezone.utc)
    return User(
        id=sample_user_id,
        email="labuser@university.edu",
        password_hash="$argon2id$v=19$m=65536,t=3,p=4$somehash",
        full_name="Lab Student",
        university="University",
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
    title: str = "Scanned Manual Experiment",
    has_manual_file: bool = True,
    file_name: Optional[str] = "scanned.pdf",
) -> Experiment:
    """Helper to instantiate an Experiment ORM model with checklist."""
    now = datetime.now(timezone.utc)
    actual_exp_id = exp_id or uuid.uuid4()
    exp = Experiment(
        id=actual_exp_id,
        user_id=user_id,
        title=title,
        subject="Physics",
        experiment_number="PHY-103",
        course_semester="Semester 3",
        creation_method="upload",
        has_manual_file=has_manual_file,
        file_name=file_name,
        status="ready",
        created_at=now,
        updated_at=now,
    )
    chk = PreparationChecklist(
        id=uuid.uuid4(),
        experiment_id=actual_exp_id,
        items={"objective": False, "theory": False, "apparatus": False, "procedure": False, "precautions": False},
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
    document: Optional[UploadedDocument] = None,
    storage_service: Optional[DocumentStorageService] = None,
    extractor_service: Optional[DocumentExtractorService] = None,
) -> tuple[httpx.AsyncClient, AsyncMock]:
    """Build test client with mocked DB session and dependency overrides."""
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
        elif "from uploaded_documents" in stmt_str:
            res.scalar_one_or_none.return_value = document
        else:
            res.scalar_one_or_none.return_value = None
            res.scalars.return_value.all.return_value = []

        return res

    db_session.execute = AsyncMock(side_effect=fake_execute)

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    if storage_service is not None:
        app.dependency_overrides[get_storage_service] = lambda: storage_service
    if extractor_service is not None:
        app.dependency_overrides[get_extractor_service] = lambda: extractor_service

    transport = httpx.ASGITransport(app=app)
    client = httpx.AsyncClient(transport=transport, base_url="http://test")
    return client, db_session


# ---------------------------------------------------------------------------
# OCR Unit Tests
# ---------------------------------------------------------------------------


def test_ocr_service_availability_check():
    """Verify is_available accurately reports engine readiness."""
    mock_avail = MockOCREngine(available=True)
    svc_avail = OCRService(engine=mock_avail)
    avail, reason = svc_avail.is_available()
    assert avail is True
    assert reason is None

    mock_unavail = MockOCREngine(available=False)
    svc_unavail = OCRService(engine=mock_unavail)
    avail, reason = svc_unavail.is_available()
    assert avail is False
    assert "unavailable" in reason.lower()


def test_ocr_service_preprocesses_image_conservatively():
    """Verify grayscale conversion and contrast normalization."""
    img = Image.new("RGB", (100, 100), color=(200, 100, 50))
    svc = OCRService(engine=MockOCREngine())
    processed = svc.preprocess_image(img)

    assert processed.mode == "L"
    assert processed.size == (100, 100)


def test_ocr_service_returns_text_for_valid_image():
    """Verify text extraction from a single image."""
    engine = MockOCREngine(default_text="Observed Focal Length: f = 15.2 ± 0.1 cm")
    svc = OCRService(engine=engine)

    test_img = Image.new("RGB", (200, 50), color=(255, 255, 255))
    text = svc.ocr_image(test_img)

    assert "Observed Focal Length: f = 15.2 ± 0.1 cm" in text


def test_ocr_service_handles_empty_output():
    """Verify OCR engine returning blank text is handled without errors."""
    engine = MockOCREngine(default_text="   \n\n  ")
    svc = OCRService(engine=engine)

    test_img = Image.new("RGB", (200, 50), color=(255, 255, 255))
    text = svc.ocr_image(test_img)

    assert text == ""


def test_ocr_service_handles_unavailable_engine():
    """Verify unavailable engine reports warning and skips rendering."""
    engine = MockOCREngine(available=False)
    svc = OCRService(engine=engine)

    results, warnings = svc.ocr_pdf_pages(Path("/dummy.pdf"), [1, 2])
    assert len(results) == 0
    assert any("not be executed" in w for w in warnings)
    assert len(engine.rendered_pages) == 0


def test_ocr_service_handles_timeout_safely():
    """Verify OCR timeout on a page records warning and produces safe empty result."""
    engine = MockOCREngine(raise_timeout=True)
    svc = OCRService(engine=engine)

    results, warnings = svc.ocr_pdf_pages(Path("/dummy.pdf"), [1])
    assert 1 in results
    assert results[1].has_text is False
    assert any("timeout" in w.lower() for w in warnings)


def test_ocr_service_handles_processing_error_safely():
    """Verify processing error on a page records warning and continues."""
    engine = MockOCREngine(raise_error=True)
    svc = OCRService(engine=engine)

    results, warnings = svc.ocr_pdf_pages(Path("/dummy.pdf"), [1])
    assert 1 in results
    assert results[1].has_text is False
    assert any("error" in w.lower() for w in warnings)


def test_ocr_service_page_limits_respected():
    """Verify that requested pages beyond max_pages are bounded."""
    engine = MockOCREngine(default_text="Page Content")
    svc = OCRService(engine=engine)

    results, warnings = svc.ocr_pdf_pages(Path("/dummy.pdf"), [1, 2, 3, 4, 5], max_pages=2)
    assert len(results) == 2
    assert 1 in results
    assert 2 in results
    assert 3 not in results
    assert any("limit (2) exceeded" in w for w in warnings)


# ---------------------------------------------------------------------------
# PDF Integration & Fallback Priority Tests
# ---------------------------------------------------------------------------


def test_digital_pdf_uses_existing_path_without_ocr():
    """Case A: Digital PDF with usable text extracts without invoking OCR engine."""
    mock_ocr = MockOCREngine(default_text="Should never be called")
    ocr_service = OCRService(engine=mock_ocr)
    extractor = DocumentExtractorService(ocr_service=ocr_service)

    pdf_bytes = make_synthetic_pdf([
        "Physics Lab Manual: Measurement of Gravitational Acceleration using Simple Pendulum with length L = 100cm."
    ])
    result = extractor.extract_from_bytes(pdf_bytes, "digital.pdf")

    assert result.status == ExtractionStatusEnum.SUCCESS
    assert "Simple Pendulum" in result.extracted_text
    assert result.metadata.get("ocr_applied") is False
    assert len(mock_ocr.rendered_pages) == 0  # Zero OCR calls


def test_scanned_pdf_invokes_ocr_fallback():
    """Case B: Scanned PDF with no digital text invokes OCR fallback on all pages."""
    mock_ocr = MockOCREngine(default_text="OCR Recovered: Apparatus - Spectrometer, Sodium Lamp, Glass Prism.")
    ocr_service = OCRService(engine=mock_ocr)
    extractor = DocumentExtractorService(ocr_service=ocr_service)

    # 2 textless / blank pages simulating a scanned document
    pdf_bytes = make_synthetic_pdf(["", ""])
    result = extractor.extract_from_bytes(pdf_bytes, "scanned.pdf")

    assert result.status == ExtractionStatusEnum.SUCCESS
    assert "OCR Recovered: Apparatus" in result.extracted_text
    assert result.metadata.get("ocr_applied") is True
    assert result.metadata.get("ocr_pages") == [1, 2]
    assert len(result.pages) == 2
    assert result.pages[0].ocr_applied is True
    assert result.pages[1].ocr_applied is True
    assert len(mock_ocr.rendered_pages) == 2


def test_mixed_pdf_invokes_ocr_only_for_textless_pages():
    """Case C: Mixed PDF preserves digital pages and invokes OCR only for textless pages."""
    mock_ocr = MockOCREngine(default_text="OCR Page 2: Table of Deviations and Observations.")
    ocr_service = OCRService(engine=mock_ocr)
    extractor = DocumentExtractorService(ocr_service=ocr_service)

    # Page 1 has digital text; Page 2 is scanned (blank)
    pdf_bytes = make_synthetic_pdf([
        "Page 1 Digital Text: Theory of Refraction through Glass Prism.",
        "",
    ])
    result = extractor.extract_from_bytes(pdf_bytes, "mixed.pdf")

    assert result.status == ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
    assert "Page 1 Digital Text: Theory" in result.extracted_text
    assert "OCR Page 2: Table of Deviations" in result.extracted_text
    assert result.metadata.get("ocr_applied") is True
    assert result.metadata.get("ocr_pages") == [2]
    assert result.metadata.get("digital_pages") == [1]

    # Page 1 kept digital, Page 2 applied OCR
    assert result.pages[0].ocr_applied is False
    assert result.pages[1].ocr_applied is True
    assert mock_ocr.rendered_pages == [2]  # Only page 2 rendered for OCR!
    assert any("mixed document" in w.lower() for w in result.warnings)


def test_ocr_failure_produces_explicit_no_text_status():
    """Case D: When OCR produces no text on a scanned document, explicit NO_TEXT_FOUND is returned."""
    mock_ocr = MockOCREngine(default_text="")
    ocr_service = OCRService(engine=mock_ocr)
    extractor = DocumentExtractorService(ocr_service=ocr_service)

    pdf_bytes = make_synthetic_pdf(["", ""])
    result = extractor.extract_from_bytes(pdf_bytes, "empty_scanned.pdf")

    assert result.status == ExtractionStatusEnum.NO_TEXT_FOUND
    assert result.extracted_text == ""
    assert result.character_count == 0


def test_ocr_engine_unavailable_on_scanned_pdf_reports_safe_warning():
    """Case E: Unavailable OCR engine on scanned PDF returns NO_TEXT_FOUND with clear warning without crashing."""
    mock_ocr = MockOCREngine(available=False)
    ocr_service = OCRService(engine=mock_ocr)
    extractor = DocumentExtractorService(ocr_service=ocr_service)

    pdf_bytes = make_synthetic_pdf([""])
    result = extractor.extract_from_bytes(pdf_bytes, "scanned_no_engine.pdf")

    assert result.status == ExtractionStatusEnum.NO_TEXT_FOUND
    assert any("could not be executed" in w for w in result.warnings)


def test_ocr_engine_unavailable_on_mixed_pdf_preserves_digital_pages():
    """Case E: Unavailable OCR engine on mixed PDF preserves digital pages safely."""
    mock_ocr = MockOCREngine(available=False)
    ocr_service = OCRService(engine=mock_ocr)
    extractor = DocumentExtractorService(ocr_service=ocr_service)

    pdf_bytes = make_synthetic_pdf([
        "Page 1: Digital text preserved despite OCR engine being absent.",
        "",
    ])
    result = extractor.extract_from_bytes(pdf_bytes, "mixed_no_engine.pdf")

    assert result.status == ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
    assert "Digital text preserved" in result.extracted_text
    assert any("could not be executed" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# API Route & Database Persistence Integration Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extract_endpoint_persists_scanned_pdf_ocr_results(
    sample_user: User,
    auth_headers: dict[str, str],
    tmp_path: Path,
):
    """Verify POST /api/v1/experiments/{id}/extract-text persists OCR results into UploadedDocument."""
    exp = create_sample_experiment(sample_user.id, has_manual_file=True, file_name="scanned_manual.pdf")
    storage = DocumentStorageService(base_dir=tmp_path)
    mock_ocr = MockOCREngine(default_text="OCR Extracted Lab Manual: Procedure and Precautions.")
    ocr_service = OCRService(engine=mock_ocr)
    extractor = DocumentExtractorService(storage_service=storage, ocr_service=ocr_service)

    # Scanned PDF file on disk
    pdf_bytes = make_synthetic_pdf([""])
    user_dir = tmp_path / str(sample_user.id) / str(exp.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "manual.pdf").write_bytes(pdf_bytes)

    rel_path = f"{sample_user.id}/{exp.id}/manual.pdf"
    doc = UploadedDocument(
        id=uuid.uuid4(),
        user_id=sample_user.id,
        experiment_id=exp.id,
        file_name="scanned_manual.pdf",
        file_size_bytes=len(pdf_bytes),
        mime_type="application/pdf",
        storage_path=rel_path,
        status=DocumentStatusEnum.PENDING.value,
        extracted_text=None,
        extracted_data={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    exp.documents = [doc]

    client, db_mock = build_test_client(
        sample_user=sample_user,
        experiment=exp,
        document=doc,
        storage_service=storage,
        extractor_service=extractor,
    )

    resp = await client.post(
        f"/api/v1/experiments/{exp.id}/extract-text",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["sourceFileType"] == "pdf"
    assert "OCR Extracted Lab Manual: Procedure and Precautions." in data["extractedText"]
    assert data["status"] == "success"
    assert data["metadata"]["ocr_applied"] is True

    # Confirm DB persistence updates
    assert doc.status == DocumentStatusEnum.COMPLETED.value
    assert "OCR Extracted Lab Manual" in doc.extracted_text
    assert doc.extracted_data.get("ocr_applied") is True
    assert db_mock.commit.called
