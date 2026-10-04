"""Digital Document Text Extraction Service.

Provides robust, modular text extraction for digital PDF and DOCX laboratory manuals:
- Digital PDF extraction via pypdf with per-page tracking and encryption detection.
- DOCX extraction via python-docx with paragraph order, headings, and table conversion.
- Conservative text normalization preserving mathematical symbols, scientific notation, and layout.
- Scanned / textless document detection without silent failure.
- Transactional metadata persistence to UploadedDocument models.
"""

from datetime import datetime, timezone
import io
import logging
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Optional
import uuid
import zipfile

import docx
from docx.table import Table
from docx.text.paragraph import Paragraph
import pypdf
import pypdf.errors
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.modules.documents.models import UploadedDocument
from app.modules.documents.schemas import (
    DocumentExtractionResult,
    DocumentStatusEnum,
    ExtractedPage,
    ExtractionStatusEnum,
)
from app.modules.documents.storage import DocumentStorageService, get_storage_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------


class DocumentExtractionError(Exception):
    """Base exception for document extraction failures."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DocumentFileNotFoundError(DocumentExtractionError):
    """Raised when the document file cannot be located on the filesystem."""


class DocumentEncryptedError(DocumentExtractionError):
    """Raised when the document is encrypted and cannot be accessed."""


class DocumentCorruptedError(DocumentExtractionError):
    """Raised when the document file structure is malformed or corrupted."""


class DocumentUnsupportedFormatError(DocumentExtractionError):
    """Raised when an unsupported document format is provided."""


class DocumentNoTextError(DocumentExtractionError):
    """Raised when no extractable digital text is found in the document."""


# ---------------------------------------------------------------------------
# Text Normalization
# ---------------------------------------------------------------------------


class TextNormalizer:
    """Conservative text normalizer preserving mathematical symbols, scientific notation, and layout."""

    @staticmethod
    def normalize(text: str) -> str:
        """Normalize line endings, remove excess whitespace, and preserve paragraph structure.
        
        Preserves:
        - Mathematical symbols (e.g., ±, ², ³, Δ, μ, °, ×, ÷, ≤, ≥, π, Ω, √)
        - Scientific notation (e.g., 1.5 x 10^-3, 9.81 m/s²)
        - Units and formulas (e.g., g/cm³, ΔV = IR, °C)
        - Paragraph and section separation
        - Table layouts
        """
        if not text:
            return ""

        # 1. Normalize line endings (\r\n and \r -> \n)
        cleaned = text.replace("\r\n", "\n").replace("\r", "\n")

        # 2. Split lines and strip trailing whitespace on each line
        lines = [re.sub(r"[ \t]+$", "", line) for line in cleaned.split("\n")]

        # 3. Clean up intra-line whitespace while preserving table pipes
        processed_lines: list[str] = []
        for line in lines:
            if "|" in line:
                # Retain markdown table rows with whitespace stripped from outer edges
                processed_lines.append(line.strip())
            else:
                # Collapse 2+ horizontal spaces to a single space
                collapsed = re.sub(r"[ \t]{2,}", " ", line)
                processed_lines.append(collapsed.strip())

        reconstructed = "\n".join(processed_lines)

        # 4. Collapse 3+ consecutive newlines to exactly 2 (\n\n) to preserve paragraph/section separation
        reconstructed = re.sub(r"\n{3,}", "\n\n", reconstructed)

        # 5. Strip leading and trailing whitespace from entire document
        return reconstructed.strip()


# ---------------------------------------------------------------------------
# Document Extractor Service
# ---------------------------------------------------------------------------


class DocumentExtractorService:
    """Modular digital text extraction service for PDF and DOCX laboratory manuals."""

    def __init__(
        self,
        storage_service: Optional[DocumentStorageService] = None,
        normalizer: Optional[TextNormalizer] = None,
        ocr_service: Optional[Any] = None,
    ) -> None:
        self.storage_service = storage_service or get_storage_service()
        self.normalizer = normalizer or TextNormalizer()
        if ocr_service is None:
            from app.modules.documents.ocr import get_ocr_service
            self.ocr_service = get_ocr_service()
        else:
            self.ocr_service = ocr_service

    def _table_to_markdown(self, table: Table) -> str:
        """Convert a python-docx Table into clean Markdown table format."""
        rows_data: list[list[str]] = []
        for row in table.rows:
            row_cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
            # Include row if at least one cell has content
            if any(row_cells):
                rows_data.append(row_cells)

        if not rows_data:
            return ""

        max_cols = max(len(r) for r in rows_data)
        if max_cols == 0:
            return ""

        # Normalize column count across all rows
        normalized_rows = [r + [""] * (max_cols - len(r)) for r in rows_data]

        lines: list[str] = []
        header = normalized_rows[0]
        lines.append("| " + " | ".join(header) + " |")
        lines.append("| " + " | ".join(["---"] * max_cols) + " |")
        for row in normalized_rows[1:]:
            lines.append("| " + " | ".join(row) + " |")

        return "\n".join(lines)

    def _extract_pdf_stream(
        self,
        stream: Any,
        pdf_path: Optional[Path] = None,
        raw_bytes: Optional[bytes] = None,
        document_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> DocumentExtractionResult:
        """Extract text from an open PDF stream, invoking OCR on textless pages when necessary."""
        warnings: list[str] = []
        pages_data: list[ExtractedPage] = []
        raw_page_texts: list[str] = []

        try:
            reader = pypdf.PdfReader(stream)
        except pypdf.errors.PdfReadError as e:
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type="pdf",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.CORRUPTED,
                warnings=[],
                failure_reason=f"Corrupted or invalid PDF structure: {str(e)}",
            )
        except Exception as e:
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type="pdf",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.CORRUPTED,
                warnings=[],
                failure_reason=f"Failed to read PDF document: {str(e)}",
            )

        # Check for encrypted PDF
        if reader.is_encrypted:
            try:
                decrypt_res = reader.decrypt("")
                if decrypt_res == 0:
                    return DocumentExtractionResult(
                        document_id=document_id,
                        experiment_id=experiment_id,
                        source_file_type="pdf",
                        extracted_text="",
                        page_count=len(reader.pages) if hasattr(reader, "pages") else 0,
                        character_count=0,
                        status=ExtractionStatusEnum.ENCRYPTED,
                        warnings=[],
                        failure_reason="PDF document is password-protected and encrypted.",
                    )
            except Exception:
                return DocumentExtractionResult(
                    document_id=document_id,
                    experiment_id=experiment_id,
                    source_file_type="pdf",
                    extracted_text="",
                    page_count=0,
                    character_count=0,
                    status=ExtractionStatusEnum.ENCRYPTED,
                    warnings=[],
                    failure_reason="PDF document is encrypted.",
                )

        total_pages = len(reader.pages)
        if total_pages == 0:
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type="pdf",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.NO_TEXT_FOUND,
                warnings=["PDF contains zero pages."],
                failure_reason="Document has 0 pages.",
            )

        max_pages = settings.DOCUMENT_MAX_EXTRACT_PAGES
        pages_to_process = min(total_pages, max_pages)
        if total_pages > max_pages:
            warnings.append(
                f"Document exceeds maximum page extraction limit ({max_pages}). "
                f"Only the first {max_pages} of {total_pages} pages were processed."
            )

        for idx in range(pages_to_process):
            page = reader.pages[idx]
            page_num = idx + 1
            try:
                raw_text = page.extract_text() or ""
            except Exception as page_err:
                warnings.append(f"Failed to extract text from page {page_num}: {str(page_err)}")
                raw_text = ""

            normalized_page = self.normalizer.normalize(raw_text)
            has_text = bool(normalized_page.strip())
            char_count = len(normalized_page)

            pages_data.append(
                ExtractedPage(
                    page_number=page_num,
                    text=normalized_page,
                    character_count=char_count,
                    has_text=has_text,
                    ocr_applied=False,
                )
            )

        # -------------------------------------------------------------------
        # OCR Fallback Phase: Apply OCR to textless pages when configured
        # -------------------------------------------------------------------
        textless_page_numbers = [p.page_number for p in pages_data if not p.has_text]
        has_digital_pages = any(p.has_text for p in pages_data)
        ocr_applied_pages: list[int] = []

        if textless_page_numbers and settings.OCR_ENABLED:
            effective_path: Optional[Path] = pdf_path
            tmp_file = None

            try:
                if effective_path is None or not effective_path.is_file():
                    if raw_bytes is None:
                        if hasattr(stream, "seek") and hasattr(stream, "read"):
                            try:
                                stream.seek(0)
                                raw_bytes = stream.read()
                            except Exception:
                                raw_bytes = None

                    if raw_bytes:
                        tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                        tmp_file.write(raw_bytes)
                        tmp_file.flush()
                        effective_path = Path(tmp_file.name)

                if effective_path and effective_path.is_file():
                    ocr_results, ocr_warnings = self.ocr_service.ocr_pdf_pages(
                        pdf_path=effective_path,
                        page_numbers=textless_page_numbers,
                    )
                    warnings.extend(ocr_warnings)

                    for page_num, ocr_page in ocr_results.items():
                        for idx, p in enumerate(pages_data):
                            if p.page_number == page_num:
                                if ocr_page.has_text:
                                    pages_data[idx] = ocr_page
                                    ocr_applied_pages.append(page_num)
                                break
                else:
                    warnings.append(
                        "OCR fallback could not be executed: Unable to access PDF bytes for page rendering."
                    )
            finally:
                if tmp_file is not None:
                    try:
                        tmp_file.close()
                        os.unlink(tmp_file.name)
                    except Exception:
                        pass
        elif textless_page_numbers and not settings.OCR_ENABLED:
            warnings.append("OCR fallback is disabled (OCR_ENABLED=False); scanned pages were not processed.")

        # Reconstruct full text in exact original page sequence
        raw_page_texts = [p.text for p in pages_data if p.has_text]
        full_extracted_text = "\n\n".join(raw_page_texts).strip()
        total_chars = len(full_extracted_text)

        metadata: dict[str, Any] = {
            "processed_pages": pages_to_process,
            "total_pages": total_pages,
            "ocr_applied": bool(ocr_applied_pages),
            "ocr_pages": ocr_applied_pages,
            "digital_pages": [p.page_number for p in pages_data if p.has_text and not p.ocr_applied],
        }

        # Status & Warning Determination
        if total_chars == 0:
            status = ExtractionStatusEnum.NO_TEXT_FOUND
            scanned_warn = (
                "No extractable digital text found in PDF. "
                "The document may be a scanned image or contain non-text pages requiring OCR."
            )
            if scanned_warn not in warnings:
                warnings.append(scanned_warn)
        elif ocr_applied_pages:
            if has_digital_pages:
                # Case C: Mixed PDF
                status = ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
                warnings.append(
                    f"Mixed document detected: OCR applied to {len(ocr_applied_pages)} scanned page(s)."
                )
            else:
                # Case B: Pure Scanned PDF
                if total_chars >= settings.DOCUMENT_MIN_TEXT_CHARS:
                    status = ExtractionStatusEnum.SUCCESS
                    warnings.append(
                        f"Scanned document detected: text recovered via OCR fallback for {len(ocr_applied_pages)} page(s)."
                    )
                else:
                    status = ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
                    warnings.append(
                        f"Scanned document detected: low text yield ({total_chars} characters) via OCR fallback."
                    )
        elif total_chars < settings.DOCUMENT_MIN_TEXT_CHARS:
            status = ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
            warnings.append(
                f"Extracted very little digital text ({total_chars} characters). "
                "The document may be partially scanned or image-based."
            )
        elif warnings:
            status = ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
        else:
            # Case A: Digital PDF
            status = ExtractionStatusEnum.SUCCESS

        return DocumentExtractionResult(
            document_id=document_id,
            experiment_id=experiment_id,
            source_file_type="pdf",
            extracted_text=full_extracted_text,
            page_count=total_pages,
            character_count=total_chars,
            status=status,
            warnings=warnings,
            failure_reason=None if status != ExtractionStatusEnum.FAILED else "Extraction failed.",
            pages=pages_data,
            metadata=metadata,
        )

    def _extract_docx_stream(
        self,
        stream: Any,
        document_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> DocumentExtractionResult:
        """Extract text from an open DOCX stream."""
        warnings: list[str] = []
        blocks_data: list[str] = []

        try:
            doc = docx.Document(stream)
        except (zipfile.BadZipFile, docx.opc.exceptions.PackageNotFoundError) as e:
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type="docx",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.CORRUPTED,
                warnings=[],
                failure_reason=f"Corrupted or invalid DOCX document: {str(e)}",
            )
        except Exception as e:
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type="docx",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.CORRUPTED,
                warnings=[],
                failure_reason=f"Failed to read DOCX document: {str(e)}",
            )

        section_count = len(doc.sections)

        # Iterate through document body children in order to preserve paragraph and table sequence
        try:
            for child in doc.element.body:
                if child.tag.endswith("p"):
                    p = Paragraph(child, doc)
                    raw_text = p.text
                    if not raw_text.strip():
                        continue

                    # Preserve headings
                    style_name = (p.style.name if p.style and p.style.name else "").lower()
                    if "heading 1" in style_name or "title" in style_name:
                        formatted_text = f"# {raw_text.strip()}"
                    elif "heading 2" in style_name:
                        formatted_text = f"## {raw_text.strip()}"
                    elif "heading 3" in style_name:
                        formatted_text = f"### {raw_text.strip()}"
                    elif "heading" in style_name:
                        formatted_text = f"#### {raw_text.strip()}"
                    else:
                        formatted_text = raw_text.strip()

                    blocks_data.append(formatted_text)

                elif child.tag.endswith("tbl"):
                    tbl = Table(child, doc)
                    tbl_md = self._table_to_markdown(tbl)
                    if tbl_md.strip():
                        blocks_data.append(tbl_md)
        except Exception as err:
            warnings.append(f"Encountered error while reading document elements: {str(err)}")

        combined_raw = "\n\n".join(blocks_data)
        normalized_text = self.normalizer.normalize(combined_raw)
        total_chars = len(normalized_text)

        # DOCX does not have fixed pages; represent structural unit as block
        pages_data = [
            ExtractedPage(
                page_number=1,
                text=normalized_text,
                character_count=total_chars,
                has_text=bool(normalized_text.strip()),
            )
        ]

        if total_chars == 0:
            status = ExtractionStatusEnum.NO_TEXT_FOUND
            warnings.append("No extractable text or tables found in DOCX document.")
        elif total_chars < settings.DOCUMENT_MIN_TEXT_CHARS:
            status = ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
            warnings.append(
                f"Extracted very little text ({total_chars} characters) from DOCX document."
            )
        elif warnings:
            status = ExtractionStatusEnum.SUCCESS_WITH_WARNINGS
        else:
            status = ExtractionStatusEnum.SUCCESS

        return DocumentExtractionResult(
            document_id=document_id,
            experiment_id=experiment_id,
            source_file_type="docx",
            extracted_text=normalized_text,
            page_count=section_count or 1,
            character_count=total_chars,
            status=status,
            warnings=warnings,
            failure_reason=None if status != ExtractionStatusEnum.FAILED else "DOCX extraction failed.",
            pages=pages_data,
            metadata={"blocks_count": len(blocks_data), "section_count": section_count},
        )

    def extract_from_path(
        self,
        file_path: Path | str,
        document_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> DocumentExtractionResult:
        """Extract text from a document on disk with format detection and safe file closing."""
        path = Path(file_path).resolve()
        if not path.is_file():
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type="unknown",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.FAILED,
                warnings=[],
                failure_reason="Source file does not exist on disk.",
            )

        ext = path.suffix.lower()
        if ext == ".pdf":
            try:
                with open(path, "rb") as f:
                    return self._extract_pdf_stream(
                        f,
                        pdf_path=path,
                        document_id=document_id,
                        experiment_id=experiment_id,
                    )
            except Exception as e:
                return DocumentExtractionResult(
                    document_id=document_id,
                    experiment_id=experiment_id,
                    source_file_type="pdf",
                    extracted_text="",
                    page_count=0,
                    character_count=0,
                    status=ExtractionStatusEnum.FAILED,
                    warnings=[],
                    failure_reason=f"Failed to access PDF file: {str(e)}",
                )
        elif ext == ".docx":
            try:
                with open(path, "rb") as f:
                    return self._extract_docx_stream(
                        f,
                        document_id=document_id,
                        experiment_id=experiment_id,
                    )
            except Exception as e:
                return DocumentExtractionResult(
                    document_id=document_id,
                    experiment_id=experiment_id,
                    source_file_type="docx",
                    extracted_text="",
                    page_count=0,
                    character_count=0,
                    status=ExtractionStatusEnum.FAILED,
                    warnings=[],
                    failure_reason=f"Failed to access DOCX file: {str(e)}",
                )
        else:
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type=ext.lstrip(".") or "unknown",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.UNSUPPORTED,
                warnings=[],
                failure_reason=f"Unsupported document format '{ext}'. Only .pdf and .docx are supported.",
            )

    def extract_from_bytes(
        self,
        content: bytes,
        file_name_or_ext: str,
        document_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> DocumentExtractionResult:
        """Extract text from in-memory document bytes."""
        ext = Path(file_name_or_ext).suffix.lower()
        if not ext and file_name_or_ext.startswith("."):
            ext = file_name_or_ext.lower()

        if ext == ".pdf":
            stream = io.BytesIO(content)
            return self._extract_pdf_stream(
                stream,
                raw_bytes=content,
                document_id=document_id,
                experiment_id=experiment_id,
            )
        elif ext == ".docx":
            stream = io.BytesIO(content)
            return self._extract_docx_stream(
                stream,
                document_id=document_id,
                experiment_id=experiment_id,
            )
        else:
            return DocumentExtractionResult(
                document_id=document_id,
                experiment_id=experiment_id,
                source_file_type=ext.lstrip(".") or "unknown",
                extracted_text="",
                page_count=0,
                character_count=0,
                status=ExtractionStatusEnum.UNSUPPORTED,
                warnings=[],
                failure_reason=f"Unsupported format '{ext}'. Only .pdf and .docx are supported.",
            )

    async def extract_document_and_persist(
        self,
        db: AsyncSession,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> DocumentExtractionResult:
        """Retrieve an uploaded document by ID, verify user ownership, extract text, and persist results."""
        query = select(UploadedDocument).where(
            UploadedDocument.id == document_id,
            UploadedDocument.user_id == user_id,
        )
        res = await db.execute(query)
        doc = res.scalar_one_or_none()

        if not doc:
            raise DocumentExtractionError("Document not found or access denied.")

        # Resolve storage path
        file_path = self.storage_service.get_file_path(doc.storage_path)
        if not file_path:
            doc.status = DocumentStatusEnum.FAILED.value
            doc.error_message = "Document file not found in storage."
            doc.updated_at = datetime.now(timezone.utc)
            await db.commit()
            raise DocumentFileNotFoundError("Document file not found in storage.")

        # Update status to processing
        doc.status = DocumentStatusEnum.PROCESSING.value
        doc.updated_at = datetime.now(timezone.utc)
        await db.commit()

        # Execute extraction
        result = self.extract_from_path(
            file_path=file_path,
            document_id=doc.id,
            experiment_id=doc.experiment_id,
        )

        # Persist results transactionally
        now = datetime.now(timezone.utc)
        if result.status in (
            ExtractionStatusEnum.SUCCESS,
            ExtractionStatusEnum.SUCCESS_WITH_WARNINGS,
            ExtractionStatusEnum.NO_TEXT_FOUND,
        ):
            doc.status = DocumentStatusEnum.COMPLETED.value
            doc.extracted_text = result.extracted_text
            doc.error_message = None
        else:
            doc.status = DocumentStatusEnum.FAILED.value
            doc.extracted_text = None
            doc.error_message = result.failure_reason

        doc.extracted_data = {
            "source_file_type": result.source_file_type,
            "page_count": result.page_count,
            "character_count": result.character_count,
            "extraction_status": result.status.value,
            "ocr_applied": result.metadata.get("ocr_applied", False),
            "warnings": result.warnings,
            "failure_reason": result.failure_reason,
            "pages": [p.model_dump(by_alias=True) for p in result.pages],
            "metadata": result.metadata,
        }
        doc.updated_at = now

        await db.commit()
        await db.refresh(doc)
        return result


# Global extractor service instance
default_extractor_service = DocumentExtractorService()


def get_extractor_service() -> DocumentExtractorService:
    """FastAPI dependency provider for DocumentExtractorService."""
    return default_extractor_service
