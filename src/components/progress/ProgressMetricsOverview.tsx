import React from "react";
import {
  FlaskConical,
  CheckCircle2,
  MessageSquareCode,
  TrendingUp,
  CheckSquare,
} from "lucide-react";
import type { ProgressOverviewMetrics } from "../../types/progress";

interface ProgressMetricsOverviewProps {
  metrics: ProgressOverviewMetrics;
  periodLabel: string;
}

export const ProgressMetricsOverview: React.FC<ProgressMetricsOverviewProps> = ({
  metrics,
  periodLabel,
}) => {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-5 gap-3.5 sm:gap-4">
      {/* 1. Total Experiments */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-neutral-500 mb-2">
          <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Total Experiments
          </span>
          <FlaskConical className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
            {metrics.totalExperiments}
          </div>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
            Available in your lab manual
          </p>
        </div>
      </div>

      {/* 2. Completed Experiments */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-neutral-500 mb-2">
          <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Completed Labs
          </span>
          <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
            {metrics.completedExperiments}
            <span className="text-sm font-normal text-neutral-400 ml-1.5">
              / {metrics.totalExperiments}
            </span>
          </div>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
            Marked as complete in workspace
          </p>
        </div>
      </div>

      {/* 3. Viva Sessions */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-neutral-500 mb-2">
          <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Viva Sessions
          </span>
          <MessageSquareCode className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
            {metrics.completedVivaSessionsCount}
          </div>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
            Oral exams finished ({periodLabel})
          </p>
        </div>
      </div>

      {/* 4. Average Viva Score */}
      <div className="p-4 sm:p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-neutral-500 mb-2">
          <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Avg Viva Score
          </span>
          <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
            {metrics.averageVivaScore !== null ? (
              <>
                {metrics.averageVivaScore}
                <span className="text-xs sm:text-sm font-normal text-neutral-400 ml-1">
                  / 10
                </span>
              </>
            ) : (
              <span className="text-neutral-400 font-normal text-2xl">—</span>
            )}
          </div>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
            {metrics.averageVivaScore !== null
              ? `${Math.round((metrics.averageVivaScore / 10) * 100)}% oral exam average`
              : "No completed vivas yet"}
          </p>
        </div>
      </div>

      {/* 5. Preparation Checklist Progress */}
      <div className="col-span-2 lg:col-span-1 p-4 sm:p-5 rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 shadow-sm flex flex-col justify-between">
        <div className="flex items-center justify-between text-neutral-500 mb-2">
          <span className="text-[11px] sm:text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
            Prep Checklist
          </span>
          <CheckSquare className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        </div>
        <div>
          <div className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
            {metrics.preparationPercentage}%
          </div>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 mt-1">
            {metrics.completedChecklistItems} of {metrics.totalChecklistItems} milestones checked
          </p>
        </div>
      </div>
    </div>
  );
};

export default ProgressMetricsOverview;
