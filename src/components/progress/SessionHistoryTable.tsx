import React from "react";
import {
  History,
  CheckCircle2,
  Calendar,
  Award,
  ChevronRight,
} from "lucide-react";
import type { VivaSessionRecord } from "../../types/viva";

interface SessionHistoryTableProps {
  sessions: VivaSessionRecord[];
  onViewScorecard: (session: VivaSessionRecord) => void;
}

export const SessionHistoryTable: React.FC<SessionHistoryTableProps> = ({
  sessions,
  onViewScorecard,
}) => {
  if (sessions.length === 0) return null;

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-5 sm:p-6 shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <History className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            Viva Session History
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Audit log of completed oral examination simulations ({sessions.length} recorded)
          </p>
        </div>
      </div>

      <div className="space-y-3">
        {sessions.map((session) => {
          const timestamp = session.completedAt || session.startedAt;
          const dateStr = new Date(timestamp).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          });
          const scorePercent = Math.round((session.averageScore / 10) * 100);

          return (
            <div
              key={session.id}
              className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50/50 dark:bg-neutral-800/20 hover:border-neutral-300 dark:hover:border-neutral-700 flex flex-col sm:flex-row sm:items-center justify-between gap-3 transition-colors"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 mb-1">
                  <span className="text-xs font-bold text-neutral-900 dark:text-white">
                    {session.experimentTitle}
                  </span>
                  <span className="text-[11px] font-semibold text-neutral-500 dark:text-neutral-400 px-2 py-0.2 rounded bg-neutral-200 dark:bg-neutral-700">
                    {session.config?.questionCount || session.totalQuestions} Questions • {session.config?.difficulty || "mixed"}
                  </span>
                  <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-700 dark:text-emerald-400">
                    <CheckCircle2 className="w-3 h-3" />
                    Completed
                  </span>
                </div>

                <div className="flex items-center gap-3 text-xs text-neutral-500 dark:text-neutral-400">
                  <span className="flex items-center gap-1">
                    <Calendar className="w-3.5 h-3.5 text-neutral-400" />
                    {dateStr}
                  </span>
                  <span>•</span>
                  <span>
                    {session.correctCount} correct, {session.partiallyCorrectCount} partial, {session.incorrectCount} missed
                  </span>
                </div>
              </div>

              <div className="flex items-center gap-4 self-end sm:self-auto">
                <div className="text-right">
                  <div className="text-sm font-bold text-neutral-900 dark:text-white">
                    {session.averageScore.toFixed(1)}/10
                  </div>
                  <div className="text-[10px] text-neutral-500 font-medium">
                    {scorePercent}% readiness
                  </div>
                </div>

                <button
                  onClick={() => onViewScorecard(session)}
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-100 dark:hover:bg-neutral-700 transition-colors shadow-2xs"
                >
                  <Award className="w-3.5 h-3.5 text-emerald-600" />
                  View Scorecard
                  <ChevronRight className="w-3 h-3 text-neutral-400" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default SessionHistoryTable;
