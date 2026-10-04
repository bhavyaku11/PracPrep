import type { WorkspaceTab } from "./experiment";

export type ReportingPeriod = "all" | "30d" | "7d";

export interface ProgressOverviewMetrics {
  totalExperiments: number;
  completedExperiments: number;
  vivaSessionsCount: number;
  completedVivaSessionsCount: number;
  averageVivaScore: number | null; // 0 to 10 scale
  preparationPercentage: number; // 0 to 100
  totalChecklistItems: number;
  completedChecklistItems: number;
  experimentsWithChecklistCount: number;
}

export type ReadinessCategory = "ready" | "in-progress" | "not-started";

export interface ExperimentReadinessItem {
  experimentId: string;
  title: string;
  subject: string;
  experimentNumber?: string;
  readinessStatus: ReadinessCategory;
  completedChecklistCount: number;
  totalChecklistCount: number;
  checklistPercentage: number;
  latestVivaScore: number | null;
  vivaSessionsCount: number;
}

export type TopicProficiency = "strong" | "moderate" | "needs-revision" | "unpracticed";

export interface TopicAggregatedPerformance {
  topicKey: string;
  topicLabel: string;
  questionsAnswered: number;
  correctCount: number;
  partiallyCorrectCount: number;
  incorrectCount: number;
  averageScore: number | null;
  scorePercentage: number;
  status: TopicProficiency;
}

export interface RevisionPriorityItem {
  id: string;
  topic: string;
  reason: string;
  experimentId: string;
  experimentTitle: string;
  suggestedAction: string;
  workspaceTab?: WorkspaceTab;
  averageScore?: number;
  severity: "high" | "medium";
}

export interface StrongTopicItem {
  topic: string;
  averageScore: number;
  questionsCount: number;
  experimentTitles: string[];
  notes: string;
}

export interface RecommendedNextStep {
  id: string;
  title: string;
  description: string;
  actionLabel: string;
  targetPath: string;
  category: "prep" | "viva" | "revision";
  priority: "high" | "medium" | "low";
}

export interface PerformanceTrendPoint {
  sessionId: string;
  experimentId: string;
  experimentTitle: string;
  timestamp: number;
  dateLabel: string;
  score: number;
  difficulty: string;
  questionCount: number;
}
