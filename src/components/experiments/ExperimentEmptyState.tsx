import React from "react";
import { FlaskConical, SearchX, FilterX, Plus, RotateCcw } from "lucide-react";

export type EmptyStateType = "no-experiments" | "no-search-results" | "no-filter-results";

interface ExperimentEmptyStateProps {
  type: EmptyStateType;
  statusLabel?: string;
  onAction: () => void;
}

export const ExperimentEmptyState: React.FC<ExperimentEmptyStateProps> = ({
  type,
  onAction,
}) => {
  if (type === "no-experiments") {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-neutral-300 bg-white py-14 px-4 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-50 text-emerald-700 mb-3">
          <FlaskConical className="h-6 w-6" />
        </div>
        <h3 className="font-jakarta text-base font-bold text-neutral-900 mb-1">
          Your lab workspace is ready.
        </h3>
        <p className="max-w-md text-xs sm:text-sm text-neutral-500 leading-relaxed mb-5">
          Create your first experiment by uploading a lab manual or entering the details manually.
        </p>
        <button
          type="button"
          onClick={onAction}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-neutral-900 px-5 text-xs sm:text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
        >
          <Plus className="h-4 w-4" />
          <span>Create Your First Experiment</span>
        </button>
      </div>
    );
  }

  if (type === "no-search-results") {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-neutral-200/90 bg-white py-12 px-4 text-center shadow-2xs">
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-500 mb-3">
          <SearchX className="h-5 w-5" />
        </div>
        <h3 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900 mb-1">
          No experiments found.
        </h3>
        <p className="max-w-sm text-xs text-neutral-500 leading-relaxed mb-4">
          Try a different keyword or clear your search.
        </p>
        <button
          type="button"
          onClick={onAction}
          className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
        >
          <RotateCcw className="h-3.5 w-3.5" />
          <span>Clear Search</span>
        </button>
      </div>
    );
  }

  // type === "no-filter-results"
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-neutral-200/90 bg-white py-12 px-4 text-center shadow-2xs">
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-500 mb-3">
        <FilterX className="h-5 w-5" />
      </div>
      <h3 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900 mb-1">
        Nothing here yet.
      </h3>
      <p className="max-w-sm text-xs text-neutral-500 leading-relaxed mb-4">
        There are no experiments in this status.
      </p>
      <button
        type="button"
        onClick={onAction}
        className="inline-flex h-9 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
      >
        <RotateCcw className="h-3.5 w-3.5" />
        <span>Clear Filter</span>
      </button>
    </div>
  );
};

export default ExperimentEmptyState;
