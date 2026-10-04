"""Optical Character Recognition (OCR) Engine for Scanned Lab Manuals.

Provides fallback OCR extraction for scanned and image-based PDF manuals:
- Detects availability of native Tesseract and Poppler binaries.
- Incremental, page-by-page rendering via pdf2image to prevent excessive memory usage.
- Conservative image preprocessing (grayscale, contrast normalization) via Pillow.
- Modular engine interface (BaseOCREngine, TesseractOCREngine, MockOCREngine)
  enabling deterministic testing on runners without native OCR tools.
- Resource safety and temporary file cleanup.
"""

from abc import ABC, abstractmethod
import io
import logging
from pathlib import Path
import shutil
from typing import Any, Optional

import pdf2image
import pdf2image.exceptions
from PIL import Image, ImageOps
import pytesseract

from app.core.config import settings
from app.modules.documents.extractor import DocumentExtractionError, TextNormalizer
from app.modules.documents.schemas import ExtractedPage

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------


class OCRError(DocumentExtractionError):
    """Base exception for optical character recognition errors."""


class OCREngineUnavailableError(OCRError):
    """Raised when native OCR binaries (Tesseract or Poppler) are missing or disabled."""


class OCRTimeoutError(OCRError):
    """Raised when OCR processing exceeds the configured timeout."""


class OCRProcessingError(OCRError):
    """Raised when page rendering or text recognition fails for an image."""


# ---------------------------------------------------------------------------
# Base OCR Engine & Implementations
# ---------------------------------------------------------------------------


class BaseOCREngine(ABC):
    """Abstract interface for optical character recognition engines."""

    @abstractmethod
    def is_available(self) -> tuple[bool, Optional[str]]:
        """Check whether the OCR engine and its system dependencies are available."""
        pass

    @abstractmethod
    def ocr_image(self, image: Image.Image, language: str, timeout: float) -> str:
        """Extract raw text from a PIL Image instance."""
        pass

    @abstractmethod
    def render_pdf_page(
        self,
        pdf_path: Path,
        page_number: int,
        dpi: int,
        poppler_path: Optional[str] = None,
    ) -> Image.Image:
        """Render a single 1-based page of a PDF file to a PIL Image."""
        pass


class TesseractOCREngine(BaseOCREngine):
    """Production OCR engine utilizing local Tesseract and Poppler executables."""

    def __init__(
        self,
        tesseract_cmd: Optional[str] = None,
        poppler_path: Optional[str] = None,
    ) -> None:
        self.tesseract_cmd = tesseract_cmd or settings.OCR_TESSERACT_CMD
        self.poppler_path = poppler_path or settings.OCR_POPPLER_PATH

        if self.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_cmd

    def is_available(self) -> tuple[bool, Optional[str]]:
        """Verify presence of Tesseract and Poppler binaries."""
        if not settings.OCR_ENABLED:
            return False, "OCR fallback is disabled in application settings (OCR_ENABLED=False)."

        # Check Tesseract binary
        tess_bin = self.tesseract_cmd or shutil.which("tesseract")
        if not tess_bin or not Path(tess_bin).exists():
            return (
                False,
                "Tesseract OCR executable not found on server. "
                "Install via 'brew install tesseract' (macOS) or 'apt-get install tesseract-ocr' (Linux).",
            )

        # Check Poppler binary (pdftoppm)
        if self.poppler_path:
            poppler_bin = Path(self.poppler_path) / "pdftoppm"
            if not poppler_bin.exists():
                return False, f"Poppler binary 'pdftoppm' not found at {self.poppler_path}."
        else:
            if not shutil.which("pdftoppm"):
                return (
                    False,
                    "Poppler utility 'pdftoppm' not found on server. "
                    "Install via 'brew install poppler' (macOS) or 'apt-get install poppler-utils' (Linux).",
                )

        return True, None

    def render_pdf_page(
        self,
        pdf_path: Path,
        page_number: int,
        dpi: int,
        poppler_path: Optional[str] = None,
    ) -> Image.Image:
        """Render a single PDF page into a PIL Image using pdf2image."""
        target_poppler = poppler_path or self.poppler_path
        try:
            images = pdf2image.convert_from_path(
                pdf_path,
                dpi=dpi,
                first_page=page_number,
                last_page=page_number,
                poppler_path=target_poppler,
            )
            if not images:
                raise OCRProcessingError(f"Failed to render page {page_number} of PDF.")
            return images[0]
        except (
            pdf2image.exceptions.PDFInfoNotInstalledError,
            pdf2image.exceptions.PDFPageCountError,
        ) as e:
            raise OCREngineUnavailableError(
                "Poppler is required for PDF page rendering but not available in PATH."
            ) from e
        except Exception as e:
            raise OCRProcessingError(f"Error rendering PDF page {page_number}: {str(e)}") from e

    def ocr_image(self, image: Image.Image, language: str, timeout: float) -> str:
        """Execute Tesseract on image."""
        try:
            return pytesseract.image_to_string(
                image,
                lang=language,
                timeout=timeout,
            )
        except pytesseract.pytesseract.TesseractNotFoundError as e:
            raise OCREngineUnavailableError("Tesseract OCR binary not found.") from e
        except pytesseract.pytesseract.TesseractError as e:
            if "timeout" in str(e).lower():
                raise OCRTimeoutError(f"OCR processing timed out after {timeout} seconds.") from e
            raise OCRProcessingError(f"Tesseract execution error: {str(e)}") from e
        except Exception as e:
            raise OCRProcessingError(f"Failed to perform OCR on image: {str(e)}") from e


class MockOCREngine(BaseOCREngine):
    """Deterministic mock OCR engine for test suites and environments without native binaries."""

    def __init__(
        self,
        available: bool = True,
        mock_text_by_page: Optional[dict[int, str]] = None,
        default_text: str = "Mock OCR Recognized Lab Manual Text",
        raise_timeout: bool = False,
        raise_error: bool = False,
    ) -> None:
        self._available = available
        self.mock_text_by_page = mock_text_by_page or {}
        self.default_text = default_text
        self.raise_timeout = raise_timeout
        self.raise_error = raise_error
        self.rendered_pages: list[int] = []

    def is_available(self) -> tuple[bool, Optional[str]]:
        if not self._available:
            return False, "Mock OCR engine marked unavailable for test."
        return True, None

    def render_pdf_page(
        self,
        pdf_path: Path,
        page_number: int,
        dpi: int,
        poppler_path: Optional[str] = None,
    ) -> Image.Image:
        self.rendered_pages.append(page_number)
        # Create a small blank image in memory
        return Image.new("RGB", (200, 200), color=(255, 255, 255))

    def ocr_image(self, image: Image.Image, language: str, timeout: float) -> str:
        if self.raise_timeout:
            raise OCRTimeoutError("Mock OCR timeout exceeded.")
        if self.raise_error:
            raise OCRProcessingError("Mock OCR processing failure.")
        return self.default_text


# ---------------------------------------------------------------------------
# OCR Service
# ---------------------------------------------------------------------------


class OCRService:
    """High-level OCR coordination service with preprocessing and batch safety."""

    def __init__(
        self,
        engine: Optional[BaseOCREngine] = None,
        normalizer: Optional[TextNormalizer] = None,
    ) -> None:
        self.engine = engine or TesseractOCREngine()
        self.normalizer = normalizer or TextNormalizer()
        self.language = settings.OCR_LANGUAGE
        self.timeout = settings.OCR_TIMEOUT_SECONDS
        self.dpi = settings.OCR_RENDERING_DPI
        self.max_pages = settings.OCR_MAX_PAGES

    def is_available(self) -> tuple[bool, Optional[str]]:
        """Return (True, None) if OCR engine is operational, or (False, reason) otherwise."""
        return self.engine.is_available()

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """Conservative image preprocessing: grayscale conversion and contrast normalization."""
        # 1. Convert to single-channel 8-bit grayscale
        gray = image.convert("L")
        # 2. Normalize contrast without aggressive binarization
        enhanced = ImageOps.autocontrast(gray)
        return enhanced

    def ocr_image(self, image: Image.Image) -> str:
        """Preprocess and run OCR on a PIL image."""
        preprocessed = self.preprocess_image(image)
        try:
            raw_text = self.engine.ocr_image(
                preprocessed,
                language=self.language,
                timeout=self.timeout,
            )
            return self.normalizer.normalize(raw_text)
        finally:
            if preprocessed is not image:
                preprocessed.close()

    def ocr_pdf_pages(
        self,
        pdf_path: Path,
        page_numbers: list[int],
        max_pages: Optional[int] = None,
    ) -> tuple[dict[int, ExtractedPage], list[str]]:
        """Incrementally render and OCR specified pages of a PDF file.
        
        Returns:
            A tuple of (mapping of {page_number: ExtractedPage}, warnings_list).
        """
        results: dict[int, ExtractedPage] = {}
        warnings: list[str] = []

        available, reason = self.is_available()
        if not available:
            warnings.append(
                f"OCR fallback could not be executed: {reason}"
            )
            return results, warnings

        effective_max = max_pages or self.max_pages
        eligible_pages = page_numbers[:effective_max]

        if len(page_numbers) > effective_max:
            warnings.append(
                f"OCR page limit ({effective_max}) exceeded. "
                f"Only the first {effective_max} textless pages were processed with OCR."
            )

        for page_num in eligible_pages:
            img: Optional[Image.Image] = None
            try:
                img = self.engine.render_pdf_page(
                    pdf_path=pdf_path,
                    page_number=page_num,
                    dpi=self.dpi,
                )
                ocr_text = self.ocr_image(img)
                has_text = bool(ocr_text.strip())
                char_count = len(ocr_text)

                results[page_num] = ExtractedPage(
                    page_number=page_num,
                    text=ocr_text,
                    character_count=char_count,
                    has_text=has_text,
                    ocr_applied=True,
                )
            except OCRTimeoutError as te:
                warnings.append(f"OCR timeout on page {page_num}: {str(te)}")
                results[page_num] = ExtractedPage(
                    page_number=page_num,
                    text="",
                    character_count=0,
                    has_text=False,
                    ocr_applied=True,
                )
            except OCREngineUnavailableError as ue:
                warnings.append(f"OCR engine became unavailable on page {page_num}: {str(ue)}")
                break
            except Exception as e:
                warnings.append(f"OCR error on page {page_num}: {str(e)}")
                results[page_num] = ExtractedPage(
                    page_number=page_num,
                    text="",
                    character_count=0,
                    has_text=False,
                    ocr_applied=True,
                )
            finally:
                if img is not None:
                    try:
                        img.close()
                    except Exception:
                        pass

        return results, warnings


# Global OCR service instance
default_ocr_service = OCRService()


def get_ocr_service() -> OCRService:
    """FastAPI dependency provider for OCRService."""
    return default_ocr_service
