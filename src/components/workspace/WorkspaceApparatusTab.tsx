import React, { useMemo } from "react";
import { Wrench, Edit2, PackageOpen } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface WorkspaceApparatusTabProps {
  experiment: ExperimentRecord;
  onEdit: () => void;
}

export const WorkspaceApparatusTab: React.FC<WorkspaceApparatusTabProps> = ({
  experiment,
  onEdit,
}) => {
  const hasApparatus = Boolean(experiment.apparatus && experiment.apparatus.trim().length > 0);

  // Split lines into structured items
  const apparatusItems = useMemo(() => {
    if (!experiment.apparatus) return [];
    return experiment.apparatus
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((item, index) => {
        // Strip common leading bullets/numbers like "1. ", "- ", "* "
        const clean = item.replace(/^(\d+[.)]|-|\*)\s*/, "").trim();
        return {
          id: index + 1,
          raw: clean || item,
        };
      });
  }, [experiment.apparatus]);

  return (
    <div className="space-y-4">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-200">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-800">
            <Wrench className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-jakarta text-base font-bold text-neutral-900">
              Apparatus & Required Equipment
            </h2>
            <p className="text-xs text-neutral-500">
              Hardware, components, and instruments needed for this laboratory session.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onEdit}
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors shadow-2xs self-start sm:self-auto"
        >
          <Edit2 className="h-3.5 w-3.5" />
          <span>Edit Apparatus</span>
        </button>
      </div>

      {/* Content or Empty State */}
      {hasApparatus && apparatusItems.length > 0 ? (
        <div className="space-y-3">
          <div className="rounded-xl border border-neutral-200/90 bg-white divide-y divide-neutral-100 shadow-2xs overflow-hidden">
            {apparatusItems.map((item) => (
              <div
                key={item.id}
                className="flex items-center gap-3 p-3.5 sm:px-5 hover:bg-neutral-50/60 transition-colors"
              >
                <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-neutral-100 text-neutral-600 text-[11px] font-mono font-medium">
                  {item.id}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-xs sm:text-sm text-neutral-800 font-medium leading-snug break-words">
                    {item.raw}
                  </p>
                </div>
              </div>
            ))}
          </div>

          <div className="flex items-center justify-between text-xs text-neutral-500 px-1">
            <span>Total apparatus items: {apparatusItems.length}</span>
            <span>Check equipment before beginning your experiment setup.</span>
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-neutral-200 bg-white py-14 px-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-500 mb-3">
            <PackageOpen className="h-6 w-6" />
          </div>
          <h3 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900 mb-1">
            No apparatus listed yet.
          </h3>
          <p className="max-w-md text-xs text-neutral-500 leading-relaxed mb-5">
            List the required meters, components, and instruments to ensure you have everything ready before your lab session.
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

export default WorkspaceApparatusTab;
