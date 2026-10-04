import React from "react";
import { Layers, Clock, CheckCircle2, FileEdit } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface ExperimentSummaryRowProps {
  experiments: ExperimentRecord[];
}

export const ExperimentSummaryRow: React.FC<ExperimentSummaryRowProps> = ({ experiments }) => {
  const total = experiments.length;
  
  // In Progress includes "in-progress", "ready", and "analyzing"
  const inProgress = experiments.filter(
    (e) => e.status === "in-progress" || e.status === "ready" || e.status === "analyzing"
  ).length;

  const completed = experiments.filter((e) => e.status === "completed").length;
  const drafts = experiments.filter((e) => e.status === "draft").length;

  const metrics = [
    {
      id: "total",
      label: "Total Experiments",
      value: total,
      hint: total === 1 ? "1 experiment" : `${total} experiments`,
      icon: Layers,
      textColor: "text-neutral-900",
      accentBg: "bg-neutral-100 text-neutral-700",
    },
    {
      id: "drafts",
      label: "Drafts",
      value: drafts,
      hint: drafts === 1 ? "1 draft" : `${drafts} drafts`,
      icon: FileEdit,
      textColor: "text-neutral-700",
      accentBg: "bg-neutral-100 text-neutral-600",
    },
    {
      id: "in-progress",
      label: "In Progress",
      value: inProgress,
      hint: inProgress === 1 ? "1 active" : `${inProgress} active`,
      icon: Clock,
      textColor: inProgress > 0 ? "text-amber-800" : "text-neutral-900",
      accentBg: "bg-amber-50 text-amber-700",
    },
    {
      id: "completed",
      label: "Completed",
      value: completed,
      hint: completed === 1 ? "1 finished" : `${completed} finished`,
      icon: CheckCircle2,
      textColor: completed > 0 ? "text-emerald-800" : "text-neutral-900",
      accentBg: "bg-emerald-100 text-emerald-800",
    },
  ];

  return (
    <section aria-label="Experiment Summary" className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      {metrics.map((item) => {
        const Icon = item.icon;
        return (
          <div
            key={item.id}
            className="flex items-center justify-between p-3.5 sm:p-4 rounded-xl border border-neutral-200/80 bg-white shadow-2xs min-w-0"
          >
            <div className="space-y-0.5 min-w-0">
              <p className="text-[11px] sm:text-xs font-medium text-neutral-500 truncate">
                {item.label}
              </p>
              <p className={`font-jakarta text-xl sm:text-2xl font-bold ${item.textColor}`}>
                {item.value}
              </p>
              <p className="text-[10px] sm:text-[11px] text-neutral-400 truncate">
                {item.hint}
              </p>
            </div>

            <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${item.accentBg}`}>
              <Icon className="h-4 w-4" />
            </div>
          </div>
        );
      })}
    </section>
  );
};

export default ExperimentSummaryRow;
