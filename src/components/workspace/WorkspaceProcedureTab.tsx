import React, { useState, useMemo } from "react";
import { ListOrdered, Edit2, CheckCircle2 } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface WorkspaceProcedureTabProps {
  experiment: ExperimentRecord;
  onEdit: () => void;
}

export const WorkspaceProcedureTab: React.FC<WorkspaceProcedureTabProps> = ({
  experiment,
  onEdit,
}) => {
  const [activeStep, setActiveStep] = useState<number | null>(null);

  const hasProcedure = Boolean(experiment.procedure && experiment.procedure.trim().length > 0);

  // Parse procedure into clean steps without rewriting content
  const steps = useMemo(() => {
    if (!experiment.procedure) return [];
    return experiment.procedure
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((line, idx) => {
        // Look for step numbers like "1. ", "Step 1: ", "1) "
        const match = line.match(/^(?:Step\s*)?(\d+)[:.)]\s*(.*)$/i);
        if (match) {
          return {
            stepNumber: parseInt(match[1], 10),
            text: match[2] || line,
          };
        }
        return {
          stepNumber: idx + 1,
          text: line,
        };
      });
  }, [experiment.procedure]);

  return (
    <div className="space-y-4">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-200">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-800">
            <ListOrdered className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-jakarta text-base font-bold text-neutral-900">
              Laboratory Procedure Steps
            </h2>
            <p className="text-xs text-neutral-500">
              Sequential guide to set up, operate, and collect measurements.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onEdit}
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors shadow-2xs self-start sm:self-auto"
        >
          <Edit2 className="h-3.5 w-3.5" />
          <span>Edit Procedure</span>
        </button>
      </div>

      {/* Content or Empty State */}
      {hasProcedure && steps.length > 0 ? (
        <div className="space-y-3">
          <div className="space-y-2.5">
            {steps.map((step) => {
              const isSelected = activeStep === step.stepNumber;
              return (
                <div
                  key={step.stepNumber}
                  onClick={() => setActiveStep(isSelected ? null : step.stepNumber)}
                  className={`group relative flex items-start gap-3.5 rounded-xl border p-4 transition-all cursor-pointer ${
                    isSelected
                      ? "border-emerald-600 bg-emerald-50/40 ring-1 ring-emerald-600/20 shadow-2xs"
                      : "border-neutral-200/90 bg-white hover:border-neutral-300 hover:bg-neutral-50/60 shadow-2xs"
                  }`}
                >
                  <div
                    className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-mono font-bold transition-colors ${
                      isSelected
                        ? "bg-emerald-700 text-white"
                        : "bg-neutral-100 text-neutral-700 group-hover:bg-neutral-200"
                    }`}
                  >
                    {step.stepNumber}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-0.5">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
                        Step {step.stepNumber}
                      </span>
                      {isSelected ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-800">
                          <CheckCircle2 className="h-3 w-3" />
                          <span>Active Focus</span>
                        </span>
                      ) : (
                        <span className="text-[11px] text-neutral-400 opacity-0 group-hover:opacity-100 transition-opacity">
                          Click to focus
                        </span>
                      )}
                    </div>
                    <p className="text-xs sm:text-sm text-neutral-800 leading-relaxed break-words font-normal whitespace-pre-wrap">
                      {step.text}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between text-xs text-neutral-500 pt-1 px-1">
            <span>{steps.length} sequential procedure steps</span>
            <span>Click any step to mark your current place during lab work.</span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-neutral-200 bg-white py-14 px-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-500 mb-3">
            <ListOrdered className="h-6 w-6" />
          </div>
          <h3 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900 mb-1">
            No procedure steps provided.
          </h3>
          <p className="max-w-md text-xs text-neutral-500 leading-relaxed mb-5">
            Add the sequential execution steps to guide your experiments and laboratory observations.
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

export default WorkspaceProcedureTab;
