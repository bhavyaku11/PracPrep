export type VivaTopic =
  | "theory"
  | "procedure"
  | "apparatus"
  | "observations"
  | "precautions"
  | "mixed";

export type VivaDifficulty = "beginner" | "intermediate" | "advanced" | "mixed";

export type EvaluationVerdict = "correct" | "partially-correct" | "incorrect";

export interface VivaQuestion {
  id: string;
  questionNumber: number;
  question: string;
  topic: VivaTopic;
  difficulty: "beginner" | "intermediate" | "advanced";
  expectedAnswer: string;
  keyPoints: string[];
  groundedSourceSection?: string;
  providerMode?: "demonstration" | "ai-live";
  providerId?: string;
}

export interface VivaEvaluation {
  verdict: EvaluationVerdict;
  score: number; // 0 to 10
  whatYouGotRight: string;
  whatWasMissing: string;
  expectedAnswer: string;
  improvementTip: string;
  providerMode: "demonstration" | "ai-live";
  providerId?: string;
  keyPointsCovered?: string[];
  keyPointsMissed?: string[];
}

export interface VivaSessionConfig {
  questionCount: 5 | 10 | 15;
  difficulty: VivaDifficulty;
  focus: VivaTopic;
}

export interface VivaAnswerRecord {
  questionId: string;
  questionNumber: number;
  questionText: string;
  topic: VivaTopic;
  difficulty: "beginner" | "intermediate" | "advanced";
  studentAnswer: string;
  evaluation: VivaEvaluation;
  timestamp: number;
}

export interface TopicPerformance {
  topic: string;
  total: number;
  correct: number;
  partiallyCorrect: number;
  incorrect: number;
  averageScore: number;
}

export interface RevisionRecommendation {
  topic: string;
  reason: string;
  suggestedAction: string;
  workspaceTab?:
    | "overview"
    | "theory"
    | "apparatus"
    | "procedure"
    | "observations"
    | "precautions"
    | "checklist";
}

export interface VivaSessionRecord {
  id: string;
  experimentId: string;
  experimentTitle: string;
  subject: string;
  config: VivaSessionConfig;
  startedAt: number;
  completedAt?: number;
  isCompleted: boolean;
  answers: VivaAnswerRecord[];
  totalQuestions: number;
  questionsAnswered: number;
  correctCount: number;
  partiallyCorrectCount: number;
  incorrectCount: number;
  averageScore: number;
  topicAnalysis: Record<string, TopicPerformance>;
  weakTopics: string[];
  strongTopics: string[];
  revisionRecommendations: RevisionRecommendation[];
  providerMode: "demonstration" | "ai-live";
}
