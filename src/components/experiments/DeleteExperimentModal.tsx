import React, { useEffect } from "react";
import { AlertTriangle, Trash2, X } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface DeleteExperimentModalProps {
  experiment: ExperimentRecord | null;
  isOpen: boolean;
  onClose: () => void;
  onConfirmDelete: (id: string) => void;
}

export const DeleteExperimentModal: React.FC<DeleteExperimentModalProps> = ({
  experiment,
  isOpen,
  onClose,
  onConfirmDelete,
}) => {
  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !experiment) return null;

  const handleDelete = () => {
    onConfirmDelete(experiment.id);
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-dialog-title"
      aria-describedby="delete-dialog-description"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/40 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-2xl border border-neutral-200 bg-white p-6 shadow-2xl animate-in zoom-in-95 duration-150 space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <h2
                id="delete-dialog-title"
                className="font-jakarta text-base font-bold text-neutral-900"
              >
                Delete Experiment
              </h2>
              <p className="text-xs text-neutral-500">
                This action is irreversible.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
            aria-label="Close delete dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Target Details Card */}
        <div className="rounded-xl border border-neutral-200/90 bg-neutral-50/70 p-3.5 space-y-1 text-xs">
          <p className="font-semibold text-neutral-900 leading-snug">
            {experiment.title}
          </p>
          <div className="flex items-center gap-2 text-neutral-500 text-[11px]">
            <span>{experiment.subject}</span>
            {experiment.experimentNumber && (
              <>
                <span>•</span>
                <span className="font-mono">{experiment.experimentNumber}</span>
              </>
            )}
            <span>•</span>
            <span>Created {experiment.createdAt}</span>
          </div>
        </div>

        <p id="delete-dialog-description" className="text-xs text-neutral-600 leading-relaxed">
          Are you sure you want to delete this experiment? All associated manual parsing, notes, and records will be removed from your workspace.
        </p>

        {/* Actions */}
        <div className="flex flex-col-reverse sm:flex-row items-center justify-end gap-2.5 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="w-full sm:w-auto inline-flex h-9 items-center justify-center rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleDelete}
            className="w-full sm:w-auto inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-red-600 px-4 text-xs font-semibold text-white shadow-sm hover:bg-red-700 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-600"
          >
            <Trash2 className="h-3.5 w-3.5" />
            <span>Delete Experiment</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default DeleteExperimentModal;
