import React, { useState } from "react";
import { ArrowLeft, CheckCircle2, RotateCcw, Sparkles, Info } from "lucide-react";
import CreationMethodSelector from "./CreationMethodSelector";
import LabManualUploader from "./LabManualUploader";
import ExperimentDetailsForm from "./ExperimentDetailsForm";
import ManualExperimentForm from "./ManualExperimentForm";
import ExperimentFormActions from "./ExperimentFormActions";
import ManualSectionReviewModal from "./ManualSectionReviewModal";
import type {
  CreationMethod,
  ExperimentFormData,
  FormValidationErrors,
  UploadedFileMeta,
  CreatedExperimentResult,
} from "../../types/experiment";
import type { UserSession } from "../../types/dashboard";
import type {
  ManualParseResponse,
  ParsedExperimentSections,
} from "../../types/document";
import { experimentStorage } from "../../services/experimentStorage";
import {
  documentService,
  formatDocumentApiError,
} from "../../services/documentService";

interface NewExperimentPageProps {
  user: UserSession;
  onNavigate: (path: string) => void;
  onExperimentCreated?: (experiment: CreatedExperimentResult) => void;
}

const INITIAL_FORM_DATA: ExperimentFormData = {
  method: "upload",
  title: "",
  subject: "",
  experimentNumber: "",
  courseSemester: "",
  description: "",
  file: null,
  objective: "",
  theory: "",
  apparatus: "",
  procedure: "",
  precautions: "",
};

export const NewExperimentPage: React.FC<NewExperimentPageProps> = ({
  user,
  onNavigate,
  onExperimentCreated,
}) => {
  const [formData, setFormData] = useState<ExperimentFormData>(INITIAL_FORM_DATA);
  const [errors, setErrors] = useState<FormValidationErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [createdResult, setCreatedResult] = useState<CreatedExperimentResult | null>(null);

  // AI Section Parser state
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<ManualParseResponse | null>(null);
  const [rawExtractedText, setRawExtractedText] = useState<string | null>(null);
  const [draftExperimentId, setDraftExperimentId] = useState<string | null>(null);
  const [aiDraftNotice, setAiDraftNotice] = useState<string | null>(null);
  const [guestNotice, setGuestNotice] = useState<string | null>(null);

  const handleSelectMethod = (method: CreationMethod) => {
    setFormData((prev) => ({ ...prev, method }));
    setErrors({});
  };

  const handleFieldChange = (fields: Partial<ExperimentFormData>) => {
    setFormData((prev) => ({ ...prev, ...fields }));
  };

  const handleClearError = (field: keyof FormValidationErrors) => {
    setErrors((prev) => {
      const updated = { ...prev };
      delete updated[field];
      return updated;
    });
  };

  const handleFileSelect = (fileMeta: UploadedFileMeta) => {
    setFormData((prev) => {
      const cleanFileName = fileMeta.name
        .replace(/\.[^/.]+$/, "")
        .replace(/[-_]/g, " ")
        .trim();

      return {
        ...prev,
        file: fileMeta,
        title: prev.title.trim() === "" ? cleanFileName : prev.title,
      };
    });
    handleClearError("file");
    setAiDraftNotice(null);
    setGuestNotice(null);
  };

  const handleFileRemove = () => {
    setFormData((prev) => ({ ...prev, file: null }));
    setParseResult(null);
    setRawExtractedText(null);
    setAiDraftNotice(null);
  };

  const handleInitiateAIParse = async () => {
    if (!formData.file) {
      setErrors((prev) => ({ ...prev, file: "Please select a lab manual file first." }));
      return;
    }

    if (user.isGuest) {
      setGuestNotice(
        "AI Section Parsing is an authenticated feature. Sign in to your account to automatically parse lab manuals with Gemini AI, or continue in Guest Mode by entering details manually."
      );
      return;
    }

    setGuestNotice(null);
    setParseError(null);
    setIsParsing(true);
    setIsReviewModalOpen(true);

    try {
      let expId = draftExperimentId;
      if (!expId) {
        const titleToUse = formData.title.trim() || formData.file.name;
        const subjectToUse = formData.subject.trim() || "Laboratory Manual";
        const draftExp = await experimentStorage.createExperiment(
          {
            title: titleToUse,
            subject: subjectToUse,
            experimentNumber: formData.experimentNumber.trim() || undefined,
            courseSemester: formData.courseSemester.trim() || undefined,
            method: "upload",
            hasManualFile: true,
            fileName: formData.file.name,
            status: "draft",
          },
          user
        );
        expId = draftExp.id;
        setDraftExperimentId(expId);
      }

      const result = await documentService.processAndParseManual(
        expId,
        formData.file.file
      );

      setParseResult(result.parseResult);
      setRawExtractedText(result.extractionResult.extractedText);
    } catch (err: unknown) {
      const msg = formatDocumentApiError(err, "parsing lab manual");
      setParseError(msg);
    } finally {
      setIsParsing(false);
    }
  };

  const handleAcceptParsedSections = (reviewed: ParsedExperimentSections) => {
    setFormData((prev) => ({
      ...prev,
      title: reviewed.title?.trim() || prev.title,
      subject: reviewed.subject?.trim() || prev.subject,
      experimentNumber: reviewed.experimentNumber?.trim() || prev.experimentNumber,
      objective: reviewed.objective?.trim() || prev.objective,
      theory: reviewed.theory?.trim() || prev.theory,
      apparatus: reviewed.apparatus?.trim() || prev.apparatus,
      procedure: reviewed.procedure?.trim() || prev.procedure,
      precautions: reviewed.precautions?.trim() || prev.precautions,
      description: reviewed.additionalNotes?.trim() || prev.description,
    }));

    if (draftExperimentId && !user.isGuest) {
      try {
        experimentStorage.updateExperiment(
          draftExperimentId,
          {
            title: reviewed.title?.trim() || formData.title,
            subject: reviewed.subject?.trim() || formData.subject,
            experimentNumber: reviewed.experimentNumber?.trim() || undefined,
            objective: reviewed.objective?.trim() || undefined,
            theory: reviewed.theory?.trim() || undefined,
            apparatus: reviewed.apparatus?.trim() || undefined,
            procedure: reviewed.procedure?.trim() || undefined,
            precautions: reviewed.precautions?.trim() || undefined,
            observations: reviewed.observations?.trim() || undefined,
            calculations: reviewed.calculations?.trim() || undefined,
            description: reviewed.additionalNotes?.trim() || undefined,
            status: "ready",
          },
          user
        );
      } catch (err) {
        console.warn("Could not update remote draft experiment:", err);
      }
    }

    setAiDraftNotice("AI draft sections accepted and applied to your experiment form.");
  };

  const validateForm = (): boolean => {
    const newErrors: FormValidationErrors = {};

    if (!formData.title.trim()) {
      newErrors.title = "Experiment title is required.";
    }

    if (!formData.subject.trim()) {
      newErrors.subject = "Subject name is required.";
    }

    if (formData.method === "upload" && !formData.file) {
      newErrors.file = "Please upload a lab manual file or enter details manually.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    // If an authenticated draft was already created during AI parsing, finalize it
    if (draftExperimentId && !user.isGuest) {
      const updated = experimentStorage.updateExperiment(
        draftExperimentId,
        {
          title: formData.title.trim(),
          subject: formData.subject.trim(),
          experimentNumber: formData.experimentNumber.trim() || undefined,
          courseSemester: formData.courseSemester.trim() || undefined,
          method: formData.method,
          hasManualFile: !!formData.file,
          fileName: formData.file?.name,
          status: "ready",
          description: formData.description?.trim() || undefined,
          objective: formData.objective?.trim() || undefined,
          theory: formData.theory?.trim() || undefined,
          apparatus: formData.apparatus?.trim() || undefined,
          procedure: formData.procedure?.trim() || undefined,
          precautions: formData.precautions?.trim() || undefined,
        },
        user
      );

      const newExp: CreatedExperimentResult = {
        id: updated?.id || draftExperimentId,
        title: updated?.title || formData.title.trim(),
        subject: updated?.subject || formData.subject.trim(),
        experimentNumber: updated?.experimentNumber,
        courseSemester: updated?.courseSemester,
        method: updated?.method || formData.method,
        hasManualFile: updated?.hasManualFile || false,
        fileName: updated?.fileName,
        createdAt: updated?.createdAt || new Date().toISOString(),
        status: updated?.status || "ready",
      };

      setIsSubmitting(false);
      setCreatedResult(newExp);
      if (onExperimentCreated) {
        onExperimentCreated(newExp);
      }
      return;
    }

    setTimeout(() => {
      const savedRecord = experimentStorage.saveExperiment(
        {
          title: formData.title.trim(),
          subject: formData.subject.trim(),
          experimentNumber: formData.experimentNumber.trim() || undefined,
          courseSemester: formData.courseSemester.trim() || undefined,
          method: formData.method,
          hasManualFile: !!formData.file,
          fileName: formData.file?.name,
          status: "ready",
          description: formData.description?.trim() || undefined,
          objective: formData.objective?.trim() || undefined,
          theory: formData.theory?.trim() || undefined,
          apparatus: formData.apparatus?.trim() || undefined,
          procedure: formData.procedure?.trim() || undefined,
          precautions: formData.precautions?.trim() || undefined,
        },
        user
      );

      const newExp: CreatedExperimentResult = {
        id: savedRecord.id,
        title: savedRecord.title,
        subject: savedRecord.subject,
        experimentNumber: savedRecord.experimentNumber,
        courseSemester: savedRecord.courseSemester,
        method: savedRecord.method || formData.method,
        hasManualFile: savedRecord.hasManualFile || false,
        fileName: savedRecord.fileName,
        createdAt: savedRecord.createdAt,
        status: savedRecord.status,
      };

      setIsSubmitting(false);
      setCreatedResult(newExp);
      if (onExperimentCreated) {
        onExperimentCreated(newExp);
      }
    }, 500);
  };

  const handleReset = () => {
    setFormData(INITIAL_FORM_DATA);
    setErrors({});
    setCreatedResult(null);
    setDraftExperimentId(null);
    setParseResult(null);
    setRawExtractedText(null);
    setAiDraftNotice(null);
    setGuestNotice(null);
  };

  const canSubmit =
    formData.title.trim().length > 0 &&
    formData.subject.trim().length > 0 &&
    (formData.method === "manual" || !!formData.file);

  return (
    <div className="w-full max-w-6xl mx-auto space-y-5 pb-16">
      {/* Header */}
      <div className="space-y-1">
        <button
          type="button"
          onClick={() => onNavigate("/experiments")}
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-neutral-500 hover:text-neutral-900 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 rounded-md"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Experiments</span>
        </button>

        <h1 className="font-jakarta text-2xl font-bold tracking-tight text-neutral-900">
          Create New Experiment
        </h1>
      </div>

      {createdResult ? (
        /* Confirmation Card */
        <div className="rounded-xl border border-emerald-200 bg-white p-6 shadow-2xs space-y-4 animate-in fade-in">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-100 text-emerald-800">
              <CheckCircle2 className="h-5 w-5 text-emerald-700" />
            </div>
            <div>
              <h2 className="font-jakarta text-base font-bold text-neutral-900">
                Experiment Created
              </h2>
              <p className="text-xs text-neutral-500">
                {createdResult.title} • {createdResult.subject}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 pt-2">
            <button
              type="button"
              onClick={() => onNavigate(`/experiments/${createdResult.id}`)}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-neutral-900 px-4 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors"
            >
              <span>Open Workspace</span>
            </button>
            <button
              type="button"
              onClick={() => onNavigate("/experiments")}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
            >
              <span>My Experiments</span>
            </button>
            <button
              type="button"
              onClick={handleReset}
              className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              <span>Create Another</span>
            </button>
          </div>
        </div>
      ) : (
        /* Form View */
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {/* Method Selector */}
          <CreationMethodSelector
            selectedMethod={formData.method}
            onSelectMethod={handleSelectMethod}
          />

          {/* Upload Method */}
          {formData.method === "upload" && (
            <div className="space-y-4">
              <LabManualUploader
                file={formData.file}
                onFileSelect={handleFileSelect}
                onFileRemove={handleFileRemove}
                error={errors.file}
              />

              {formData.file && (
                <div className="rounded-xl border border-emerald-200 bg-gradient-to-r from-emerald-50/70 via-emerald-50/30 to-white p-4 shadow-2xs space-y-3">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-xs">
                        <Sparkles className="h-4 w-4" />
                      </div>
                      <div className="space-y-0.5">
                        <div className="flex items-center gap-2">
                          <h3 className="text-xs font-bold text-neutral-900">
                            AI Section Parser & Preview
                          </h3>
                          <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-bold text-emerald-800">
                            Suggested Draft
                          </span>
                        </div>
                        <p className="text-[11px] text-neutral-600 leading-relaxed">
                          Analyze your manual to automatically extract Aim, Theory, Apparatus, Procedure, and Precautions into an editable preview.
                        </p>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={handleInitiateAIParse}
                      disabled={isParsing}
                      className="inline-flex shrink-0 items-center justify-center gap-1.5 rounded-lg bg-emerald-700 px-4 py-2 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-800 transition-colors disabled:opacity-50"
                    >
                      <Sparkles className="h-3.5 w-3.5" />
                      <span>{isParsing ? "Analyzing..." : "Extract Sections with AI"}</span>
                    </button>
                  </div>

                  {aiDraftNotice && (
                    <div className="flex items-center gap-2 rounded-lg bg-emerald-100/80 px-3 py-2 text-xs font-medium text-emerald-900 border border-emerald-200">
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700 shrink-0" />
                      <span>{aiDraftNotice}</span>
                    </div>
                  )}

                  {guestNotice && (
                    <div className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-900 border border-amber-200">
                      <Info className="h-3.5 w-3.5 text-amber-700 shrink-0 mt-0.5" />
                      <span>{guestNotice}</span>
                    </div>
                  )}
                </div>
              )}

              <ExperimentDetailsForm
                formData={formData}
                errors={errors}
                onChange={handleFieldChange}
                onClearError={handleClearError}
              />
            </div>
          )}

          {/* Manual Entry */}
          {formData.method === "manual" && (
            <ManualExperimentForm
              formData={formData}
              errors={errors}
              onChange={handleFieldChange}
              onClearError={handleClearError}
            />
          )}

          {/* Action Buttons */}
          <ExperimentFormActions
            isSubmitting={isSubmitting}
            canSubmit={canSubmit}
            onCancel={() => onNavigate("/experiments")}
            onSubmit={handleSubmit}
            validationError={
              errors.title || errors.subject || errors.file || errors.general
            }
            isGuest={user.isGuest}
          />
        </form>
      )}

      {/* AI Section Review Modal */}
      <ManualSectionReviewModal
        isOpen={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        parseResult={parseResult}
        rawExtractedText={rawExtractedText}
        isLoading={isParsing}
        error={parseError}
        onRetry={handleInitiateAIParse}
        onAccept={handleAcceptParsedSections}
        fileName={formData.file?.name}
      />
    </div>
  );
};

export default NewExperimentPage;
