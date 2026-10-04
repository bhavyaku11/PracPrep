import type { VivaDifficulty, VivaTopic } from "./viva";

export type ThemePreference = "light" | "dark" | "system";
export type DensityPreference = "comfortable" | "compact";

export interface StudyPreferences {
  defaultDifficulty: VivaDifficulty;
  defaultQuestionCount: 5 | 10 | 15;
  preferredFocus: VivaTopic;
}

export interface UserSettings {
  theme: ThemePreference;
  density: DensityPreference;
  reducedMotion: boolean;
  studyPreferences: StudyPreferences;
}

export interface ExportDataPayload {
  exportVersion: string;
  exportTimestamp: number;
  exportedAt: string;
  userSession: {
    isGuest: boolean;
    name?: string;
    email?: string;
  };
  experimentsCount: number;
  vivaSessionsCount: number;
  experiments: unknown[];
  vivaSessions: unknown[];
  settings: UserSettings;
}
