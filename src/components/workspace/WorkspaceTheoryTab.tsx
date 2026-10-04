import React from "react";
import { BookOpen, Edit2, BookMarked } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface WorkspaceTheoryTabProps {
  experiment: ExperimentRecord;
  onEdit: () => void;
}

export const WorkspaceTheoryTab: React.FC<WorkspaceTheoryTabProps> = ({
  experiment,
  onEdit,
}) => {
  const hasTheory = Boolean(experiment.theory && experiment.theory.trim().length > 0);

  return (
    <div className="space-y-4">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-200">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-800">
            <BookOpen className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-jakarta text-base font-bold text-neutral-900">
              Theoretical Principles & Equations
            </h2>
            <p className="text-xs text-neutral-500">
              Fundamental laws, concepts, and working principles for this experiment.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onEdit}
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors shadow-2xs self-start sm:self-auto"
        >
          <Edit2 className="h-3.5 w-3.5" />
          <span>Edit Theory</span>
        </button>
      </div>

      {/* Content or Empty State */}
      {hasTheory ? (
        <div className="rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-7 shadow-2xs">
          <article className="prose prose-sm prose-neutral max-w-none space-y-4 text-xs sm:text-sm text-neutral-800 leading-relaxed break-words whitespace-pre-wrap font-normal">
            {experiment.theory}
          </article>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-neutral-200 bg-white py-14 px-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-500 mb-3">
            <BookMarked className="h-6 w-6" />
          </div>
          <h3 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900 mb-1">
            Theory not added yet.
          </h3>
          <p className="max-w-md text-xs text-neutral-500 leading-relaxed mb-5">
            Add the underlying concepts and principles to strengthen your understanding before entering the lab.
          </p>
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-neutral-900 px-4 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 transition-colors"
          >
            <Edit2 className="h-3.5 w-3.5" />
            <span>Edit Experiment</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default WorkspaceTheoryTab;
