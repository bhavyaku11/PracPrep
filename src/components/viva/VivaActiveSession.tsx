import React, { useState } from "react";
import {
  Send,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  XCircle,
  LogOut,
  AlertTriangle,
  Lightbulb,
  Check,
} from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";
import type {
  VivaQuestion,
  VivaEvaluation,
} from "../../types/viva";

interface VivaActiveSessionProps {
  experiment: ExperimentRecord;
  questions: VivaQuestion[];
  currentIndex: number;
  currentEvaluation: VivaEvaluation | null;
  isEvaluating: boolean;
  evaluationError: string | null;
  onSubmitAnswer: (answer: string) => void;
  onNextQuestion: () => void;
  onRetryEvaluation: () => void;
  onExitSession: () => void;
}

export const VivaActiveSession: React.FC<VivaActiveSessionProps> = ({
  experiment,
  questions,
  currentIndex,
  currentEvaluation,
  isEvaluating,
  evaluationError,
  onSubmitAnswer,
  onNextQuestion,
  onRetryEvaluation,
  onExitSession,
}) => {
  const [answerText, setAnswerText] = useState("");
  const [showExitConfirm, setShowExitConfirm] = useState(false);

  const currentQuestion = questions[currentIndex];
  const totalQuestions = questions.length;
  const isLastQuestion = currentIndex === totalQuestions - 1;
  const progressPercent = Math.round(((currentIndex + (currentEvaluation ? 1 : 0)) / totalQuestions) * 100);

  const isAnswerValid = answerText.trim().length > 0;

  const handleSubmit = (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!isAnswerValid || isEvaluating || currentEvaluation) return;
    onSubmitAnswer(answerText);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Submit on Cmd+Enter (Mac) or Ctrl+Enter (Windows/Linux)
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleProceedNext = () => {
    setAnswerText("");
    onNextQuestion();
  };

  const getVerdictBadge = (verdict: VivaEvaluation["verdict"]) => {
    switch (verdict) {
      case "correct":
        return {
          label: "Correct",
          icon: CheckCircle2,
          bg: "bg-emerald-50 border-emerald-200 text-emerald-800",
          iconColor: "text-emerald-700",
        };
      case "partially-correct":
        return {
          label: "Partially Correct",
          icon: AlertCircle,
          bg: "bg-amber-50 border-amber-200 text-amber-800",
          iconColor: "text-amber-700",
        };
      case "incorrect":
      default:
        return {
          label: "Needs Improvement",
          icon: XCircle,
          bg: "bg-red-50 border-red-200 text-red-800",
          iconColor: "text-red-700",
        };
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-5 pb-16">
      {/* 1. Active Session Header */}
      <div className="rounded-2xl border border-neutral-200/90 bg-white p-4 sm:p-5 shadow-2xs space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="space-y-0.5 min-w-0">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
              Active Viva Voce
            </span>
            <h1 className="font-jakarta text-base sm:text-lg font-bold text-neutral-900 truncate" title={experiment.title}>
              {experiment.title}
            </h1>
          </div>

          <div className="flex items-center gap-3 shrink-0 self-end sm:self-auto">
            <div className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-lg bg-neutral-100 text-neutral-700">
              <span className="capitalize">{currentQuestion.difficulty}</span>
              <span className="text-neutral-300">•</span>
              <span className="capitalize">{currentQuestion.topic}</span>
            </div>

            <button
              type="button"
              onClick={() => setShowExitConfirm(true)}
              className="inline-flex items-center gap-1 text-xs font-semibold text-neutral-500 hover:text-red-600 transition-colors p-1 rounded"
              title="Exit session"
            >
              <LogOut className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Exit</span>
            </button>
          </div>
        </div>

        {/* Progress Bar & Question Counter */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-xs text-neutral-500">
            <span className="font-semibold text-neutral-800">
              Question {currentIndex + 1} of {totalQuestions}
            </span>
            <span>{progressPercent}% completed</span>
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-neutral-100">
            <div
              className="h-full rounded-full bg-emerald-700 transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>
      </div>

      {/* 2. Question Display Card */}
      <div className="rounded-2xl border border-neutral-200/90 bg-white p-6 sm:p-7 shadow-2xs space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-100 text-emerald-800 text-xs font-bold font-mono">
              Q{currentQuestion.questionNumber}
            </span>
            <span className="text-xs font-semibold uppercase tracking-wider text-neutral-500">
              Topic: {currentQuestion.topic}
            </span>
          </div>
          {currentQuestion.groundedSourceSection && (
            <span className="text-[11px] font-medium text-neutral-400">
              Source: {currentQuestion.groundedSourceSection}
            </span>
          )}
        </div>

        <h2 className="font-jakarta text-base sm:text-xl font-bold text-neutral-900 leading-snug">
          {currentQuestion.question}
        </h2>
      </div>

      {/* 3. Student Answer Input Area (Shown before evaluation) */}
      {!currentEvaluation && (
        <div className="rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-2xs space-y-3.5">
          <div className="flex items-center justify-between">
            <label
              htmlFor="student-viva-answer"
              className="block text-xs font-semibold text-neutral-800"
            >
              Your Verbal Answer Formulation
            </label>
            <span className="text-[11px] text-neutral-400">
              Press Cmd+Enter or click Submit
            </span>
          </div>

          <textarea
            id="student-viva-answer"
            rows={5}
            value={answerText}
            onChange={(e) => setAnswerText(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isEvaluating}
            placeholder="Type your explanation here as you would speak it to an examiner in a viva voce... Include key formulas, definitions, and reasons."
            className="w-full rounded-xl border border-neutral-300 bg-neutral-50/40 p-4 text-xs sm:text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y leading-relaxed"
          />

          {evaluationError && (
            <div className="flex items-center justify-between p-3 rounded-xl bg-red-50 border border-red-200 text-xs text-red-800">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />
                <span>{evaluationError}</span>
              </div>
              <button
                type="button"
                onClick={onRetryEvaluation}
                className="font-semibold underline hover:text-red-950 shrink-0"
              >
                Retry Evaluation
              </button>
            </div>
          )}

          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] text-neutral-400">
              {answerText.trim() ? `${answerText.trim().split(/\s+/).length} words` : "Empty answer"}
            </span>

            <button
              type="button"
              onClick={() => handleSubmit()}
              disabled={!isAnswerValid || isEvaluating}
              className={`inline-flex h-10 items-center justify-center gap-2 rounded-xl px-5 text-xs sm:text-sm font-semibold transition-all ${
                isAnswerValid && !isEvaluating
                  ? "bg-neutral-900 text-white shadow-sm hover:bg-emerald-700 active:scale-[0.98]"
                  : "bg-neutral-200 text-neutral-400 cursor-not-allowed"
              }`}
            >
              {isEvaluating ? (
                <>
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Evaluating Response...</span>
                </>
              ) : (
                <>
                  <span>Submit Answer</span>
                  <Send className="h-3.5 w-3.5" />
                </>
              )}
            </button>
          </div>
        </div>
      )}

      {/* 4. Structured Evaluation Feedback Display */}
      {currentEvaluation && (
        <div className="space-y-4 animate-in fade-in duration-200">
          {/* Student Submitted Answer Summary */}
          <div className="rounded-xl border border-neutral-200/90 bg-neutral-50/70 p-4 space-y-1 text-xs">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-neutral-400">
              Your Submitted Answer
            </span>
            <p className="text-neutral-800 font-normal leading-relaxed whitespace-pre-wrap">
              {answerText}
            </p>
          </div>

          {/* Feedback Card */}
          {(() => {
            const badge = getVerdictBadge(currentEvaluation.verdict);
            const VerdictIcon = badge.icon;
            return (
              <div className="rounded-2xl border border-neutral-200/90 bg-white p-6 shadow-2xs space-y-5">
                {/* Verdict & Score Banner */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-neutral-100">
                  <div className="flex items-center gap-2.5">
                    <div className={`flex items-center gap-1.5 px-3 py-1 rounded-xl border text-xs font-bold ${badge.bg}`}>
                      <VerdictIcon className={`h-4 w-4 ${badge.iconColor}`} />
                      <span>{badge.label}</span>
                    </div>

                    <div className="flex items-center gap-1 px-3 py-1 rounded-xl bg-neutral-100 text-neutral-800 text-xs font-bold font-mono">
                      <span>Score:</span>
                      <span className="text-emerald-800 text-sm font-jakarta">
                        {currentEvaluation.score}
                      </span>
                      <span className="text-neutral-400">/ 10</span>
                    </div>
                  </div>

                  <span className="text-[11px] font-medium text-neutral-400">
                    Engine:{" "}
                    {currentEvaluation.providerMode === "ai-live"
                      ? `Live AI (${currentEvaluation.providerId || "gemini"})`
                      : "Demonstration Evaluator"}
                  </span>
                </div>

                {/* 1. What You Got Right */}
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-emerald-800">
                    <Check className="h-3.5 w-3.5 text-emerald-700" />
                    <span>What You Got Right</span>
                  </div>
                  <p className="text-xs sm:text-sm text-neutral-700 bg-emerald-50/40 border border-emerald-100 rounded-xl p-3.5 leading-relaxed">
                    {currentEvaluation.whatYouGotRight}
                  </p>
                </div>

                {/* 2. What Was Missing */}
                <div className="space-y-1.5">
                  <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
                    <AlertCircle className="h-3.5 w-3.5 text-amber-700" />
                    <span>What Was Missing or Incomplete</span>
                  </div>
                  <p className="text-xs sm:text-sm text-neutral-700 bg-amber-50/40 border border-amber-100 rounded-xl p-3.5 leading-relaxed">
                    {currentEvaluation.whatWasMissing}
                  </p>
                </div>

                {/* 3. Expected Answer Reference */}
                <div className="space-y-1.5">
                  <span className="block text-xs font-semibold text-neutral-800">
                    Expected Reference Answer (Lab Manual Grounded)
                  </span>
                  <p className="text-xs sm:text-sm text-neutral-800 bg-neutral-50 rounded-xl p-3.5 leading-relaxed border border-neutral-200/80 whitespace-pre-wrap">
                    {currentEvaluation.expectedAnswer}
                  </p>
                </div>

                {/* 4. Actionable Improvement Tip */}
                <div className="flex items-start gap-2.5 p-3.5 rounded-xl bg-neutral-900 text-white text-xs">
                  <Lightbulb className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                  <div className="space-y-0.5">
                    <span className="font-semibold text-emerald-300">Oral Viva Tip: </span>
                    <span className="text-neutral-200">{currentEvaluation.improvementTip}</span>
                  </div>
                </div>

                {/* Progression Button */}
                <div className="pt-2 flex justify-end">
                  <button
                    type="button"
                    onClick={handleProceedNext}
                    className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-neutral-900 px-6 text-xs sm:text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 active:scale-[0.98] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
                  >
                    <span>{isLastQuestion ? "View Session Results" : "Next Question"}</span>
                    <ArrowRight className="h-4 w-4" />
                  </button>
                </div>
              </div>
            );
          })()}
        </div>
      )}

      {/* 5. Exit Confirmation Modal */}
      {showExitConfirm && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/40 backdrop-blur-xs animate-in fade-in duration-150"
        >
          <div className="w-full max-w-md rounded-2xl border border-neutral-200 bg-white p-6 shadow-2xl space-y-4">
            <div className="flex items-start gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-700">
                <AlertTriangle className="h-5 w-5" />
              </div>
              <div>
                <h3 className="font-jakarta text-base font-bold text-neutral-900">
                  Exit Viva Session?
                </h3>
                <p className="text-xs text-neutral-500 mt-1 leading-relaxed">
                  Your current session is in progress ({currentIndex + 1} of {totalQuestions} answered). Exiting will discard this active session without recording it as completed.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                onClick={() => setShowExitConfirm(false)}
                className="inline-flex h-9 items-center justify-center rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
              >
                Continue Session
              </button>
              <button
                type="button"
                onClick={onExitSession}
                className="inline-flex h-9 items-center justify-center rounded-lg bg-red-600 px-4 text-xs font-semibold text-white hover:bg-red-700 transition-colors"
              >
                Exit Session
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VivaActiveSession;
