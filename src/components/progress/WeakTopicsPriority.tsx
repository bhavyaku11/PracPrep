import React from "react";
import {
  AlertTriangle,
  BookOpen,
  HelpCircle,
} from "lucide-react";
import type { RevisionPriorityItem } from "../../types/progress";

interface WeakTopicsPriorityProps {
  priorities: RevisionPriorityItem[];
  onNavigate: (path: string) => void;
}

export const WeakTopicsPriority: React.FC<WeakTopicsPriorityProps> = ({
  priorities,
  onNavigate,
}) => {
  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            Focus on These Topics (Revision Priorities)
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Key conceptual gaps and omissions flagged during oral examinations
          </p>
        </div>

        {priorities.length > 0 && (
          <span className="text-xs font-semibold px-2 py-0.5 rounded bg-amber-100 dark:bg-amber-950 text-amber-800 dark:text-amber-300 self-start sm:self-auto">
            {priorities.length} {priorities.length === 1 ? "priority" : "priorities"} flagged
          </span>
        )}
      </div>

      {priorities.length === 0 ? (
        <div className="p-6 text-center bg-neutral-50/60 dark:bg-neutral-800/30 rounded-xl border border-dashed border-neutral-200 dark:border-neutral-800 space-y-2">
          <HelpCircle className="w-8 h-8 text-neutral-400 mx-auto" />
          <h3 className="text-sm font-bold text-neutral-800 dark:text-neutral-200">
            No revision priorities identified yet.
          </h3>
          <p className="text-xs text-neutral-500 max-w-md mx-auto">
            Complete a few viva sessions to build a more detailed picture of your strengths and areas for improvement.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 sm:gap-4">
          {priorities.map((item) => (
            <div
              key={item.id}
              className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/40 dark:bg-amber-950/20 flex flex-col justify-between hover:border-amber-300 transition-all space-y-3"
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-1.5">
                  <span className="text-xs font-bold text-neutral-900 dark:text-white flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-amber-500" />
                    {item.topic}
                  </span>
                  <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-white dark:bg-neutral-900 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                    {item.severity} priority
                  </span>
                </div>

                <div className="text-[11px] text-neutral-500 dark:text-neutral-400 mb-2">
                  Experiment: <strong className="text-neutral-700 dark:text-neutral-300 font-semibold">{item.experimentTitle}</strong>
                </div>

                <p className="text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed bg-white/70 dark:bg-neutral-900/60 p-2.5 rounded-lg border border-neutral-200/60 dark:border-neutral-800">
                  {item.reason}
                </p>
              </div>

              <div className="pt-2 border-t border-amber-200/60 dark:border-amber-900/40 flex items-center justify-between gap-2">
                <span className="text-[11px] font-medium text-amber-900 dark:text-amber-300 truncate max-w-[200px]">
                  {item.suggestedAction}
                </span>

                <button
                  onClick={() => onNavigate(`/experiments/${item.experimentId}`)}
                  className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-white bg-neutral-900 dark:bg-white dark:text-neutral-900 hover:bg-neutral-800 dark:hover:bg-neutral-100 rounded-lg transition-colors flex-shrink-0 shadow-2xs"
                >
                  <BookOpen className="w-3 h-3" />
                  Study in Lab Manual
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default WeakTopicsPriority;
