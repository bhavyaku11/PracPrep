import React from "react";
import {
  Compass,
  ArrowRight,
  BookOpen,
  Sparkles,
  CheckSquare,
} from "lucide-react";
import type { RecommendedNextStep } from "../../types/progress";

interface RevisionPlannerSectionProps {
  steps: RecommendedNextStep[];
  onNavigate: (path: string) => void;
}

export const RevisionPlannerSection: React.FC<RevisionPlannerSectionProps> = ({
  steps,
  onNavigate,
}) => {
  if (steps.length === 0) return null;

  const getStepIcon = (category: RecommendedNextStep["category"]) => {
    switch (category) {
      case "revision":
        return <BookOpen className="w-4 h-4 text-amber-600 dark:text-amber-400" />;
      case "prep":
        return <CheckSquare className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
      case "viva":
      default:
        return <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />;
    }
  };

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-2 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <Compass className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            Revision Planner — Recommended Next Steps
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Targeted preparation actions dynamically prioritized by your laboratory readiness and exam data
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {steps.map((step) => (
          <div
            key={step.id}
            className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-800/20 flex flex-col justify-between hover:border-neutral-300 dark:hover:border-neutral-700 transition-all space-y-3"
          >
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                {getStepIcon(step.category)}
                <h3 className="text-xs sm:text-sm font-bold text-neutral-900 dark:text-white">
                  {step.title}
                </h3>
              </div>
              <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
                {step.description}
              </p>
            </div>

            <div className="pt-2 border-t border-neutral-200/60 dark:border-neutral-800 flex justify-end">
              <button
                onClick={() => onNavigate(step.targetPath)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-neutral-900 dark:text-white bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-700 shadow-2xs transition-colors"
              >
                <span>{step.actionLabel}</span>
                <ArrowRight className="w-3 h-3 text-neutral-400" />
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RevisionPlannerSection;
