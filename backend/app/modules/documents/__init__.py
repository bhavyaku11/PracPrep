"""Documents module package initialization."""

from app.modules.documents.extractor import (
    DocumentCorruptedError,
    DocumentEncryptedError,
    DocumentExtractionError,
    DocumentExtractorService,
    DocumentFileNotFoundError,
    DocumentNoTextError,
    DocumentUnsupportedFormatError,
    TextNormalizer,
    get_extractor_service,
)
from app.modules.documents.models import UploadedDocument
from app.modules.documents.ocr import (
    BaseOCREngine,
    MockOCREngine,
    OCREngineUnavailableError,
    OCRError,
    OCRProcessingError,
    OCRService,
    OCRTimeoutError,
    TesseractOCREngine,
    get_ocr_service,
)
from app.modules.documents.parser import (
    DocumentParsingError,
    DocumentSectionParserService,
    get_section_parser_service,
)
from app.modules.documents.router import router
from app.modules.documents.schemas import (
    DocumentExtractionResult,
    DocumentStatusEnum,
    DocumentUploadResponse,
    ExtractedPage,
    ExtractionStatusEnum,
    ManualParseRequestBody,
    ManualParseResponse,
    ManualParseStatusEnum,
    ParsedExperimentSections,
)
from app.modules.documents.storage import DocumentStorageService, get_storage_service

__all__ = [
    "UploadedDocument",
    "router",
    "DocumentStatusEnum",
    "DocumentUploadResponse",
    "DocumentStorageService",
    "get_storage_service",
    "DocumentExtractorService",
    "get_extractor_service",
    "TextNormalizer",
    "ExtractionStatusEnum",
    "ExtractedPage",
    "DocumentExtractionResult",
    "DocumentExtractionError",
    "DocumentFileNotFoundError",
    "DocumentEncryptedError",
    "DocumentCorruptedError",
    "DocumentUnsupportedFormatError",
    "DocumentNoTextError",
    "BaseOCREngine",
    "TesseractOCREngine",
    "MockOCREngine",
    "OCRService",
    "get_ocr_service",
    "OCRError",
    "OCREngineUnavailableError",
    "OCRTimeoutError",
    "OCRProcessingError",
    "DocumentSectionParserService",
    "get_section_parser_service",
    "DocumentParsingError",
    "ParsedExperimentSections",
    "ManualParseResponse",
    "ManualParseStatusEnum",
    "ManualParseRequestBody",
]

