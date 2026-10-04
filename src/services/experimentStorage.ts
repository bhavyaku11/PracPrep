/**
 * PracPrep Experiment Storage Facade
 *
 * Implements a dual-mode storage service that delegates to the FastAPI REST backend
 * (/api/v1/experiments) for authenticated students while preserving zero-latency
 * localStorage persistence for guest students.
 *
 * Architecture:
 * - LocalExperimentAdapter: Encapsulates guest and legacy localStorage persistence.
 * - ApiExperimentAdapter: Centralizes backend API requests, DTO mapping, and in-memory cache.
 * - ModeResolver: Deterministically selects active storage strategy without circular dependencies.
 * - Dual-Mode Facade: Preserves synchronous contracts for existing React components while
 *   providing full async support and reactive subscription updates.
 */

import type {
  CreationMethod,
  ExperimentRecord,
  ExperimentStatus,
} from "../types/experiment.ts";
import type { UserSession } from "../types/dashboard.ts";
import { apiClient, tokenManager, ApiError } from "../lib/apiClient.ts";

export type { ExperimentRecord, ExperimentStatus, CreationMethod };
export { ApiError };

const BASE_STORAGE_KEY = "pracprep_experiments";
const UPDATE_EVENT_NAME = "pracprep_experiments_changed";

export type StorageMode = "authenticated" | "guest" | "local";

export interface ModeResolver {
  resolveMode(user?: UserSession): StorageMode;
}

export interface BackendPreparationChecklistResponse {
  id: string;
  experimentId: string;
  items: Record<string, boolean>;
  createdAt: string;
  updatedAt: string;
}

export interface BackendExperimentListItemResponse {
  id: string;
  title: string;
  subject: string;
  experimentNumber?: string | null;
  courseSemester?: string | null;
  creationMethod: string;
  hasManualFile: boolean;
  fileName?: string | null;
  status: string;
  createdAt: string;
  updatedAt: string;
}

export interface BackendExperimentResponse extends BackendExperimentListItemResponse {
  description?: string | null;
  objective?: string | null;
  theory?: string | null;
  apparatus?: string | null;
  procedure?: string | null;
  observations?: string | null;
  calculations?: string | null;
  precautions?: string | null;
  checklist?: BackendPreparationChecklistResponse | null;
  preparationChecklist?: Record<string, boolean> | null;
  vivaQuestionsCount: number;
}

export interface BackendExperimentListResponse {
  items: BackendExperimentListItemResponse[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ListExperimentsOptions {
  page?: number;
  pageSize?: number;
  subject?: string;
  status?: string;
  search?: string;
}

/**
 * Format a timestamp into a friendly date string: e.g. "Oct 3, 2026"
 */
export function formatDate(timestampOrDate: number | string | Date): string {
  const d = new Date(timestampOrDate);
  if (isNaN(d.getTime())) {
    return typeof timestampOrDate === "string" ? timestampOrDate : "Recently";
  }
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

/**
 * Format relative or short timestamp for Last Updated
 */
export function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diffMinutes = Math.floor((now - timestamp) / (1000 * 60));

  if (diffMinutes < 1) return "Just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;

  return formatDate(timestamp);
}

/**
 * Normalizes a raw object from localStorage into a complete ExperimentRecord
 */
export function normalizeRecord(raw: any): ExperimentRecord {
  const now = Date.now();

  let parsedTimestamp = now;
  if (typeof raw.createdAtTimestamp === "number" && !isNaN(raw.createdAtTimestamp)) {
    parsedTimestamp = raw.createdAtTimestamp;
  } else if (typeof raw.id === "string" && raw.id.startsWith("exp-")) {
    const idNum = parseInt(raw.id.replace("exp-", ""), 10);
    if (!isNaN(idNum) && idNum > 1000000000000) {
      parsedTimestamp = idNum;
    }
  }

  const updatedTimestamp =
    typeof raw.updatedAtTimestamp === "number" && !isNaN(raw.updatedAtTimestamp)
      ? raw.updatedAtTimestamp
      : parsedTimestamp;

  const validStatuses: ExperimentStatus[] = [
    "draft",
    "in-progress",
    "completed",
    "ready",
    "analyzing",
  ];
  const status: ExperimentStatus = validStatuses.includes(raw.status)
    ? raw.status
    : "ready";

  return {
    id: String(raw.id || `exp-${now}`),
    title: String(raw.title || "Untitled Experiment").trim(),
    subject: String(raw.subject || "General Science").trim(),
    experimentNumber: raw.experimentNumber ? String(raw.experimentNumber).trim() : undefined,
    courseSemester: raw.courseSemester ? String(raw.courseSemester).trim() : undefined,
    method: raw.method === "manual" ? "manual" : "upload",
    hasManualFile: Boolean(raw.hasManualFile || raw.fileName),
    fileName: raw.fileName ? String(raw.fileName) : undefined,
    createdAt: raw.createdAt ? String(raw.createdAt) : formatDate(parsedTimestamp),
    createdAtTimestamp: parsedTimestamp,
    updatedAt: raw.updatedAt ? String(raw.updatedAt) : formatRelativeTime(updatedTimestamp),
    updatedAtTimestamp: updatedTimestamp,
    status,
    vivaQuestionsCount:
      typeof raw.vivaQuestionsCount === "number" ? raw.vivaQuestionsCount : 0,
    description: raw.description ? String(raw.description) : undefined,
    objective: raw.objective ? String(raw.objective) : undefined,
    theory: raw.theory ? String(raw.theory) : undefined,
    apparatus: raw.apparatus ? String(raw.apparatus) : undefined,
    procedure: raw.procedure ? String(raw.procedure) : undefined,
    observations: raw.observations ? String(raw.observations) : undefined,
    calculations: raw.calculations ? String(raw.calculations) : undefined,
    precautions: raw.precautions ? String(raw.precautions) : undefined,
    preparationChecklist:
      raw.preparationChecklist && typeof raw.preparationChecklist === "object"
        ? raw.preparationChecklist
        : undefined,
  };
}

/**
 * Bidirectional DTO Mapping: Backend DTO -> Frontend ExperimentRecord
 */
export function mapBackendExperimentToRecord(
  dto: BackendExperimentResponse | BackendExperimentListItemResponse,
  existing?: ExperimentRecord
): ExperimentRecord {
  const detail = dto as BackendExperimentResponse;
  const createdAtMs = new Date(dto.createdAt).getTime();
  const updatedAtMs = new Date(dto.updatedAt).getTime();
  const validCreatedAt = !isNaN(createdAtMs) ? createdAtMs : Date.now();
  const validUpdatedAt = !isNaN(updatedAtMs) ? updatedAtMs : validCreatedAt;

  const validStatuses: ExperimentStatus[] = [
    "draft",
    "in-progress",
    "completed",
    "ready",
    "analyzing",
  ];
  const status: ExperimentStatus = validStatuses.includes(dto.status as ExperimentStatus)
    ? (dto.status as ExperimentStatus)
    : "ready";

  const creationMethod: CreationMethod =
    dto.creationMethod === "upload" ? "upload" : "manual";

  const preparationChecklist =
    detail.preparationChecklist ||
    detail.checklist?.items ||
    existing?.preparationChecklist ||
    undefined;

  return {
    id: String(dto.id),
    title: String(dto.title || "").trim(),
    subject: String(dto.subject || "").trim(),
    experimentNumber: dto.experimentNumber
      ? String(dto.experimentNumber).trim()
      : (existing?.experimentNumber ?? undefined),
    courseSemester: dto.courseSemester
      ? String(dto.courseSemester).trim()
      : (existing?.courseSemester ?? undefined),
    method: creationMethod,
    hasManualFile: Boolean(dto.hasManualFile),
    fileName: dto.fileName ? String(dto.fileName) : (existing?.fileName ?? undefined),
    createdAt: formatDate(validCreatedAt),
    createdAtTimestamp: validCreatedAt,
    updatedAt: formatRelativeTime(validUpdatedAt),
    updatedAtTimestamp: validUpdatedAt,
    status,
    vivaQuestionsCount:
      typeof detail.vivaQuestionsCount === "number"
        ? detail.vivaQuestionsCount
        : (existing?.vivaQuestionsCount ?? 0),
    description:
      detail.description !== undefined
        ? detail.description ? String(detail.description).trim() : undefined
        : existing?.description,
    objective:
      detail.objective !== undefined
        ? detail.objective ? String(detail.objective).trim() : undefined
        : existing?.objective,
    theory:
      detail.theory !== undefined
        ? detail.theory ? String(detail.theory).trim() : undefined
        : existing?.theory,
    apparatus:
      detail.apparatus !== undefined
        ? detail.apparatus ? String(detail.apparatus).trim() : undefined
        : existing?.apparatus,
    procedure:
      detail.procedure !== undefined
        ? detail.procedure ? String(detail.procedure).trim() : undefined
        : existing?.procedure,
    observations:
      detail.observations !== undefined
        ? detail.observations ? String(detail.observations).trim() : undefined
        : existing?.observations,
    calculations:
      detail.calculations !== undefined
        ? detail.calculations ? String(detail.calculations).trim() : undefined
        : existing?.calculations,
    precautions:
      detail.precautions !== undefined
        ? detail.precautions ? String(detail.precautions).trim() : undefined
        : existing?.precautions,
    preparationChecklist,
  };
}

/**
 * Bidirectional DTO Mapping: Frontend Creation Payload -> Backend DTO
 */
export function mapRecordToCreateDto(
  data: Partial<ExperimentRecord> & { title: string; subject: string }
): Record<string, unknown> {
  const dto: Record<string, unknown> = {
    title: data.title.trim(),
    subject: data.subject.trim(),
  };

  if (data.experimentNumber !== undefined) {
    dto.experiment_number = data.experimentNumber.trim() || null;
  }
  if (data.courseSemester !== undefined) {
    dto.course_semester = data.courseSemester.trim() || null;
  }
  if (data.method !== undefined) {
    dto.creation_method = data.method === "upload" ? "upload" : "manual";
  }
  if (data.hasManualFile !== undefined || data.fileName !== undefined) {
    dto.has_manual_file = Boolean(data.hasManualFile || data.fileName);
  }
  if (data.fileName !== undefined) {
    dto.file_name = data.fileName ? data.fileName.trim() : null;
  }
  if (data.status !== undefined) {
    dto.status = data.status;
  }
  if (data.description !== undefined) {
    dto.description = data.description ? data.description.trim() : null;
  }
  if (data.objective !== undefined) {
    dto.objective = data.objective ? data.objective.trim() : null;
  }
  if (data.theory !== undefined) {
    dto.theory = data.theory ? data.theory.trim() : null;
  }
  if (data.apparatus !== undefined) {
    dto.apparatus = data.apparatus ? data.apparatus.trim() : null;
  }
  if (data.procedure !== undefined) {
    dto.procedure = data.procedure ? data.procedure.trim() : null;
  }
  if (data.observations !== undefined) {
    dto.observations = data.observations ? data.observations.trim() : null;
  }
  if (data.calculations !== undefined) {
    dto.calculations = data.calculations ? data.calculations.trim() : null;
  }
  if (data.precautions !== undefined) {
    dto.precautions = data.precautions ? data.precautions.trim() : null;
  }

  return dto;
}

/**
 * Bidirectional DTO Mapping: Frontend Update Payload -> Backend DTO
 */
export function mapRecordToUpdateDto(
  updates: Partial<Omit<ExperimentRecord, "id" | "createdAt" | "createdAtTimestamp">>
): Record<string, unknown> {
  const dto: Record<string, unknown> = {};

  if (updates.title !== undefined) {
    dto.title = updates.title.trim();
  }
  if (updates.subject !== undefined) {
    dto.subject = updates.subject.trim();
  }
  if (updates.experimentNumber !== undefined) {
    dto.experiment_number = updates.experimentNumber ? updates.experimentNumber.trim() : null;
  }
  if (updates.courseSemester !== undefined) {
    dto.course_semester = updates.courseSemester ? updates.courseSemester.trim() : null;
  }
  if (updates.method !== undefined) {
    dto.creation_method = updates.method === "upload" ? "upload" : "manual";
  }
  if (updates.hasManualFile !== undefined) {
    dto.has_manual_file = Boolean(updates.hasManualFile);
  }
  if (updates.fileName !== undefined) {
    dto.file_name = updates.fileName ? updates.fileName.trim() : null;
  }
  if (updates.status !== undefined) {
    dto.status = updates.status;
  }
  if (updates.description !== undefined) {
    dto.description = updates.description ? updates.description.trim() : null;
  }
  if (updates.objective !== undefined) {
    dto.objective = updates.objective ? updates.objective.trim() : null;
  }
  if (updates.theory !== undefined) {
    dto.theory = updates.theory ? updates.theory.trim() : null;
  }
  if (updates.apparatus !== undefined) {
    dto.apparatus = updates.apparatus ? updates.apparatus.trim() : null;
  }
  if (updates.procedure !== undefined) {
    dto.procedure = updates.procedure ? updates.procedure.trim() : null;
  }
  if (updates.observations !== undefined) {
    dto.observations = updates.observations ? updates.observations.trim() : null;
  }
  if (updates.calculations !== undefined) {
    dto.calculations = updates.calculations ? updates.calculations.trim() : null;
  }
  if (updates.precautions !== undefined) {
    dto.precautions = updates.precautions ? updates.precautions.trim() : null;
  }

  return dto;
}

/**
 * Dispatch reactive update notification to all subscribers in the current window.
 */
function notifyUpdate(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(UPDATE_EVENT_NAME));
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
 * Local Experiment Adapter: Preserves 100% of the existing localStorage behavior for guest mode.
 */
export const localExperimentAdapter = {
  getScopedStorageKey(user?: UserSession): string {
    if (user && !user.isGuest && user.email) {
      const safeEmail = user.email.toLowerCase().replace(/[^a-z0-9]/g, "_");
      return `${BASE_STORAGE_KEY}_user_${safeEmail}`;
    }
    return `${BASE_STORAGE_KEY}_guest`;
  },

  getExperiments(user?: UserSession): ExperimentRecord[] {
    if (typeof window === "undefined") return [];
    try {
      const key = this.getScopedStorageKey(user);
      let stored = localStorage.getItem(key);

      // Fallback for guest session if legacy un-scoped key exists
      if (!stored && (!user || user.isGuest)) {
        const legacy = localStorage.getItem(BASE_STORAGE_KEY);
        if (legacy) {
          stored = legacy;
          localStorage.setItem(key, legacy);
        }
      }

      if (!stored) return [];
      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) return [];
      return parsed.map(normalizeRecord);
    } catch {
      return [];
    }
  },

  getExperimentById(id: string, user?: UserSession): ExperimentRecord | null {
    const list = this.getExperiments(user);
    return list.find((exp) => exp.id === id) || null;
  },

  saveExperiment(
    data: Partial<ExperimentRecord> & { title: string; subject: string },
    user?: UserSession
  ): ExperimentRecord {
    const now = Date.now();
    const newRecord: ExperimentRecord = {
      id: data.id || `exp-${now}`,
      title: data.title.trim(),
      subject: data.subject.trim(),
      experimentNumber: data.experimentNumber?.trim() || undefined,
      courseSemester: data.courseSemester?.trim() || undefined,
      method: data.method || "upload",
      hasManualFile: Boolean(data.hasManualFile || data.fileName),
      fileName: data.fileName,
      createdAt: data.createdAt || formatDate(now),
      createdAtTimestamp: now,
      updatedAt: "Just now",
      updatedAtTimestamp: now,
      status: data.status || "ready",
      vivaQuestionsCount: data.vivaQuestionsCount || 0,
      description: data.description?.trim() || undefined,
      objective: data.objective?.trim() || undefined,
      theory: data.theory?.trim() || undefined,
      apparatus: data.apparatus?.trim() || undefined,
      procedure: data.procedure?.trim() || undefined,
      observations: data.observations?.trim() || undefined,
      calculations: data.calculations?.trim() || undefined,
      precautions: data.precautions?.trim() || undefined,
      preparationChecklist: data.preparationChecklist || undefined,
    };

    if (typeof window !== "undefined") {
      try {
        const key = this.getScopedStorageKey(user);
        const existing = this.getExperiments(user);
        const updated = [newRecord, ...existing.filter((e) => e.id !== newRecord.id)];

        localStorage.setItem(key, JSON.stringify(updated));
        if (!user || user.isGuest) {
          localStorage.setItem(BASE_STORAGE_KEY, JSON.stringify(updated));
        }

        notifyUpdate();
      } catch (err) {
        console.error("Failed to save experiment to storage:", err);
      }
    }

    return newRecord;
  },

  updateExperiment(
    id: string,
    updates: Partial<Omit<ExperimentRecord, "id" | "createdAt" | "createdAtTimestamp">>,
    user?: UserSession
  ): ExperimentRecord | null {
    if (typeof window === "undefined") return null;

    try {
      const key = this.getScopedStorageKey(user);
      const existing = this.getExperiments(user);
      const targetIndex = existing.findIndex((e) => e.id === id);
      if (targetIndex === -1) return null;

      const current = existing[targetIndex];
      const now = Date.now();

      const updatedRecord: ExperimentRecord = {
        ...current,
        ...updates,
        title: updates.title !== undefined ? updates.title.trim() : current.title,
        subject: updates.subject !== undefined ? updates.subject.trim() : current.subject,
        experimentNumber:
          updates.experimentNumber !== undefined
            ? updates.experimentNumber ? updates.experimentNumber.trim() : undefined
            : current.experimentNumber,
        courseSemester:
          updates.courseSemester !== undefined
            ? updates.courseSemester ? updates.courseSemester.trim() : undefined
            : current.courseSemester,
        status: updates.status || current.status,
        description:
          updates.description !== undefined
            ? updates.description ? updates.description.trim() : undefined
            : current.description,
        objective:
          updates.objective !== undefined
            ? updates.objective ? updates.objective.trim() : undefined
            : current.objective,
        theory:
          updates.theory !== undefined
            ? updates.theory ? updates.theory.trim() : undefined
            : current.theory,
        apparatus:
          updates.apparatus !== undefined
            ? updates.apparatus ? updates.apparatus.trim() : undefined
            : current.apparatus,
        procedure:
          updates.procedure !== undefined
            ? updates.procedure ? updates.procedure.trim() : undefined
            : current.procedure,
        observations:
          updates.observations !== undefined
            ? updates.observations ? updates.observations.trim() : undefined
            : current.observations,
        calculations:
          updates.calculations !== undefined
            ? updates.calculations ? updates.calculations.trim() : undefined
            : current.calculations,
        precautions:
          updates.precautions !== undefined
            ? updates.precautions ? updates.precautions.trim() : undefined
            : current.precautions,
        preparationChecklist:
          updates.preparationChecklist !== undefined
            ? updates.preparationChecklist
            : current.preparationChecklist,
        updatedAt: "Just now",
        updatedAtTimestamp: now,
      };

      existing[targetIndex] = updatedRecord;
      localStorage.setItem(key, JSON.stringify(existing));
      if (!user || user.isGuest) {
        localStorage.setItem(BASE_STORAGE_KEY, JSON.stringify(existing));
      }

      notifyUpdate();
      return updatedRecord;
    } catch (err) {
      console.error("Failed to update experiment:", err);
      return null;
    }
  },

  toggleChecklistItem(
    id: string,
    itemId: string,
    completed: boolean,
    user?: UserSession
  ): ExperimentRecord | null {
    const existing = this.getExperimentById(id, user);
    if (!existing) return null;

    const currentChecklist = existing.preparationChecklist || {};
    const updatedChecklist = {
      ...currentChecklist,
      [itemId]: completed,
    };

    return this.updateExperiment(id, { preparationChecklist: updatedChecklist }, user);
  },

  deleteExperiment(id: string, user?: UserSession): boolean {
    if (typeof window === "undefined") return false;
    try {
      const key = this.getScopedStorageKey(user);
      const existing = this.getExperiments(user);
      const updated = existing.filter((e) => e.id !== id);
      if (updated.length === existing.length) return false;

      localStorage.setItem(key, JSON.stringify(updated));
      if (!user || user.isGuest) {
        localStorage.setItem(BASE_STORAGE_KEY, JSON.stringify(updated));
      }

      notifyUpdate();
      return true;
    } catch (err) {
      console.error("Failed to delete experiment:", err);
      return false;
    }
  },

  clearExperiments(user?: UserSession): boolean {
    if (typeof window === "undefined") return false;
    try {
      const key = this.getScopedStorageKey(user);
      localStorage.removeItem(key);
      if (!user || user.isGuest) {
        localStorage.removeItem(BASE_STORAGE_KEY);
      }
      notifyUpdate();
      return true;
    } catch (err) {
      console.error("Failed to clear experiments:", err);
      return false;
    }
  },
};

/**
 * Remote API Adapter: Implements backend experiment REST communication (/api/v1/experiments)
 */
const authenticatedCache = new Map<string, ExperimentRecord[]>();
let inFlightFetchPromise: Promise<ExperimentRecord[]> | null = null;

function getAuthCacheKey(user?: UserSession): string {
  if (user?.email) {
    return user.email.toLowerCase().trim();
  }
  return "__active_auth_user__";
}

export const apiExperimentAdapter = {
  getCachedExperiments(user?: UserSession): ExperimentRecord[] {
    const key = getAuthCacheKey(user);
    return authenticatedCache.get(key) || [];
  },

  setCachedExperiments(user: UserSession | undefined, list: ExperimentRecord[]): void {
    const key = getAuthCacheKey(user);
    authenticatedCache.set(key, list);
  },

  clearCache(): void {
    authenticatedCache.clear();
    inFlightFetchPromise = null;
  },

  async fetchExperiments(
    user?: UserSession,
    options?: ListExperimentsOptions
  ): Promise<ExperimentRecord[]> {
    const isDefaultQuery = !options || Object.keys(options).length === 0;
    if (isDefaultQuery && inFlightFetchPromise) {
      return inFlightFetchPromise;
    }

    const fetchTask = (async () => {
      const params: Record<string, string | number> = {};
      if (options?.page) params.page = options.page;
      if (options?.pageSize) params.pageSize = options.pageSize;
      if (options?.subject) params.subject = options.subject;
      if (options?.status && options.status !== "all") params.status = options.status;
      if (options?.search) params.search = options.search;

      const response = await apiClient.get<BackendExperimentListResponse>("/experiments", {
        params,
        requiresAuth: true,
      });

      const currentCached = this.getCachedExperiments(user);
      const existingMap = new Map(currentCached.map((e) => [e.id, e]));

      const mappedList: ExperimentRecord[] = (response.items || []).map((item) => {
        return mapBackendExperimentToRecord(item, existingMap.get(String(item.id)));
      });

      this.setCachedExperiments(user, mappedList);
      notifyUpdate();
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

  async getExperimentById(id: string, user?: UserSession): Promise<ExperimentRecord | null> {
    try {
      const response = await apiClient.get<BackendExperimentResponse>(`/experiments/${id}`, {
        requiresAuth: true,
      });

      const currentCached = this.getCachedExperiments(user);
      const existing = currentCached.find((e) => e.id === id);
      const record = mapBackendExperimentToRecord(response, existing);

      const updatedList = currentCached.some((e) => e.id === id)
        ? currentCached.map((e) => (e.id === id ? record : e))
        : [record, ...currentCached];
      this.setCachedExperiments(user, updatedList);
      notifyUpdate();

      return record;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        return null;
      }
      throw err;
    }
  },

  async createExperiment(
    data: Partial<ExperimentRecord> & { title: string; subject: string },
    user?: UserSession
  ): Promise<ExperimentRecord> {
    const payload = mapRecordToCreateDto(data);
    const response = await apiClient.post<BackendExperimentResponse>("/experiments", payload, {
      requiresAuth: true,
    });

    const record = mapBackendExperimentToRecord(response);
    const currentCached = this.getCachedExperiments(user);
    this.setCachedExperiments(user, [record, ...currentCached.filter((e) => e.id !== record.id)]);
    notifyUpdate();

    return record;
  },

  async updateExperiment(
    id: string,
    updates: Partial<Omit<ExperimentRecord, "id" | "createdAt" | "createdAtTimestamp">>,
    user?: UserSession
  ): Promise<ExperimentRecord | null> {
    try {
      const payload = mapRecordToUpdateDto(updates);
      const response = await apiClient.patch<BackendExperimentResponse>(
        `/experiments/${id}`,
        payload,
        { requiresAuth: true }
      );

      const currentCached = this.getCachedExperiments(user);
      const existing = currentCached.find((e) => e.id === id);
      const record = mapBackendExperimentToRecord(response, existing);

      const updatedList = currentCached.some((e) => e.id === id)
        ? currentCached.map((e) => (e.id === id ? record : e))
        : [record, ...currentCached];
      this.setCachedExperiments(user, updatedList);
      notifyUpdate();

      return record;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        return null;
      }
      throw err;
    }
  },

  async deleteExperiment(id: string, user?: UserSession): Promise<boolean> {
    try {
      await apiClient.delete(`/experiments/${id}`, {
        requiresAuth: true,
      });

      const currentCached = this.getCachedExperiments(user);
      this.setCachedExperiments(user, currentCached.filter((e) => e.id !== id));
      notifyUpdate();

      return true;
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        return false;
      }
      throw err;
    }
  },

  async updateChecklist(
    id: string,
    items: Record<string, boolean>,
    user?: UserSession
  ): Promise<Record<string, boolean>> {
    const response = await apiClient.patch<BackendPreparationChecklistResponse>(
      `/experiments/${id}/checklist`,
      items,
      { requiresAuth: true }
    );

    const checklistItems = response.items || items;
    const currentCached = this.getCachedExperiments(user);
    const target = currentCached.find((e) => e.id === id);
    if (target) {
      target.preparationChecklist = {
        ...(target.preparationChecklist || {}),
        ...checklistItems,
      };
      notifyUpdate();
    }

    return checklistItems;
  },

  async toggleChecklistItem(
    id: string,
    itemId: string,
    completed: boolean,
    user?: UserSession
  ): Promise<ExperimentRecord | null> {
    const response = await apiClient.patch<BackendPreparationChecklistResponse>(
      `/experiments/${id}/checklist`,
      { [itemId]: completed },
      { requiresAuth: true }
    );

    const currentCached = this.getCachedExperiments(user);
    const target = currentCached.find((e) => e.id === id);
    if (target) {
      target.preparationChecklist = {
        ...(target.preparationChecklist || {}),
        ...(response.items || { [itemId]: completed }),
      };
      notifyUpdate();
      return target;
    }

    return this.getExperimentById(id, user);
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
 * Experiment Storage Facade
 */
export const experimentStorage = {
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
    apiExperimentAdapter.clearCache();
  },

  /**
   * Retrieve all experiments.
   * Authenticated: returns cached records immediately & thenable fetching from API.
   * Guest / Local: reads localStorage synchronously.
   */
  getExperiments(user?: UserSession): ExperimentRecord[] {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.getExperiments(user);
    }

    const cached = apiExperimentAdapter.getCachedExperiments(user);
    const promise = apiExperimentAdapter.fetchExperiments(user);
    return createThenableArray(cached, promise);
  },

  /**
   * Explicit async retrieval with pagination, search, and filtering.
   */
  async getExperimentsAsync(
    user?: UserSession,
    options?: ListExperimentsOptions
  ): Promise<ExperimentRecord[]> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      let list = localExperimentAdapter.getExperiments(user);
      if (options?.subject) {
        list = list.filter(
          (e) => e.subject.toLowerCase() === options.subject!.toLowerCase()
        );
      }
      if (options?.status && options.status !== "all") {
        list = list.filter((e) => e.status === options.status);
      }
      if (options?.search) {
        const q = options.search.toLowerCase();
        list = list.filter(
          (e) =>
            e.title.toLowerCase().includes(q) ||
            e.subject.toLowerCase().includes(q) ||
            e.description?.toLowerCase().includes(q) ||
            e.experimentNumber?.toLowerCase().includes(q)
        );
      }
      return list;
    }

    return apiExperimentAdapter.fetchExperiments(user, options);
  },

  /**
   * Alias for getExperimentsAsync.
   */
  async fetchExperiments(
    user?: UserSession,
    options?: ListExperimentsOptions
  ): Promise<ExperimentRecord[]> {
    return this.getExperimentsAsync(user, options);
  },

  /**
   * Retrieve single experiment by id.
   */
  getExperimentById(
    id: string,
    user?: UserSession
  ): ExperimentRecord | null {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.getExperimentById(id, user);
    }

    const cachedList = apiExperimentAdapter.getCachedExperiments(user);
    const cached = cachedList.find((e) => e.id === id);
    const promise = apiExperimentAdapter.getExperimentById(id, user);

    if (cached) {
      return createThenableRecord(cached, promise);
    }

    const placeholder: ExperimentRecord = {
      id,
      title: "",
      subject: "",
      createdAt: "",
      createdAtTimestamp: 0,
      updatedAt: "",
      updatedAtTimestamp: 0,
      status: "ready",
      vivaQuestionsCount: 0,
    };
    return createThenableRecord(placeholder, promise);
  },

  /**
   * Explicit async experiment retrieval by id.
   */
  async getExperimentByIdAsync(id: string, user?: UserSession): Promise<ExperimentRecord | null> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.getExperimentById(id, user);
    }
    return apiExperimentAdapter.getExperimentById(id, user);
  },

  /**
   * Create and persist a new experiment.
   */
  saveExperiment(
    data: Partial<ExperimentRecord> & { title: string; subject: string },
    user?: UserSession
  ): ExperimentRecord {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.saveExperiment(data, user);
    }

    const now = Date.now();
    const optimisticRecord: ExperimentRecord = {
      id: data.id || `temp-${now}`,
      title: data.title.trim(),
      subject: data.subject.trim(),
      experimentNumber: data.experimentNumber?.trim(),
      courseSemester: data.courseSemester?.trim(),
      method: data.method || "manual",
      hasManualFile: Boolean(data.hasManualFile || data.fileName),
      fileName: data.fileName,
      createdAt: data.createdAt || formatDate(now),
      createdAtTimestamp: now,
      updatedAt: "Just now",
      updatedAtTimestamp: now,
      status: data.status || "ready",
      vivaQuestionsCount: data.vivaQuestionsCount || 0,
      description: data.description?.trim(),
      objective: data.objective?.trim(),
      theory: data.theory?.trim(),
      apparatus: data.apparatus?.trim(),
      procedure: data.procedure?.trim(),
      observations: data.observations?.trim(),
      calculations: data.calculations?.trim(),
      precautions: data.precautions?.trim(),
      preparationChecklist: data.preparationChecklist,
    };

    const promise = apiExperimentAdapter.createExperiment(data, user);
    return createThenableRecord(optimisticRecord, promise);
  },

  /**
   * Explicit async experiment creation.
   */
  async createExperiment(
    data: Partial<ExperimentRecord> & { title: string; subject: string },
    user?: UserSession
  ): Promise<ExperimentRecord> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.saveExperiment(data, user);
    }
    return apiExperimentAdapter.createExperiment(data, user);
  },

  async saveExperimentAsync(
    data: Partial<ExperimentRecord> & { title: string; subject: string },
    user?: UserSession
  ): Promise<ExperimentRecord> {
    return this.createExperiment(data, user);
  },

  /**
   * Update existing experiment metadata.
   */
  updateExperiment(
    id: string,
    updates: Partial<Omit<ExperimentRecord, "id" | "createdAt" | "createdAtTimestamp">>,
    user?: UserSession
  ): ExperimentRecord | null {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.updateExperiment(id, updates, user);
    }

    const currentCached = apiExperimentAdapter.getCachedExperiments(user);
    const existing = currentCached.find((e) => e.id === id);
    const optimisticRecord: ExperimentRecord = {
      ...(existing || {
        id,
        title: "",
        subject: "",
        createdAt: "",
        createdAtTimestamp: 0,
        updatedAt: "",
        updatedAtTimestamp: 0,
        status: "ready",
        vivaQuestionsCount: 0,
      }),
      ...updates,
      updatedAt: "Just now",
      updatedAtTimestamp: Date.now(),
    };

    const promise = apiExperimentAdapter.updateExperiment(id, updates, user);
    return createThenableRecord(optimisticRecord, promise);
  },

  /**
   * Explicit async experiment update.
   */
  async updateExperimentAsync(
    id: string,
    updates: Partial<Omit<ExperimentRecord, "id" | "createdAt" | "createdAtTimestamp">>,
    user?: UserSession
  ): Promise<ExperimentRecord | null> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.updateExperiment(id, updates, user);
    }
    return apiExperimentAdapter.updateExperiment(id, updates, user);
  },

  /**
   * Toggle a specific preparation checklist item for an experiment.
   */
  toggleChecklistItem(
    id: string,
    itemId: string,
    completed: boolean,
    user?: UserSession
  ): ExperimentRecord | null {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.toggleChecklistItem(id, itemId, completed, user);
    }

    const currentCached = apiExperimentAdapter.getCachedExperiments(user);
    const existing = currentCached.find((e) => e.id === id);
    const optimisticRecord: ExperimentRecord = {
      ...(existing || {
        id,
        title: "",
        subject: "",
        createdAt: "",
        createdAtTimestamp: 0,
        updatedAt: "",
        updatedAtTimestamp: 0,
        status: "ready",
        vivaQuestionsCount: 0,
      }),
      preparationChecklist: {
        ...(existing?.preparationChecklist || {}),
        [itemId]: completed,
      },
    };

    const promise = apiExperimentAdapter.toggleChecklistItem(id, itemId, completed, user);
    return createThenableRecord(optimisticRecord, promise);
  },


  async toggleChecklistItemAsync(
    id: string,
    itemId: string,
    completed: boolean,
    user?: UserSession
  ): Promise<ExperimentRecord | null> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.toggleChecklistItem(id, itemId, completed, user);
    }
    return apiExperimentAdapter.toggleChecklistItem(id, itemId, completed, user);
  },

  /**
   * Update full checklist state directly.
   */
  async updateChecklistAsync(
    id: string,
    items: Record<string, boolean>,
    user?: UserSession
  ): Promise<Record<string, boolean>> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      const exp = localExperimentAdapter.getExperimentById(id, user);
      if (!exp) return {};
      const updated = localExperimentAdapter.updateExperiment(
        id,
        {
          preparationChecklist: {
            ...(exp.preparationChecklist || {}),
            ...items,
          },
        },
        user
      );
      return updated?.preparationChecklist || {};
    }
    return apiExperimentAdapter.updateChecklist(id, items, user);
  },

  /**
   * Delete experiment by id.
   */
  deleteExperiment(id: string, user?: UserSession): boolean | Promise<boolean> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.deleteExperiment(id, user);
    }
    return apiExperimentAdapter.deleteExperiment(id, user);
  },

  async deleteExperimentAsync(id: string, user?: UserSession): Promise<boolean> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.deleteExperiment(id, user);
    }
    return apiExperimentAdapter.deleteExperiment(id, user);
  },

  /**
   * Clear all experiments for the active user or guest session.
   */
  clearExperiments(user?: UserSession): boolean | Promise<boolean> {
    const mode = this.resolveMode(user);
    if (mode !== "authenticated") {
      return localExperimentAdapter.clearExperiments(user);
    }
    apiExperimentAdapter.clearCache();
    notifyUpdate();
    return true;
  },

  /**
   * Subscribe to experiment storage updates (window custom event & storage event).
   */
  subscribe(callback: () => void): () => void {
    if (typeof window === "undefined") return () => {};

    const handleCustom = () => callback();
    const handleStorage = (e: StorageEvent) => {
      if (e.key?.startsWith(BASE_STORAGE_KEY)) {
        callback();
      }
    };

    window.addEventListener(UPDATE_EVENT_NAME, handleCustom);
    window.addEventListener("storage", handleStorage);

    return () => {
      window.removeEventListener(UPDATE_EVENT_NAME, handleCustom);
      window.removeEventListener("storage", handleStorage);
    };
  },
};

export default experimentStorage;
