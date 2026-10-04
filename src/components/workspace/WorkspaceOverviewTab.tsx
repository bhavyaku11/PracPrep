import React, { useState } from "react";
import {
  Target,
  FileText,
  Calendar,
  Clock,
  CheckCircle2,
  FileUp,
  Edit2,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";
import type { UserSession } from "../../types/dashboard";
import type {
  ManualParseResponse,
  ParsedExperimentSections,
} from "../../types/document";
import {
  documentService,
  formatDocumentApiError,
} from "../../services/documentService";
import { experimentStorage } from "../../services/experimentStorage";
import ManualSectionReviewModal from "../experiment/ManualSectionReviewModal";

interface WorkspaceOverviewTabProps {
  experiment: ExperimentRecord;
  checklistCount: { completed: number; total: number; percentage: number };
  onNavigateTab: (tab: "theory" | "apparatus" | "procedure" | "observations" | "precautions" | "checklist") => void;
  onEdit: (section?: "basic" | "content") => void;
  user?: UserSession;
}

export const WorkspaceOverviewTab: React.FC<WorkspaceOverviewTabProps> = ({
  experiment,
  checklistCount,
  onNavigateTab,
  onEdit,
  user,
}) => {
  const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<ManualParseResponse | null>(null);
  const [rawExtractedText, setRawExtractedText] = useState<string | null>(null);

  const handleOpenAIParser = async () => {
    if (user?.isGuest) {
      alert("AI Section Parsing is an authenticated feature. Please sign in to parse lab manuals with AI.");
      return;
    }

    setParseError(null);
    setIsParsing(true);
    setIsReviewModalOpen(true);

    try {
      let result: ManualParseResponse;
      try {
        result = await documentService.parseManualSections(experiment.id);
      } catch (err: any) {
        // If extraction hasn't been run yet, trigger text extraction first
        if (err?.status === 400 && String(err?.detail || "").includes("extraction")) {
          const ext = await documentService.extractManualText(experiment.id);
          setRawExtractedText(ext.extractedText);
          result = await documentService.parseManualSections(experiment.id);
        } else {
          throw err;
        }
      }

      setParseResult(result);
    } catch (err: unknown) {
      const msg = formatDocumentApiError(err, "parsing lab manual");
      setParseError(msg);
    } finally {
      setIsParsing(false);
    }
  };

  const handleAcceptParsedSections = (reviewed: ParsedExperimentSections) => {
    experimentStorage.updateExperiment(
      experiment.id,
      {
        title: reviewed.title?.trim() || experiment.title,
        subject: reviewed.subject?.trim() || experiment.subject,
        experimentNumber: reviewed.experimentNumber?.trim() || experiment.experimentNumber,
        objective: reviewed.objective?.trim() || experiment.objective,
        theory: reviewed.theory?.trim() || experiment.theory,
        apparatus: reviewed.apparatus?.trim() || experiment.apparatus,
        procedure: reviewed.procedure?.trim() || experiment.procedure,
        precautions: reviewed.precautions?.trim() || experiment.precautions,
        observations: reviewed.observations?.trim() || experiment.observations,
        calculations: reviewed.calculations?.trim() || experiment.calculations,
        description: reviewed.additionalNotes?.trim() || experiment.description,
      },
      user
    );
  };
  return (
    <div className="space-y-6">
      {/* 1. Top Cards Grid: Objective & Preparation Readiness */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Objective & Scope Card (spans 2 cols on lg) */}
        <div className="lg:col-span-2 rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-2xs space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-800">
                <Target className="h-4 w-4" />
              </div>
              <h2 className="font-jakarta text-base font-bold text-neutral-900">
                Experiment Objective & Aim
              </h2>
            </div>
            <button
              type="button"
              onClick={() => onEdit("content")}
              className="inline-flex items-center gap-1 text-xs font-semibold text-neutral-600 hover:text-emerald-700 hover:underline"
            >
              <Edit2 className="h-3 w-3" />
              <span>Edit</span>
            </button>
          </div>

          {experiment.objective ? (
            <p className="text-xs sm:text-sm text-neutral-800 leading-relaxed font-normal whitespace-pre-wrap bg-neutral-50/70 p-4 rounded-xl border border-neutral-100">
              {experiment.objective}
            </p>
          ) : (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-neutral-50/50 p-5 text-center space-y-2">
              <p className="text-xs text-neutral-500">
                No formal objective specified for this experiment yet.
              </p>
              <button
                type="button"
                onClick={() => onEdit("content")}
                className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
              >
                <Edit2 className="h-3 w-3" />
                <span>Add Aim / Objective</span>
              </button>
            </div>
          )}

          {/* Description or Summary */}
          {experiment.description ? (
            <div className="pt-2 border-t border-neutral-100">
              <span className="block text-[11px] font-semibold uppercase tracking-wider text-neutral-400 mb-1">
                Student Notes & Overview
              </span>
              <p className="text-xs text-neutral-600 leading-relaxed whitespace-pre-wrap">
                {experiment.description}
              </p>
            </div>
          ) : null}
        </div>

        {/* Preparation Readiness Card */}
        <div className="rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-2xs space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
                Preparation Progress
              </span>
              <span className="font-jakarta text-sm font-bold text-emerald-800">
                {checklistCount.percentage}% Ready
              </span>
            </div>

            {/* Dynamic Progress Bar */}
            <div className="h-2 w-full overflow-hidden rounded-full bg-neutral-100">
              <div
                className="h-full rounded-full bg-emerald-700 transition-all duration-300"
                style={{ width: `${checklistCount.percentage}%` }}
              />
            </div>

            <div className="mt-3 flex items-center justify-between text-xs text-neutral-600">
              <span className="flex items-center gap-1.5 font-medium">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-700" />
                {checklistCount.completed} of {checklistCount.total} items completed
              </span>
              <span className="text-neutral-400">
                {checklistCount.total - checklistCount.completed} remaining
              </span>
            </div>
          </div>

          <div className="pt-4 border-t border-neutral-100 space-y-2">
            <p className="text-[11px] text-neutral-500 leading-normal">
              Review theory, apparatus, procedure, and safety precautions before entering the lab.
            </p>
            <button
              type="button"
              onClick={() => onNavigateTab("checklist")}
              className="w-full inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-neutral-900 px-3 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 transition-colors"
            >
              <span>Open Preparation Checklist</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      </div>

      {/* 2. Metadata & Document Source Section */}
      <div className="rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-2xl-none space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-neutral-100">
          <h3 className="font-jakarta text-sm font-bold text-neutral-900">
            Source & Academic Context
          </h3>
          <div className="flex items-center gap-2">
            {(experiment.hasManualFile || experiment.method === "upload") && (
              <button
                type="button"
                onClick={handleOpenAIParser}
                disabled={isParsing}
                className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-50 border border-emerald-200 px-2.5 py-1 text-xs font-semibold text-emerald-800 hover:bg-emerald-100 transition-colors shadow-2xs"
              >
                <Sparkles className="h-3 w-3 text-emerald-700" />
                <span>{isParsing ? "Parsing..." : "AI Section Parser"}</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => onEdit("basic")}
              className="inline-flex items-center gap-1 text-xs font-semibold text-neutral-600 hover:text-emerald-700 hover:underline"
            >
              <Edit2 className="h-3 w-3" />
              <span>Edit Metadata</span>
            </button>
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-xs">
          {/* Method / Source */}
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-neutral-400">Source Type</span>
            <div className="flex items-center gap-1.5 font-semibold text-neutral-800">
              {experiment.hasManualFile || experiment.method === "upload" ? (
                <>
                  <FileUp className="h-3.5 w-3.5 text-emerald-700" />
                  <span>Lab Manual Upload</span>
                </>
              ) : (
                <>
                  <FileText className="h-3.5 w-3.5 text-neutral-600" />
                  <span>Manual Entry</span>
                </>
              )}
            </div>
            {experiment.fileName && (
              <p className="text-[11px] font-mono text-neutral-500 truncate" title={experiment.fileName}>
                {experiment.fileName}
              </p>
            )}
          </div>

          {/* Subject / Lab */}
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-neutral-400">Subject / Lab</span>
            <p className="font-semibold text-neutral-900 truncate" title={experiment.subject}>
              {experiment.subject}
            </p>
            {experiment.courseSemester && (
              <p className="text-[11px] text-neutral-500">{experiment.courseSemester}</p>
            )}
          </div>

          {/* Experiment Number */}
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-neutral-400">Experiment No.</span>
            <p className="font-semibold font-mono text-neutral-900">
              {experiment.experimentNumber || "Unassigned"}
            </p>
          </div>

          {/* Timestamps */}
          <div className="space-y-1">
            <span className="text-[11px] font-medium text-neutral-400">Timestamps</span>
            <div className="flex items-center gap-1 text-neutral-600 text-[11px]">
              <Calendar className="h-3 w-3 text-neutral-400" />
              <span>Created {experiment.createdAt}</span>
            </div>
            <div className="flex items-center gap-1 text-neutral-600 text-[11px]">
              <Clock className="h-3 w-3 text-neutral-400" />
              <span>Updated {experiment.updatedAt}</span>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Quick Section Navigation Cards */}
      <div className="space-y-2 pt-2">
        <h3 className="font-jakarta text-sm font-bold text-neutral-900">
          Workspace Study Sections
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            { id: "theory", title: "Theory", hasContent: !!experiment.theory },
            { id: "apparatus", title: "Apparatus", hasContent: !!experiment.apparatus },
            { id: "procedure", title: "Procedure", hasContent: !!experiment.procedure },
            { id: "observations", title: "Observations", hasContent: !!(experiment.observations || experiment.calculations) },
            { id: "precautions", title: "Precautions", hasContent: !!experiment.precautions },
            { id: "checklist", title: "Checklist", hasContent: true },
          ].map((sec) => (
            <button
              key={sec.id}
              type="button"
              onClick={() => onNavigateTab(sec.id as any)}
              className="flex flex-col items-start justify-between p-3 rounded-xl border border-neutral-200/80 bg-white hover:border-emerald-600/60 hover:bg-neutral-50/70 transition-all text-left shadow-2xs group"
            >
              <span className="text-xs font-semibold text-neutral-900 group-hover:text-emerald-800 transition-colors">
                {sec.title}
              </span>
              <span className="mt-2 text-[10px] font-medium px-1.5 py-0.5 rounded bg-neutral-100 text-neutral-600">
                {sec.hasContent ? "Available" : "Not added"}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* AI Section Review Modal */}
      <ManualSectionReviewModal
        isOpen={isReviewModalOpen}
        onClose={() => setIsReviewModalOpen(false)}
        parseResult={parseResult}
        rawExtractedText={rawExtractedText}
        isLoading={isParsing}
        error={parseError}
        onRetry={handleOpenAIParser}
        onAccept={handleAcceptParsedSections}
        fileName={experiment.fileName}
      />
    </div>
  );
};

export default WorkspaceOverviewTab;
