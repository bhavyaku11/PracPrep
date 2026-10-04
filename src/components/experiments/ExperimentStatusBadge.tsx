import React from "react";
import type { ExperimentStatus } from "../../types/experiment";

interface ExperimentStatusBadgeProps {
  status: ExperimentStatus;
  className?: string;
}

export const ExperimentStatusBadge: React.FC<ExperimentStatusBadgeProps> = ({ status, className = "" }) => {
  const getBadgeStyle = () => {
    switch (status) {
      case "draft":
        return {
          label: "Draft",
          classes: "bg-neutral-100 text-neutral-700 border-neutral-200/90",
          dotColor: "bg-neutral-400",
        };
      case "completed":
        return {
          label: "Completed",
          classes: "bg-emerald-100 text-emerald-900 border-emerald-200",
          dotColor: "bg-emerald-600",
        };
      case "in-progress":
        return {
          label: "In Progress",
          classes: "bg-emerald-50 text-emerald-800 border-emerald-200/80",
          dotColor: "bg-emerald-500",
        };
      case "analyzing":
        return {
          label: "Analyzing",
          classes: "bg-amber-50 text-amber-800 border-amber-200/80",
          dotColor: "bg-amber-500 animate-pulse",
        };
      case "ready":
      default:
        return {
          label: "Ready",
          classes: "bg-emerald-50 text-emerald-800 border-emerald-200/80",
          dotColor: "bg-emerald-500",
        };
    }
  };

  const info = getBadgeStyle();

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold tracking-wide ${info.classes} ${className}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${info.dotColor}`} aria-hidden="true" />
      <span>{info.label}</span>
    </span>
  );
};

export default ExperimentStatusBadge;
