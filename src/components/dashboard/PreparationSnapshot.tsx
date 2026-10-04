import React from "react";
import { CheckCircle2, MessageSquare, BookOpen } from "lucide-react";

interface PreparationSnapshotProps {
  experimentsCount?: number;
  vivaCount?: number;
  revisionCount?: number;
}

export const PreparationSnapshot: React.FC<PreparationSnapshotProps> = ({
  experimentsCount = 0,
  vivaCount = 0,
  revisionCount = 0,
}) => {
  const metrics = [
    {
      id: "experiments",
      label: "Experiments",
      value: experimentsCount,
      icon: CheckCircle2,
    },
    {
      id: "viva",
      label: "Viva Sessions",
      value: vivaCount,
      icon: MessageSquare,
    },
    {
      id: "revision",
      label: "Revision Topics",
      value: revisionCount,
      icon: BookOpen,
    },
  ];

  return (
    <section aria-labelledby="snapshot-heading" className="space-y-2.5">
      <h2
        id="snapshot-heading"
        className="font-jakarta text-xs font-semibold uppercase tracking-wider text-neutral-500"
      >
        Preparation Snapshot
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div
              key={metric.id}
              className="rounded-xl border border-neutral-200/80 bg-white p-3.5 space-y-1 shadow-2xs min-w-0"
            >
              <div className="flex items-center justify-between text-neutral-400">
                <span className="text-xs text-neutral-500 truncate">{metric.label}</span>
                <Icon className="h-3.5 w-3.5 shrink-0 ml-2" />
              </div>
              <div className="font-jakarta text-xl font-bold text-neutral-900">
                {metric.value}
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default PreparationSnapshot;
