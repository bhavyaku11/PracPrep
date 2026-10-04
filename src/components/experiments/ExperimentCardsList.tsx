import React from "react";
import { FileText, ArrowRight, Edit2, Trash2, Clock, Calendar } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";
import ExperimentStatusBadge from "./ExperimentStatusBadge";

interface ExperimentCardsListProps {
  experiments: ExperimentRecord[];
  onOpen: (id: string) => void;
  onEdit: (experiment: ExperimentRecord) => void;
  onDelete: (experiment: ExperimentRecord) => void;
}

export const ExperimentCardsList: React.FC<ExperimentCardsListProps> = ({
  experiments,
  onOpen,
  onEdit,
  onDelete,
}) => {
  return (
    <div className="space-y-3">
      {experiments.map((exp) => (
        <div
          key={exp.id}
          className="rounded-xl border border-neutral-200/90 bg-white p-4 shadow-2xs space-y-3 transition-colors hover:border-neutral-300"
        >
          {/* Header Row: Subject & Status */}
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded-md truncate max-w-[180px]">
              {exp.subject}
            </span>
            <ExperimentStatusBadge status={exp.status} />
          </div>

          {/* Title & Experiment number */}
          <div className="space-y-1">
            <div className="flex items-start gap-2">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 mt-0.5">
                <FileText className="h-3.5 w-3.5" />
              </div>
              <div className="min-w-0 flex-1">
                <button
                  type="button"
                  onClick={() => onOpen(exp.id)}
                  className="text-left font-jakarta text-sm font-bold text-neutral-900 hover:text-emerald-700 hover:underline transition-colors block break-words"
                >
                  {exp.title}
                </button>
                <div className="flex flex-wrap items-center gap-2 mt-1 text-[11px] text-neutral-500">
                  {exp.experimentNumber && (
                    <span className="font-mono font-medium text-neutral-700 bg-neutral-100 px-1.5 py-0.2 rounded">
                      {exp.experimentNumber}
                    </span>
                  )}
                  {exp.courseSemester && (
                    <span className="text-neutral-500">{exp.courseSemester}</span>
                  )}
                  {exp.hasManualFile && (
                    <span className="text-neutral-400">• Manual attached</span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Metadata Row: Timestamps */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-neutral-100 text-[11px] text-neutral-400">
            <div className="flex items-center gap-1.5">
              <Clock className="h-3 w-3 shrink-0" />
              <span>Updated {exp.updatedAt}</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Calendar className="h-3 w-3 shrink-0" />
              <span>{exp.createdAt}</span>
            </div>
          </div>

          {/* Action Buttons Row */}
          <div className="flex items-center justify-between gap-2 pt-1">
            <button
              type="button"
              onClick={() => onOpen(exp.id)}
              className="flex-1 inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-neutral-900 px-3 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 transition-colors"
            >
              <span>Open Experiment</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </button>

            <button
              type="button"
              onClick={() => onEdit(exp)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-200 bg-white text-neutral-700 hover:bg-neutral-50 hover:text-neutral-900 transition-colors"
              aria-label={`Edit ${exp.title}`}
            >
              <Edit2 className="h-3.5 w-3.5" />
            </button>

            <button
              type="button"
              onClick={() => onDelete(exp)}
              className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-neutral-200 bg-white text-neutral-400 hover:bg-red-50 hover:text-red-600 hover:border-red-200 transition-colors"
              aria-label={`Delete ${exp.title}`}
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ExperimentCardsList;
