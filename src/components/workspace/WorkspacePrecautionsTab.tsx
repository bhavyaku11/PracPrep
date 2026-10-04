import React, { useMemo } from "react";
import { ShieldAlert, Edit2, ShieldCheck } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface WorkspacePrecautionsTabProps {
  experiment: ExperimentRecord;
  onEdit: () => void;
}

export const WorkspacePrecautionsTab: React.FC<WorkspacePrecautionsTabProps> = ({
  experiment,
  onEdit,
}) => {
  const hasPrecautions = Boolean(experiment.precautions && experiment.precautions.trim().length > 0);

  // Parse precautions lines
  const precautionItems = useMemo(() => {
    if (!experiment.precautions) return [];
    return experiment.precautions
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((item, index) => {
        const clean = item.replace(/^(\d+[.)]|-|\*)\s*/, "").trim();
        return {
          id: index + 1,
          text: clean || item,
        };
      });
  }, [experiment.precautions]);

  return (
    <div className="space-y-4">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-200">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-50 text-amber-800">
            <ShieldAlert className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-jakarta text-base font-bold text-neutral-900">
              Precautions & Safety Instructions
            </h2>
            <p className="text-xs text-neutral-500">
              Essential safety guidelines, circuit limits, and handling precautions.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onEdit}
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors shadow-2xs self-start sm:self-auto"
        >
          <Edit2 className="h-3.5 w-3.5" />
          <span>Edit Precautions</span>
        </button>
      </div>

      {/* Content or Empty State */}
      {hasPrecautions && precautionItems.length > 0 ? (
        <div className="space-y-3">
          <div className="space-y-2.5">
            {precautionItems.map((item) => (
              <div
                key={item.id}
                className="flex items-start gap-3 rounded-xl border border-amber-200/60 bg-amber-50/20 p-4 transition-colors shadow-2xs"
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-amber-100/80 text-amber-800 text-xs font-mono font-semibold mt-0.5">
                  {item.id}
                </div>
                <p className="text-xs sm:text-sm text-neutral-800 leading-relaxed font-normal break-words flex-1">
                  {item.text}
                </p>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs text-neutral-500 pt-1 px-1">
            <span>{precautionItems.length} safety precautions recorded</span>
            <span>Always adhere strictly to laboratory safety instructions.</span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-neutral-200 bg-white py-14 px-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-500 mb-3">
            <ShieldCheck className="h-6 w-6" />
          </div>
          <h3 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900 mb-1">
            No precautions added yet.
          </h3>
          <p className="max-w-md text-xs text-neutral-500 leading-relaxed mb-5">
            Document important equipment handling warnings, electrical hazards, or safety measures before beginning work.
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

export default WorkspacePrecautionsTab;
