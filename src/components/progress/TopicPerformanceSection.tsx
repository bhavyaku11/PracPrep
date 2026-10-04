import React from "react";
import {
  BarChart2,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Sparkles,
} from "lucide-react";
import type { TopicAggregatedPerformance, TopicProficiency } from "../../types/progress";

interface TopicPerformanceSectionProps {
  topics: TopicAggregatedPerformance[];
}

export const TopicPerformanceSection: React.FC<TopicPerformanceSectionProps> = ({
  topics,
}) => {
  const getProficiencyBadge = (status: TopicProficiency) => {
    switch (status) {
      case "strong":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Strong Mastery
          </span>
        );
      case "moderate":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300">
            Moderate
          </span>
        );
      case "needs-revision":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-semibold bg-red-100 text-red-800 dark:bg-red-950/80 dark:text-red-300">
            <AlertCircle className="w-3 h-3 text-red-600" />
            Needs Revision
          </span>
        );
      case "unpracticed":
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-neutral-100 text-neutral-600 dark:bg-neutral-800 dark:text-neutral-400">
            <HelpCircle className="w-3 h-3 text-neutral-400" />
            Not Yet Practiced
          </span>
        );
    }
  };

  const hasAnyPractice = topics.some((t) => t.questionsAnswered > 0);

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-5">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <BarChart2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            Topic-Level Oral Exam Performance
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Aggregated proficiency across key experimental domains from completed viva sessions
          </p>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-neutral-500 bg-neutral-50 dark:bg-neutral-800/60 p-2 rounded-lg border border-neutral-200 dark:border-neutral-700 self-start sm:self-auto">
          <Sparkles className="w-3.5 h-3.5 text-emerald-500" />
          <span>Grounded Evaluation Engine</span>
        </div>
      </div>

      {!hasAnyPractice ? (
        <div className="text-center py-8 px-4 bg-neutral-50/50 dark:bg-neutral-800/20 rounded-xl border border-dashed border-neutral-200 dark:border-neutral-800">
          <HelpCircle className="w-8 h-8 text-neutral-400 mx-auto mb-2" />
          <p className="text-sm font-semibold text-neutral-800 dark:text-neutral-200">
            No Topic Analysis Data Available
          </p>
          <p className="text-xs text-neutral-500 max-w-md mx-auto mt-1">
            Complete oral viva practice sessions to generate conceptual proficiency analytics across theory, procedures, apparatus, and precautions.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {topics.map((t) => {
            const hasData = t.questionsAnswered > 0;
            return (
              <div
                key={t.topicKey}
                className="p-3.5 rounded-xl border border-neutral-100 dark:border-neutral-800/80 bg-neutral-50/40 dark:bg-neutral-800/20 space-y-2"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-neutral-900 dark:text-white">
                      {t.topicLabel}
                    </span>
                    {getProficiencyBadge(t.status)}
                  </div>

                  <div className="text-neutral-500 dark:text-neutral-400 font-medium">
                    {hasData ? (
                      <>
                        <span className="font-bold text-neutral-800 dark:text-neutral-200">
                          {t.averageScore?.toFixed(1)}/10
                        </span>{" "}
                        avg • {t.questionsAnswered} questions ({t.correctCount} correct, {t.partiallyCorrectCount} partial, {t.incorrectCount} missed)
                      </>
                    ) : (
                      "0 questions answered"
                    )}
                  </div>
                </div>

                {/* Progress bar */}
                <div className="w-full h-2 rounded-full bg-neutral-200 dark:bg-neutral-700 overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${
                      !hasData
                        ? "w-0"
                        : t.scorePercentage >= 75
                        ? "bg-emerald-500"
                        : t.scorePercentage >= 50
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }`}
                    style={{ width: `${hasData ? Math.max(t.scorePercentage, 4) : 0}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}

      <p className="text-[11px] text-neutral-500 dark:text-neutral-400 italic pt-1">
        * Topic evaluations reflect answered viva simulation questions. Unpracticed topics are not labeled weak without examination evidence.
      </p>
    </div>
  );
};

export default TopicPerformanceSection;
