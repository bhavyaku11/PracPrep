import React from "react";
import { CheckSquare, Check, ArrowRight, RotateCcw } from "lucide-react";
import type { ExperimentRecord, WorkspaceTab } from "../../types/experiment";
import { PREPARATION_CHECKLIST_ITEMS } from "../../types/experiment";

interface WorkspaceChecklistTabProps {
  experiment: ExperimentRecord;
  onToggleItem: (itemId: string, completed: boolean) => void;
  onNavigateTab: (tab: WorkspaceTab) => void;
}

export const WorkspaceChecklistTab: React.FC<WorkspaceChecklistTabProps> = ({
  experiment,
  onToggleItem,
  onNavigateTab,
}) => {
  const checklistState = experiment.preparationChecklist || {};

  const total = PREPARATION_CHECKLIST_ITEMS.length;
  const completedCount = PREPARATION_CHECKLIST_ITEMS.filter(
    (item) => checklistState[item.id] === true
  ).length;
  const percentage = Math.round((completedCount / total) * 100);

  const handleReset = () => {
    PREPARATION_CHECKLIST_ITEMS.forEach((item) => {
      onToggleItem(item.id, false);
    });
  };

  return (
    <div className="space-y-5">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-200">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-800">
            <CheckSquare className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-jakarta text-base font-bold text-neutral-900">
              Laboratory Preparation Checklist
            </h2>
            <p className="text-xs text-neutral-500">
              Interactive readiness verification before performing your experiment.
            </p>
          </div>
        </div>

        {completedCount > 0 && (
          <button
            type="button"
            onClick={handleReset}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors shadow-2xs self-start sm:self-auto"
          >
            <RotateCcw className="h-3 w-3 text-neutral-400" />
            <span>Reset Checklist</span>
          </button>
        )}
      </div>

      {/* Progress Metric Card */}
      <div className="rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-2xs space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
              Preparation Readiness
            </span>
            <p className="font-jakarta text-xl sm:text-2xl font-bold text-neutral-900">
              {percentage}% Complete
            </p>
          </div>
          <div className="text-right">
            <span className="text-xs font-semibold text-emerald-800 bg-emerald-50 px-2.5 py-1 rounded-lg">
              {completedCount} of {total} Completed
            </span>
            <p className="text-[11px] text-neutral-400 mt-1">
              {total - completedCount} items remaining
            </p>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="h-2.5 w-full overflow-hidden rounded-full bg-neutral-100">
          <div
            className="h-full rounded-full bg-emerald-700 transition-all duration-300"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Interactive Checklist Items */}
      <div className="rounded-2xl border border-neutral-200/90 bg-white divide-y divide-neutral-100 shadow-2xs overflow-hidden">
        {PREPARATION_CHECKLIST_ITEMS.map((item, index) => {
          const isChecked = Boolean(checklistState[item.id]);

          return (
            <div
              key={item.id}
              className={`flex items-start justify-between gap-3 p-4 transition-colors ${
                isChecked ? "bg-emerald-50/20" : "hover:bg-neutral-50/60"
              }`}
            >
              <div className="flex items-start gap-3.5 flex-1 min-w-0">
                {/* Accessible Custom Checkbox */}
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={isChecked}
                  aria-label={item.label}
                  onClick={() => onToggleItem(item.id, !isChecked)}
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border transition-all mt-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
                    isChecked
                      ? "border-emerald-700 bg-emerald-700 text-white"
                      : "border-neutral-300 bg-white hover:border-emerald-600"
                  }`}
                >
                  {isChecked && <Check className="h-3.5 w-3.5 stroke-[2.5]" />}
                </button>

                <div className="flex-1 min-w-0">
                  <label
                    onClick={() => onToggleItem(item.id, !isChecked)}
                    className={`block text-xs sm:text-sm font-semibold cursor-pointer select-none transition-colors ${
                      isChecked ? "text-neutral-500 line-through" : "text-neutral-900"
                    }`}
                  >
                    <span className="font-mono text-neutral-400 font-normal mr-1.5">
                      {index + 1}.
                    </span>
                    {item.label}
                  </label>
                  <p className="text-xs text-neutral-500 mt-0.5 leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </div>

              {/* Jump to section action */}
              {item.tabTarget && (
                <button
                  type="button"
                  onClick={() => onNavigateTab(item.tabTarget!)}
                  className="inline-flex items-center gap-1 text-[11px] font-semibold text-neutral-500 hover:text-emerald-800 transition-colors shrink-0 pt-0.5"
                  title={`View ${item.tabTarget} section`}
                >
                  <span className="hidden sm:inline">View</span>
                  <ArrowRight className="h-3 w-3" />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default WorkspaceChecklistTab;
