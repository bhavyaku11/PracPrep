import React from "react";
import { Plus, Beaker, FileText, ArrowRight, Clock } from "lucide-react";
import type { ExperimentSummary } from "../../types/dashboard";

interface RecentExperimentsProps {
  experiments: ExperimentSummary[];
  onNavigate: (path: string) => void;
}

export const RecentExperiments: React.FC<RecentExperimentsProps> = ({
  experiments,
  onNavigate,
}) => {
  const hasExperiments = experiments && experiments.length > 0;

  return (
    <section aria-labelledby="recent-experiments-heading" className="space-y-2.5">
      <div className="flex items-center justify-between">
        <h2
          id="recent-experiments-heading"
          className="font-jakarta text-xs font-semibold uppercase tracking-wider text-neutral-500"
        >
          Recent Experiments
        </h2>

        {hasExperiments && (
          <button
            type="button"
            onClick={() => onNavigate("/experiments")}
            className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 hover:text-emerald-800"
          >
            <span>View All</span>
            <ArrowRight className="h-3 w-3" />
          </button>
        )}
      </div>

      {hasExperiments ? (
        <div className="divide-y divide-neutral-200/80 rounded-xl border border-neutral-200/90 bg-white shadow-2xs overflow-hidden">
          {experiments.map((exp) => (
            <div
              key={exp.id}
              className="flex items-center justify-between gap-3 p-3.5 transition-colors hover:bg-neutral-50 min-w-0"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
                  <FileText className="h-4 w-4" />
                </div>
                <div className="min-w-0">
                  <h3 className="font-medium text-neutral-900 text-sm truncate" title={exp.title}>
                    {exp.title}
                  </h3>
                  <div className="flex items-center gap-2 text-xs text-neutral-400 mt-0.5 truncate">
                    <span className="truncate">{exp.subject}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1 shrink-0">
                      <Clock className="h-3 w-3" />
                      {exp.updatedAt}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-2">
                <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 capitalize">
                  {exp.status}
                </span>
                <button
                  type="button"
                  onClick={() => onNavigate(`/experiments/${exp.id}`)}
                  className="rounded-lg border border-neutral-200 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-100"
                >
                  Open
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Clean, Uncluttered Empty State */
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-neutral-300 bg-white py-8 px-4 text-center">
          <Beaker className="h-7 w-7 text-neutral-400 mb-2" />
          <p className="text-xs font-semibold text-neutral-700">No experiments yet</p>
          <button
            type="button"
            onClick={() => onNavigate("/create-experiment")}
            className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-neutral-900 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-emerald-700 transition-colors"
          >
            <Plus className="h-3.5 w-3.5" />
            <span>Create Experiment</span>
          </button>
        </div>
      )}
    </section>
  );
};

export default RecentExperiments;
