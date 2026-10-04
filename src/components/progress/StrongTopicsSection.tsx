import React from "react";
import { Award, CheckCircle2 } from "lucide-react";
import type { StrongTopicItem } from "../../types/progress";

interface StrongTopicsSectionProps {
  strongTopics: StrongTopicItem[];
}

export const StrongTopicsSection: React.FC<StrongTopicsSectionProps> = ({
  strongTopics,
}) => {
  if (strongTopics.length === 0) return null;

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-3">
      <div className="flex items-center gap-2 pb-2 border-b border-neutral-100 dark:border-neutral-800">
        <Award className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
        <h2 className="text-sm sm:text-base font-bold text-neutral-900 dark:text-white">
          Demonstrated Strengths
        </h2>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {strongTopics.map((st) => (
          <div
            key={st.topic}
            className="p-3.5 rounded-xl border border-emerald-200/80 dark:border-emerald-800/40 bg-emerald-50/40 dark:bg-emerald-950/20 space-y-1.5"
          >
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-emerald-900 dark:text-emerald-300 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
                {st.topic}
              </span>
              <span className="font-bold text-emerald-800 dark:text-emerald-300">
                {st.averageScore.toFixed(1)}/10 avg
              </span>
            </div>
            <p className="text-[11px] text-emerald-950 dark:text-emerald-200 leading-snug">
              {st.notes}
            </p>
            {st.experimentTitles.length > 0 && (
              <p className="text-[10px] text-emerald-800/80 dark:text-emerald-400 truncate">
                Demonstrated in: {st.experimentTitles.join(", ")}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default StrongTopicsSection;
