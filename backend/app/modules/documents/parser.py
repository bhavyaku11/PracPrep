"""Document Section Parser Service.

Transforms extracted laboratory manual text into structured experiment sections
using the pluggable AI provider architecture (Google Gemini with deterministic fallback).
Performs untrusted data containment, schema validation, completeness scoring, and diagnostic warnings.
"""

from datetime import datetime, timezone
import logging
from typing import Annotated, Optional
import uuid

from fastapi import Depends

from app.modules.ai.base import BaseAIProvider
from app.modules.ai.exceptions import AIProviderError
from app.modules.ai.factory import get_ai_provider
from app.modules.documents.schemas import (
    ManualParseResponse,
    ManualParseStatusEnum,
    ParsedExperimentSections,
)

logger = logging.getLogger(__name__)

# Maximum character threshold for LLM prompt context safety
MAX_TEXT_PARSE_CHARS = 60000
MIN_TEXT_PARSE_CHARS = 20


class DocumentParsingError(Exception):
    """Domain exception raised when document parsing encounters an unrecoverable error."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DocumentSectionParserService:
    """Service orchestrating AI-assisted laboratory manual section extraction."""

    def __init__(self, ai_provider: BaseAIProvider) -> None:
        """Initialize parser service with configured AI provider.

        Args:
            ai_provider: Conforming BaseAIProvider implementation (e.g. Gemini, Fallback, Demonstration).
        """
        self._ai_provider = ai_provider

    @property
    def ai_provider(self) -> BaseAIProvider:
        """Configured AI provider instance."""
        return self._ai_provider

    async def parse_document_text(
        self,
        text: str,
        file_name: Optional[str] = None,
        document_id: Optional[uuid.UUID] = None,
        experiment_id: Optional[uuid.UUID] = None,
    ) -> ManualParseResponse:
        """Parse raw extracted lab manual text into structured experiment sections.

        Args:
            text: Extracted plain text or OCR text from document.
            file_name: Optional original document filename.
            document_id: Optional associated UploadedDocument UUID.
            experiment_id: Target experiment workspace UUID.

        Returns:
            ManualParseResponse containing validated section draft, warnings, and confidence metrics.
        """
        target_exp_id = experiment_id or uuid.uuid4()
        now = datetime.now(timezone.utc)
        warnings: list[str] = []

        # 1. Validate input text sufficiency
        if not text or not text.strip():
            return ManualParseResponse(
                document_id=document_id,
                experiment_id=target_exp_id,
                status=ManualParseStatusEnum.FAILED,
                sections=ParsedExperimentSections(),
                confidence_score=0.0,
                warnings=["Extracted manual text is empty. No content available to parse."],
                missing_sections=["title", "objective", "theory", "apparatus", "procedure"],
                provider_mode=self._ai_provider.provider_mode.value,
                provider_id=self._ai_provider.provider_id,
                raw_character_count=0,
                created_at=now,
            )

        stripped_text = text.strip()
        raw_char_count = len(stripped_text)

        if raw_char_count < MIN_TEXT_PARSE_CHARS:
            return ManualParseResponse(
                document_id=document_id,
                experiment_id=target_exp_id,
                status=ManualParseStatusEnum.FAILED,
                sections=ParsedExperimentSections(),
                confidence_score=0.0,
                warnings=[
                    f"Extracted manual text is too brief ({raw_char_count} characters) "
                    "to reliably identify experiment sections."
                ],
                missing_sections=["title", "objective", "theory", "apparatus", "procedure"],
                provider_mode=self._ai_provider.provider_mode.value,
                provider_id=self._ai_provider.provider_id,
                raw_character_count=raw_char_count,
                created_at=now,
            )

        # 2. Text boundary safety check (truncation with warning)
        safe_text = stripped_text
        if raw_char_count > MAX_TEXT_PARSE_CHARS:
            safe_text = stripped_text[:MAX_TEXT_PARSE_CHARS]
            warnings.append(
                f"Manual source text exceeded {MAX_TEXT_PARSE_CHARS:,} characters; "
                f"truncated for model context safety (processed {MAX_TEXT_PARSE_CHARS:,} of {raw_char_count:,} characters)."
            )

        # 3. Invoke AI Provider with error containment
        try:
            parsed_sections = await self._ai_provider.parse_manual_sections(
                raw_text=safe_text,
                file_name=file_name,
            )
        except AIProviderError as err:
            logger.warning(
                "AI provider error during manual section parsing: %s",
                err.message,
            )
            return ManualParseResponse(
                document_id=document_id,
                experiment_id=target_exp_id,
                status=ManualParseStatusEnum.FAILED,
                sections=ParsedExperimentSections(),
                confidence_score=0.0,
                warnings=[f"AI section parser unavailable: {err.message}"],
                missing_sections=["title", "objective", "theory", "apparatus", "procedure"],
                provider_mode=self._ai_provider.provider_mode.value,
                provider_id=self._ai_provider.provider_id,
                raw_character_count=raw_char_count,
                created_at=now,
            )
        except Exception as exc:
            logger.error(
                "Unexpected failure during manual section parsing: %s",
                exc,
                exc_info=True,
            )
            return ManualParseResponse(
                document_id=document_id,
                experiment_id=target_exp_id,
                status=ManualParseStatusEnum.FAILED,
                sections=ParsedExperimentSections(),
                confidence_score=0.0,
                warnings=["An internal error occurred while parsing laboratory manual sections."],
                missing_sections=["title", "objective", "theory", "apparatus", "procedure"],
                provider_mode=self._ai_provider.provider_mode.value,
                provider_id=self._ai_provider.provider_id,
                raw_character_count=raw_char_count,
                created_at=now,
            )

        # 4. Assess section coverage and missing standard components
        standard_sections: dict[str, Optional[str]] = {
            "title": parsed_sections.title,
            "objective": parsed_sections.objective,
            "theory": parsed_sections.theory,
            "apparatus": parsed_sections.apparatus,
            "procedure": parsed_sections.procedure,
            "observations": parsed_sections.observations,
            "calculations": parsed_sections.calculations,
            "precautions": parsed_sections.precautions,
            "result": parsed_sections.result,
        }

        missing_sections: list[str] = [
            sec_name
            for sec_name, sec_val in standard_sections.items()
            if not sec_val or not sec_val.strip()
        ]

        # 5. Diagnostic warnings for absent sections
        if "precautions" in missing_sections:
            warnings.append(
                "Safety precautions were not identified in the manual; "
                "please review safety requirements with your instructor before entering the lab."
            )
        if "calculations" in missing_sections and "observations" in missing_sections:
            warnings.append(
                "No observation tables or calculation formulas were detected in the source text."
            )
        if "apparatus" in missing_sections:
            warnings.append(
                "Required apparatus list was not found in the extracted text."
            )
        if "objective" in missing_sections:
            warnings.append(
                "Experiment aim or objective could not be distinctly isolated."
            )

        # 6. Confidence scoring based on presence of core and supplementary sections
        core_sections = ["title", "objective", "theory", "apparatus", "procedure"]
        core_present = sum(1 for s in core_sections if s not in missing_sections)
        supplementary_sections = ["observations", "calculations", "precautions", "result"]
        supplementary_present = sum(1 for s in supplementary_sections if s not in missing_sections)

        # Base score from core (up to 0.65) + supplementary (up to 0.30)
        core_score = (core_present / len(core_sections)) * 0.65
        supp_score = (supplementary_present / len(supplementary_sections)) * 0.30
        calculated_confidence = round(min(0.95, max(0.20, core_score + supp_score)), 2)

        # 7. Status determination
        if core_present >= 4 and len(missing_sections) <= 3:
            status = ManualParseStatusEnum.SUCCESS
        else:
            status = ManualParseStatusEnum.SUCCESS_WITH_WARNINGS

        return ManualParseResponse(
            document_id=document_id,
            experiment_id=target_exp_id,
            status=status,
            sections=parsed_sections,
            confidence_score=calculated_confidence,
            warnings=warnings,
            missing_sections=missing_sections,
            provider_mode=self._ai_provider.provider_mode.value,
            provider_id=self._ai_provider.provider_id,
            raw_character_count=raw_char_count,
            created_at=now,
        )


def get_section_parser_service() -> DocumentSectionParserService:
    """Dependency factory returning DocumentSectionParserService instance."""
    return DocumentSectionParserService(ai_provider=get_ai_provider())
