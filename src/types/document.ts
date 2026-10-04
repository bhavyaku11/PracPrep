/**
 * Document Ingestion and Section Parsing Type Definitions
 *
 * Models for document upload, text extraction, OCR status,
 * and AI-assisted experiment section structuring.
 */

export interface DocumentUploadResponse {
  id: string;
  experimentId: string;
  fileName: string;
  mimeType: string;
  fileSizeBytes: number;
  status: string;
  hasManualFile: boolean;
  createdAt: string;
  updatedAt: string;
}

export interface ExtractedPage {
  pageNumber: number;
  text: string;
  characterCount: number;
  hasText: boolean;
  ocrApplied: boolean;
}

export type ExtractionStatus =
  | "pending"
  | "completed"
  | "completed_with_warnings"
  | "failed"
  | "unreadable";

export interface DocumentExtractionResult {
  documentId?: string;
  experimentId?: string;
  sourceFileType: string;
  extractedText: string;
  pageCount: number;
  characterCount: number;
  status: ExtractionStatus;
  warnings: string[];
  failureReason?: string;
  pages: ExtractedPage[];
  metadata: Record<string, unknown>;
}

export interface ParsedExperimentSections {
  title?: string | null;
  subject?: string | null;
  experimentNumber?: string | null;
  objective?: string | null;
  theory?: string | null;
  apparatus?: string | null;
  procedure?: string | null;
  observations?: string | null;
  calculations?: string | null;
  precautions?: string | null;
  result?: string | null;
  additionalNotes?: string | null;
}

export type ManualParseStatus = "success" | "success_with_warnings" | "failed";

export interface ManualParseResponse {
  documentId?: string | null;
  experimentId: string;
  status: ManualParseStatus;
  sections: ParsedExperimentSections;
  confidenceScore: number;
  warnings: string[];
  missingSections: string[];
  providerMode: string;
  providerId: string;
  rawCharacterCount: number;
  createdAt: string;
}

export interface ManualParseRequestBody {
  rawText?: string;
}
