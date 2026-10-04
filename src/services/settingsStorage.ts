/**
 * PracPrep Settings & Personalization Storage Facade
 *
 * Implements a dual-mode storage service supporting:
 * 1. Guest mode: Completely local, zero network requests, stored under pracprep_settings_guest.
 * 2. Authenticated mode: Synchronizes study preferences with PostgreSQL via FastAPI endpoints
 *    (/api/v1/users/me/settings) while preserving display preferences (theme, density, reducedMotion)
 *    strictly client-local.
 *
 * Architecture:
 * - LocalSettingsAdapter: Encapsulates guest persistence and authenticated localStorage caching.
 * - ApiSettingsAdapter: Communicates with /users/me/settings endpoints using apiClient.
 * - ModeResolver: Resolves active storage mode ("authenticated" | "guest" | "local").
 * - SettingsStorage Facade: Exposes synchronous getSettings() contract for existing UI consumers
 *   alongside asynchronous syncRemoteSettings() and saveSettingsAsync() methods.
 */

import type { UserSession } from "../types/dashboard.ts";
import type {
  UserSettings,
  ThemePreference,
  ExportDataPayload,
  StudyPreferences,
} from "../types/settings.ts";
import type { VivaDifficulty, VivaTopic } from "../types/viva.ts";
import { experimentStorage } from "./experimentStorage.ts";
import { vivaStorage } from "./vivaStorage.ts";
import { apiClient, tokenManager, ApiError } from "../lib/apiClient.ts";

export type { UserSettings, ThemePreference, ExportDataPayload, StudyPreferences };
export { ApiError };

export const BASE_SETTINGS_KEY = "pracprep_settings";
export const SETTINGS_UPDATE_EVENT = "pracprep_settings_changed";
export const USER_UPDATE_EVENT = "pracprep_user_changed";

export type StorageMode = "authenticated" | "guest" | "local";

export interface ModeResolver {
  resolveMode(user?: UserSession): StorageMode;
}

export interface BackendUserSettingsResponse {
  id: string;
  userId: string;
  defaultDifficulty: VivaDifficulty;
  defaultQuestionCount: 5 | 10 | 15;
  preferredFocus: VivaTopic;
  createdAt: string;
  updatedAt: string;
}

export interface BackendUserSettingsUpdateRequest {
  defaultDifficulty?: VivaDifficulty;
  defaultQuestionCount?: 5 | 10 | 15;
  preferredFocus?: VivaTopic;
}

export const DEFAULT_SETTINGS: UserSettings = {
  theme: "system",
  density: "comfortable",
  reducedMotion: false,
  studyPreferences: {
    defaultDifficulty: "mixed",
    defaultQuestionCount: 5,
    preferredFocus: "mixed",
  },
};

/**
 * Dispatch reactive update notification to all subscribers in the current window.
 */
export function notifySettingsUpdate(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(SETTINGS_UPDATE_EVENT));
  }
}

export function notifyUserUpdate(): void {
  if (typeof window !== "undefined") {
    window.dispatchEvent(new CustomEvent(USER_UPDATE_EVENT));
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

export function setModeResolver(resolver: ModeResolver): void {
  activeModeResolver = resolver;
}

export function resetModeResolver(): void {
  activeModeResolver = defaultModeResolver;
}

/**
 * Local Settings Adapter: Handles localStorage caching with strict account partitioning.
 */
export const localSettingsAdapter = {
  getScopedSettingsKey(user?: UserSession): string {
    if (user && !user.isGuest && user.email) {
      const safeEmail = user.email.toLowerCase().replace(/[^a-z0-9]/g, "_");
      return `${BASE_SETTINGS_KEY}_user_${safeEmail}`;
    }

    if (!user && typeof window !== "undefined") {
      try {
        const stored = window.localStorage.getItem("pracprep_user");
        if (stored) {
          const parsed = JSON.parse(stored);
          if (parsed && !parsed.isGuest && parsed.email) {
            const safeEmail = parsed.email.toLowerCase().replace(/[^a-z0-9]/g, "_");
            return `${BASE_SETTINGS_KEY}_user_${safeEmail}`;
          }
        }
      } catch {
        // Safe fallback
      }
    }

    return `${BASE_SETTINGS_KEY}_guest`;
  },

  getSettings(user?: UserSession): UserSettings {
    if (typeof window === "undefined") return DEFAULT_SETTINGS;
    try {
      const key = this.getScopedSettingsKey(user);
      const stored = localStorage.getItem(key);
      if (!stored) return DEFAULT_SETTINGS;
      const parsed = JSON.parse(stored);

      // Normalize legacy values if present in storage
      const rawPrefs = parsed.studyPreferences || {};
      let diff = rawPrefs.defaultDifficulty || DEFAULT_SETTINGS.studyPreferences.defaultDifficulty;
      if (diff === "medium") diff = "intermediate";
      let focus = rawPrefs.preferredFocus || DEFAULT_SETTINGS.studyPreferences.preferredFocus;
      if (focus === "all") focus = "mixed";
      const count =
        typeof rawPrefs.defaultQuestionCount === "number"
          ? rawPrefs.defaultQuestionCount
          : DEFAULT_SETTINGS.studyPreferences.defaultQuestionCount;

      return {
        ...DEFAULT_SETTINGS,
        ...parsed,
        studyPreferences: {
          defaultDifficulty: diff,
          defaultQuestionCount: count,
          preferredFocus: focus,
        },
      };
    } catch {
      return DEFAULT_SETTINGS;
    }
  },

  saveSettings(settings: UserSettings, user?: UserSession): UserSettings {
    if (typeof window !== "undefined") {
      try {
        const key = this.getScopedSettingsKey(user);
        localStorage.setItem(key, JSON.stringify(settings));
      } catch (err) {
        console.error("Failed to save local settings:", err);
      }
    }
    return settings;
  },

  clearSettings(user?: UserSession): boolean {
    if (typeof window === "undefined") return false;
    try {
      const key = this.getScopedSettingsKey(user);
      localStorage.removeItem(key);
      return true;
    } catch {
      return false;
    }
  },
};

/**
 * API Settings Adapter: Direct communications with the FastAPI settings endpoints.
 */
export const apiSettingsAdapter = {
  async fetchRemoteSettings(): Promise<BackendUserSettingsResponse> {
    return apiClient.get<BackendUserSettingsResponse>("/users/me/settings");
  },

  async updateRemoteSettings(
    payload: BackendUserSettingsUpdateRequest
  ): Promise<BackendUserSettingsResponse> {
    return apiClient.patch<BackendUserSettingsResponse>("/users/me/settings", payload);
  },
};

// In-flight sync promises keyed by scoped cache key to avoid duplicate concurrent calls
const inFlightSyncs = new Map<string, Promise<UserSettings>>();

// Sequence counter to preserve consistency during rapid sequential updates
let latestUpdateSequence = 0;

/**
 * Main Settings Storage Facade
 */
export const settingsStorage = {
  /**
   * Introspect active storage mode
   */
  getMode(user?: UserSession): StorageMode {
    return activeModeResolver.resolveMode(user);
  },

  /**
   * Override active mode resolver (useful for testing or switching contexts)
   */
  setModeResolver(resolver: ModeResolver): void {
    setModeResolver(resolver);
  },

  /**
   * Reset to default mode resolver
   */
  resetModeResolver(): void {
    resetModeResolver();
  },

  /**
   * Get settings synchronously for current user or guest from local cache.
   * Guarantees zero latency and retains synchronous return type for UI consumers.
   */
  getSettings(user?: UserSession): UserSettings {
    return localSettingsAdapter.getSettings(user);
  },

  /**
   * Synchronize remote study preferences for authenticated students.
   * Merges remote preferences into local cache without overwriting display preferences.
   * Dedupes concurrent in-flight requests.
   */
  async syncRemoteSettings(user?: UserSession): Promise<UserSettings> {
    const mode = this.getMode(user);
    if (mode !== "authenticated") {
      return localSettingsAdapter.getSettings(user);
    }

    const cacheKey = localSettingsAdapter.getScopedSettingsKey(user);

    // Reuse in-flight promise if a sync is already pending
    const existing = inFlightSyncs.get(cacheKey);
    if (existing) {
      return existing;
    }

    const syncPromise = (async () => {
      try {
        const remote = await apiSettingsAdapter.fetchRemoteSettings();
        const currentLocal = localSettingsAdapter.getSettings(user);

        // Normalize remote values if necessary
        let diff = remote.defaultDifficulty;
        if ((diff as string) === "medium") diff = "intermediate";
        let focus = remote.preferredFocus;
        if ((focus as string) === "all") focus = "mixed";
        const count = remote.defaultQuestionCount;

        const merged: UserSettings = {
          ...currentLocal,
          studyPreferences: {
            defaultDifficulty: diff || currentLocal.studyPreferences.defaultDifficulty,
            defaultQuestionCount: count || currentLocal.studyPreferences.defaultQuestionCount,
            preferredFocus: focus || currentLocal.studyPreferences.preferredFocus,
          },
        };

        localSettingsAdapter.saveSettings(merged, user);
        notifySettingsUpdate();
        return merged;
      } finally {
        inFlightSyncs.delete(cacheKey);
      }
    })();

    inFlightSyncs.set(cacheKey, syncPromise);
    return syncPromise;
  },

  /**
   * Asynchronously save user settings with backend synchronization for authenticated students.
   * Sends ONLY study preferences to PATCH /users/me/settings; display preferences remain local.
   * Reconciles cache upon confirmed server response.
   */
  async saveSettingsAsync(settings: UserSettings, user?: UserSession): Promise<UserSettings> {
    const mode = this.getMode(user);

    // 1. Immediately apply theme & display preferences to DOM
    this.applyTheme(settings.theme);
    this.applyDisplayPreferences(settings);

    // 2. Guest or unauthenticated local mode: Persist locally with zero network requests
    if (mode !== "authenticated") {
      const saved = localSettingsAdapter.saveSettings(settings, user);
      notifySettingsUpdate();
      return saved;
    }

    // 3. Authenticated mode:
    // Determine whether study preferences changed
    const current = localSettingsAdapter.getSettings(user);
    const studyPrefsChanged =
      current.studyPreferences.defaultDifficulty !== settings.studyPreferences.defaultDifficulty ||
      current.studyPreferences.defaultQuestionCount !== settings.studyPreferences.defaultQuestionCount ||
      current.studyPreferences.preferredFocus !== settings.studyPreferences.preferredFocus;

    // Save optimistically to local cache so synchronous getSettings() reflects changes immediately
    localSettingsAdapter.saveSettings(settings, user);
    notifySettingsUpdate();

    // If only display preferences (theme, density, reducedMotion) changed, do NOT issue network request
    if (!studyPrefsChanged) {
      return settings;
    }

    // Send only the 3 study preference fields to the backend
    const patchPayload: BackendUserSettingsUpdateRequest = {
      defaultDifficulty: settings.studyPreferences.defaultDifficulty,
      defaultQuestionCount: settings.studyPreferences.defaultQuestionCount,
      preferredFocus: settings.studyPreferences.preferredFocus,
    };

    const updateSeq = ++latestUpdateSequence;

    const remote = await apiSettingsAdapter.updateRemoteSettings(patchPayload);

    // Only reconcile if this is still the latest update
    if (updateSeq === latestUpdateSequence) {
      const latestLocal = localSettingsAdapter.getSettings(user);
      let diff = remote.defaultDifficulty;
      if ((diff as string) === "medium") diff = "intermediate";
      let focus = remote.preferredFocus;
      if ((focus as string) === "all") focus = "mixed";

      const reconciled: UserSettings = {
        ...latestLocal,
        studyPreferences: {
          defaultDifficulty: diff || latestLocal.studyPreferences.defaultDifficulty,
          defaultQuestionCount: remote.defaultQuestionCount || latestLocal.studyPreferences.defaultQuestionCount,
          preferredFocus: focus || latestLocal.studyPreferences.preferredFocus,
        },
      };

      localSettingsAdapter.saveSettings(reconciled, user);
      notifySettingsUpdate();
      return reconciled;
    }

    return localSettingsAdapter.getSettings(user);
  },

  /**
   * Synchronously save user settings to local cache and apply theme/density.
   * If authenticated and study preferences were modified, dispatches background sync.
   */
  saveSettings(settings: UserSettings, user?: UserSession): UserSettings {
    const current = localSettingsAdapter.getSettings(user);
    const studyPrefsChanged =
      current.studyPreferences.defaultDifficulty !== settings.studyPreferences.defaultDifficulty ||
      current.studyPreferences.defaultQuestionCount !== settings.studyPreferences.defaultQuestionCount ||
      current.studyPreferences.preferredFocus !== settings.studyPreferences.preferredFocus;

    const saved = localSettingsAdapter.saveSettings(settings, user);
    this.applyTheme(saved.theme);
    this.applyDisplayPreferences(saved);
    notifySettingsUpdate();

    const mode = this.getMode(user);
    if (mode === "authenticated" && studyPrefsChanged) {
      void this.saveSettingsAsync(settings, user).catch((err) => {
        console.warn("Background study preferences synchronization failed:", err);
      });
    }

    return saved;
  },

  /**
   * Clear settings back to default
   */
  clearSettings(user?: UserSession): boolean {
    const cleared = localSettingsAdapter.clearSettings(user);
    this.applyTheme(DEFAULT_SETTINGS.theme);
    notifySettingsUpdate();
    return cleared;
  },

  /**
   * Apply theme across the application (maintained in light mode as requested)
   */
  applyTheme(_theme?: ThemePreference): void {
    if (typeof window === "undefined" || typeof document === "undefined") return;

    const root = document.documentElement;
    // For now, website is maintained strictly in light mode as requested
    root.classList.remove("dark");
  },

  /**
   * Apply density or reduced-motion attributes
   */
  applyDisplayPreferences(settings: UserSettings): void {
    if (typeof document === "undefined") return;
    const root = document.documentElement;
    root.setAttribute("data-density", settings.density);
    if (settings.reducedMotion) {
      root.classList.add("reduce-motion");
    } else {
      root.classList.remove("reduce-motion");
    }
  },

  /**
   * Initialize theme on app load
   */
  initTheme(user?: UserSession): void {
    if (typeof document !== "undefined") {
      document.documentElement.classList.remove("dark");
    }
    const current = this.getSettings(user);
    this.applyTheme(current.theme);
    this.applyDisplayPreferences(current);
  },

  /**
   * Update authenticated profile in localStorage and notify components
   */
  updateUserProfile(updates: Partial<UserSession>): UserSession {
    let current: UserSession = {
      isGuest: false,
      name: "Student",
      email: "student@university.edu",
    };

    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("pracprep_user");
        if (stored) {
          current = JSON.parse(stored);
        }
      } catch {
        // fallback
      }

      const updated = {
        ...current,
        ...updates,
      };

      try {
        localStorage.setItem("pracprep_user", JSON.stringify(updated));
        notifyUserUpdate();
      } catch (err) {
        console.error("Failed to update user profile:", err);
      }
      return updated;
    }

    return current;
  },

  /**
   * Export all data for the active user or guest session
   */
  exportUserData(user?: UserSession): ExportDataPayload {
    const experiments = experimentStorage.getExperiments(user);
    const vivaSessions = vivaStorage.getSessions(user);
    const settings = this.getSettings(user);

    return {
      exportVersion: "1.0",
      exportTimestamp: Date.now(),
      exportedAt: new Date().toISOString(),
      userSession: {
        isGuest: Boolean(user?.isGuest),
        name: user?.name,
        email: user?.email,
      },
      experimentsCount: experiments.length,
      vivaSessionsCount: vivaSessions.length,
      experiments,
      vivaSessions,
      settings,
    };
  },

  /**
   * Clear all stored PracPrep data strictly scoped to active user or guest session
   */
  clearAllUserData(user?: UserSession): boolean {
    const expCleared = experimentStorage.clearExperiments(user);
    const vivaCleared = vivaStorage.clearSessions(user);
    const settingsCleared = this.clearSettings(user);
    return expCleared && vivaCleared && settingsCleared;
  },

  /**
   * Subscribe to settings updates (custom event & storage event for cross-tab sync)
   */
  subscribe(callback: () => void): () => void {
    if (typeof window === "undefined") return () => {};
    const handleEvent = () => callback();
    const handleStorage = (e: StorageEvent) => {
      if (
        e.key?.startsWith(BASE_SETTINGS_KEY) ||
        e.key === "pracprep_theme" ||
        e.key === "pracprep_user"
      ) {
        callback();
      }
    };
    window.addEventListener(SETTINGS_UPDATE_EVENT, handleEvent);
    window.addEventListener("storage", handleStorage);
    return () => {
      window.removeEventListener(SETTINGS_UPDATE_EVENT, handleEvent);
      window.removeEventListener("storage", handleStorage);
    };
  },
};

export default settingsStorage;
