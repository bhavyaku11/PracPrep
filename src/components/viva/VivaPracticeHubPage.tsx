import React, { useState, useEffect } from "react";
import {
  MessageSquareCode,
  Sparkles,
  FlaskConical,
  Clock,
  CheckCircle2,
  Calendar,
  Award,
  Plus,
  BookOpen,
  TrendingUp,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import type { ExperimentRecord } from "../../types/experiment";
import type { VivaSessionRecord } from "../../types/viva";
import { experimentStorage } from "../../services/experimentStorage";
import { vivaStorage } from "../../services/vivaStorage";

interface VivaPracticeHubPageProps {
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const VivaPracticeHubPage: React.FC<VivaPracticeHubPageProps> = ({
  user,
  onNavigate,
}) => {
  const [experiments, setExperiments] = useState<ExperimentRecord[]>(() =>
    experimentStorage.getExperiments(user)
  );
  const [sessions, setSessions] = useState<VivaSessionRecord[]>(() =>
    vivaStorage.getSessions(user)
  );

  useEffect(() => {
    const unsubExp = experimentStorage.subscribe(() => {
      setExperiments(experimentStorage.getExperiments(user));
    });
    const unsubViva = vivaStorage.subscribe(() => {
      setSessions(vivaStorage.getSessions(user));
    });

    return () => {
      unsubExp();
      unsubViva();
    };
  }, [user]);

  // Overall stats
  const completedSessions = sessions.filter((s) => s.isCompleted);
  const totalCompleted = completedSessions.length;
  const averageOverallScore =
    totalCompleted > 0
      ? completedSessions.reduce((acc, s) => acc + s.averageScore, 0) / totalCompleted
      : 0;

  return (
    <div className="w-full max-w-6xl mx-auto space-y-8">
      {/* Header section */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-neutral-200 dark:border-neutral-800">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              Oral Examination Simulator
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
            Viva Practice Hub
          </h1>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1 max-w-2xl">
            Simulate realistic lab oral examinations grounded directly in your laboratory experiment manuals. Test concepts, procedures, calculations, and safety precautions.
          </p>
        </div>

        {/* Engine Transparency Pill */}
        <div className="p-3 bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl text-xs text-neutral-500 flex items-center gap-2.5 self-start md:self-auto">
          <BookOpen className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0" />
          <span>Academic Evaluation Engine (Demonstration Mode)</span>
        </div>
      </div>

      {/* Quick Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Practiced Sessions
            </span>
            <MessageSquareCode className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            {totalCompleted}
          </div>
          <p className="text-xs text-neutral-500 mt-1">
            Across {experiments.length} experiments
          </p>
        </div>

        <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Average Viva Score
            </span>
            <TrendingUp className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            {totalCompleted > 0 ? `${averageOverallScore.toFixed(1)} / 10` : "—"}
          </div>
          <p className="text-xs text-neutral-500 mt-1">
            {totalCompleted > 0
              ? `${Math.round((averageOverallScore / 10) * 100)}% overall readiness`
              : "Complete your first session to track readiness"}
          </p>
        </div>

        <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 shadow-sm">
          <div className="flex items-center justify-between text-neutral-500 mb-2">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Ready Experiments
            </span>
            <FlaskConical className="w-4 h-4 text-emerald-600" />
          </div>
          <div className="text-2xl font-bold text-neutral-900 dark:text-white">
            {experiments.length}
          </div>
          <p className="text-xs text-neutral-500 mt-1">
            Available for viva generation
          </p>
        </div>
      </div>

      {/* Select an Experiment to Practice */}
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 shadow-sm">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-6 pb-4 border-b border-neutral-100 dark:border-neutral-800">
          <div>
            <h2 className="text-lg font-bold text-neutral-900 dark:text-white">
              Select an Experiment to Practice
            </h2>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
              Choose an experiment from your workspace to configure and launch an oral viva simulator session
            </p>
          </div>

          <button
            onClick={() => onNavigate("/create-experiment")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-neutral-700 dark:text-neutral-300 bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 transition-colors self-start sm:self-auto"
          >
            <Plus className="w-3.5 h-3.5" />
            Add New Experiment
          </button>
        </div>

        {experiments.length === 0 ? (
          <div className="text-center py-12 px-4">
            <FlaskConical className="w-10 h-10 text-neutral-400 mx-auto mb-3" />
            <h3 className="text-sm font-semibold text-neutral-900 dark:text-white mb-1">
              No experiments added yet
            </h3>
            <p className="text-xs text-neutral-500 max-w-sm mx-auto mb-4">
              Add your first laboratory manual or experiment details to begin practicing oral vivas.
            </p>
            <button
              onClick={() => onNavigate("/create-experiment")}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-neutral-900 text-white dark:bg-white dark:text-neutral-900 text-xs font-semibold hover:bg-neutral-800 dark:hover:bg-neutral-100 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              Create Experiment
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {experiments.map((exp) => {
              const expSessions = completedSessions.filter((s) => s.experimentId === exp.id);
              const latestSession = expSessions[0];

              return (
                <div
                  key={exp.id}
                  className="p-5 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-800/20 hover:border-neutral-300 dark:hover:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-800/40 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span className="text-[11px] font-semibold uppercase tracking-wider text-emerald-700 dark:text-emerald-300 px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950">
                        {exp.subject}
                      </span>
                      {exp.experimentNumber && (
                        <span className="text-[11px] text-neutral-500 font-medium">
                          Exp #{exp.experimentNumber}
                        </span>
                      )}
                    </div>

                    <h3 className="text-sm font-bold text-neutral-900 dark:text-white mb-1.5 line-clamp-2">
                      {exp.title}
                    </h3>

                    {exp.objective && (
                      <p className="text-xs text-neutral-500 dark:text-neutral-400 line-clamp-2 mb-3">
                        {exp.objective}
                      </p>
                    )}

                    {latestSession && (
                      <div className="text-[11px] text-neutral-500 flex items-center gap-1.5 mb-3 bg-white dark:bg-neutral-900 p-2 rounded border border-neutral-200 dark:border-neutral-800">
                        <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                        <span>
                          Last practiced: {latestSession.averageScore.toFixed(1)}/10 avg
                        </span>
                      </div>
                    )}
                  </div>

                  <div className="pt-3 border-t border-neutral-200/80 dark:border-neutral-800 flex items-center justify-between gap-2 mt-2">
                    <button
                      onClick={() => onNavigate(`/experiments/${exp.id}`)}
                      className="text-xs text-neutral-500 hover:text-neutral-900 dark:hover:text-white font-medium transition-colors"
                    >
                      View Manual
                    </button>

                    <button
                      onClick={() => onNavigate(`/experiments/${exp.id}/viva`)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-white bg-neutral-900 dark:bg-white dark:text-neutral-900 hover:bg-neutral-800 dark:hover:bg-neutral-100 transition-colors shadow-2xs"
                    >
                      <Sparkles className="w-3 h-3 text-emerald-400" />
                      Practice Viva
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Recent Viva Sessions History */}
      {sessions.length > 0 && (
        <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 shadow-sm">
          <div className="flex items-center justify-between gap-3 mb-4 pb-3 border-b border-neutral-100 dark:border-neutral-800">
            <div>
              <h2 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
                <Clock className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
                Recent Practice Sessions History ({sessions.length})
              </h2>
              <p className="text-xs text-neutral-500 dark:text-neutral-400">
                Review past oral evaluations, weak topics, and questions answered
              </p>
            </div>
          </div>

          <div className="space-y-3">
            {sessions.map((s) => {
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
                  className="p-4 bg-neutral-50 dark:bg-neutral-800/40 rounded-xl border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:border-neutral-300 dark:hover:border-neutral-700 transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <span className="text-xs font-bold text-neutral-900 dark:text-white">
                        {s.experimentTitle}
                      </span>
                      <span className="text-[11px] font-semibold text-neutral-500 px-2 py-0.5 rounded bg-neutral-200 dark:bg-neutral-700">
                        {s.config.questionCount} Questions • {s.config.difficulty}
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

                  <div className="flex items-center gap-4 self-end sm:self-auto">
                    <div className="text-right">
                      <div className="text-sm font-bold text-neutral-900 dark:text-white">
                        {s.averageScore.toFixed(1)}/10
                      </div>
                      <div className="text-[10px] text-neutral-500 font-medium">
                        {pct}% readiness
                      </div>
                    </div>

                    <button
                      onClick={() => onNavigate(`/experiments/${s.experimentId}/viva`)}
                      className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-white dark:bg-neutral-800 border border-neutral-200 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors"
                    >
                      <Award className="w-3.5 h-3.5 text-emerald-600" />
                      View Session
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default VivaPracticeHubPage;
