import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  AlertCircle,
  ArrowLeft,
  Loader2,
  History,
  CheckCircle2,
  Calendar,
  Award,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import type { ExperimentRecord } from "../../types/experiment";
import type {
  VivaSessionConfig,
  VivaQuestion,
  VivaAnswerRecord,
  VivaEvaluation,
  VivaSessionRecord,
} from "../../types/viva";
import { experimentStorage } from "../../services/experimentStorage";
import { vivaAIProvider, formatVivaApiError } from "../../services/vivaAIProvider";
import { vivaStorage } from "../../services/vivaStorage";
import { VivaSetupScreen } from "./VivaSetupScreen";
import { VivaActiveSession } from "./VivaActiveSession";
import { VivaResultsScreen } from "./VivaResultsScreen";

interface VivaSimulatorPageProps {
  experimentId: string;
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const VivaSimulatorPage: React.FC<VivaSimulatorPageProps> = ({
  experimentId,
  user,
  onNavigate,
}) => {
  const [experiment, setExperiment] = useState<ExperimentRecord | null>(() =>
    experimentStorage.getExperimentById(experimentId, user) || null
  );

  // Session phase: "setup" | "generating" | "active" | "results"
  const [phase, setPhase] = useState<"setup" | "generating" | "active" | "results">("setup");
  const [config, setConfig] = useState<VivaSessionConfig | null>(null);
  const [questions, setQuestions] = useState<VivaQuestion[]>([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [answers, setAnswers] = useState<VivaAnswerRecord[]>([]);

  // Active answer evaluation state
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [evaluationError, setEvaluationError] = useState<string | null>(null);
  const [lastEvaluation, setLastEvaluation] = useState<VivaEvaluation | null>(null);
  const lastAttemptedAnswerRef = useRef<string>("");

  // Completed session record
  const [completedSession, setCompletedSession] = useState<VivaSessionRecord | null>(null);

  // Past sessions for this experiment
  const [pastSessions, setPastSessions] = useState<VivaSessionRecord[]>(() =>
    vivaStorage.getSessionsByExperiment(experimentId, user)
  );

  // Reload experiment and past sessions when store changes
  const reloadData = useCallback(() => {
    const exp = experimentStorage.getExperimentById(experimentId, user);
    setExperiment(exp || null);

    const past = vivaStorage.getSessionsByExperiment(experimentId, user);
    setPastSessions(past);
  }, [experimentId, user]);

  // Subscribe to storage changes
  useEffect(() => {
    const unsubExp = experimentStorage.subscribe(reloadData);
    const unsubViva = vivaStorage.subscribe(reloadData);
    return () => {
      unsubExp();
      unsubViva();
    };
  }, [reloadData]);

  // Start Session handler
  const handleStartSession = async (newConfig: VivaSessionConfig) => {
    if (!experiment) return;
    setConfig(newConfig);
    setPhase("generating");
    setEvaluationError(null);

    try {
      const generated = await vivaAIProvider.generateQuestions(experiment, newConfig, user);
      if (generated.length === 0) {
        setEvaluationError("Unable to generate viva questions for this experiment. Please check experiment content.");
        setPhase("setup");
        return;
      }
      setQuestions(generated);
      setCurrentQuestionIndex(0);
      setAnswers([]);
      setLastEvaluation(null);
      setPhase("active");
    } catch (err) {
      console.error("Failed to generate questions:", err);
      setEvaluationError(formatVivaApiError(err, "generate questions"));
      setPhase("setup");
    }
  };

  // Evaluate single answer
  const handleSubmitAnswer = async (studentAnswer: string) => {
    if (!experiment || questions.length === 0) return;
    const currentQ = questions[currentQuestionIndex];
    if (!currentQ) return;

    lastAttemptedAnswerRef.current = studentAnswer;
    setIsEvaluating(true);
    setEvaluationError(null);

    try {
      const evalResult = await vivaAIProvider.evaluateAnswer(
        currentQ,
        studentAnswer,
        experiment,
        {
          previousAnswers: answers,
          currentQuestionIndex,
        },
        user
      );

      const record: VivaAnswerRecord = {
        questionId: currentQ.id,
        questionNumber: currentQ.questionNumber,
        questionText: currentQ.question,
        topic: currentQ.topic,
        difficulty: currentQ.difficulty,
        studentAnswer,
        evaluation: evalResult,
        timestamp: Date.now(),
      };

      setLastEvaluation(evalResult);
      // Append answer record
      setAnswers((prev) => [...prev, record]);
    } catch (err) {
      console.error("Evaluation failed:", err);
      setEvaluationError(formatVivaApiError(err, "evaluate your answer"));
    } finally {
      setIsEvaluating(false);
    }
  };

  // Move to next question or complete session
  const handleNextQuestion = async () => {
    setEvaluationError(null);
    setLastEvaluation(null);

    if (currentQuestionIndex + 1 < questions.length) {
      setCurrentQuestionIndex((prev) => prev + 1);
    } else {
      // Final question reached: analyze and persist session
      if (!experiment || !config) return;
      setIsEvaluating(true);

      try {
        const analysis = await vivaAIProvider.analyzeSession(experiment, answers);

        // Compute metrics
        let totalScore = 0;
        let correctCount = 0;
        let partiallyCorrectCount = 0;
        let incorrectCount = 0;

        answers.forEach((ans) => {
          totalScore += ans.evaluation.score;
          if (ans.evaluation.verdict === "correct") correctCount++;
          else if (ans.evaluation.verdict === "partially-correct") partiallyCorrectCount++;
          else incorrectCount++;
        });

        const avgScore = answers.length > 0 ? totalScore / answers.length : 0;

        // Resolve session-level provider mode:
        const hasLive = answers.some((a) => a.evaluation.providerMode === "ai-live") ||
                        questions.some((q) => q.providerMode === "ai-live");
        const resolvedProviderMode: "ai-live" | "demonstration" = hasLive ? "ai-live" : "demonstration";

        const sessionRecord: VivaSessionRecord = {
          id: `viva_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
          experimentId: experiment.id,
          experimentTitle: experiment.title,
          subject: experiment.subject,
          config,
          startedAt: answers.length > 0 ? answers[0].timestamp : Date.now(),
          completedAt: Date.now(),
          isCompleted: true,
          answers,
          totalQuestions: questions.length,
          questionsAnswered: answers.length,
          correctCount,
          partiallyCorrectCount,
          incorrectCount,
          averageScore: avgScore,
          topicAnalysis: analysis.topicAnalysis,
          weakTopics: analysis.weakTopics,
          strongTopics: analysis.strongTopics,
          revisionRecommendations: analysis.revisionRecommendations,
          providerMode: resolvedProviderMode,
        };

        // Persist session
        vivaStorage.saveSession(sessionRecord, user);
        setCompletedSession(sessionRecord);
        setPhase("results");
      } catch (err) {
        console.error("Failed to finalize session:", err);
        setEvaluationError("Failed to calculate session results. Please retry viewing results.");
      } finally {
        setIsEvaluating(false);
      }
    }
  };

  // Restart practice session
  const handlePracticeAgain = () => {
    setPhase("setup");
    setCompletedSession(null);
    setAnswers([]);
    setQuestions([]);
    setCurrentQuestionIndex(0);
    setLastEvaluation(null);
    setEvaluationError(null);
  };

  // Not found state
  if (!experiment) {
    return (
      <div className="w-full max-w-2xl mx-auto py-16 px-4 text-center">
        <div className="w-16 h-16 rounded-2xl bg-amber-100 dark:bg-amber-950/60 border border-amber-300 dark:border-amber-800 text-amber-700 dark:text-amber-400 flex items-center justify-center mx-auto mb-4">
          <AlertCircle className="w-8 h-8" />
        </div>
        <h2 className="text-xl font-bold text-neutral-900 dark:text-white mb-2">
          Experiment Not Found
        </h2>
        <p className="text-sm text-neutral-600 dark:text-neutral-400 mb-6 max-w-md mx-auto">
          The experiment you are trying to practice for could not be found or has been deleted.
        </p>
        <button
          onClick={() => onNavigate("/experiments")}
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 text-xs font-semibold shadow-sm hover:bg-neutral-800 dark:hover:bg-neutral-100 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Return to My Experiments
        </button>
      </div>
    );
  }

  // Question generation in progress
  if (phase === "generating") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[65vh] gap-4 text-center px-4">
        <div className="w-16 h-16 rounded-2xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-300 dark:border-emerald-800 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
        <div>
          <h2 className="text-lg font-bold text-neutral-900 dark:text-white mb-1">
            Formulating Oral Viva Questions
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 max-w-md">
            Analyzing "{experiment.title}" objectives, theory, apparatus, and procedure to curate grounded examination questions...
          </p>
        </div>
      </div>
    );
  }

  // Active examination view
  if (phase === "active") {
    return (
      <VivaActiveSession
        experiment={experiment}
        questions={questions}
        currentIndex={currentQuestionIndex}
        currentEvaluation={lastEvaluation}
        isEvaluating={isEvaluating}
        evaluationError={evaluationError}
        onSubmitAnswer={handleSubmitAnswer}
        onNextQuestion={handleNextQuestion}
        onRetryEvaluation={() => {
          if (lastAttemptedAnswerRef.current) {
            handleSubmitAnswer(lastAttemptedAnswerRef.current);
          } else {
            const lastAns = answers[currentQuestionIndex];
            if (lastAns) {
              handleSubmitAnswer(lastAns.studentAnswer);
            }
          }
        }}
        onExitSession={() => onNavigate(`/experiments/${experiment.id}`)}
      />
    );
  }

  // Results screen
  if (phase === "results" && completedSession) {
    return (
      <VivaResultsScreen
        session={completedSession}
        onPracticeAgain={handlePracticeAgain}
        onReturnToExperiment={(_tab) => onNavigate(`/experiments/${experiment.id}`)}
        onBackToExperiments={() => onNavigate("/experiments")}
      />
    );
  }

  // Default: Setup screen
  return (
    <div className="space-y-8">
      <VivaSetupScreen
        experiment={experiment}
        onStartSession={handleStartSession}
        onBack={() => onNavigate(`/experiments/${experiment.id}`)}
      />

      {/* Past completed sessions history for this experiment (if any) */}
      {pastSessions.length > 0 && (
        <div className="w-full max-w-4xl mx-auto px-4">
          <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 shadow-sm">
            <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-neutral-100 dark:border-neutral-800">
              <div className="flex items-center gap-2">
                <History className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                  Previous Viva Sessions for this Experiment ({pastSessions.length})
                </h3>
              </div>
              <span className="text-xs text-neutral-500">
                Saved in local session
              </span>
            </div>

            <div className="space-y-3">
              {pastSessions.slice(0, 4).map((s) => {
                const dateStr = new Date(s.completedAt || s.startedAt).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                });
                const pct = Math.round((s.averageScore / 10) * 100);

                return (
                  <div
                    key={s.id}
                    className="p-3.5 bg-neutral-50 dark:bg-neutral-800/40 rounded-xl border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-neutral-300 dark:hover:border-neutral-700 transition-colors"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-bold text-neutral-800 dark:text-neutral-200">
                          {s.config.questionCount} Questions • {s.config.difficulty}
                        </span>
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
                          <CheckCircle2 className="w-3 h-3" />
                          Completed
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs text-neutral-500">
                        <span className="flex items-center gap-1">
                          <Calendar className="w-3.5 h-3.5" />
                          {dateStr}
                        </span>
                        <span>•</span>
                        <span>
                          {s.correctCount} correct, {s.partiallyCorrectCount} partial, {s.incorrectCount} incorrect
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 self-end sm:self-auto">
                      <div className="text-right">
                        <div className="text-xs font-bold text-neutral-900 dark:text-white">
                          {s.averageScore.toFixed(1)}/10
                        </div>
                        <div className="text-[10px] text-neutral-500 font-medium">
                          {pct}% score
                        </div>
                      </div>

                      <button
                        onClick={() => {
                          setCompletedSession(s);
                          setPhase("results");
                        }}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
                      >
                        <Award className="w-3.5 h-3.5 text-emerald-600" />
                        View Scorecard
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default VivaSimulatorPage;
