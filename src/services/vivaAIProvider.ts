import type { ExperimentRecord } from "../types/experiment.ts";
import type {
  VivaQuestion,
  VivaEvaluation,
  VivaSessionConfig,
  VivaAnswerRecord,
  TopicPerformance,
  RevisionRecommendation,
  EvaluationVerdict,
  VivaTopic,
} from "../types/viva.ts";
import type { UserSession } from "../types/dashboard.ts";
import { apiClient, tokenManager, ApiError } from "../lib/apiClient.ts";
import { isValidUuid } from "./vivaStorage.ts";

export interface IVivaAIProvider {
  readonly mode: "demonstration" | "ai-live";
  readonly displayName: string;
  generateQuestions(
    experiment: ExperimentRecord,
    config: VivaSessionConfig,
    user?: UserSession
  ): Promise<VivaQuestion[]>;
  evaluateAnswer(
    question: VivaQuestion,
    studentAnswer: string,
    experiment: ExperimentRecord,
    sessionContext: {
      previousAnswers: VivaAnswerRecord[];
      currentQuestionIndex: number;
    },
    user?: UserSession
  ): Promise<VivaEvaluation>;
  analyzeSession(
    experiment: ExperimentRecord,
    answers: VivaAnswerRecord[]
  ): Promise<{
    topicAnalysis: Record<string, TopicPerformance>;
    weakTopics: string[];
    strongTopics: string[];
    revisionRecommendations: RevisionRecommendation[];
  }>;
}

/**
 * Helper to extract keywords and key concepts from text
 */
function extractSignificantTerms(text?: string): string[] {
  if (!text) return [];
  return text
    .toLowerCase()
    .replace(/[^\w\s-]/g, " ")
    .split(/\s+/)
    .filter((word) => word.length > 3 && !COMMON_STOPWORDS.has(word));
}

const COMMON_STOPWORDS = new Set([
  "this", "that", "with", "from", "have", "were", "what", "when", "where",
  "which", "while", "about", "above", "after", "again", "against", "because",
  "been", "before", "being", "below", "between", "both", "during", "each",
  "further", "here", "into", "more", "most", "other", "some", "such", "than",
  "then", "their", "them", "there", "these", "they", "through", "under",
  "until", "very", "will", "would", "should", "could", "also", "using",
  "used", "value", "table", "given", "note", "read", "take", "step"
]);

/**
 * Intelligent Demonstration Provider
 * Grounded directly in user's experiment manual content with zero fake AI claims.
 */
export class DemonstrationVivaProvider implements IVivaAIProvider {
  readonly mode = "demonstration" as const;
  readonly displayName = "PracPrep Academic Evaluation Engine (Demonstration Mode)";

  async generateQuestions(
    experiment: ExperimentRecord,
    config: VivaSessionConfig
  ): Promise<VivaQuestion[]> {
    // Artificial small delay to reflect processing
    await new Promise((resolve) => setTimeout(resolve, 350));

    const pool: Omit<VivaQuestion, "id" | "questionNumber">[] = [];
    const expTitle = experiment.title || "this experiment";
    const expSubject = experiment.subject || "laboratory engineering";

    // 1. Objective / Core Aim Questions
    if (experiment.objective) {
      pool.push({
        question: `What is the primary scientific aim or objective of "${expTitle}", and what key parameter is being determined?`,
        topic: "theory",
        difficulty: "beginner",
        expectedAnswer: `The primary objective is: ${experiment.objective}`,
        keyPoints: [
          "State the exact experimental objective",
          "Identify the independent and dependent variables",
          "Explain what property or parameter is being measured or verified",
        ],
        groundedSourceSection: "Objective",
      });
    } else {
      pool.push({
        question: `In the context of ${expSubject}, what is the fundamental purpose of conducting "${expTitle}"?`,
        topic: "theory",
        difficulty: "beginner",
        expectedAnswer: `The experiment aims to understand and demonstrate the fundamental concepts and working principles of ${expTitle}.`,
        keyPoints: [
          "Explain the primary goal of the lab exercise",
          "Relate the experiment to course fundamentals",
        ],
        groundedSourceSection: "Title",
      });
    }

    // 2. Theory & Governing Principles Questions
    if (experiment.theory && experiment.theory.trim().length > 0) {
      pool.push({
        question: `Explain the fundamental governing scientific law or principle that forms the basis of "${expTitle}".`,
        topic: "theory",
        difficulty: "intermediate",
        expectedAnswer: `The underlying principle is based on: ${experiment.theory.slice(0, 300)}...`,
        keyPoints: [
          "State the governing law or equation accurately",
          "Define the physical terms and symbols involved",
          "Explain the key theoretical assumptions",
        ],
        groundedSourceSection: "Theory",
      });

      pool.push({
        question: `What mathematical formulas or equations are used in this experiment, and what do each of the variables represent?`,
        topic: "theory",
        difficulty: "advanced",
        expectedAnswer: `The theoretical relations from the manual state: ${experiment.theory.slice(0, 250)}`,
        keyPoints: [
          "Write the primary mathematical relationship",
          "Specify the SI units for each variable",
          "State boundary conditions or constants used",
        ],
        groundedSourceSection: "Theory",
      });

      pool.push({
        question: `Under what conditions or limitations does the theory of "${expTitle}" hold true in a real laboratory environment?`,
        topic: "theory",
        difficulty: "advanced",
        expectedAnswer: `The theory applies when standard conditions (e.g. temperature, ideal connections, linear range) are maintained as outlined in the theoretical documentation.`,
        keyPoints: [
          "Mention environmental factors (temperature, resistance, frequency)",
          "Identify sources of non-ideal behavior in real components",
          "Explain how theoretical models differ from physical setups",
        ],
        groundedSourceSection: "Theory",
      });
    } else {
      pool.push({
        question: `What theoretical concepts in ${expSubject} are most critical to understand before setting up "${expTitle}"?`,
        topic: "theory",
        difficulty: "beginner",
        expectedAnswer: `Understanding the circuit or system model and fundamental equations of ${expSubject} is essential.`,
        keyPoints: [
          "Identify relevant laws in " + expSubject,
          "Explain basic concepts behind the experiment",
        ],
        groundedSourceSection: "General Subject",
      });
    }

    // 3. Apparatus & Instruments Questions
    if (experiment.apparatus && experiment.apparatus.trim().length > 0) {
      pool.push({
        question: `List the key apparatus, meters, or components required for "${expTitle}" and describe the function of each instrument.`,
        topic: "apparatus",
        difficulty: "beginner",
        expectedAnswer: `The required apparatus includes: ${experiment.apparatus.slice(0, 250)}. Each instrument is selected to measure or provide specific parameters.`,
        keyPoints: [
          "Identify the instruments used",
          "Explain the measurement role of each meter or component",
          "Mention rating or sensitivity considerations",
        ],
        groundedSourceSection: "Apparatus",
      });

      pool.push({
        question: `Why are the specific measuring instruments chosen for this experiment, and how would you select their measurement ranges?`,
        topic: "apparatus",
        difficulty: "intermediate",
        expectedAnswer: `Instruments must be selected such that expected readings fall within the middle one-third of the meter scale to minimize percentage deflection error.`,
        keyPoints: [
          "Range selection based on maximum expected parameter",
          "Least count and sensitivity of meters",
          "Minimizing loading effects on the test circuit/setup",
        ],
        groundedSourceSection: "Apparatus",
      });
    } else {
      pool.push({
        question: `What essential measuring tools or equipment are typically required when conducting practicals in ${expSubject}?`,
        topic: "apparatus",
        difficulty: "beginner",
        expectedAnswer: `Standard calibrated measurement meters, power supplies, probes, and mounting breadboards/test benches are needed.`,
        keyPoints: [
          "Name standard apparatus",
          "Explain instrument calibration",
        ],
        groundedSourceSection: "Apparatus Context",
      });
    }

    // 4. Procedure & Experimental Method Questions
    if (experiment.procedure && experiment.procedure.trim().length > 0) {
      pool.push({
        question: `Walk through the initial setup and preparation steps before taking the first reading in "${expTitle}".`,
        topic: "procedure",
        difficulty: "intermediate",
        expectedAnswer: `Initial steps: ${experiment.procedure.slice(0, 280)}...`,
        keyPoints: [
          "Verifying zero-error on meters",
          "Checking connections against the circuit or schematic diagram",
          "Ensuring supply is off before final inspection",
        ],
        groundedSourceSection: "Procedure",
      });

      pool.push({
        question: `What step-by-step sequence is followed to vary the independent variable and record systematic observations?`,
        topic: "procedure",
        difficulty: "intermediate",
        expectedAnswer: `The procedure specifies systematically adjusting the control parameter and noting corresponding dependent readings: ${experiment.procedure.slice(0, 250)}`,
        keyPoints: [
          "Gradual increment of parameters",
          "Waiting for steady-state before reading",
          "Repeating readings to identify random errors",
        ],
        groundedSourceSection: "Procedure",
      });

      pool.push({
        question: `If an unexpected or anomalous reading occurs during the procedure, how should you troubleshoot the setup?`,
        topic: "procedure",
        difficulty: "advanced",
        expectedAnswer: `Immediately isolate power, check loose connection terminals, verify meter polarity, and inspect component continuity.`,
        keyPoints: [
          "Isolate power before inspecting",
          "Check polarity and terminal tightness",
          "Verify meter ranges and calibration",
        ],
        groundedSourceSection: "Procedure",
      });
    } else {
      pool.push({
        question: `Describe the general experimental methodology you would adopt to verify experimental results in "${expTitle}".`,
        topic: "procedure",
        difficulty: "beginner",
        expectedAnswer: `Set up the apparatus cleanly, check all connections, apply inputs incrementally, and record values in a systematic table.`,
        keyPoints: [
          "Systematic procedure execution",
          "Careful observation recording",
        ],
        groundedSourceSection: "Procedure",
      });
    }

    // 5. Observations & Calculations Questions
    if (experiment.observations || experiment.calculations) {
      const obsContent = (experiment.observations || "") + " " + (experiment.calculations || "");
      pool.push({
        question: `Explain how the recorded raw data is processed mathematically to arrive at the final result of the experiment.`,
        topic: "observations",
        difficulty: "intermediate",
        expectedAnswer: `The calculation procedure applies the formula to tabular data: ${obsContent.slice(0, 250)}`,
        keyPoints: [
          "State the calculation formula used on table columns",
          "Explain the significance of averaging multiple trials",
          "Indicate how units are converted to standard SI format",
        ],
        groundedSourceSection: "Observations & Calculations",
      });

      pool.push({
        question: `What graphical plots or curves are drawn for this experiment, and what does the slope of the curve represent physically?`,
        topic: "observations",
        difficulty: "advanced",
        expectedAnswer: `The plot shows the relationship between measured variables, where the slope directly corresponds to the physical constant or parameter being evaluated.`,
        keyPoints: [
          "Identify variables plotted on X and Y axes",
          "State whether the curve is linear or non-linear",
          "Physical interpretation of the slope and intercept",
        ],
        groundedSourceSection: "Observations",
      });
    } else {
      pool.push({
        question: `How would you structure an observation table for "${expTitle}" to avoid recording ambiguous data?`,
        topic: "observations",
        difficulty: "beginner",
        expectedAnswer: `Include serial number, clear column headings with SI units, trial repetitions, and calculated mean columns.`,
        keyPoints: [
          "Column headings with proper units",
          "Provision for multiple trials and averages",
        ],
        groundedSourceSection: "Observations Context",
      });
    }

    // 6. Precautions & Safety Questions
    if (experiment.precautions && experiment.precautions.trim().length > 0) {
      pool.push({
        question: `What are the critical safety precautions and handling instructions that must be observed during "${expTitle}"?`,
        topic: "precautions",
        difficulty: "beginner",
        expectedAnswer: `The key precautions include: ${experiment.precautions.slice(0, 250)}`,
        keyPoints: [
          "Preventing electrical shock or short-circuits",
          "Operating components strictly within rated voltage/current",
          "Parallax error prevention when reading analog meters",
        ],
        groundedSourceSection: "Precautions",
      });

      pool.push({
        question: `What specific precautions are necessary to prevent instrument damage or severe measurement error in this setup?`,
        topic: "precautions",
        difficulty: "intermediate",
        expectedAnswer: `Ensure correct polarity connections, start power supply from zero, and avoid exceeding maximum instrument deflection.`,
        keyPoints: [
          "Polarity verification",
          "Zero-setting and parallax elimination",
          "Gradual voltage/load application",
        ],
        groundedSourceSection: "Precautions",
      });
    } else {
      pool.push({
        question: `What general laboratory safety precautions should always be followed when working on "${expSubject}" practicals?`,
        topic: "precautions",
        difficulty: "beginner",
        expectedAnswer: `Verify circuit connections with the lab instructor before turning on power, wear safety gear, and ensure zero error on meters.`,
        keyPoints: [
          "Power off during wiring changes",
          "Inspection before energizing",
        ],
        groundedSourceSection: "Precautions",
      });
    }

    // Filter by topic focus if specified (unless "mixed")
    let filtered = pool;
    if (config.focus !== "mixed") {
      const topicMatches = pool.filter((q) => q.topic === config.focus);
      if (topicMatches.length > 0) {
        filtered = topicMatches;
      }
    }

    // Filter by difficulty if specified (unless "mixed")
    if (config.difficulty !== "mixed") {
      const diffMatches = filtered.filter((q) => q.difficulty === config.difficulty);
      if (diffMatches.length >= 3) {
        filtered = diffMatches;
      }
    }

    // Cycle or select questions to reach requested count
    const selected: VivaQuestion[] = [];
    const targetCount = config.questionCount;

    for (let i = 0; i < targetCount; i++) {
      const source = filtered[i % filtered.length];
      selected.push({
        ...source,
        id: `vq-${experiment.id}-${i + 1}-${Date.now().toString(36)}`,
        questionNumber: i + 1,
      });
    }

    return selected;
  }

  async evaluateAnswer(
    question: VivaQuestion,
    studentAnswer: string,
    _experiment: ExperimentRecord,
    _sessionContext: {
      previousAnswers: VivaAnswerRecord[];
      currentQuestionIndex: number;
    }
  ): Promise<VivaEvaluation> {
    // Artificial small delay to simulate analysis
    await new Promise((resolve) => setTimeout(resolve, 400));

    const cleanAnswer = studentAnswer.trim();
    if (!cleanAnswer || cleanAnswer.length < 5) {
      return {
        verdict: "incorrect",
        score: 0,
        whatYouGotRight: "No substantive technical response was provided.",
        whatWasMissing: `A complete answer should address: ${question.keyPoints.join("; ")}.`,
        expectedAnswer: question.expectedAnswer,
        improvementTip: "State the core scientific definition or working principle before elaborating.",
        providerMode: "demonstration",
      };
    }

    // Low effort check (gibberish or dismissive responses)
    const lower = cleanAnswer.toLowerCase();
    if (/^(idk|dont know|i don't know|no idea|asdf|qwerty|na|nil|\?+)$/i.test(lower)) {
      return {
        verdict: "incorrect",
        score: 1,
        whatYouGotRight: "Attempted response, but without technical content.",
        whatWasMissing: `You missed the core explanation: ${question.keyPoints.join(", ")}.`,
        expectedAnswer: question.expectedAnswer,
        improvementTip: "Even if uncertain, mention the primary formula, law, or equipment involved.",
        providerMode: "demonstration",
      };
    }

    // Technical term matching
    const answerTerms = new Set(extractSignificantTerms(cleanAnswer));
    const expectedTerms = extractSignificantTerms(question.expectedAnswer);
    const keyPointTerms = question.keyPoints.flatMap((kp) => extractSignificantTerms(kp));

    const targetTerms = Array.from(new Set([...expectedTerms, ...keyPointTerms]));
    let matchedCount = 0;
    const recognizedConcepts: string[] = [];
    const missingConcepts: string[] = [];

    targetTerms.forEach((term) => {
      if (answerTerms.has(term)) {
        matchedCount++;
        if (recognizedConcepts.length < 4 && term.length > 3) {
          recognizedConcepts.push(term);
        }
      } else {
        if (missingConcepts.length < 3 && term.length > 4) {
          missingConcepts.push(term);
        }
      }
    });

    // Check key point coverage
    let coveredPoints = 0;
    const keyPointFeedback: string[] = [];
    question.keyPoints.forEach((kp) => {
      const kpTerms = extractSignificantTerms(kp);
      const hits = kpTerms.filter((t) => answerTerms.has(t)).length;
      if (hits >= Math.max(1, Math.floor(kpTerms.length * 0.35))) {
        coveredPoints++;
        keyPointFeedback.push(kp);
      }
    });

    const matchRatio = targetTerms.length > 0 ? matchedCount / targetTerms.length : 0.5;
    const keyPointRatio = question.keyPoints.length > 0 ? coveredPoints / question.keyPoints.length : 0.5;
    const lengthBonus = Math.min(cleanAnswer.split(/\s+/).length / 25, 1);

    // Compute composite score (0 to 10)
    let score = Math.round(keyPointRatio * 5 + matchRatio * 3 + lengthBonus * 2);
    score = Math.max(1, Math.min(10, score));

    let verdict: EvaluationVerdict = "partially-correct";
    if (score >= 8) {
      verdict = "correct";
    } else if (score <= 3) {
      verdict = "incorrect";
    }

    const whatYouGotRight =
      recognizedConcepts.length > 0 || keyPointFeedback.length > 0
        ? `Correctly identified key principles regarding: ${[
            ...keyPointFeedback.slice(0, 2),
            ...recognizedConcepts.slice(0, 3).map((c) => `"${c}"`),
          ].join(", ")}.`
        : "You mentioned general context, but lacked specific technical terminology from the lab manual.";

    const whatWasMissing =
      missingConcepts.length > 0 || coveredPoints < question.keyPoints.length
        ? `Missing critical concepts: ${question.keyPoints
            .filter((kp) => !keyPointFeedback.includes(kp))
            .join("; ") || "More precise scientific terminology and units."}`
        : "No major concepts were omitted.";

    // Actionable viva tip
    const tips = [
      "In oral viva voce, always define the scientific parameter first, then specify its standard SI units.",
      "Mention any underlying assumptions or boundary conditions when stating equations to oral examiners.",
      "Relate your answer directly to the physical instruments used on your test bench.",
      "State how errors are mitigated (e.g. eliminating parallax error, taking multiple readings).",
      "Explain the physical significance of the slope or intercept when describing graphs.",
    ];
    const improvementTip = tips[question.questionNumber % tips.length];

    return {
      verdict,
      score,
      whatYouGotRight,
      whatWasMissing,
      expectedAnswer: question.expectedAnswer,
      improvementTip,
      providerMode: "demonstration",
    };
  }

  async analyzeSession(
    _experiment: ExperimentRecord,
    answers: VivaAnswerRecord[]
  ): Promise<{
    topicAnalysis: Record<string, TopicPerformance>;
    weakTopics: string[];
    strongTopics: string[];
    revisionRecommendations: RevisionRecommendation[];
  }> {
    const topicMap: Record<string, { total: number; correct: number; partially: number; incorrect: number; scores: number[] }> = {};

    answers.forEach((rec) => {
      const top = rec.topic || "theory";
      if (!topicMap[top]) {
        topicMap[top] = { total: 0, correct: 0, partially: 0, incorrect: 0, scores: [] };
      }
      topicMap[top].total++;
      topicMap[top].scores.push(rec.evaluation.score);
      if (rec.evaluation.verdict === "correct") topicMap[top].correct++;
      else if (rec.evaluation.verdict === "partially-correct") topicMap[top].partially++;
      else topicMap[top].incorrect++;
    });

    const topicAnalysis: Record<string, TopicPerformance> = {};
    const weakTopics: string[] = [];
    const strongTopics: string[] = [];

    Object.entries(topicMap).forEach(([t, data]) => {
      const avg =
        data.scores.length > 0
          ? Math.round((data.scores.reduce((a, b) => a + b, 0) / data.scores.length) * 10) / 10
          : 0;
      topicAnalysis[t] = {
        topic: t,
        total: data.total,
        correct: data.correct,
        partiallyCorrect: data.partially,
        incorrect: data.incorrect,
        averageScore: avg,
      };

      if (avg >= 7.5 && data.correct >= data.incorrect) {
        strongTopics.push(t);
      } else if (avg < 6.0 || data.incorrect > 0) {
        weakTopics.push(t);
      }
    });

    // Targeted Revision Recommendations linked to Experiment Workspace tabs
    const revisionRecommendations: RevisionRecommendation[] = [];

    if (weakTopics.includes("theory") || (topicAnalysis["theory"] && topicAnalysis["theory"].averageScore < 6)) {
      revisionRecommendations.push({
        topic: "Underlying Theoretical Principles",
        reason: "Responses showed gaps in governing equations, physical definitions, or theoretical assumptions.",
        suggestedAction: "Revisit the theoretical derivations and principle formulations in your workspace.",
        workspaceTab: "theory",
      });
    }

    if (weakTopics.includes("procedure") || (topicAnalysis["procedure"] && topicAnalysis["procedure"].averageScore < 6)) {
      revisionRecommendations.push({
        topic: "Step-by-Step Procedure",
        reason: "Examiner queries about initial zero-error settings and parameter variations had omissions.",
        suggestedAction: "Walk through the sequential step checklist in the Procedure tab.",
        workspaceTab: "procedure",
      });
    }

    if (weakTopics.includes("apparatus") || (topicAnalysis["apparatus"] && topicAnalysis["apparatus"].averageScore < 6)) {
      revisionRecommendations.push({
        topic: "Apparatus Ratings & Range Selection",
        reason: "Instrument functions and range calculations were partially described.",
        suggestedAction: "Check instrument specifications and ratings in the Apparatus section.",
        workspaceTab: "apparatus",
      });
    }

    if (weakTopics.includes("observations") || (topicAnalysis["observations"] && topicAnalysis["observations"].averageScore < 6)) {
      revisionRecommendations.push({
        topic: "Observations & Calculations",
        reason: "Formulas and graphical slope representations need clearer mathematical articulation.",
        suggestedAction: "Review your calculation formulas and observation table structure.",
        workspaceTab: "observations",
      });
    }

    if (weakTopics.includes("precautions") || (topicAnalysis["precautions"] && topicAnalysis["precautions"].averageScore < 6)) {
      revisionRecommendations.push({
        topic: "Safety & Error Elimination",
        reason: "Questions on parallax elimination and circuit safety received lower scores.",
        suggestedAction: "Review safety warnings and precautions in the Precautions tab.",
        workspaceTab: "precautions",
      });
    }

    // Default recommendation if all did well or no specific weak topic
    if (revisionRecommendations.length === 0) {
      revisionRecommendations.push({
        topic: "Preparation Readiness Review",
        reason: "Good overall performance across tested questions. Consolidate your confidence.",
        suggestedAction: "Review your final checklist in the Experiment Workspace before lab day.",
        workspaceTab: "checklist",
      });
    }

    return {
      topicAnalysis,
      weakTopics,
      strongTopics,
      revisionRecommendations,
    };
  }
}

// ==============================================================================
// Remote AI Provider & Backend DTOs
// ==============================================================================

export interface BackendVivaGeneratedQuestion {
  id: string;
  questionNumber: number;
  question: string;
  topic: string;
  difficulty: string;
  expectedAnswer?: string | null;
  keyPoints?: string[];
  groundedSourceSection?: string | null;
}

export interface BackendVivaGenerateQuestionsResponse {
  questions: BackendVivaGeneratedQuestion[];
  providerMode: "demonstration" | "ai-live";
  providerId: string;
  totalCount: number;
}

export interface BackendVivaEvaluationResponse {
  verdict: EvaluationVerdict;
  score: number;
  feedback?: string | null;
  whatYouGotRight?: string;
  whatWasMissing?: string;
  expectedAnswer?: string;
  improvementTip?: string;
  providerMode: "demonstration" | "ai-live";
  providerId: string;
  keyPointsCovered?: string[];
  keyPointsMissed?: string[];
}

/**
 * Remote Viva AI Provider
 * Communicates with FastAPI backend AI endpoints (/api/v1/viva/generate-questions
 * and /api/v1/viva/evaluate-answer) with authentication and provider metadata preservation.
 */
export class RemoteVivaAIProvider implements IVivaAIProvider {
  readonly mode = "ai-live" as const;
  readonly displayName = "PracPrep Live AI Evaluation Engine (Remote)";

  private demonstrationFallback = new DemonstrationVivaProvider();

  async generateQuestions(
    experiment: ExperimentRecord,
    config: VivaSessionConfig,
    _user?: UserSession
  ): Promise<VivaQuestion[]> {
    const body: Record<string, unknown> = {
      questionCount: config.questionCount,
      difficulty: config.difficulty,
      topicFocus: config.focus,
    };

    if (experiment.id && isValidUuid(experiment.id)) {
      body.experimentId = experiment.id;
    } else {
      body.experimentContext = {
        title: experiment.title || "Laboratory Experiment",
        subject: experiment.subject || "Engineering",
        experiment_number: experiment.experimentNumber || null,
        description: experiment.description || null,
        objective: experiment.objective || null,
        theory: experiment.theory || null,
        apparatus: experiment.apparatus || null,
        procedure: experiment.procedure || null,
        observations: experiment.observations || null,
        calculations: experiment.calculations || null,
        precautions: experiment.precautions || null,
      };
    }

    const response = await apiClient.post<BackendVivaGenerateQuestionsResponse>(
      "/viva/generate-questions",
      body,
      { requiresAuth: true }
    );

    if (!response || !response.questions || response.questions.length === 0) {
      throw new ApiError({
        message: "The AI evaluation service returned no questions for this experiment.",
        status: 502,
        statusText: "Bad Gateway",
        code: "INVALID_RESPONSE",
      });
    }

    return response.questions.map((q) => ({
      id: q.id,
      questionNumber: q.questionNumber,
      question: q.question,
      topic: q.topic as VivaTopic,
      difficulty: (q.difficulty?.toLowerCase() || "intermediate") as "beginner" | "intermediate" | "advanced",
      expectedAnswer: q.expectedAnswer || "",
      keyPoints: q.keyPoints || [],
      groundedSourceSection: q.groundedSourceSection || undefined,
      providerMode: response.providerMode,
      providerId: response.providerId,
    }));
  }

  async evaluateAnswer(
    question: VivaQuestion,
    studentAnswer: string,
    _experiment: ExperimentRecord,
    _sessionContext: {
      previousAnswers: VivaAnswerRecord[];
      currentQuestionIndex: number;
    },
    _user?: UserSession
  ): Promise<VivaEvaluation> {
    const body = {
      question: {
        id: question.id,
        questionNumber: question.questionNumber,
        question: question.question,
        topic: question.topic,
        difficulty: question.difficulty,
        expectedAnswer: question.expectedAnswer,
        keyPoints: question.keyPoints,
        groundedSourceSection: question.groundedSourceSection,
      },
      studentAnswer: studentAnswer.trim(),
    };

    const response = await apiClient.post<BackendVivaEvaluationResponse>(
      "/viva/evaluate-answer",
      body,
      { requiresAuth: true }
    );

    if (!response || response.score === undefined || !response.verdict) {
      throw new ApiError({
        message: "The AI evaluation service returned an incomplete evaluation response.",
        status: 502,
        statusText: "Bad Gateway",
        code: "INVALID_RESPONSE",
      });
    }

    return {
      verdict: response.verdict,
      score: response.score,
      whatYouGotRight: response.whatYouGotRight || "",
      whatWasMissing: response.whatWasMissing || "",
      expectedAnswer: response.expectedAnswer || "",
      improvementTip: response.improvementTip || "",
      providerMode: response.providerMode,
      providerId: response.providerId,
      keyPointsCovered: response.keyPointsCovered || [],
      keyPointsMissed: response.keyPointsMissed || [],
    };
  }

  async analyzeSession(
    experiment: ExperimentRecord,
    answers: VivaAnswerRecord[]
  ) {
    return this.demonstrationFallback.analyzeSession(experiment, answers);
  }
}

// ==============================================================================
// Dual-Mode Viva AI Strategy & Mode Resolution
// ==============================================================================

export type VivaAIMode = "authenticated" | "guest";

export interface VivaAIModeResolver {
  resolveMode(user?: UserSession): VivaAIMode;
}

export const defaultVivaAIModeResolver: VivaAIModeResolver = {
  resolveMode(user?: UserSession): VivaAIMode {
    if (user) {
      if (user.isGuest) return "guest";
      if (tokenManager.hasAccessToken()) return "authenticated";
      return "guest";
    }
    if (typeof window !== "undefined") {
      try {
        const stored = window.localStorage.getItem("pracprep_user");
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed && parsed.isGuest) return "guest";
          if (parsed && !parsed.isGuest && tokenManager.hasAccessToken()) {
            return "authenticated";
          }
        }
      } catch {
        // Safe fallback
      }
    }
    return tokenManager.hasAccessToken() ? "authenticated" : "guest";
  },
};

/**
 * Dual-Mode Viva AI Facade
 * Routes requests to RemoteVivaAIProvider for authenticated users and DemonstrationVivaProvider
 * for guest students. Strictly avoids silent fallback when remote calls fail.
 */
export class DualModeVivaAIProvider implements IVivaAIProvider {
  private localProvider: IVivaAIProvider;
  private remoteProvider: IVivaAIProvider;
  private modeResolver: VivaAIModeResolver;

  constructor(
    localProvider: IVivaAIProvider = new DemonstrationVivaProvider(),
    remoteProvider: IVivaAIProvider = new RemoteVivaAIProvider(),
    modeResolver: VivaAIModeResolver = defaultVivaAIModeResolver
  ) {
    this.localProvider = localProvider;
    this.remoteProvider = remoteProvider;
    this.modeResolver = modeResolver;
  }

  get mode(): "demonstration" | "ai-live" {
    return this.modeResolver.resolveMode() === "authenticated" ? "ai-live" : "demonstration";
  }

  get displayName(): string {
    return this.modeResolver.resolveMode() === "authenticated"
      ? this.remoteProvider.displayName
      : this.localProvider.displayName;
  }

  setModeResolver(resolver: VivaAIModeResolver): void {
    this.modeResolver = resolver;
  }

  resetModeResolver(): void {
    this.modeResolver = defaultVivaAIModeResolver;
  }

  getModeResolver(): VivaAIModeResolver {
    return this.modeResolver;
  }

  setRemoteProvider(provider: IVivaAIProvider): void {
    this.remoteProvider = provider;
  }

  setLocalProvider(provider: IVivaAIProvider): void {
    this.localProvider = provider;
  }

  getLocalProvider(): IVivaAIProvider {
    return this.localProvider;
  }

  getRemoteProvider(): IVivaAIProvider {
    return this.remoteProvider;
  }

  async generateQuestions(
    experiment: ExperimentRecord,
    config: VivaSessionConfig,
    user?: UserSession
  ): Promise<VivaQuestion[]> {
    const activeMode = this.modeResolver.resolveMode(user);
    if (activeMode === "authenticated") {
      // Must NOT silently fall back on error for authenticated users
      return await this.remoteProvider.generateQuestions(experiment, config, user);
    }
    return await this.localProvider.generateQuestions(experiment, config, user);
  }

  async evaluateAnswer(
    question: VivaQuestion,
    studentAnswer: string,
    experiment: ExperimentRecord,
    sessionContext: {
      previousAnswers: VivaAnswerRecord[];
      currentQuestionIndex: number;
    },
    user?: UserSession
  ): Promise<VivaEvaluation> {
    const activeMode = this.modeResolver.resolveMode(user);
    if (activeMode === "authenticated") {
      // Must NOT silently fall back on error for authenticated users
      return await this.remoteProvider.evaluateAnswer(
        question,
        studentAnswer,
        experiment,
        sessionContext,
        user
      );
    }
    return await this.localProvider.evaluateAnswer(
      question,
      studentAnswer,
      experiment,
      sessionContext,
      user
    );
  }

  async analyzeSession(
    experiment: ExperimentRecord,
    answers: VivaAnswerRecord[]
  ) {
    return await this.localProvider.analyzeSession(experiment, answers);
  }
}

/**
 * Format Viva API errors into actionable, user-friendly messages.
 */
export function formatVivaApiError(
  err: unknown,
  action: string = "generating questions"
): string {
  if (err instanceof ApiError) {
    if (err.status === 401 || err.isAuthError) {
      return "Your session has expired. Please log in again to continue.";
    }
    if (err.status === 422) {
      if (typeof err.detail === "string" && err.detail.trim().length > 0) {
        return err.detail;
      }
      if (Array.isArray(err.validationErrors) && err.validationErrors.length > 0) {
        return err.validationErrors.map((v) => v.msg).join(", ");
      }
      return `The request for ${action} contained invalid data. Please verify your experiment content.`;
    }
    if (err.status === 429) {
      return "AI service rate limit exceeded. Please wait a moment and try again.";
    }
    if (err.status === 502) {
      return "The AI evaluation service returned an invalid response. Please try again.";
    }
    if (err.status === 503) {
      return "The AI evaluation service is temporarily unavailable. Please try again in a moment.";
    }
    if (err.status === 504) {
      return "The AI evaluation request timed out. Please try again.";
    }
    if (err.isNetworkError) {
      return "Network connection error. Please check your internet connection and try again.";
    }
    if (typeof err.detail === "string" && err.detail.trim().length > 0) {
      return err.detail;
    }
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return `An unexpected error occurred while ${action}. Please try again.`;
}

// Singleton instances
export const localVivaAIProvider = new DemonstrationVivaProvider();
export const remoteVivaAIProvider = new RemoteVivaAIProvider();
export const vivaAIProvider: DualModeVivaAIProvider = new DualModeVivaAIProvider(
  localVivaAIProvider,
  remoteVivaAIProvider
);
export default vivaAIProvider;

