/**
 * PracPrep Guest Data Migration Service
 *
 * Coordinates detection, payload generation, batch API submission,
 * and state reconciliation when a student transitions from guest mode
 * to an authenticated account.
 *
 * Data Safety Guarantees:
 * - Guest data is NEVER cleared before confirmed 200 OK from server.
 * - Idempotency key prevents duplicates on retries, refreshes, or network glitches.
 * - Local guest storage is kept isolated from authenticated storage keys.
 * - On failure, guest data is preserved for safe retry.
 */

import { apiClient, ApiError } from "../lib/apiClient.ts";
import { experimentStorage } from "./experimentStorage.ts";
import { vivaStorage } from "./vivaStorage.ts";
import type { ExperimentRecord } from "../types/experiment.ts";
import type { VivaSessionRecord } from "../types/viva.ts";

export { ApiError };

export interface GuestDataSummary {
  experimentCount: number;
  vivaSessionCount: number;
  hasData: boolean;
}

export interface GuestDataMigrationResponseDTO {
  message: string;
  idempotencyKey: string;
  isIdempotentReplay: boolean;
  experimentsMigrated: number;
  vivaSessionsMigrated: number;
  vivaAnswersMigrated: number;
  migratedAt: string;
}

const GUEST_EXPERIMENTS_KEY = "pracprep_experiments_guest";
const LEGACY_EXPERIMENTS_KEY = "pracprep_experiments";
const GUEST_VIVA_KEY = "pracprep_viva_sessions_guest";
const LEGACY_VIVA_KEY = "pracprep_viva_sessions";

function generateMigrationId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `mig-${crypto.randomUUID()}`;
  }
  return `mig-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
}

/**
 * Safely parse a JSON array from localStorage.
 */
function readArrayFromStorage<T>(key: string): T[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export const migrationService = {
  /**
   * Read all available guest experiments.
   */
  getGuestExperiments(): ExperimentRecord[] {
    const primary = readArrayFromStorage<ExperimentRecord>(GUEST_EXPERIMENTS_KEY);
    if (primary.length > 0) return primary;
    return readArrayFromStorage<ExperimentRecord>(LEGACY_EXPERIMENTS_KEY);
  },

  /**
   * Read all available guest viva examination sessions.
   */
  getGuestVivaSessions(): VivaSessionRecord[] {
    const primary = readArrayFromStorage<VivaSessionRecord>(GUEST_VIVA_KEY);
    if (primary.length > 0) return primary;
    return readArrayFromStorage<VivaSessionRecord>(LEGACY_VIVA_KEY);
  },

  /**
   * Determine whether the client currently holds guest data eligible for account migration.
   */
  checkHasGuestData(): boolean {
    const experiments = this.getGuestExperiments();
    const vivaSessions = this.getGuestVivaSessions();
    return experiments.length > 0 || vivaSessions.length > 0;
  },

  /**
   * Summary of guest data for display in user prompts.
   */
  getGuestDataSummary(): GuestDataSummary {
    const experiments = this.getGuestExperiments();
    const vivaSessions = this.getGuestVivaSessions();
    return {
      experimentCount: experiments.length,
      vivaSessionCount: vivaSessions.length,
      hasData: experiments.length > 0 || vivaSessions.length > 0,
    };
  },

  /**
   * Formats local storage records into the typed migration payload matching
   * POST /api/v1/users/me/migrate-guest-data.
   */
  prepareMigrationPayload(idempotencyKey?: string) {
    const key = idempotencyKey || generateMigrationId();
    const experiments = this.getGuestExperiments();
    const vivaSessions = this.getGuestVivaSessions();

    const formattedExperiments = experiments.map((exp) => ({
      clientId: exp.id,
      title: exp.title,
      subject: exp.subject,
      experimentNumber: exp.experimentNumber,
      courseSemester: exp.courseSemester,
      creationMethod: exp.method === "upload" ? "upload" : "manual",
      status: exp.status || "ready",
      description: exp.description,
      objective: exp.objective,
      theory: exp.theory,
      apparatus: exp.apparatus,
      procedure: exp.procedure,
      observations: exp.observations,
      calculations: exp.calculations,
      precautions: exp.precautions,
      preparationChecklist: exp.preparationChecklist,
      createdAtTimestamp: exp.createdAtTimestamp || Date.now(),
      updatedAtTimestamp: exp.updatedAtTimestamp || Date.now(),
    }));

    const formattedVivaSessions = vivaSessions.map((sess) => ({
      clientId: sess.id || generateMigrationId(),
      clientExperimentId: sess.experimentId,
      difficulty: sess.config?.difficulty || "intermediate",
      questionCount: sess.config?.questionCount || 5,
      topicFocus: sess.config?.focus || "mixed",
      providerMode: sess.providerMode || "demonstration",
      isCompleted: Boolean(sess.isCompleted),
      startedAt: sess.startedAt,
      completedAt: sess.completedAt,
      averageScore: sess.averageScore,
      totalQuestions: sess.totalQuestions || 5,
      questionsAnswered: sess.questionsAnswered || 0,
      correctCount: sess.correctCount || 0,
      partiallyCorrectCount: sess.partiallyCorrectCount || 0,
      incorrectCount: sess.incorrectCount || 0,
      topicAnalysis: sess.topicAnalysis || {},
      weakTopics: sess.weakTopics || [],
      strongTopics: sess.strongTopics || [],
      revisionRecommendations: sess.revisionRecommendations || [],
      answers: (sess.answers || []).map((ans) => ({
        questionId: ans.questionId,
        questionNumber: ans.questionNumber || 1,
        topic: ans.topic || "theory",
        difficulty: ans.difficulty || "intermediate",
        questionText: ans.questionText,
        studentAnswer: ans.studentAnswer,
        score: ans.evaluation?.score,
        verdict: ans.evaluation?.verdict,
        whatYouGotRight: ans.evaluation?.whatYouGotRight,
        whatWasMissing: ans.evaluation?.whatWasMissing,
        expectedAnswer: ans.evaluation?.expectedAnswer,
        suggestedImprovement: ans.evaluation?.improvementTip,
        keyPointsCovered: ans.evaluation?.keyPointsCovered || [],
        keyPointsMissed: ans.evaluation?.keyPointsMissed || [],
        evaluationData: ans.evaluation || {},
        createdAt: ans.timestamp ? new Date(ans.timestamp).toISOString() : undefined,
      })),
    }));

    return {
      idempotencyKey: key,
      experiments: formattedExperiments,
      vivaSessions: formattedVivaSessions,
    };
  },

  /**
   * Submit guest data to the backend migration endpoint.
   *
   * Crucial safety guarantee:
   * Local guest storage is cleared ONLY after the server returns confirmed 200 OK.
   */
  async migrateGuestData(idempotencyKey?: string | unknown): Promise<GuestDataMigrationResponseDTO> {
    const key = typeof idempotencyKey === "string" ? idempotencyKey : undefined;
    const payload = this.prepareMigrationPayload(key);

    const response = await apiClient.post<GuestDataMigrationResponseDTO>(
      "/users/me/migrate-guest-data",
      payload,
      { requiresAuth: true }
    );

    // Cleared ONLY on confirmed success
    this.clearGuestStorage();

    // Reconcile caches and notify active listeners
    experimentStorage.clearCache();
    vivaStorage.clearCache();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("pracprep_experiments_changed"));
      window.dispatchEvent(new CustomEvent("pracprep_viva_sessions_changed"));
    }

    return response;
  },

  /**
   * Remove guest storage keys from this browser.
   */
  clearGuestStorage(): void {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.removeItem(GUEST_EXPERIMENTS_KEY);
      window.localStorage.removeItem(LEGACY_EXPERIMENTS_KEY);
      window.localStorage.removeItem(GUEST_VIVA_KEY);
      window.localStorage.removeItem(LEGACY_VIVA_KEY);
    } catch {
      // Safe fallback
    }
  },

  /**
   * Explicit user choice to discard guest records without transferring.
   */
  discardGuestData(): void {
    this.clearGuestStorage();
    experimentStorage.clearCache();
    vivaStorage.clearCache();
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("pracprep_experiments_changed"));
      window.dispatchEvent(new CustomEvent("pracprep_viva_sessions_changed"));
    }
  },
};
