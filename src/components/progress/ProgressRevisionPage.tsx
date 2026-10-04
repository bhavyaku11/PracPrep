import React, { useState, useEffect, useMemo } from "react";
import {
  TrendingUp,
  FlaskConical,
  Plus,
  ArrowRight,
  X,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import type { ExperimentRecord } from "../../types/experiment";
import type { VivaSessionRecord } from "../../types/viva";
import type { ReportingPeriod } from "../../types/progress";
import { experimentStorage } from "../../services/experimentStorage";
import { vivaStorage } from "../../services/vivaStorage";
import {
  calculateOverviewMetrics,
  calculateExperimentReadiness,
  extractPerformanceTrendPoints,
  aggregateTopicPerformance,
  extractRevisionPriorities,
  extractStrongTopics,
  generateRecommendedNextSteps,
  filterSessionsByPeriod,
} from "../../utils/progressAnalytics";
import { ProgressMetricsOverview } from "./ProgressMetricsOverview";
import { LabReadinessOverview } from "./LabReadinessOverview";
import { PerformanceTrendsChart } from "./PerformanceTrendsChart";
import { TopicPerformanceSection } from "./TopicPerformanceSection";
import { WeakTopicsPriority } from "./WeakTopicsPriority";
import { StrongTopicsSection } from "./StrongTopicsSection";
import { RevisionPlannerSection } from "./RevisionPlannerSection";
import { SessionHistoryTable } from "./SessionHistoryTable";
import { VivaResultsScreen } from "../viva/VivaResultsScreen";

interface ProgressRevisionPageProps {
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const ProgressRevisionPage: React.FC<ProgressRevisionPageProps> = ({
  user,
  onNavigate,
}) => {
  const [period, setPeriod] = useState<ReportingPeriod>("all");
  const [experiments, setExperiments] = useState<ExperimentRecord[]>(() =>
    experimentStorage.getExperiments(user)
  );
  const [sessions, setSessions] = useState<VivaSessionRecord[]>(() =>
    vivaStorage.getSessions(user)
  );

  // Inspect scorecard modal state
  const [inspectingSession, setInspectingSession] = useState<VivaSessionRecord | null>(null);

  // Synchronize with storage updates
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

  // Derived Analytics via Pure Utility Functions
  const overviewMetrics = useMemo(
    () => calculateOverviewMetrics(experiments, sessions, period),
    [experiments, sessions, period]
  );

  const readinessItems = useMemo(
    () => calculateExperimentReadiness(experiments, sessions),
    [experiments, sessions]
  );

  const trendPoints = useMemo(
    () => extractPerformanceTrendPoints(sessions, period),
    [sessions, period]
  );

  const topicAnalytics = useMemo(
    () => aggregateTopicPerformance(sessions, period),
    [sessions, period]
  );

  const revisionPriorities = useMemo(
    () => extractRevisionPriorities(sessions, experiments),
    [sessions, experiments]
  );

  const strongTopics = useMemo(
    () => extractStrongTopics(sessions, topicAnalytics),
    [sessions, topicAnalytics]
  );

  const nextSteps = useMemo(
    () => generateRecommendedNextSteps(experiments, sessions, revisionPriorities),
    [experiments, sessions, revisionPriorities]
  );

  const periodFilteredSessions = useMemo(
    () => filterSessionsByPeriod(sessions, period).filter((s) => s.isCompleted),
    [sessions, period]
  );

  const periodLabel =
    period === "7d" ? "Last 7 Days" : period === "30d" ? "Last 30 Days" : "All Time";

  // Handle Scorecard view from Session History or Chart
  const handleViewScorecardById = (sessionId: string) => {
    const found = sessions.find((s) => s.id === sessionId);
    if (found) {
      setInspectingSession(found);
    }
  };

  // Scenario A: No experiments exist at all
  if (experiments.length === 0) {
    return (
      <div className="w-full max-w-4xl mx-auto py-12 px-4 text-center space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-neutral-100 dark:bg-neutral-800 text-neutral-400 flex items-center justify-center mx-auto">
          <FlaskConical className="w-8 h-8" />
        </div>
        <div className="space-y-2 max-w-md mx-auto">
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-white tracking-tight">
            Your progress starts here.
          </h1>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 leading-relaxed">
            Create your first experiment to begin tracking your laboratory preparation, checklist readiness, and oral viva exam performance.
          </p>
        </div>
        <div>
          <button
            onClick={() => onNavigate("/create-experiment")}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 text-xs font-semibold hover:bg-neutral-800 dark:hover:bg-neutral-100 shadow-sm transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Experiment
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full max-w-6xl mx-auto space-y-8 pb-12">
      {/* 1. Header & Reporting Period Selector */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-neutral-200 dark:border-neutral-800">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-100 dark:bg-emerald-950/80 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              <TrendingUp className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              Learning Analytics
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold text-neutral-900 dark:text-white tracking-tight">
            Progress & Revision
          </h1>
          <p className="text-sm text-neutral-600 dark:text-neutral-400 mt-1 max-w-2xl">
            Track your laboratory readiness, understand your performance, and focus your revision where it matters most.
          </p>
        </div>

        {/* Right side controls: Period filter + My Experiments link */}
        <div className="flex flex-wrap items-center gap-2.5 self-start sm:self-auto">
          {/* Period filter buttons */}
          <div className="flex items-center bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl p-1 text-xs">
            <button
              onClick={() => setPeriod("all")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                period === "all"
                  ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 shadow-2xs"
                  : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900"
              }`}
            >
              All Time
            </button>
            <button
              onClick={() => setPeriod("30d")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                period === "30d"
                  ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 shadow-2xs"
                  : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900"
              }`}
            >
              30 Days
            </button>
            <button
              onClick={() => setPeriod("7d")}
              className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                period === "7d"
                  ? "bg-neutral-900 text-white dark:bg-neutral-100 dark:text-neutral-900 shadow-2xs"
                  : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900"
              }`}
            >
              7 Days
            </button>
          </div>

          <button
            onClick={() => onNavigate("/experiments")}
            className="inline-flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-semibold text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-800 transition-colors"
          >
            My Experiments
            <ArrowRight className="w-3.5 h-3.5 text-neutral-400" />
          </button>
        </div>
      </div>

      {/* 2. Overview Metrics Cards */}
      <ProgressMetricsOverview
        metrics={overviewMetrics}
        periodLabel={periodLabel}
      />

      {/* 3. Laboratory Readiness Overview */}
      <LabReadinessOverview
        items={readinessItems}
        onNavigate={onNavigate}
      />

      {/* 4. Viva Performance Trends Chart */}
      <PerformanceTrendsChart
        trendPoints={trendPoints}
        periodLabel={periodLabel}
        onNavigate={onNavigate}
        onViewSessionScorecard={handleViewScorecardById}
      />

      {/* 5. Topic-Level Performance Analysis */}
      <TopicPerformanceSection
        topics={topicAnalytics}
      />

      {/* 6. Focus on These Topics (Revision Priorities) */}
      <WeakTopicsPriority
        priorities={revisionPriorities}
        onNavigate={onNavigate}
      />

      {/* 7. Strong Topics */}
      <StrongTopicsSection
        strongTopics={strongTopics}
      />

      {/* 8. Revision Planner (Recommended Next Steps) */}
      <RevisionPlannerSection
        steps={nextSteps}
        onNavigate={onNavigate}
      />

      {/* 9. Session History Table */}
      <SessionHistoryTable
        sessions={periodFilteredSessions}
        onViewScorecard={(session) => setInspectingSession(session)}
      />

      {/* Modal / Overlay for inspecting a past session scorecard */}
      {inspectingSession && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs overflow-y-auto"
          role="dialog"
          aria-modal="true"
        >
          <div className="relative w-full max-w-5xl bg-neutral-50 dark:bg-neutral-950 rounded-2xl shadow-2xl border border-neutral-200 dark:border-neutral-800 max-h-[90vh] overflow-y-auto my-auto p-4 sm:p-6">
            <button
              onClick={() => setInspectingSession(null)}
              className="absolute top-4 right-4 z-10 p-2 rounded-xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 text-neutral-500 hover:text-neutral-900 dark:hover:text-white transition-colors"
              aria-label="Close Scorecard"
            >
              <X className="w-5 h-5" />
            </button>

            <VivaResultsScreen
              session={inspectingSession}
              onPracticeAgain={() => {
                setInspectingSession(null);
                onNavigate(`/experiments/${inspectingSession.experimentId}/viva`);
              }}
              onReturnToExperiment={(_tab) => {
                setInspectingSession(null);
                onNavigate(`/experiments/${inspectingSession.experimentId}`);
              }}
              onBackToExperiments={() => {
                setInspectingSession(null);
                onNavigate("/experiments");
              }}
            />
          </div>
        </div>
      )}
    </div>
  );
};

export default ProgressRevisionPage;
