import type { ExperimentRecord, WorkspaceTab } from "../types/experiment";
import type { VivaSessionRecord } from "../types/viva";
import type {
  ReportingPeriod,
  ProgressOverviewMetrics,
  ExperimentReadinessItem,
  TopicAggregatedPerformance,
  RevisionPriorityItem,
  StrongTopicItem,
  RecommendedNextStep,
  PerformanceTrendPoint,
  ReadinessCategory,
} from "../types/progress";

const STANDARD_TOPICS = [
  { key: "theory", label: "Theory & Principles", tab: "theory" as WorkspaceTab },
  { key: "procedure", label: "Experimental Procedure", tab: "procedure" as WorkspaceTab },
  { key: "apparatus", label: "Apparatus & Setup", tab: "apparatus" as WorkspaceTab },
  { key: "observations", label: "Observations & Calculations", tab: "observations" as WorkspaceTab },
  { key: "precautions", label: "Safety Precautions", tab: "precautions" as WorkspaceTab },
];

/**
 * Filter sessions by reporting period based on start/completion timestamp
 */
export function filterSessionsByPeriod(
  sessions: VivaSessionRecord[],
  period: ReportingPeriod
): VivaSessionRecord[] {
  if (period === "all") return sessions;

  const now = Date.now();
  const cutoff = period === "7d" ? now - 7 * 86400000 : now - 30 * 86400000;

  return sessions.filter((s) => {
    const timestamp = s.completedAt || s.startedAt;
    return timestamp >= cutoff;
  });
}

/**
 * Calculate high-level summary overview metrics
 */
export function calculateOverviewMetrics(
  experiments: ExperimentRecord[],
  sessions: VivaSessionRecord[],
  period: ReportingPeriod = "all"
): ProgressOverviewMetrics {
  const filteredSessions = filterSessionsByPeriod(sessions, period);
  const completedSessions = filteredSessions.filter((s) => s.isCompleted);

  const totalExperiments = experiments.length;
  const completedExperiments = experiments.filter(
    (e) => e.status === "completed"
  ).length;

  let averageVivaScore: number | null = null;
  if (completedSessions.length > 0) {
    const totalScore = completedSessions.reduce(
      (acc, s) => acc + (typeof s.averageScore === "number" ? s.averageScore : 0),
      0
    );
    averageVivaScore = Number((totalScore / completedSessions.length).toFixed(1));
  }

  // Calculate preparation checklist progress across all experiments
  let totalChecklistItems = 0;
  let completedChecklistItems = 0;

  experiments.forEach((exp) => {
    // Each experiment has 5 standard checklist milestones
    totalChecklistItems += 5;
    if (exp.preparationChecklist) {
      const keys = ["objective", "theory", "apparatus", "procedure", "precautions"];
      keys.forEach((k) => {
        if (exp.preparationChecklist?.[k]) {
          completedChecklistItems++;
        }
      });
    }
  });

  const preparationPercentage =
    totalChecklistItems > 0
      ? Math.round((completedChecklistItems / totalChecklistItems) * 100)
      : 0;

  return {
    totalExperiments,
    completedExperiments,
    vivaSessionsCount: filteredSessions.length,
    completedVivaSessionsCount: completedSessions.length,
    averageVivaScore,
    preparationPercentage,
    totalChecklistItems,
    completedChecklistItems,
    experimentsWithChecklistCount: experiments.length,
  };
}

/**
 * Determine readiness status for each experiment
 */
export function calculateExperimentReadiness(
  experiments: ExperimentRecord[],
  sessions: VivaSessionRecord[]
): ExperimentReadinessItem[] {
  return experiments.map((exp) => {
    let completedCount = 0;
    const checklistKeys = ["objective", "theory", "apparatus", "procedure", "precautions"];
    checklistKeys.forEach((key) => {
      if (exp.preparationChecklist?.[key]) {
        completedCount++;
      }
    });

    let readinessStatus: ReadinessCategory = "not-started";
    if (completedCount === 5 || exp.status === "completed") {
      readinessStatus = "ready";
    } else if (completedCount > 0 || exp.status === "in-progress") {
      readinessStatus = "in-progress";
    }

    const expSessions = sessions.filter(
      (s) => s.experimentId === exp.id && s.isCompleted
    );
    const latestSession = expSessions.length > 0 ? expSessions[0] : null;

    return {
      experimentId: exp.id,
      title: exp.title,
      subject: exp.subject,
      experimentNumber: exp.experimentNumber,
      readinessStatus,
      completedChecklistCount: completedCount,
      totalChecklistCount: 5,
      checklistPercentage: Math.round((completedCount / 5) * 100),
      latestVivaScore: latestSession ? latestSession.averageScore : null,
      vivaSessionsCount: expSessions.length,
    };
  });
}

/**
 * Format chronological performance trend points for charting
 */
export function extractPerformanceTrendPoints(
  sessions: VivaSessionRecord[],
  period: ReportingPeriod = "all"
): PerformanceTrendPoint[] {
  const filtered = filterSessionsByPeriod(sessions, period).filter(
    (s) => s.isCompleted && typeof s.averageScore === "number"
  );

  // Sort ascending by date
  const sorted = [...filtered].sort(
    (a, b) => (a.completedAt || a.startedAt) - (b.completedAt || b.startedAt)
  );

  return sorted.map((s, index) => {
    const timestamp = s.completedAt || s.startedAt;
    const dateObj = new Date(timestamp);
    const dateLabel = dateObj.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });

    return {
      sessionId: s.id,
      experimentId: s.experimentId,
      experimentTitle: s.experimentTitle,
      timestamp,
      dateLabel: `${dateLabel} (#${index + 1})`,
      score: Number(s.averageScore.toFixed(1)),
      difficulty: s.config?.difficulty || "mixed",
      questionCount: s.config?.questionCount || s.totalQuestions || 5,
    };
  });
}

/**
 * Aggregate topic-level performance across all completed sessions
 */
export function aggregateTopicPerformance(
  sessions: VivaSessionRecord[],
  period: ReportingPeriod = "all"
): TopicAggregatedPerformance[] {
  const filtered = filterSessionsByPeriod(sessions, period).filter(
    (s) => s.isCompleted
  );

  const accumulators: Record<
    string,
    {
      total: number;
      correct: number;
      partially: number;
      incorrect: number;
      scoreSum: number;
    }
  > = {};

  STANDARD_TOPICS.forEach((t) => {
    accumulators[t.key] = {
      total: 0,
      correct: 0,
      partially: 0,
      incorrect: 0,
      scoreSum: 0,
    };
  });

  filtered.forEach((session) => {
    if (session.answers && Array.isArray(session.answers)) {
      session.answers.forEach((ans) => {
        const rawTopic = (ans.topic || "").toLowerCase();
        let matchedKey = "theory";
        if (rawTopic.includes("procedure")) matchedKey = "procedure";
        else if (rawTopic.includes("apparatus")) matchedKey = "apparatus";
        else if (rawTopic.includes("observation") || rawTopic.includes("calculation"))
          matchedKey = "observations";
        else if (rawTopic.includes("precaution")) matchedKey = "precautions";
        else matchedKey = "theory";

        const acc = accumulators[matchedKey];
        if (acc) {
          acc.total += 1;
          acc.scoreSum += ans.evaluation?.score || 0;
          if (ans.evaluation?.verdict === "correct") acc.correct += 1;
          else if (ans.evaluation?.verdict === "partially-correct") acc.partially += 1;
          else acc.incorrect += 1;
        }
      });
    }
  });

  return STANDARD_TOPICS.map((topicDef) => {
    const acc = accumulators[topicDef.key];
    const total = acc ? acc.total : 0;
    const avgScore =
      total > 0 && acc ? Number((acc.scoreSum / total).toFixed(1)) : null;
    const scorePercentage = avgScore !== null ? Math.round((avgScore / 10) * 100) : 0;

    let status: TopicAggregatedPerformance["status"] = "unpracticed";
    if (total === 0) {
      status = "unpracticed";
    } else if (avgScore !== null && avgScore >= 7.5 && total >= 2) {
      status = "strong";
    } else if (avgScore !== null && avgScore < 5.5) {
      status = "needs-revision";
    } else {
      status = "moderate";
    }

    return {
      topicKey: topicDef.key,
      topicLabel: topicDef.label,
      questionsAnswered: total,
      correctCount: acc ? acc.correct : 0,
      partiallyCorrectCount: acc ? acc.partially : 0,
      incorrectCount: acc ? acc.incorrect : 0,
      averageScore: avgScore,
      scorePercentage,
      status,
    };
  });
}

/**
 * Extract prioritized revision focus items from session history
 */
export function extractRevisionPriorities(
  sessions: VivaSessionRecord[],
  experiments: ExperimentRecord[]
): RevisionPriorityItem[] {
  const existingExperimentIds = new Set(experiments.map((e) => e.id));
  const expMap = new Map(experiments.map((e) => [e.id, e]));
  const priorities: RevisionPriorityItem[] = [];
  const seenKeys = new Set<string>();

  // Most recent sessions first
  const sortedSessions = [...sessions].sort(
    (a, b) => (b.completedAt || b.startedAt) - (a.completedAt || a.startedAt)
  );

  sortedSessions.forEach((s) => {
    // Only consider sessions for experiments that currently exist
    if (!existingExperimentIds.has(s.experimentId)) return;
    const exp = expMap.get(s.experimentId);
    if (!exp) return;

    if (s.revisionRecommendations && Array.isArray(s.revisionRecommendations)) {
      s.revisionRecommendations.forEach((rec) => {
        const dedupeKey = `${s.experimentId}_${rec.topic.toLowerCase()}`;
        if (!seenKeys.has(dedupeKey)) {
          seenKeys.add(dedupeKey);
          priorities.push({
            id: `prio_${dedupeKey}_${Math.random().toString(36).substring(2, 6)}`,
            topic: rec.topic,
            reason: rec.reason,
            experimentId: s.experimentId,
            experimentTitle: s.experimentTitle || exp.title,
            suggestedAction: rec.suggestedAction,
            workspaceTab: rec.workspaceTab,
            severity: rec.reason.toLowerCase().includes("lower") ? "high" : "medium",
          });
        }
      });
    }
  });

  return priorities.slice(0, 6);
}

/**
 * Identify topics where student consistently excels
 */
export function extractStrongTopics(
  sessions: VivaSessionRecord[],
  topicAnalysis: TopicAggregatedPerformance[]
): StrongTopicItem[] {
  const strong: StrongTopicItem[] = [];

  topicAnalysis.forEach((top) => {
    if (top.status === "strong" && top.averageScore !== null) {
      const expTitles = new Set<string>();
      sessions.forEach((s) => {
        if (s.isCompleted && s.strongTopics?.some((st) => st.toLowerCase().includes(top.topicKey))) {
          expTitles.add(s.experimentTitle);
        }
      });

      strong.push({
        topic: top.topicLabel,
        averageScore: top.averageScore,
        questionsCount: top.questionsAnswered,
        experimentTitles: Array.from(expTitles).slice(0, 3),
        notes: `Consistently answered ${top.correctCount} of ${top.questionsAnswered} oral questions with high technical precision.`,
      });
    }
  });

  return strong;
}

/**
 * Generate actionable next steps for the Revision Planner
 */
export function generateRecommendedNextSteps(
  experiments: ExperimentRecord[],
  sessions: VivaSessionRecord[],
  revisionPriorities: RevisionPriorityItem[]
): RecommendedNextStep[] {
  const steps: RecommendedNextStep[] = [];

  // Step 1: Address any high-priority revision items
  if (revisionPriorities.length > 0) {
    const topPriority = revisionPriorities[0];
    steps.push({
      id: "step_revise_weak",
      title: `Revise ${topPriority.topic}`,
      description: `${topPriority.reason} in "${topPriority.experimentTitle}".`,
      actionLabel: "Study in Workspace",
      targetPath: `/experiments/${topPriority.experimentId}`,
      category: "revision",
      priority: "high",
    });
  }

  // Step 2: Unfinished preparation checklist
  const inProgressExp = experiments.find((e) => {
    const checked = Object.values(e.preparationChecklist || {}).filter(Boolean).length;
    return checked > 0 && checked < 5;
  });
  if (inProgressExp) {
    steps.push({
      id: `step_checklist_${inProgressExp.id}`,
      title: `Complete Preparation Checklist`,
      description: `Finish the 5 lab readiness verification steps for "${inProgressExp.title}".`,
      actionLabel: "Open Checklist",
      targetPath: `/experiments/${inProgressExp.id}`,
      category: "prep",
      priority: "high",
    });
  }

  // Step 3: Experiments with 0 viva practice
  const testedExpIds = new Set(sessions.filter((s) => s.isCompleted).map((s) => s.experimentId));
  const untestedExp = experiments.find((e) => !testedExpIds.has(e.id));
  if (untestedExp) {
    steps.push({
      id: `step_viva_${untestedExp.id}`,
      title: `Test Understanding with Viva`,
      description: `Run your first oral examination simulator for "${untestedExp.title}".`,
      actionLabel: "Start Viva Practice",
      targetPath: `/experiments/${untestedExp.id}/viva`,
      category: "viva",
      priority: "medium",
    });
  }

  // Step 4: If all experiments prepared and tested, challenge with advanced difficulty
  if (steps.length === 0 && experiments.length > 0) {
    steps.push({
      id: "step_advanced_prep",
      title: "Consolidate Lab Mastery",
      description: "Challenge yourself with an Advanced Viva session across all mixed topics.",
      actionLabel: "Practice Advanced Viva",
      targetPath: "/viva-practice",
      category: "viva",
      priority: "low",
    });
  }

  return steps.slice(0, 4);
}
