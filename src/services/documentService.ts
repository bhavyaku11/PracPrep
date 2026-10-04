/**
 * Document Ingestion & Section Parser Client Service
 *
 * Provides typed frontend methods to upload laboratory manuals, trigger digital
 * and OCR text extraction, and request structured experiment section drafts
 * from the FastAPI backend.
 */

import { apiClient, ApiError } from "../lib/apiClient.ts";
import type {
  DocumentExtractionResult,
  DocumentUploadResponse,
  ManualParseRequestBody,
  ManualParseResponse,
} from "../types/document.ts";

export class DocumentService {
  /**
   * Upload a laboratory manual file (.pdf, .docx) for an experiment workspace.
   */
  async uploadManual(
    experimentId: string,
    file: File
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("experiment_id", experimentId);

    return await apiClient.post<DocumentUploadResponse>(
      "/experiments/upload-manual",
      formData
    );
  }

  /**
   * Run digital PDF/DOCX or OCR text extraction on the uploaded manual.
   */
  async extractManualText(
    experimentId: string
  ): Promise<DocumentExtractionResult> {
    return await apiClient.post<DocumentExtractionResult>(
      `/experiments/${experimentId}/extract-text`
    );
  }

  /**
   * Parse extracted manual text into structured experiment sections using AI.
   */
  async parseManualSections(
    experimentId: string,
    body?: ManualParseRequestBody
  ): Promise<ManualParseResponse> {
    return await apiClient.post<ManualParseResponse>(
      `/experiments/${experimentId}/parse-manual`,
      body ?? {}
    );
  }

  /**
   * Complete pipeline: upload file (if provided) -> extract text -> parse sections.
   */
  async processAndParseManual(
    experimentId: string,
    file?: File
  ): Promise<{
    uploadResult?: DocumentUploadResponse;
    extractionResult: DocumentExtractionResult;
    parseResult: ManualParseResponse;
  }> {
    let uploadResult: DocumentUploadResponse | undefined;

    if (file) {
      uploadResult = await this.uploadManual(experimentId, file);
    }

    const extractionResult = await this.extractManualText(experimentId);

    if (
      extractionResult.status === "failed" ||
      extractionResult.status === "unreadable" ||
      !extractionResult.extractedText ||
      extractionResult.extractedText.trim().length === 0
    ) {
      throw new ApiError({
        message:
          extractionResult.failureReason ||
          "Could not extract usable text from the uploaded laboratory manual.",
        status: 400,
        statusText: "Extraction Failed",
        code: "EXTRACTION_FAILED",
      });
    }

    const parseResult = await this.parseManualSections(experimentId);

    return {
      uploadResult,
      extractionResult,
      parseResult,
    };
  }
}

/**
 * Format document and parsing API errors into clear, actionable messages.
 */
export function formatDocumentApiError(
  err: unknown,
  action: string = "parsing manual"
): string {
  if (err instanceof ApiError) {
    if (err.status === 401 || err.isAuthError) {
      return "Your session has expired or authentication is required. Please sign in.";
    }
    if (err.status === 404) {
      if (typeof err.detail === "string" && err.detail.trim().length > 0) {
        return err.detail;
      }
      return "Experiment or uploaded document was not found.";
    }
    if (err.status === 400) {
      if (typeof err.detail === "string" && err.detail.trim().length > 0) {
        return err.detail;
      }
      return `Unable to complete ${action}: source text may be empty or unreadable.`;
    }
    if (err.status === 422) {
      if (typeof err.detail === "string" && err.detail.trim().length > 0) {
        return err.detail;
      }
      if (Array.isArray(err.validationErrors) && err.validationErrors.length > 0) {
        return err.validationErrors.map((v) => v.msg).join(", ");
      }
      return `Invalid parameters for ${action}.`;
    }
    if (err.status === 429) {
      return "AI service rate limit reached. Please wait a moment and try again.";
    }
    if (err.status === 502) {
      return "The AI parser returned an unparseable response. Please retry.";
    }
    if (err.status === 503) {
      return "The document parser service is temporarily unavailable. Please try again in a moment.";
    }
    if (err.status === 504) {
      return "The document parsing request timed out. Please try again with a smaller document.";
    }
    if (err.isNetworkError) {
      return "Network connection error. Please check your connection and try again.";
    }
    if (typeof err.detail === "string" && err.detail.trim().length > 0) {
      return err.detail;
    }
  }

  if (err instanceof Error && err.message) {
    return err.message;
  }

  return `An unexpected error occurred while ${action}.`;
}

export const documentService = new DocumentService();
export default documentService;
