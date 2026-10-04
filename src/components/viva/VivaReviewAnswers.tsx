import React, { useState } from "react";
import {
  CheckCircle2,
  AlertCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  BookOpen,
  Lightbulb,
  Check,
  HelpCircle,
  ArrowLeft,
  Filter,
} from "lucide-react";
import type { VivaAnswerRecord, EvaluationVerdict } from "../../types/viva";

interface VivaReviewAnswersProps {
  answers: VivaAnswerRecord[];
  onBackToSummary?: () => void;
}

export const VivaReviewAnswers: React.FC<VivaReviewAnswersProps> = ({
  answers,
  onBackToSummary,
}) => {
  // Track open/collapsed state of each card
  const [openCards, setOpenCards] = useState<Record<string, boolean>>(() => {
    // Default open the first answer or all if <= 5
    const initial: Record<string, boolean> = {};
    answers.forEach((ans, idx) => {
      initial[ans.questionId] = idx === 0 || answers.length <= 5;
    });
    return initial;
  });

  const [verdictFilter, setVerdictFilter] = useState<"all" | EvaluationVerdict>("all");

  const toggleCard = (id: string) => {
    setOpenCards((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const expandAll = () => {
    const updated: Record<string, boolean> = {};
    answers.forEach((ans) => {
      updated[ans.questionId] = true;
    });
    setOpenCards(updated);
  };

  const collapseAll = () => {
    setOpenCards({});
  };

  const filteredAnswers = answers.filter((ans) => {
    if (verdictFilter === "all") return true;
    return ans.evaluation.verdict === verdictFilter;
  });

  const getVerdictBadge = (verdict: EvaluationVerdict) => {
    switch (verdict) {
      case "correct":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/80 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
            Correct
          </span>
        );
      case "partially-correct":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
            <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
            Partially Correct
          </span>
        );
      case "incorrect":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-100 text-red-800 dark:bg-red-950/80 dark:text-red-300 border border-red-300 dark:border-red-800">
            <XCircle className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
            Incorrect
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top action bar */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-neutral-200 dark:border-neutral-800">
        <div className="flex items-center gap-3">
          {onBackToSummary && (
            <button
              onClick={onBackToSummary}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-lg hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              Back to Summary
            </button>
          )}
          <div>
            <h2 className="text-lg font-bold text-neutral-900 dark:text-white">
              Question-by-Question Review
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400">
              Examining all {answers.length} answered questions and examiner evaluations
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={expandAll}
            className="text-xs font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white px-2.5 py-1 rounded border border-neutral-200 dark:border-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            Expand All
          </button>
          <button
            onClick={collapseAll}
            className="text-xs font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white px-2.5 py-1 rounded border border-neutral-200 dark:border-neutral-800 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
          >
            Collapse All
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-neutral-500 dark:text-neutral-400 flex items-center gap-1 mr-1">
          <Filter className="w-3.5 h-3.5" /> Filter:
        </span>
        <button
          onClick={() => setVerdictFilter("all")}
          className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
            verdictFilter === "all"
              ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900"
              : "bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-400 hover:bg-neutral-200 dark:hover:bg-neutral-700"
          }`}
        >
          All ({answers.length})
        </button>
        <button
          onClick={() => setVerdictFilter("correct")}
          className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
            verdictFilter === "correct"
              ? "bg-emerald-600 text-white dark:bg-emerald-500"
              : "bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-100 dark:hover:bg-emerald-900/50"
          }`}
        >
          Correct ({answers.filter((a) => a.evaluation.verdict === "correct").length})
        </button>
        <button
          onClick={() => setVerdictFilter("partially-correct")}
          className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
            verdictFilter === "partially-correct"
              ? "bg-amber-600 text-white dark:bg-amber-500"
              : "bg-amber-50 dark:bg-amber-950/50 text-amber-700 dark:text-amber-400 hover:bg-amber-100 dark:hover:bg-amber-900/50"
          }`}
        >
          Partially Correct ({answers.filter((a) => a.evaluation.verdict === "partially-correct").length})
        </button>
        <button
          onClick={() => setVerdictFilter("incorrect")}
          className={`px-3 py-1.5 rounded-md font-medium transition-colors ${
            verdictFilter === "incorrect"
              ? "bg-red-600 text-white dark:bg-red-500"
              : "bg-red-50 dark:bg-red-950/50 text-red-700 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/50"
          }`}
        >
          Incorrect ({answers.filter((a) => a.evaluation.verdict === "incorrect").length})
        </button>
      </div>

      {/* Answers list */}
      <div className="space-y-4">
        {filteredAnswers.length === 0 ? (
          <div className="p-8 text-center bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl">
            <HelpCircle className="w-8 h-8 text-neutral-400 mx-auto mb-2" />
            <p className="text-sm font-medium text-neutral-700 dark:text-neutral-300">
              No questions found matching this filter.
            </p>
          </div>
        ) : (
          filteredAnswers.map((ans) => {
            const isOpen = !!openCards[ans.questionId];
            return (
              <div
                key={ans.questionId}
                className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl overflow-hidden shadow-sm transition-all"
              >
                {/* Header row / toggle */}
                <button
                  type="button"
                  onClick={() => toggleCard(ans.questionId)}
                  className="w-full text-left p-4 sm:p-5 flex items-start justify-between gap-4 hover:bg-neutral-50 dark:hover:bg-neutral-800/40 transition-colors cursor-pointer"
                  aria-expanded={isOpen}
                >
                  <div className="flex items-start gap-3.5 min-w-0 flex-1">
                    <span className="flex-shrink-0 w-8 h-8 rounded-lg bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 font-bold text-xs flex items-center justify-center border border-neutral-200 dark:border-neutral-700">
                      Q{ans.questionNumber}
                    </span>

                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2 mb-1.5">
                        <span className="capitalize text-xs font-semibold px-2 py-0.5 rounded bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300">
                          {ans.topic}
                        </span>
                        <span className="capitalize text-xs text-neutral-500 dark:text-neutral-400">
                          {ans.difficulty}
                        </span>
                        {getVerdictBadge(ans.evaluation.verdict)}
                        <span className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 ml-auto sm:ml-0">
                          Score: {ans.evaluation.score.toFixed(1)}/10
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-neutral-900 dark:text-white leading-snug line-clamp-2">
                        {ans.questionText}
                      </p>
                    </div>
                  </div>

                  <div className="flex-shrink-0 text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300 mt-1">
                    {isOpen ? (
                      <ChevronUp className="w-5 h-5" />
                    ) : (
                      <ChevronDown className="w-5 h-5" />
                    )}
                  </div>
                </button>

                {/* Expanded details */}
                {isOpen && (
                  <div className="p-4 sm:p-6 border-t border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-900/50 space-y-5">
                    {/* Student response box */}
                    <div>
                      <h4 className="text-xs font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400 mb-2">
                        Your Submitted Response
                      </h4>
                      <div className="p-3.5 bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-lg text-sm text-neutral-800 dark:text-neutral-200 whitespace-pre-wrap leading-relaxed">
                        {ans.studentAnswer}
                      </div>
                    </div>

                    {/* Feedback cards grid */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* What you got right */}
                      <div className="p-3.5 bg-emerald-50/70 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40 rounded-lg">
                        <div className="flex items-center gap-2 mb-1.5">
                          <Check className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                          <h5 className="text-xs font-bold text-emerald-900 dark:text-emerald-300 uppercase tracking-wide">
                            What You Got Right
                          </h5>
                        </div>
                        <p className="text-xs text-emerald-900 dark:text-emerald-200 leading-relaxed">
                          {ans.evaluation.whatYouGotRight}
                        </p>
                      </div>

                      {/* What was missing */}
                      <div className="p-3.5 bg-amber-50/70 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40 rounded-lg">
                        <div className="flex items-center gap-2 mb-1.5">
                          <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                          <h5 className="text-xs font-bold text-amber-900 dark:text-amber-300 uppercase tracking-wide">
                            What Was Missing or Incomplete
                          </h5>
                        </div>
                        <p className="text-xs text-amber-900 dark:text-amber-200 leading-relaxed">
                          {ans.evaluation.whatWasMissing}
                        </p>
                      </div>
                    </div>

                    {/* Expected answer */}
                    <div className="p-4 bg-white dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-lg">
                      <div className="flex items-center gap-2 mb-2">
                        <BookOpen className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                        <h5 className="text-xs font-bold text-neutral-800 dark:text-neutral-200 uppercase tracking-wide">
                          Grounded Reference Answer (Lab Manual Standard)
                        </h5>
                      </div>
                      <p className="text-xs text-neutral-700 dark:text-neutral-300 leading-relaxed bg-neutral-50 dark:bg-neutral-900 p-3 rounded border border-neutral-200 dark:border-neutral-800">
                        {ans.evaluation.expectedAnswer}
                      </p>
                    </div>

                    {/* Improvement tip */}
                    <div className="p-3.5 bg-blue-50/70 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800/40 rounded-lg flex items-start gap-3">
                      <Lightbulb className="w-4 h-4 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
                      <div>
                        <h5 className="text-xs font-bold text-blue-900 dark:text-blue-300 uppercase tracking-wide mb-1">
                          Oral Examination Tip
                        </h5>
                        <p className="text-xs text-blue-900 dark:text-blue-200 leading-relaxed">
                          {ans.evaluation.improvementTip}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default VivaReviewAnswers;
