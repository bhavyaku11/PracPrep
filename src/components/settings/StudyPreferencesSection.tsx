import React, { useState } from "react";
import {
  Sparkles,
  Check,
  Save,
  HelpCircle,
  AlertCircle,
  Loader2,
} from "lucide-react";
import type { UserSettings, StudyPreferences } from "../../types/settings";
import type { VivaDifficulty, VivaTopic } from "../../types/viva";
import type { UserSession } from "../../types/dashboard";
import { settingsStorage } from "../../services/settingsStorage";
import { ApiError } from "../../lib/apiClient";

interface StudyPreferencesSectionProps {
  settings: UserSettings;
  onUpdateSettings: (newSettings: UserSettings) => void;
  user?: UserSession;
}

export const StudyPreferencesSection: React.FC<StudyPreferencesSectionProps> = ({
  settings,
  onUpdateSettings,
  user,
}) => {
  // Controlled form state: keep a separate state variable that tracks which
  // settings.studyPreferences reference we last synchronised from.  When the
  // parent pushes a new reference (i.e. after a remote sync), we reset prefs
  // during this render without needing a useEffect or a ref.current access.
  const [prevExternalPrefs, setPrevExternalPrefs] = useState<StudyPreferences>(
    settings.studyPreferences
  );
  const [prefs, setPrefs] = useState<StudyPreferences>(settings.studyPreferences);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [syncError, setSyncError] = useState<string | null>(null);

  // When the parent passes a new studyPreferences object reference (e.g.
  // following a successful remote sync), reset the in-flight form state
  // during render so the component reflects the updated values immediately
  // without an extra effect pass.
  if (settings.studyPreferences !== prevExternalPrefs) {
    setPrevExternalPrefs(settings.studyPreferences);
    setPrefs(settings.studyPreferences);
  }

  const handleDifficultyChange = (difficulty: VivaDifficulty) => {
    setPrefs((prev) => ({ ...prev, defaultDifficulty: difficulty }));
  };

  const handleCountChange = (count: 5 | 10 | 15) => {
    setPrefs((prev) => ({ ...prev, defaultQuestionCount: count }));
  };

  const handleFocusChange = (focus: VivaTopic) => {
    setPrefs((prev) => ({ ...prev, preferredFocus: focus }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSyncError(null);
    setSaveSuccess(false);

    const updated: UserSettings = {
      ...settings,
      studyPreferences: prefs,
    };

    try {
      const saved = await settingsStorage.saveSettingsAsync(updated, user);
      onUpdateSettings(saved);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
          ? err.message
          : "Unable to sync preferences with server";
      setSyncError(message);
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-7 shadow-sm space-y-7">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            Viva Simulation & Study Preferences
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Configure default settings for oral examination practice sessions
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isSaving && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300 border border-neutral-300 dark:border-neutral-700">
              <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-600 dark:text-emerald-400" />
              Saving…
            </span>
          )}

          {!isSaving && saveSuccess && (
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
              <Check className="w-3.5 h-3.5 text-emerald-600" />
              Preferences saved
            </span>
          )}

          {!isSaving && syncError && (
            <span
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
              title={syncError}
            >
              <AlertCircle className="w-3.5 h-3.5 text-rose-600 dark:text-rose-400 flex-shrink-0" />
              Unable to sync
            </span>
          )}
        </div>
      </div>

      {syncError && (
        <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 text-xs text-rose-700 dark:text-rose-300 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 flex-shrink-0" />
            <span>Unable to sync with server: {syncError}. Changes saved to local cache.</span>
          </div>
          <button
            type="button"
            onClick={handleSave}
            className="text-xs font-bold underline hover:no-underline cursor-pointer flex-shrink-0"
          >
            Retry
          </button>
        </div>
      )}

      <div className="p-3.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800 text-xs text-neutral-600 dark:text-neutral-400 flex items-start gap-2.5">
        <HelpCircle className="w-4 h-4 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
        <span>
          These preferences are preselected whenever you open the <strong>Viva Setup Screen</strong>. You can always override them for any individual session without affecting your defaults.
        </span>
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {/* 1. Default Question Count */}
        <div className="space-y-2.5">
          <label className="text-xs font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400 block">
            Default Question Count
          </label>
          <div className="grid grid-cols-3 gap-3">
            {([5, 10, 15] as const).map((count) => (
              <button
                key={count}
                type="button"
                onClick={() => handleCountChange(count)}
                className={`py-3 px-4 rounded-xl border text-center transition-all cursor-pointer ${
                  prefs.defaultQuestionCount === count
                    ? "border-emerald-600 bg-emerald-50/50 dark:bg-emerald-950/20 text-neutral-900 dark:text-white font-bold ring-2 ring-emerald-500/20"
                    : "border-neutral-200 dark:border-neutral-800 bg-neutral-50/40 dark:bg-neutral-800/20 text-neutral-600 dark:text-neutral-400 hover:border-neutral-300"
                }`}
              >
                <div className="text-base font-extrabold">{count}</div>
                <div className="text-[11px] text-neutral-500 mt-0.5">Questions</div>
              </button>
            ))}
          </div>
        </div>

        {/* 2. Default Difficulty */}
        <div className="space-y-2.5">
          <label className="text-xs font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400 block">
            Default Examination Difficulty
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {(
              [
                { id: "beginner", label: "Beginner", desc: "Basic definitions & aims" },
                { id: "intermediate", label: "Intermediate", desc: "Step-by-step logic" },
                { id: "advanced", label: "Advanced", desc: "Critical derivations" },
                { id: "mixed", label: "Mixed", desc: "Adaptive progression" },
              ] as const
            ).map((diff) => (
              <button
                key={diff.id}
                type="button"
                onClick={() => handleDifficultyChange(diff.id)}
                className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                  prefs.defaultDifficulty === diff.id
                    ? "border-emerald-600 bg-emerald-50/50 dark:bg-emerald-950/20 text-neutral-900 dark:text-white font-bold ring-2 ring-emerald-500/20"
                    : "border-neutral-200 dark:border-neutral-800 bg-neutral-50/40 dark:bg-neutral-800/20 text-neutral-600 dark:text-neutral-400 hover:border-neutral-300"
                }`}
              >
                <div className="text-xs font-bold">{diff.label}</div>
                <div className="text-[10px] text-neutral-500 mt-0.5 line-clamp-1">
                  {diff.desc}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* 3. Preferred Focus Area */}
        <div className="space-y-2.5">
          <label className="text-xs font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400 block">
            Preferred Question Focus
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {(
              [
                { id: "mixed", label: "Mixed Topics" },
                { id: "theory", label: "Theory & Principles" },
                { id: "procedure", label: "Experimental Procedure" },
                { id: "apparatus", label: "Apparatus & Setup" },
                { id: "observations", label: "Observations & Calculations" },
                { id: "precautions", label: "Safety Precautions" },
              ] as const
            ).map((focusItem) => (
              <button
                key={focusItem.id}
                type="button"
                onClick={() => handleFocusChange(focusItem.id)}
                className={`p-3 rounded-xl border text-left transition-all cursor-pointer ${
                  prefs.preferredFocus === focusItem.id
                    ? "border-emerald-600 bg-emerald-50/50 dark:bg-emerald-950/20 text-neutral-900 dark:text-white font-bold ring-2 ring-emerald-500/20"
                    : "border-neutral-200 dark:border-neutral-800 bg-neutral-50/40 dark:bg-neutral-800/20 text-neutral-600 dark:text-neutral-400 hover:border-neutral-300"
                }`}
              >
                <div className="text-xs font-semibold">{focusItem.label}</div>
              </button>
            ))}
          </div>
        </div>

        {/* Submit */}
        <div className="flex justify-end pt-3 border-t border-neutral-100 dark:border-neutral-800">
          <button
            type="submit"
            disabled={isSaving}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold text-white bg-neutral-900 dark:bg-white dark:text-neutral-900 hover:bg-neutral-800 dark:hover:bg-neutral-100 transition-colors shadow-sm cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Saving…
              </>
            ) : (
              <>
                <Save className="w-3.5 h-3.5" />
                Save Study Defaults
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
};

export default StudyPreferencesSection;
