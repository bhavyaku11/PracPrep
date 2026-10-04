import React, { useState } from "react";
import {
  CheckCircle2,
  Clock,
  CircleDashed,
  ExternalLink,
  MessageSquareCode,
  Sparkles,
  Filter,
} from "lucide-react";
import type { ExperimentReadinessItem, ReadinessCategory } from "../../types/progress";

interface LabReadinessOverviewProps {
  items: ExperimentReadinessItem[];
  onNavigate: (path: string) => void;
}

export const LabReadinessOverview: React.FC<LabReadinessOverviewProps> = ({
  items,
  onNavigate,
}) => {
  const [filter, setFilter] = useState<"all" | ReadinessCategory>("all");

  const readyCount = items.filter((i) => i.readinessStatus === "ready").length;
  const inProgressCount = items.filter((i) => i.readinessStatus === "in-progress").length;
  const notStartedCount = items.filter((i) => i.readinessStatus === "not-started").length;

  const filteredItems = items.filter((item) => {
    if (filter === "all") return true;
    return item.readinessStatus === filter;
  });

  const getStatusBadge = (status: ReadinessCategory) => {
    switch (status) {
      case "ready":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            Ready for Lab
          </span>
        );
      case "in-progress":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
            <Clock className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            Prep In Progress
          </span>
        );
      case "not-started":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400 border border-neutral-300 dark:border-neutral-700">
            <CircleDashed className="w-3.5 h-3.5 text-neutral-400" />
            Not Started
          </span>
        );
    }
  };

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-5">
      {/* Header and Filter pills */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            Laboratory Readiness Overview
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Preparation status based on verified checklist completion and oral viva practice
          </p>
        </div>

        {/* Filter buttons */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-neutral-400 flex items-center gap-1 mr-1">
            <Filter className="w-3.5 h-3.5" /> Filter:
          </span>
          <button
            onClick={() => setFilter("all")}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              filter === "all"
                ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
                : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200"
            }`}
          >
            All ({items.length})
          </button>
          <button
            onClick={() => setFilter("ready")}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              filter === "ready"
                ? "bg-emerald-600 text-white"
                : "bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100"
            }`}
          >
            Ready ({readyCount})
          </button>
          <button
            onClick={() => setFilter("in-progress")}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              filter === "in-progress"
                ? "bg-amber-600 text-white"
                : "bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-400 hover:bg-amber-100"
            }`}
          >
            In Progress ({inProgressCount})
          </button>
          <button
            onClick={() => setFilter("not-started")}
            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
              filter === "not-started"
                ? "bg-neutral-700 text-white"
                : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200"
            }`}
          >
            Not Started ({notStartedCount})
          </button>
        </div>
      </div>

      {/* Grid of Experiment Readiness Cards */}
      {filteredItems.length === 0 ? (
        <div className="text-center py-8 text-xs text-neutral-500">
          No experiments match this readiness status.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 sm:gap-4">
          {filteredItems.map((item) => (
            <div
              key={item.experimentId}
              className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50/60 dark:bg-neutral-800/30 flex flex-col justify-between hover:border-neutral-300 dark:hover:border-neutral-700 transition-all"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-2">
                  <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300 px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950">
                    {item.subject}
                  </span>
                  {getStatusBadge(item.readinessStatus)}
                </div>

                <h3 className="text-sm font-bold text-neutral-900 dark:text-white line-clamp-1 mb-2">
                  {item.title}
                </h3>

                {/* Progress bar and milestone count */}
                <div className="space-y-1 mb-3">
                  <div className="flex items-center justify-between text-[11px] text-neutral-500">
                    <span>Preparation Checklist</span>
                    <span className="font-semibold text-neutral-700 dark:text-neutral-300">
                      {item.completedChecklistCount}/{item.totalChecklistCount} steps ({item.checklistPercentage}%)
                    </span>
                  </div>
                  <div className="w-full h-1.5 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        item.checklistPercentage === 100
                          ? "bg-emerald-500"
                          : item.checklistPercentage > 0
                          ? "bg-amber-500"
                          : "bg-neutral-300 dark:bg-neutral-600"
                      }`}
                      style={{ width: `${item.checklistPercentage}%` }}
                    />
                  </div>
                </div>

                {/* Viva Status info */}
                <div className="flex items-center justify-between text-xs py-1.5 px-2.5 rounded-lg bg-white dark:bg-neutral-900 border border-neutral-200/80 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 mb-3">
                  <span className="flex items-center gap-1.5">
                    <MessageSquareCode className="w-3.5 h-3.5 text-emerald-600" />
                    Viva Status:
                  </span>
                  <span className="font-semibold text-neutral-900 dark:text-white">
                    {item.latestVivaScore !== null
                      ? `${item.latestVivaScore.toFixed(1)}/10 (${item.vivaSessionsCount} practiced)`
                      : "Not Practiced Yet"}
                  </span>
                </div>
              </div>

              {/* Action row */}
              <div className="flex items-center justify-between gap-2 pt-2 border-t border-neutral-200/60 dark:border-neutral-800">
                <button
                  onClick={() => onNavigate(`/experiments/${item.experimentId}`)}
                  className="inline-flex items-center gap-1 text-xs font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors"
                >
                  Open Workspace <ExternalLink className="w-3 h-3" />
                </button>

                <button
                  onClick={() => onNavigate(`/experiments/${item.experimentId}/viva`)}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors shadow-2xs"
                >
                  <Sparkles className="w-3 h-3 text-emerald-500" />
                  {item.vivaSessionsCount > 0 ? "Practice Again" : "Start Viva"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default LabReadinessOverview;
