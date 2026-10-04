/**
 * PracPrep Viva Storage Facade
 *
 * Implements a dual-mode storage service that delegates to the FastAPI REST backend
 * (/api/v1/viva/sessions) for authenticated students while preserving zero-latency
 * localStorage persistence for guest students.
 *
 * Architecture:
 * - LocalVivaAdapter: Encapsulates guest and legacy localStorage persistence.
 * - ApiVivaAdapter: Centralizes backend API requests, DTO mapping, and in-memory cache.
 * - ModeResolver: Deterministically selects active storage strategy without circular dependencies.
 * - Dual-Mode Facade: Preserves synchronous contracts for existing React components while
 *   providing full async support and reactive subscription updates.
 */

import type {
  EvaluationVerdict,
  RevisionRecommendation,
  TopicPerformance,
  VivaAnswerRecord,
  VivaDifficulty,
  VivaEvaluation,
  VivaSessionConfig,
  VivaSessionRecord,
  VivaTopic,
} from "../types/viva.ts";
import type { UserSession } from "../types/dashboard.ts";
import { apiClient, tokenManager, ApiError } from "../lib/apiClient.ts";

export type {
  VivaSessionRecord,
  VivaAnswerRecord,
  VivaTopic,
  VivaDifficulty,
  EvaluationVerdict,
  VivaEvaluation,
  VivaSessionConfig,
  TopicPerformance,
  RevisionRecommendation,
};
export { ApiError };

const BASE_VIVA_STORAGE_KEY = "pracprep_viva_sessions";
const VIVA_UPDATE_EVENT = "pracprep_viva_sessions_changed";

export type StorageMode = "authenticated" | "guest" | "local";

export interface ModeResolver {
  resolveMode(user?: UserSession): StorageMode;
}

export interface BackendVivaSessionConfigDTO {
  questionCount: number;
  difficulty: VivaDifficulty;
  focus: VivaTopic;
}

export interface BackendTopicPerformanceResponse {
  topic: string;
  total: number;
  correct: number;
  partiallyCorrect: number;
  incorrect: number;
  averageScore: number;
}

export interface BackendRevisionRecommendationResponse {
  topic: string;
  reason: string;
  suggestedAction: string;
  workspaceTab?: string | null;
}

export interface BackendVivaEvaluationResponse {
  verdict: EvaluationVerdict;
  score: number;
  whatYouGotRight?: string;
  whatWasMissing?: string;
  expectedAnswer?: string;
  improvementTip?: string;
  providerMode?: "demonstration" | "ai-live";
  keyPointsCovered?: string[];
  keyPointsMissed?: string[];
}

export interface BackendVivaAnswerResponse {
  id: string;
  sessionId: string;
  questionId?: string | null;
  questionNumber: number;
  questionText: string;
  topic: string;
  difficulty: string;
  studentAnswer: string;
  score?: number | null;
  verdict?: string | null;
  feedback?: string | null;
  expectedAnswer?: string | null;
  whatYouGotRight?: string | null;
  whatWasMissing?: string | null;
  suggestedImprovement?: string | null;
  keyPointsCovered?: string[];
  keyPointsMissed?: string[];
  evaluation?: BackendVivaEvaluationResponse | null;
  timeSpentSeconds?: number | null;
  createdAt: string;
  timestamp?: number | null;
}

export interface BackendVivaSessionListItemResponse {
  id: string;
  experimentId: string;
  experimentTitle?: string | null;
  subject?: string | null;
  difficulty: string;
  questionCount: number;
  topicFocus: string;
  providerMode: string;
  isCompleted: boolean;
  totalQuestions: number;
  questionsAnswered: number;
  correctCount: number;
  averageScore?: number | null;
  startedAt: string;
  completedAt?: string | null;
  createdAt: string;
}

export interface BackendVivaSessionResponse extends BackendVivaSessionListItemResponse {
  status?: string;
  config?: BackendVivaSessionConfigDTO | null;
  startedAtTimestamp?: number | null;
  completedAtTimestamp?: number | null;
  partiallyCorrectCount?: number;
  incorrectCount?: number;
  topicAnalysis?: Record<string, BackendTopicPerformanceResponse>;
  weakTopics?: string[];
  strongTopics?: string[];
  revisionRecommendations?: BackendRevisionRecommendationResponse[];
  answers?: BackendVivaAnswerResponse[];
  updatedAt?: string;
}

export interface BackendVivaSessionListResponse {
  items: BackendVivaSessionListItemResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ListVivaSessionsOptions {
  page?: number;
  pageSize?: number;
  experimentId?: string;
  status?: "in-progress" | "completed";
  difficulty?: VivaDifficulty;
}

export interface CreateVivaSessionData {
  experimentId: string;
  difficulty?: VivaDifficulty;
  questionCount?: 5 | 10 | 15 | number;
  topicFocus?: VivaTopic;
  focus?: VivaTopic;
  providerMode?: "demonstration" | "ai-live";
}

/**
 * Validates whether a string is a standard UUID format
 */
export function isValidUuid(val: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(val);
}

/**
 * Bidirectional DTO Mapping: Backend Viva Answer DTO -> Frontend VivaAnswerRecord
 */
export function mapBackendAnswerToRecord(dto: BackendVivaAnswerResponse): VivaAnswerRecord {
  const ts =
    typeof dto.timestamp === "number" && !isNaN(dto.timestamp)
      ? dto.timestamp
      : dto.createdAt
        ? new Date(dto.createdAt).getTime()
        : Date.now();

  const evaluation: VivaEvaluation = dto.evaluation
    ? {
        verdict: dto.evaluation.verdict,
        score: dto.evaluation.score,
        whatYouGotRight: dto.evaluation.whatYouGotRight || "",
        whatWasMissing: dto.evaluation.whatWasMissing || "",
        expectedAnswer: dto.evaluation.expectedAnswer || "",
        improvementTip: dto.evaluation.improvementTip || "",
        providerMode: dto.evaluation.providerMode || "demonstration",
      }
    : {
        verdict: (dto.verdict as EvaluationVerdict) || "incorrect",
        score: typeof dto.score === "number" ? dto.score : 0,
        whatYouGotRight: dto.whatYouGotRight || "",
        whatWasMissing: dto.whatWasMissing || "",
        expectedAnswer: dto.expectedAnswer || "",
        improvementTip: dto.suggestedImprovement || dto.feedback || "",
        providerMode: "demonstration",
      };

  const validTopics: VivaTopic[] = [
    "theory",
    "procedure",
    "apparatus",
    "observations",
    "precautions",
    "mixed",
  ];
  const topic: VivaTopic = validTopics.includes(dto.topic as VivaTopic)
    ? (dto.topic as VivaTopic)
    : "mixed";

  const validDiffs: ("beginner" | "intermediate" | "advanced")[] = [
    "beginner",
    "intermediate",
    "advanced",
  ];
  const difficulty = validDiffs.includes(dto.difficulty as "beginner" | "intermediate" | "advanced")
    ? (dto.difficulty as "beginner" | "intermediate" | "advanced")
    : "intermediate";

  return {
    questionId: dto.questionId || `q-${dto.questionNumber}`,
    questionNumber: dto.questionNumber,
    questionText: dto.questionText,
    topic,
    difficulty,
    studentAnswer: dto.studentAnswer,
    evaluation,
    timestamp: ts,
  };
}

/**
 * Bidirectional DTO Mapping: Backend Viva Session DTO -> Frontend VivaSessionRecord
 */
export function mapBackendVivaSessionToRecord(
  dto: BackendVivaSessionResponse | BackendVivaSessionListItemResponse,
  existing?: VivaSessionRecord
): VivaSessionRecord {
  const detail = dto as BackendVivaSessionResponse;

  let startedAtMs = detail.startedAtTimestamp;
  if (!startedAtMs && dto.startedAt) {
    const parsed = new Date(dto.startedAt).getTime();
    if (!isNaN(parsed)) startedAtMs = parsed;
  }
  if (!startedAtMs) {
    startedAtMs = existing?.startedAt || Date.now();
  }

  let completedAtMs = detail.completedAtTimestamp;
  if (!completedAtMs && dto.completedAt) {
    const parsed = new Date(dto.completedAt).getTime();
    if (!isNaN(parsed)) completedAtMs = parsed;
  }
  if (!completedAtMs && existing?.completedAt) {
    completedAtMs = existing.completedAt;
  }

  const validDiffs: VivaDifficulty[] = ["beginner", "intermediate", "advanced", "mixed"];
  const difficulty: VivaDifficulty = validDiffs.includes(dto.difficulty as VivaDifficulty)
    ? (dto.difficulty as VivaDifficulty)
    : "intermediate";

  const validTopics: VivaTopic[] = [
    "theory",
    "procedure",
    "apparatus",
    "observations",
    "precautions",
    "mixed",
  ];
  const topicFocus: VivaTopic = validTopics.includes(dto.topicFocus as VivaTopic)
    ? (dto.topicFocus as VivaTopic)
    : "mixed";

  const config: VivaSessionConfig = detail.config
    ? {
        questionCount: (detail.config.questionCount as 5 | 10 | 15) || 5,
        difficulty: detail.config.difficulty || difficulty,
        focus: detail.config.focus || topicFocus,
      }
    : existing?.config || {
        questionCount: (dto.questionCount as 5 | 10 | 15) || 5,
        difficulty,
        focus: topicFocus,
      };

  // Map answers if present in detail, else preserve existing answers
  const rawAnswers = detail.answers
    ? detail.answers.map(mapBackendAnswerToRecord)
    : existing?.answers || [];

  // Sort answers strictly by questionNumber chronologically
  const answers = [...rawAnswers].sort((a, b) => a.questionNumber - b.questionNumber);

  const topicAnalysis: Record<string, TopicPerformance> = {};
  if (detail.topicAnalysis) {
    for (const [k, v] of Object.entries(detail.topicAnalysis)) {
      topicAnalysis[k] = {
        topic: v.topic,
        total: v.total,
        correct: v.correct,
        partiallyCorrect: v.partiallyCorrect,
        incorrect: v.incorrect,
        averageScore: v.averageScore,
      };
    }
  } else if (existing?.topicAnalysis) {
    Object.assign(topicAnalysis, existing.topicAnalysis);
  }

  const revisionRecommendations: RevisionRecommendation[] = detail.revisionRecommendations
    ? detail.revisionRecommendations.map((r) => ({
        topic: r.topic,
        reason: r.reason,
        suggestedAction: r.suggestedAction,
        workspaceTab: (r.workspaceTab as RevisionRecommendation["workspaceTab"]) || undefined,
      }))
    : existing?.revisionRecommendations || [];

  return {
    id: String(dto.id),
    experimentId: String(dto.experimentId),
    experimentTitle: String(dto.experimentTitle || existing?.experimentTitle || ""),
    subject: String(dto.subject || existing?.subject || ""),
    config,
    startedAt: startedAtMs,
    completedAt: completedAtMs || undefined,
    isCompleted: Boolean(dto.isCompleted),
    answers,
    totalQuestions: dto.totalQuestions,
    questionsAnswered: dto.questionsAnswered,
    correctCount: dto.correctCount,
    partiallyCorrectCount: detail.partiallyCorrectCount ?? (existing?.partiallyCorrectCount ?? 0),
    incorrectCount: detail.incorrectCount ?? (existing?.incorrectCount ?? 0),
    averageScore: dto.averageScore ?? (existing?.averageScore ?? 0),
    topicAnalysis,
    weakTopics: detail.weakTopics || existing?.weakTopics || [],
    strongTopics: detail.strongTopics || existing?.strongTopics || [],
    revisionRecommendations,
    providerMode: dto.providerMode === "ai-live" ? "ai-live" : "demonstration",
  };
}

/**
 * Bidirectional DTO Mapping: Frontend Session Creation Data -> Backend DTO
 */
export function mapRecordToCreateSessionDto(
  data: CreateVivaSessionData
): Record<string, unknown> {
  const focus = data.topicFocus || data.focus || "mixed";
  return {
    experiment_id: data.experimentId,
    difficulty: data.difficulty || "intermediate",
    question_count: data.questionCount || 5,
    topic_focus: focus,
    provider_mode: data.providerMode || "demonstration",
  };
}

/**
 * Dispatch reactive update notification to all subscribers in the current window.
 */
function notifyVivaUpdate(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(VIVA_UPDATE_EVENT));
  }
}

/**
 * Default Mode Resolver
 */
export const defaultModeResolver: ModeResolver = {
  resolveMode(user?: UserSession): StorageMode {
    if (user?.isGuest) {
      return "guest";
    }

    if (user && !user.isGuest && tokenManager.hasAccessToken()) {
      return "authenticated";
    }

    if (user && !user.isGuest && !tokenManager.hasAccessToken()) {
      return "local";
    }

    if (typeof window !== "undefined") {
      try {
        const stored = window.localStorage.getItem("pracprep_user");
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed && !parsed.isGuest && tokenManager.hasAccessToken()) {
            return "authenticated";
          }
        }
      } catch {
        // Safe fallback
      }
    }

    return "guest";
  },
};

let activeModeResolver: ModeResolver = defaultModeResolver;

/**
 * Local Viva Adapter: Preserves 100% of existing localStorage behavior for guest mode and offline local mode.
 */
export const localVivaAdapter = {
  getScopedStorageKey(user?: UserSession): string {
    if (user && !user.isGuest && user.email) {
      const safeEmail = user.email.toLowerCase().replace(/[^a-z0-9]/g, "_");
      return `${BASE_VIVA_STORAGE_KEY}_user_${safeEmail}`;
    }
    return `${BASE_VIVA_STORAGE_KEY}_guest`;
  },

  getSessions(user?: UserSession): VivaSessionRecord[] {
    if (typeof window === "undefined") return [];
    try {
      const key = this.getScopedStorageKey(user);
      let stored = localStorage.getItem(key);
      if (!stored && (!user || user.isGuest)) {
        stored = localStorage.getItem(BASE_VIVA_STORAGE_KEY);
      }
      if (!stored) return [];
      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) return [];
      return parsed;
    } catch {
      return [];
    }
  },

  getSessionsByExperiment(experimentId: string, user?: UserSession): VivaSessionRecord[] {
    const all = this.getSessions(user);
    return all.filter((s) => s.experimentId === experimentId);
  },

  getSessionById(sessionId: string, user?: UserSession): VivaSessionRecord | null {
    const all = this.getSessions(user);
    return all.find((s) => s.id === sessionId) || null;
  },

  saveSession(session: VivaSessionRecord, user?: UserSession): VivaSessionRecord {
    if (typeof window !== "undefined") {
      try {
        const key = this.getScopedStorageKey(user);
        const existing = this.getSessions(user);
        const filtered = existing.filter((s) => s.id !== session.id);
        const updated = [session, ...filtered];
        localStorage.setItem(key, JSON.stringify(updated));
        if (!user || user.isGuest) {
          localStorage.setItem(BASE_VIVA_STORAGE_KEY, JSON.stringify(updated));
        }
        notifyVivaUpdate();
      } catch (err) {
        console.error("Failed to save viva session locally:", err);
      }
    }
    return session;
  },

  deleteSession(sessionId: string, user?: UserSession): boolean {
    if (typeof window === "undefined") return false;
    try {
      const key = this.getScopedStorageKey(user);
      const existing = this.getSessions(user);
      const updated = existing.filter((s) => s.id !== sessionId);
      if (updated.length === existing.length) return false;
      localStorage.setItem(key, JSON.stringify(updated));
      if (!user || user.isGuest) {
        localStorage.setItem(BASE_VIVA_STORAGE_KEY, JSON.stringify(updated));
      }
      notifyVivaUpdate();
      return true;
    } catch {
      return false;
    }
  },

  clearSessions(user?: UserSession): boolean {
    if (typeof window === "undefined") return false;
    try {
      const key = this.getScopedStorageKey(user);
      localStorage.removeItem(key);
      if (!user || user.isGuest) {
        localStorage.removeItem(BASE_VIVA_STORAGE_KEY);
      }
      notifyVivaUpdate();
      return true;
    } catch {
      return false;
    }
  },
};

/**
 * Remote API Adapter: Implements backend viva REST communication (/api/v1/viva/sessions)
 */
const authenticatedCache = new Map<string, VivaSessionRecord[]>();
let inFlightFetchPromise: Promise<VivaSessionRecord[]> | null = null;

function getAuthCacheKey(user?: UserSession): string {
  if (user?.email) {
    return user.email.toLowerCase().trim();
  }
  return "__active_auth_user__";
}

export const apiVivaAdapter = {
  getCachedSessions(user?: UserSession): VivaSessionRecord[] {
    const key = getAuthCacheKey(user);
    return authenticatedCache.get(key) || [];
  },

  setCachedSessions(user: UserSession | undefined, list: VivaSessionRecord[]): void {
    const key = getAuthCacheKey(user);
    authenticatedCache.set(key, list);
  },

  clearCache(): void {
    authenticatedCache.clear();
    inFlightFetchPromise = null;
  },

  async fetchSessions(
    user?: UserSession,
    options?: ListVivaSessionsOptions
  ): Promise<VivaSessionRecord[]> {
    const isDefaultQuery = !options || Object.keys(options).length === 0;
    if (isDefaultQuery && inFlightFetchPromise) {
      return inFlightFetchPromise;
    }

    const fetchTask = (async () => {
      // If experimentId is given but invalid as UUID, no backend records can match
      if (options?.experimentId && !isValidUuid(options.experimentId)) {
        return [];
      }

      const params: Record<string, string | number> = {};
      if (options?.page) params.page = options.page;
      if (options?.pageSize) params.pageSize = options.pageSize;
      if (options?.experimentId) params.experimentId = options.experimentId;
      if (options?.status) params.status = options.status;
      if (options?.difficulty) params.difficulty = options.difficulty;

      const response = await apiClient.get<BackendVivaSessionListResponse>("/viva/sessions", {
        params,
        requiresAuth: true,
      });

      const currentCached = this.getCachedSessions(user);
      const existingMap = new Map(currentCached.map((s) => [s.id, s]));

      const mappedList: VivaSessionRecord[] = (response.items || []).map((item) => {
        return mapBackendVivaSessionToRecord(item, existingMap.get(String(item.id)));
      });

      if (isDefaultQuery) {
        this.setCachedSessions(user, mappedList);
      }
      notifyVivaUpdate();
      return mappedList;
    })();

    if (isDefaultQuery) {
      inFlightFetchPromise = fetchTask;
      fetchTask.finally(() => {
        inFlightFetchPromise = null;
      });
    }

    return fetchTask;
  },

  async fetchSessionsByExperiment(
    experimentId: string,
    user?: UserSession
  ): Promise<VivaSessionRecord[]> {
    if (!isValidUuid(experimentId)) {
      const cached = this.getCachedSessions(user);
      return cached.filter((s) => s.experimentId === experimentId);
    }

    return this.fetchSessions(user, { experimentId });
  },

  async getSessionById(sessionId: string, user?: UserSession): Promise<VivaSessionRecord | null> {
    try {
      const response = await apiClient.get<BackendVivaSessionResponse>(
        `/viva/sessions/${sessionId}`,
        {
          requiresAuth: true,
        }
      );

      const currentCached = this.getCachedSessions(user);
      const existing = currentCached.find((s) => s.id === sessionId);
      const record = mapBackendVivaSessionToRecord(response, existing);

      const updatedList = currentCached.some((s) => s.id === sessionId)
        ? currentCached.map((s) => (s.id === sessionId ? record : s))
        : [record, ...currentCached];
      this.setCachedSessions(user, updatedList);
      notifyVivaUpdate();

      return record;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        return null;
      }
      throw err;
    }
  },

  async createSession(
    data: CreateVivaSessionData,
    user?: UserSession
  ): Promise<VivaSessionRecord> {
    const payload = mapRecordToCreateSessionDto(data);
    const response = await apiClient.post<BackendVivaSessionResponse>("/viva/sessions", payload, {
      requiresAuth: true,
    });

    const record = mapBackendVivaSessionToRecord(response);
    const currentCached = this.getCachedSessions(user);
    this.setCachedSessions(user, [record, ...currentCached.filter((s) => s.id !== record.id)]);
    notifyVivaUpdate();

    return record;
  },

  async deleteSession(sessionId: string, user?: UserSession): Promise<boolean> {
    try {
      await apiClient.delete(`/viva/sessions/${sessionId}`, {
        requiresAuth: true,
      });

      const currentCached = this.getCachedSessions(user);
      this.setCachedSessions(
        user,
        currentCached.filter((s) => s.id !== sessionId)
      );
      notifyVivaUpdate();

      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        return false;
      }
      throw err;
    }
  },
};

/**
 * Creates an array that also implements PromiseLike so synchronous callers receive
 * an immediate array while async/await consumers receive the resolved network list.
 */
function createThenableArray<T>(initial: T[], promise: Promise<T[]>): T[] & PromiseLike<T[]> {
  promise.catch(() => {});
  return Object.assign([...initial], {
    then: promise.then.bind(promise),
  });
}

/**
 * Creates an object that also implements PromiseLike for seamless sync + async consumption.
 */
function createThenableRecord<T extends object, P = T>(
  initial: T,
  promise: Promise<P>
): T & PromiseLike<P> {
  promise.catch(() => {});
  return Object.assign(initial, {
    then: promise.then.bind(promise),
  });
}

/**
 * Dual-Mode Viva Storage Facade
 */
export const vivaStorage = {
  // Mode selection & dependency injection
  resolveMode(user?: UserSession): StorageMode {
    return activeModeResolver.resolveMode(user);
  },

  setModeResolver(resolver: ModeResolver): void {
    activeModeResolver = resolver;
  },

  resetModeResolver(): void {
    activeModeResolver = defaultModeResolver;
  },

  getModeResolver(): ModeResolver {
    return activeModeResolver;
  },

  clearCache(): void {
    apiVivaAdapter.clearCache();
  },

  /**
   * Retrieve all viva session records for the current user or guest.
   * Authenticated: returns cached records immediately & thenable fetching from API.
   * Guest / Local: reads localStorage synchronously.
   */
  getSessions(user?: UserSession): VivaSessionRecord[] {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.getSessions(user);
    }

    const cached = apiVivaAdapter.getCachedSessions(user);
    const promise = apiVivaAdapter.fetchSessions(user);
    return createThenableArray(cached, promise);
  },

  /**
   * Explicit async retrieval with pagination and filtering.
   */
  async getSessionsAsync(
    user?: UserSession,
    options?: ListVivaSessionsOptions
  ): Promise<VivaSessionRecord[]> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      let list = localVivaAdapter.getSessions(user);
      if (options?.experimentId) {
        list = list.filter((s) => s.experimentId === options.experimentId);
      }
      if (options?.status) {
        list = list.filter((s) =>
          options.status === "completed" ? s.isCompleted : !s.isCompleted
        );
      }
      if (options?.difficulty) {
        list = list.filter((s) => s.config?.difficulty === options.difficulty);
      }
      if (options?.page && options?.pageSize) {
        const start = (options.page - 1) * options.pageSize;
        list = list.slice(start, start + options.pageSize);
      }
      return list;
    }

    return apiVivaAdapter.fetchSessions(user, options);
  },

  /**
   * Alias for getSessionsAsync.
   */
  async fetchSessions(
    user?: UserSession,
    options?: ListVivaSessionsOptions
  ): Promise<VivaSessionRecord[]> {
    return this.getSessionsAsync(user, options);
  },

  /**
   * Get sessions filtered for a specific experiment.
   */
  getSessionsByExperiment(experimentId: string, user?: UserSession): VivaSessionRecord[] {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.getSessionsByExperiment(experimentId, user);
    }

    const currentCached = apiVivaAdapter.getCachedSessions(user);
    const filteredCached = currentCached.filter((s) => s.experimentId === experimentId);
    const promise = apiVivaAdapter.fetchSessionsByExperiment(experimentId, user);
    return createThenableArray(filteredCached, promise);
  },

  /**
   * Explicit async session retrieval by experiment.
   */
  async getSessionsByExperimentAsync(
    experimentId: string,
    user?: UserSession
  ): Promise<VivaSessionRecord[]> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.getSessionsByExperiment(experimentId, user);
    }
    return apiVivaAdapter.fetchSessionsByExperiment(experimentId, user);
  },

  /**
   * Get a specific session by its unique ID.
   */
  getSessionById(sessionId: string, user?: UserSession): VivaSessionRecord | null {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.getSessionById(sessionId, user);
    }

    const cachedList = apiVivaAdapter.getCachedSessions(user);
    const cached = cachedList.find((s) => s.id === sessionId);
    const promise = apiVivaAdapter.getSessionById(sessionId, user);

    if (cached) {
      return createThenableRecord(cached, promise);
    }

    const placeholder: VivaSessionRecord = {
      id: sessionId,
      experimentId: "",
      experimentTitle: "",
      subject: "",
      config: { questionCount: 5, difficulty: "intermediate", focus: "mixed" },
      startedAt: 0,
      isCompleted: false,
      answers: [],
      totalQuestions: 5,
      questionsAnswered: 0,
      correctCount: 0,
      partiallyCorrectCount: 0,
      incorrectCount: 0,
      averageScore: 0,
      topicAnalysis: {},
      weakTopics: [],
      strongTopics: [],
      revisionRecommendations: [],
      providerMode: "demonstration",
    };
    return createThenableRecord(placeholder, promise);
  },

  /**
   * Explicit async session retrieval by ID.
   */
  async getSessionByIdAsync(
    sessionId: string,
    user?: UserSession
  ): Promise<VivaSessionRecord | null> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.getSessionById(sessionId, user);
    }
    return apiVivaAdapter.getSessionById(sessionId, user);
  },

  /**
   * Create and initiate a new viva practice session.
   * Authenticated: calls POST /api/v1/viva/sessions.
   * Guest: creates and saves record locally.
   */
  createSession(
    data: CreateVivaSessionData,
    user?: UserSession
  ): VivaSessionRecord & PromiseLike<VivaSessionRecord> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      const now = Date.now();
      const config: VivaSessionConfig = {
        questionCount: (data.questionCount as 5 | 10 | 15) || 5,
        difficulty: data.difficulty || "intermediate",
        focus: data.topicFocus || data.focus || "mixed",
      };
      const newSession: VivaSessionRecord = {
        id: `viva-${now}`,
        experimentId: data.experimentId,
        experimentTitle: "",
        subject: "",
        config,
        startedAt: now,
        isCompleted: false,
        answers: [],
        totalQuestions: config.questionCount,
        questionsAnswered: 0,
        correctCount: 0,
        partiallyCorrectCount: 0,
        incorrectCount: 0,
        averageScore: 0,
        topicAnalysis: {},
        weakTopics: [],
        strongTopics: [],
        revisionRecommendations: [],
        providerMode: data.providerMode || "demonstration",
      };
      const saved = localVivaAdapter.saveSession(newSession, user);
      return createThenableRecord(saved, Promise.resolve(saved));
    }

    const now = Date.now();
    const optimistic: VivaSessionRecord = {
      id: `temp-${now}`,
      experimentId: data.experimentId,
      experimentTitle: "",
      subject: "",
      config: {
        questionCount: (data.questionCount as 5 | 10 | 15) || 5,
        difficulty: data.difficulty || "intermediate",
        focus: data.topicFocus || data.focus || "mixed",
      },
      startedAt: now,
      isCompleted: false,
      answers: [],
      totalQuestions: data.questionCount || 5,
      questionsAnswered: 0,
      correctCount: 0,
      partiallyCorrectCount: 0,
      incorrectCount: 0,
      averageScore: 0,
      topicAnalysis: {},
      weakTopics: [],
      strongTopics: [],
      revisionRecommendations: [],
      providerMode: data.providerMode || "demonstration",
    };

    const promise = apiVivaAdapter.createSession(data, user);
    return createThenableRecord(optimistic, promise);
  },

  /**
   * Explicit async session creation.
   */
  async createSessionAsync(
    data: CreateVivaSessionData,
    user?: UserSession
  ): Promise<VivaSessionRecord> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      const now = Date.now();
      const config: VivaSessionConfig = {
        questionCount: (data.questionCount as 5 | 10 | 15) || 5,
        difficulty: data.difficulty || "intermediate",
        focus: data.topicFocus || data.focus || "mixed",
      };
      const newSession: VivaSessionRecord = {
        id: `viva-${now}`,
        experimentId: data.experimentId,
        experimentTitle: "",
        subject: "",
        config,
        startedAt: now,
        isCompleted: false,
        answers: [],
        totalQuestions: config.questionCount,
        questionsAnswered: 0,
        correctCount: 0,
        partiallyCorrectCount: 0,
        incorrectCount: 0,
        averageScore: 0,
        topicAnalysis: {},
        weakTopics: [],
        strongTopics: [],
        revisionRecommendations: [],
        providerMode: data.providerMode || "demonstration",
      };
      return localVivaAdapter.saveSession(newSession, user);
    }

    return apiVivaAdapter.createSession(data, user);
  },

  /**
   * Save a newly completed or updated session record.
   * Guest: saves to localStorage.
   * Authenticated: updates in-memory cache and dispatches notification.
   */
  saveSession(session: VivaSessionRecord, user?: UserSession): VivaSessionRecord {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.saveSession(session, user);
    }

    // In authenticated mode, update the active user's in-memory cache
    const currentCached = apiVivaAdapter.getCachedSessions(user);
    const filtered = currentCached.filter((s) => s.id !== session.id);
    const updated = [session, ...filtered];
    apiVivaAdapter.setCachedSessions(user, updated);
    notifyVivaUpdate();

    return session;
  },

  /**
   * Explicit async session save.
   */
  async saveSessionAsync(
    session: VivaSessionRecord,
    user?: UserSession
  ): Promise<VivaSessionRecord> {
    return this.saveSession(session, user);
  },

  /**
   * Delete a session record.
   */
  deleteSession(sessionId: string, user?: UserSession): boolean {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.deleteSession(sessionId, user);
    }

    const currentCached = apiVivaAdapter.getCachedSessions(user);
    apiVivaAdapter.setCachedSessions(
      user,
      currentCached.filter((s) => s.id !== sessionId)
    );
    notifyVivaUpdate();

    apiVivaAdapter.deleteSession(sessionId, user).catch((err) => {
      console.error("Failed to delete viva session from backend:", err);
    });
    return true;
  },

  /**
   * Explicit async session deletion.
   */
  async deleteSessionAsync(sessionId: string, user?: UserSession): Promise<boolean> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.deleteSession(sessionId, user);
    }
    return apiVivaAdapter.deleteSession(sessionId, user);
  },

  /**
   * Clear all viva session records for the active user or guest session.
   */
  clearSessions(user?: UserSession): boolean {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localVivaAdapter.clearSessions(user);
    }

    apiVivaAdapter.setCachedSessions(user, []);
    notifyVivaUpdate();
    return true;
  },

  /**
   * Reactive subscription for viva session changes (custom event & storage event for cross-tab sync).
   */
  subscribe(callback: () => void): () => void {
    if (typeof window === "undefined") return () => {};
    const handleEvent = () => callback();
    const handleStorage = (e: StorageEvent) => {
      if (e.key?.startsWith(BASE_VIVA_STORAGE_KEY)) {
        callback();
      }
    };
    window.addEventListener(VIVA_UPDATE_EVENT, handleEvent);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener(VIVA_UPDATE_EVENT, handleEvent);
      window.removeEventListener("storage", handleStorage);
    };
  },
};

export default vivaStorage;
