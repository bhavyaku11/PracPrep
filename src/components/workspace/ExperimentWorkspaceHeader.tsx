import React from "react";
import {
  ArrowLeft,
  Edit2,
  Sparkles,
  Calendar,
  Clock,
  FileUp,
} from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";
import ExperimentStatusBadge from "../experiments/ExperimentStatusBadge";

interface ExperimentWorkspaceHeaderProps {
  experiment: ExperimentRecord;
  onNavigate: (path: string) => void;
  onEdit: () => void;
}

export const ExperimentWorkspaceHeader: React.FC<ExperimentWorkspaceHeaderProps> = ({
  experiment,
  onNavigate,
  onEdit,
}) => {
  return (
    <div className="space-y-4">
      {/* 1. Breadcrumb navigation */}
      <div className="flex items-center gap-2 text-xs text-neutral-500">
        <button
          type="button"
          onClick={() => onNavigate("/experiments")}
          className="inline-flex items-center gap-1 font-medium text-neutral-600 hover:text-emerald-800 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>My Experiments</span>
        </button>
        <span className="text-neutral-300">/</span>
        <span className="text-neutral-900 font-semibold truncate max-w-xs sm:max-w-md">
          {experiment.title}
        </span>
      </div>

      {/* 2. Main Title Row + Action Buttons */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1.5 min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {experiment.experimentNumber && (
              <span className="font-mono text-xs font-semibold text-neutral-700 bg-neutral-200/70 px-2 py-0.5 rounded-md">
                {experiment.experimentNumber}
              </span>
            )}
            <span className="text-xs font-semibold text-emerald-800 bg-emerald-50 px-2.5 py-0.5 rounded-md">
              {experiment.subject}
            </span>
            {experiment.courseSemester && (
              <span className="text-xs text-neutral-500">
                {experiment.courseSemester}
              </span>
            )}
            <ExperimentStatusBadge status={experiment.status} />
          </div>

          <h1 className="font-jakarta text-xl sm:text-2xl font-bold tracking-tight text-neutral-900 break-words">
            {experiment.title}
          </h1>

          <div className="flex flex-wrap items-center gap-3 text-xs text-neutral-500 pt-0.5">
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5 text-neutral-400" />
              <span>Updated {experiment.updatedAt}</span>
            </span>
            <span className="text-neutral-300">•</span>
            <span className="flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5 text-neutral-400" />
              <span>Created {experiment.createdAt}</span>
            </span>
            {experiment.hasManualFile && (
              <>
                <span className="text-neutral-300">•</span>
                <span className="flex items-center gap-1 text-emerald-700 font-medium">
                  <FileUp className="h-3.5 w-3.5" />
                  <span>Lab Manual Attached</span>
                </span>
              </>
            )}
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-neutral-300 bg-white px-3.5 text-xs font-semibold text-neutral-700 shadow-2xs hover:bg-neutral-50 transition-colors"
          >
            <Edit2 className="h-3.5 w-3.5" />
            <span>Edit Experiment</span>
          </button>

          <button
            type="button"
            onClick={() => onNavigate(`/experiments/${experiment.id}/viva`)}
            className="inline-flex h-9 items-center justify-center gap-1.5 rounded-xl bg-neutral-900 px-4 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 transition-colors"
            title="Practice viva questions for this experiment"
          >
            <Sparkles className="h-3.5 w-3.5 text-emerald-400" />
            <span>Start Viva Practice</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ExperimentWorkspaceHeader;
