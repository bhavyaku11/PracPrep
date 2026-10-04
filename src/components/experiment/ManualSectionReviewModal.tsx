import React, { useState } from "react";
import {
  Sparkles,
  AlertTriangle,
  FileText,
  CheckCircle2,
  X,
  RotateCcw,
  Check,
  ChevronDown,
  ChevronUp,
  Info,
  ShieldAlert,
} from "lucide-react";
import type {
  ManualParseResponse,
  ParsedExperimentSections,
} from "../../types/document";

interface ManualSectionReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  parseResult: ManualParseResponse | null;
  rawExtractedText?: string | null;
  isLoading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  onAccept: (reviewedSections: ParsedExperimentSections) => void | Promise<void>;
  fileName?: string;
}

interface ReviewFormProps {
  parseResult: ManualParseResponse;
  rawExtractedText?: string | null;
  onAccept: (reviewedSections: ParsedExperimentSections) => void | Promise<void>;
  onClose: () => void;
  onRetry?: () => void;
}

const ManualSectionReviewForm: React.FC<ReviewFormProps> = ({
  parseResult,
  rawExtractedText,
  onAccept,
  onClose,
  onRetry,
}) => {
  const [editedSections, setEditedSections] = useState<ParsedExperimentSections>(() => ({
    title: parseResult.sections.title || "",
    subject: parseResult.sections.subject || "",
    experimentNumber: parseResult.sections.experimentNumber || "",
    objective: parseResult.sections.objective || "",
    theory: parseResult.sections.theory || "",
    apparatus: parseResult.sections.apparatus || "",
    procedure: parseResult.sections.procedure || "",
    observations: parseResult.sections.observations || "",
    calculations: parseResult.sections.calculations || "",
    precautions: parseResult.sections.precautions || "",
    result: parseResult.sections.result || "",
    additionalNotes: parseResult.sections.additionalNotes || "",
  }));

  const [showRawText, setShowRawText] = useState(false);
  const [activeTab, setActiveTab] = useState<
    "overview" | "core" | "procedure" | "observations" | "precautions"
  >("overview");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleFieldChange = (field: keyof ParsedExperimentSections, value: string) => {
    setEditedSections((prev) => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleAccept = async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      await onAccept(editedSections);
      onClose();
    } finally {
      setIsSubmitting(false);
    }
  };

  const confidenceScore = parseResult.confidenceScore ?? 0.85;
  const confidencePercent = Math.round(confidenceScore * 100);

  const getConfidenceBadgeColor = (score: number) => {
    if (score >= 0.8) return "bg-emerald-50 text-emerald-700 border-emerald-200";
    if (score >= 0.6) return "bg-amber-50 text-amber-700 border-amber-200";
    return "bg-rose-50 text-rose-700 border-rose-200";
  };

  return (
    <>
      {/* Modal Content Body */}
      <div className="flex-1 overflow-y-auto p-5 sm:p-6 space-y-5">
        {/* AI Disclaimer & Metadata Callout */}
        <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-4 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4 text-emerald-700 shrink-0" />
              <span className="text-xs font-semibold text-emerald-950">
                AI suggestions require student verification
              </span>
            </div>
            <div className="flex flex-wrap items-center gap-2 text-[11px]">
              <span
                className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border font-semibold ${getConfidenceBadgeColor(
                  confidenceScore
                )}`}
              >
                <CheckCircle2 className="h-3 w-3" />
                {confidencePercent}% Section Match
              </span>
              <span className="px-2 py-0.5 rounded-full border border-neutral-200 bg-white font-mono text-neutral-600">
                {parseResult.rawCharacterCount?.toLocaleString() || 0} chars analyzed
              </span>
              <span className="px-2 py-0.5 rounded-full border border-neutral-200 bg-white font-mono text-neutral-600">
                mode: {parseResult.providerMode}
              </span>
            </div>
          </div>

          <p className="text-xs text-neutral-600 leading-relaxed">
            The sections below are an editable draft extracted from your manual. Scientific formulas, procedure steps, and precautions must be verified by you before saving to your workspace.
          </p>
        </div>

        {/* Warnings and Missing Sections Banner */}
        {(parseResult.warnings?.length > 0 || parseResult.missingSections?.length > 0) && (
          <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-3.5 space-y-2 text-xs">
            <div className="flex items-center gap-1.5 font-semibold text-amber-900">
              <AlertTriangle className="h-3.5 w-3.5 text-amber-700 shrink-0" />
              <span>Parser Review Notices</span>
            </div>
            <ul className="list-disc list-inside space-y-1 text-amber-800 text-[11px]">
              {parseResult.missingSections?.map((sec, idx) => (
                <li key={`missing-${idx}`}>
                  <span className="font-semibold capitalize">{sec}</span>: Section was not explicitly found in the manual. You can fill it in below or leave it empty.
                </li>
              ))}
              {parseResult.warnings?.map((warn, idx) => (
                <li key={`warn-${idx}`}>{warn}</li>
              ))}
            </ul>
          </div>
        )}

        {/* Source Text Drawer Toggle */}
        {rawExtractedText && (
          <div className="border border-neutral-200 rounded-xl overflow-hidden">
            <button
              type="button"
              onClick={() => setShowRawText(!showRawText)}
              className="w-full flex items-center justify-between px-4 py-2.5 bg-neutral-50 hover:bg-neutral-100 text-neutral-700 text-xs font-semibold transition-colors"
            >
              <div className="flex items-center gap-2">
                <FileText className="h-3.5 w-3.5 text-neutral-500" />
                <span>Original Extracted Text from Lab Manual</span>
              </div>
              {showRawText ? (
                <ChevronUp className="h-3.5 w-3.5" />
              ) : (
                <ChevronDown className="h-3.5 w-3.5" />
              )}
            </button>
            {showRawText && (
              <div className="p-3 bg-neutral-900 text-neutral-200 text-xs font-mono max-h-48 overflow-y-auto whitespace-pre-wrap select-text border-t border-neutral-200">
                {rawExtractedText}
              </div>
            )}
          </div>
        )}

        {/* Category Tab Navigation */}
        <div className="flex items-center gap-1 border-b border-neutral-200 pb-px overflow-x-auto">
          {[
            { id: "overview", label: "Overview & Aim" },
            { id: "core", label: "Theory & Apparatus" },
            { id: "procedure", label: "Procedure" },
            { id: "observations", label: "Readings & Results" },
            { id: "precautions", label: "Precautions & Notes" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-3 py-2 text-xs font-semibold rounded-t-lg transition-colors whitespace-nowrap ${
                activeTab === tab.id
                  ? "border-b-2 border-emerald-600 text-emerald-800 bg-emerald-50/30"
                  : "text-neutral-500 hover:text-neutral-900 hover:bg-neutral-50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Form Panels */}
        <div className="space-y-4 pt-1">
          {/* 1. Overview Tab */}
          {activeTab === "overview" && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="sm:col-span-2 space-y-1">
                  <label className="text-xs font-semibold text-neutral-800">
                    Experiment Title <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={editedSections.title || ""}
                    onChange={(e) => handleFieldChange("title", e.target.value)}
                    placeholder="e.g. Verification of Thevenin's Theorem"
                    className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-neutral-800">
                    Experiment Code / No.
                  </label>
                  <input
                    type="text"
                    value={editedSections.experimentNumber || ""}
                    onChange={(e) =>
                      handleFieldChange("experimentNumber", e.target.value)
                    }
                    placeholder="e.g. EXP-01"
                    className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 font-mono"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <label className="text-xs font-semibold text-neutral-800">
                  Subject / Laboratory Course <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  value={editedSections.subject || ""}
                  onChange={(e) => handleFieldChange("subject", e.target.value)}
                  placeholder="e.g. Basic Electrical Engineering Laboratory"
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600"
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Aim / Objective
                  </label>
                  <span className="text-[11px] text-neutral-400">
                    {editedSections.objective ? "Extracted" : "Optional"}
                  </span>
                </div>
                <textarea
                  rows={3}
                  value={editedSections.objective || ""}
                  onChange={(e) => handleFieldChange("objective", e.target.value)}
                  placeholder="State the core experimental purpose and target outcome..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 leading-relaxed"
                />
              </div>
            </div>
          )}

          {/* 2. Core Tab: Theory & Apparatus */}
          {activeTab === "core" && (
            <div className="space-y-4">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Theoretical Background & Principles
                  </label>
                  <span className="text-[11px] text-neutral-400">
                    {editedSections.theory ? "Extracted" : "Optional"}
                  </span>
                </div>
                <textarea
                  rows={5}
                  value={editedSections.theory || ""}
                  onChange={(e) => handleFieldChange("theory", e.target.value)}
                  placeholder="Theoretical principles, governing scientific equations, theorems, and assumptions..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 leading-relaxed"
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Apparatus & Equipment Required
                  </label>
                  <span className="text-[11px] text-neutral-400">
                    {editedSections.apparatus ? "Extracted" : "Optional"}
                  </span>
                </div>
                <textarea
                  rows={4}
                  value={editedSections.apparatus || ""}
                  onChange={(e) => handleFieldChange("apparatus", e.target.value)}
                  placeholder="List of instruments, ranges, specifications, components, and tools..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 leading-relaxed"
                />
              </div>
            </div>
          )}

          {/* 3. Procedure Tab */}
          {activeTab === "procedure" && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-semibold text-neutral-800">
                  Step-by-Step Experimental Procedure
                </label>
                <span className="text-[11px] text-neutral-400">
                  {editedSections.procedure ? "Extracted" : "Optional"}
                </span>
              </div>
              <textarea
                rows={8}
                value={editedSections.procedure || ""}
                onChange={(e) => handleFieldChange("procedure", e.target.value)}
                placeholder="Numbered steps, circuit connections, parameter adjustments, and reading recordings..."
                className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 font-mono leading-relaxed"
              />
            </div>
          )}

          {/* 4. Observations & Calculations Tab */}
          {activeTab === "observations" && (
            <div className="space-y-4">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Observation Tables & Readings
                  </label>
                  <span className="text-[11px] text-neutral-400">
                    {editedSections.observations ? "Extracted" : "Optional"}
                  </span>
                </div>
                <textarea
                  rows={4}
                  value={editedSections.observations || ""}
                  onChange={(e) => handleFieldChange("observations", e.target.value)}
                  placeholder="Recorded observation table structures, columns, and measurement units..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 font-mono leading-relaxed"
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Calculations & Formulas
                  </label>
                  <span className="text-[11px] text-neutral-400">
                    {editedSections.calculations ? "Extracted" : "Optional"}
                  </span>
                </div>
                <textarea
                  rows={3}
                  value={editedSections.calculations || ""}
                  onChange={(e) => handleFieldChange("calculations", e.target.value)}
                  placeholder="Formula expressions, constant values, and error percentage formulas..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 font-mono leading-relaxed"
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Experimental Result / Conclusion
                  </label>
                  <span className="text-[11px] text-neutral-400">
                    {editedSections.result ? "Extracted" : "Optional"}
                  </span>
                </div>
                <textarea
                  rows={3}
                  value={editedSections.result || ""}
                  onChange={(e) => handleFieldChange("result", e.target.value)}
                  placeholder="Outcome statement, verified theorems, or measured constants..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 leading-relaxed"
                />
              </div>
            </div>
          )}

          {/* 5. Precautions & Additional Tab */}
          {activeTab === "precautions" && (
            <div className="space-y-4">
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Laboratory Precautions & Safety Instructions
                  </label>
                  <span className="text-[11px] text-neutral-400">
                    {editedSections.precautions ? "Extracted" : "Optional"}
                  </span>
                </div>
                <textarea
                  rows={4}
                  value={editedSections.precautions || ""}
                  onChange={(e) => handleFieldChange("precautions", e.target.value)}
                  placeholder="Equipment ratings, handling warnings, switch precautions, and zero adjustments..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 leading-relaxed"
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-semibold text-neutral-800">
                    Additional Notes / Relevant Sections
                  </label>
                  <span className="text-[11px] text-neutral-400">Optional</span>
                </div>
                <textarea
                  rows={3}
                  value={editedSections.additionalNotes || ""}
                  onChange={(e) =>
                    handleFieldChange("additionalNotes", e.target.value)
                  }
                  placeholder="Any extra remarks, pre-lab reading references, or lab instructor instructions..."
                  className="w-full rounded-lg border border-neutral-300 px-3 py-2 text-xs text-neutral-900 focus:border-emerald-600 focus:outline-none focus:ring-1 focus:ring-emerald-600 leading-relaxed"
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal Footer Actions */}
      <div className="flex items-center justify-between px-5 py-3.5 border-t border-neutral-100 bg-neutral-50/70 shrink-0">
        <div className="flex items-center gap-2">
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              disabled={isSubmitting}
              className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-100 transition-colors disabled:opacity-50"
            >
              <RotateCcw className="h-3 w-3" />
              <span>Re-parse</span>
            </button>
          )}
        </div>

        <div className="flex items-center gap-2.5">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-lg border border-neutral-200 bg-white px-3.5 py-1.5 text-xs font-semibold text-neutral-700 hover:bg-neutral-100 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>

          <button
            type="button"
            onClick={handleAccept}
            disabled={isSubmitting || !editedSections.title?.trim() || !editedSections.subject?.trim()}
            className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 px-4 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800 transition-colors shadow-2xs disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Check className="h-3.5 w-3.5" />
            <span>{isSubmitting ? "Applying..." : "Accept & Apply to Experiment"}</span>
          </button>
        </div>
      </div>
    </>
  );
};

export const ManualSectionReviewModal: React.FC<ManualSectionReviewModalProps> = ({
  isOpen,
  onClose,
  parseResult,
  rawExtractedText,
  isLoading = false,
  error = null,
  onRetry,
  onAccept,
  fileName,
}) => {
  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="manual-review-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-neutral-950/60 backdrop-blur-xs animate-in fade-in duration-150 overflow-y-auto"
      onClick={onClose}
    >
      <div
        className="w-full max-w-4xl max-h-[92vh] flex flex-col rounded-2xl border border-neutral-200 bg-white shadow-2xl animate-in zoom-in-95 duration-150 overflow-hidden my-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-neutral-100 bg-neutral-50/50 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-100 text-emerald-800 shrink-0">
              <Sparkles className="h-5 w-5 text-emerald-700" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2
                  id="manual-review-modal-title"
                  className="font-jakarta text-base sm:text-lg font-bold text-neutral-900"
                >
                  Review AI-Structured Lab Manual
                </h2>
                <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-800 uppercase tracking-wide">
                  Suggestion Draft
                </span>
              </div>
              <p className="text-xs text-neutral-500 truncate max-w-md">
                {fileName ? `Source: ${fileName}` : "Extracted manual sections"} • Review, modify, and accept before saving.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
            aria-label="Close review dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="py-24 flex flex-col items-center justify-center text-center space-y-4">
            <div className="relative">
              <div className="h-12 w-12 rounded-full border-3 border-emerald-200 border-t-emerald-700 animate-spin" />
              <Sparkles className="h-5 w-5 text-emerald-700 absolute inset-0 m-auto" />
            </div>
            <div className="space-y-1 max-w-sm">
              <p className="font-semibold text-neutral-900 text-sm">
                Analyzing & Structuring Manual with AI
              </p>
              <p className="text-xs text-neutral-500">
                Parsing technical theory, equipment lists, procedural steps, and precautions from the uploaded document...
              </p>
            </div>
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <div className="p-6">
            <div className="rounded-xl border border-rose-200 bg-rose-50/60 p-5 text-left space-y-3">
              <div className="flex items-start gap-3">
                <ShieldAlert className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
                <div className="space-y-1">
                  <h3 className="text-sm font-semibold text-rose-900">
                    Document Section Parsing Could Not Complete
                  </h3>
                  <p className="text-xs text-rose-700 leading-relaxed">{error}</p>
                </div>
              </div>
              <div className="flex items-center gap-2 pt-2">
                {onRetry && (
                  <button
                    type="button"
                    onClick={onRetry}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-700 transition-colors"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    <span>Retry Parsing</span>
                  </button>
                )}
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-lg border border-rose-200 bg-white px-3 py-1.5 text-xs font-semibold text-rose-800 hover:bg-rose-50 transition-colors"
                >
                  Close & Enter Details Manually
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Form view with key for clean state re-initialization */}
        {!isLoading && !error && parseResult && (
          <ManualSectionReviewForm
            key={parseResult.createdAt || parseResult.experimentId}
            parseResult={parseResult}
            rawExtractedText={rawExtractedText}
            onAccept={onAccept}
            onClose={onClose}
            onRetry={onRetry}
          />
        )}
      </div>
    </div>
  );
};

export default ManualSectionReviewModal;
