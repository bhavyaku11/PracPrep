import React from "react";
import { Loader2, Plus, ArrowLeft } from "lucide-react";

interface ExperimentFormActionsProps {
  isSubmitting: boolean;
  canSubmit: boolean;
  onCancel: () => void;
  onSubmit: (e: React.FormEvent) => void;
  validationError?: string;
  isGuest?: boolean;
}

export const ExperimentFormActions: React.FC<ExperimentFormActionsProps> = ({
  isSubmitting,
  canSubmit,
  onCancel,
  onSubmit,
  validationError,
}) => {
  return (
    <div className="space-y-3 pt-1">
      {validationError && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-2.5 text-xs text-amber-900">
          <span>{validationError}</span>
        </div>
      )}

      <div className="flex flex-col-reverse sm:flex-row sm:items-center justify-between gap-3 pt-3 border-t border-neutral-200/80">
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="inline-flex h-10 w-full sm:w-auto items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 hover:border-neutral-900 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 disabled:opacity-50"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Cancel</span>
        </button>

        <button
          type="button"
          onClick={onSubmit}
          disabled={!canSubmit || isSubmitting}
          className="inline-flex h-10 w-full sm:w-auto items-center justify-center gap-1.5 rounded-lg bg-neutral-900 px-5 text-xs font-semibold text-white shadow-sm transition-all hover:bg-emerald-700 active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-neutral-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
              <span>Creating...</span>
            </>
          ) : (
            <>
              <Plus className="h-3.5 w-3.5" />
              <span>Create Experiment</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default ExperimentFormActions;
