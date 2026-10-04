import React, { useState } from "react";
import {
  Award,
  CheckCircle2,
  AlertCircle,
  XCircle,
  RotateCcw,
  BookOpen,
  ArrowLeft,
  Sparkles,
  BarChart2,
  ExternalLink,
  ChevronRight,
  TrendingUp,
} from "lucide-react";
import type { VivaSessionRecord } from "../../types/viva";
import { VivaReviewAnswers } from "./VivaReviewAnswers";

interface VivaResultsScreenProps {
  session: VivaSessionRecord;
  onPracticeAgain: () => void;
  onReturnToExperiment: (tab?: string) => void;
  onBackToExperiments: () => void;
}

export const VivaResultsScreen: React.FC<VivaResultsScreenProps> = ({
  session,
  onPracticeAgain,
  onReturnToExperiment,
  onBackToExperiments,
}) => {
  const [showReview, setShowReview] = useState(false);

  // Compute percentage score
  const scorePercent = Math.round((session.averageScore / 10) * 100);

  // Determine performance tier & theme
  const getPerformanceSummary = () => {
    if (scorePercent >= 80) {
      return {
        label: "Lab Ready — Strong Performance",
        color: "text-emerald-700 dark:text-emerald-400",
        badgeBg: "bg-emerald-100 dark:bg-emerald-950/80 border-emerald-300 dark:border-emerald-800",
        description: "You demonstrated solid conceptual understanding across core topics. Review minor omissions before the oral exam.",
      };
    }
    if (scorePercent >= 55) {
      return {
        label: "Moderate Preparation — Targeted Revision Needed",
        color: "text-amber-700 dark:text-amber-400",
        badgeBg: "bg-amber-100 dark:bg-amber-950/80 border-amber-300 dark:border-amber-800",
        description: "You have a working grasp of basic steps, but specific technical points, formulas, or precautions require review.",
      };
    }
    return {
      label: "Needs Structured Revision",
      color: "text-red-700 dark:text-red-400",
      badgeBg: "bg-red-100 dark:bg-red-950/80 border-red-300 dark:border-red-800",
      description: "Several fundamental questions had missing key details. We recommend studying the experiment manual tabs highlighted below.",
    };
  };

  const performance = getPerformanceSummary();

  if (showReview) {
    return (
      <div className="w-full max-w-5xl mx-auto py-6 px-4">
        <VivaReviewAnswers
          answers={session.answers}
          onBackToSummary={() => setShowReview(false)}
        />
      </div>
    );
  }

  const topicEntries = Object.entries(session.topicAnalysis || {});

  return (
    <div className="w-full max-w-5xl mx-auto py-6 px-4 space-y-8">
      {/* Engine Transparency Notice */}
      <div className="flex items-center justify-between gap-3 p-3.5 bg-neutral-50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl text-xs text-neutral-600 dark:text-neutral-400">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
          <span>
            <strong className="font-semibold text-neutral-900 dark:text-white">
              PracPrep Evaluation Engine ({session.providerMode === "ai-live" ? "Live AI Mode" : "Demonstration Mode"})
            </strong>
            : Grounded in your experiment lab manual with zero fabricated citations.
          </span>
        </div>
        <span className="hidden sm:inline-block px-2 py-0.5 rounded text-[11px] font-medium bg-neutral-200 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300">
          Session #{session.id.slice(-6)}
        </span>
      </div>

      {/* Main Results Hero Card */}
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-8 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6 pb-6 border-b border-neutral-200 dark:border-neutral-800">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-neutral-500 dark:text-neutral-400">
                Viva Practice Session Completed
              </span>
              <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${performance.badgeBg} ${performance.color}`}>
                {performance.label}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
              {session.experimentTitle}
            </h1>
            <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
              {session.subject} • Configured for {session.config.questionCount} Questions ({session.config.difficulty} difficulty)
            </p>
          </div>

          {/* Overall score badge */}
          <div className="flex items-center gap-4 bg-neutral-50 dark:bg-neutral-800/60 p-4 rounded-xl border border-neutral-200 dark:border-neutral-700 flex-shrink-0">
            <div className="w-14 h-14 rounded-full bg-emerald-100 dark:bg-emerald-950 flex items-center justify-center border-2 border-emerald-500 text-emerald-700 dark:text-emerald-300 font-black text-xl">
              {scorePercent}%
            </div>
            <div>
              <div className="text-xs uppercase font-bold tracking-wider text-neutral-500 dark:text-neutral-400">
                Average Score
              </div>
              <div className="text-xl font-bold text-neutral-900 dark:text-white">
                {session.averageScore.toFixed(1)}{" "}
                <span className="text-sm font-normal text-neutral-500">/ 10</span>
              </div>
            </div>
          </div>
        </div>

        {/* Metric counts grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-6">
          <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
            <div className="text-xs font-medium text-neutral-500 dark:text-neutral-400 mb-1">
              Questions Answered
            </div>
            <div className="text-2xl font-bold text-neutral-900 dark:text-white">
              {session.questionsAnswered}{" "}
              <span className="text-sm font-normal text-neutral-400">/ {session.totalQuestions}</span>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-emerald-50/60 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-800/40">
            <div className="flex items-center gap-1.5 text-xs font-medium text-emerald-800 dark:text-emerald-300 mb-1">
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              Correct
            </div>
            <div className="text-2xl font-bold text-emerald-700 dark:text-emerald-300">
              {session.correctCount}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-amber-50/60 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-800/40">
            <div className="flex items-center gap-1.5 text-xs font-medium text-amber-800 dark:text-amber-300 mb-1">
              <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
              Partially Correct
            </div>
            <div className="text-2xl font-bold text-amber-700 dark:text-amber-300">
              {session.partiallyCorrectCount}
            </div>
          </div>

          <div className="p-4 rounded-xl bg-red-50/60 dark:bg-red-950/20 border border-red-200 dark:border-red-800/40">
            <div className="flex items-center gap-1.5 text-xs font-medium text-red-800 dark:text-red-300 mb-1">
              <XCircle className="w-3.5 h-3.5 text-red-600 dark:text-red-400" />
              Incorrect
            </div>
            <div className="text-2xl font-bold text-red-700 dark:text-red-300">
              {session.incorrectCount}
            </div>
          </div>
        </div>

        {/* Performance text */}
        <p className="mt-6 text-sm text-neutral-600 dark:text-neutral-300 bg-neutral-50 dark:bg-neutral-800/40 p-4 rounded-xl border border-neutral-200 dark:border-neutral-800">
          {performance.description}
        </p>
      </div>

      {/* Two Column Layout: Topic Breakdown & Recommendations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Topic Breakdown */}
        <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <BarChart2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Topic-Level Analysis
              </h3>
              <span className="text-xs text-neutral-500">
                {topicEntries.length} evaluated {topicEntries.length === 1 ? "topic" : "topics"}
              </span>
            </div>

            {topicEntries.length === 0 ? (
              <p className="text-xs text-neutral-500 italic">No topic details recorded for this session.</p>
            ) : (
              <div className="space-y-4">
                {topicEntries.map(([topicKey, perf]) => {
                  const topicPercent = Math.round((perf.averageScore / 10) * 100);
                  const isStrong = perf.averageScore >= 7.5;
                  const isWeak = perf.averageScore < 6;

                  return (
                    <div key={topicKey} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-neutral-800 dark:text-neutral-200 capitalize flex items-center gap-1.5">
                          {topicKey}
                          {isStrong && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 font-semibold">
                              Strong
                            </span>
                          )}
                          {isWeak && (
                            <span className="text-[10px] px-1.5 py-0.2 rounded bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 font-semibold">
                              Revise
                            </span>
                          )}
                        </span>
                        <span className="text-neutral-500 dark:text-neutral-400 font-medium">
                          {perf.correct}/{perf.total} correct • avg {perf.averageScore.toFixed(1)}/10 ({topicPercent}%)
                        </span>
                      </div>

                      {/* Progress bar */}
                      <div className="w-full h-2 rounded-full bg-neutral-100 dark:bg-neutral-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            topicPercent >= 75
                              ? "bg-emerald-500"
                              : topicPercent >= 50
                              ? "bg-amber-500"
                              : "bg-red-500"
                          }`}
                          style={{ width: `${Math.max(topicPercent, 6)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Quick Summary of Strengths and Gaps */}
          <div className="mt-6 pt-5 border-t border-neutral-100 dark:border-neutral-800 text-xs space-y-2">
            {session.strongTopics.length > 0 && (
              <div className="flex items-start gap-2">
                <span className="font-semibold text-emerald-700 dark:text-emerald-400 flex-shrink-0">Confidently answered:</span>
                <span className="text-neutral-600 dark:text-neutral-300 capitalize">
                  {session.strongTopics.join(", ")}
                </span>
              </div>
            )}
            {session.weakTopics.length > 0 && (
              <div className="flex items-start gap-2">
                <span className="font-semibold text-amber-700 dark:text-amber-400 flex-shrink-0">Requires revision:</span>
                <span className="text-neutral-600 dark:text-neutral-300 capitalize">
                  {session.weakTopics.join(", ")}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Targeted Revision Recommendations */}
        <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 shadow-sm flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Targeted Revision Recommendations
              </h3>
            </div>

            {session.revisionRecommendations.length === 0 ? (
              <p className="text-xs text-neutral-500">No specific revision items needed.</p>
            ) : (
              <div className="space-y-3">
                {session.revisionRecommendations.map((rec, i) => (
                  <div
                    key={i}
                    className="p-3.5 bg-neutral-50 dark:bg-neutral-800/50 rounded-xl border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-neutral-900 dark:text-white">
                          {rec.topic}
                        </span>
                        {rec.workspaceTab && (
                          <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300">
                            {rec.workspaceTab} tab
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-snug">
                        {rec.suggestedAction}
                      </p>
                    </div>

                    {rec.workspaceTab && (
                      <button
                        onClick={() => onReturnToExperiment(rec.workspaceTab)}
                        className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-600 dark:text-emerald-400 hover:text-emerald-700 dark:hover:text-emerald-300 flex-shrink-0 self-start sm:self-auto transition-colors"
                      >
                        Study Tab <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="mt-6 pt-5 border-t border-neutral-100 dark:border-neutral-800">
            <button
              onClick={() => onReturnToExperiment("checklist")}
              className="w-full inline-flex items-center justify-center gap-2 text-xs font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white p-2 rounded-lg hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
            >
              <BookOpen className="w-3.5 h-3.5" />
              Open Lab Readiness Checklist in Workspace
            </button>
          </div>
        </div>
      </div>

      {/* Action Buttons Bar */}
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 shadow-sm flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <button
            onClick={() => setShowReview(true)}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-neutral-800 dark:text-neutral-200 bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 rounded-xl transition-colors"
          >
            <Award className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            Review All Answers ({session.answers.length})
          </button>

          <button
            onClick={onPracticeAgain}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 dark:bg-emerald-500 dark:hover:bg-emerald-600 rounded-xl shadow-sm transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Practice Again
          </button>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto justify-end">
          <button
            onClick={() => onReturnToExperiment()}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded-lg transition-colors"
          >
            Return to Experiment
            <ChevronRight className="w-3.5 h-3.5" />
          </button>

          <button
            onClick={onBackToExperiments}
            className="flex-1 sm:flex-none inline-flex items-center justify-center gap-1.5 px-3.5 py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-white rounded-lg transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            My Experiments
          </button>
        </div>
      </div>
    </div>
  );
};

export default VivaResultsScreen;
