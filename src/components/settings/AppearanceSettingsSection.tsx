import React from "react";
import {
  Sun,
  Moon,
  Laptop,
  Check,
  Eye,
} from "lucide-react";
import type { UserSettings, ThemePreference, DensityPreference } from "../../types/settings";
import { settingsStorage } from "../../services/settingsStorage";

interface AppearanceSettingsSectionProps {
  settings: UserSettings;
  onUpdateSettings: (newSettings: UserSettings) => void;
}

export const AppearanceSettingsSection: React.FC<AppearanceSettingsSectionProps> = ({
  settings,
  onUpdateSettings,
}) => {
  const handleThemeChange = (newTheme: ThemePreference) => {
    const updated = {
      ...settings,
      theme: newTheme,
    };
    settingsStorage.saveSettings(updated);
    onUpdateSettings(updated);
  };

  const handleDensityChange = (density: DensityPreference) => {
    const updated = {
      ...settings,
      density,
    };
    settingsStorage.saveSettings(updated);
    onUpdateSettings(updated);
  };

  const handleReducedMotionToggle = (e: React.ChangeEvent<HTMLInputElement>) => {
    const updated = {
      ...settings,
      reducedMotion: e.target.checked,
    };
    settingsStorage.saveSettings(updated);
    onUpdateSettings(updated);
  };

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-7 shadow-sm space-y-7">
      <div className="pb-4 border-b border-neutral-100 dark:border-neutral-800">
        <h2 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
          <Eye className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          Appearance & Interface
        </h2>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
          Customize color themes, visual contrast, content density, and system motion
        </p>
      </div>

      {/* Theme Selection */}
      <div className="space-y-3">
        <label className="text-xs font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400 block">
          Interface Color Theme
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
          {/* Light Theme Card */}
          <button
            type="button"
            onClick={() => handleThemeChange("light")}
            className={`p-4 rounded-xl border text-left flex flex-col justify-between gap-3 transition-all cursor-pointer ${
              settings.theme === "light"
                ? "border-emerald-600 bg-emerald-50/50 dark:bg-emerald-950/20 ring-2 ring-emerald-500/20"
                : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700 bg-neutral-50/40 dark:bg-neutral-800/20"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="w-8 h-8 rounded-lg bg-amber-100 text-amber-700 flex items-center justify-center">
                <Sun className="w-4 h-4" />
              </div>
              {settings.theme === "light" && (
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                  <Check className="w-3 h-3 stroke-[3]" />
                </span>
              )}
            </div>
            <div>
              <div className="text-sm font-bold text-neutral-900 dark:text-white">
                Light Theme
              </div>
              <div className="text-xs text-neutral-500 mt-0.5">
                Crisp daytime contrast for laboratory reading
              </div>
            </div>
          </button>

          {/* Dark Theme Card */}
          <button
            type="button"
            onClick={() => handleThemeChange("dark")}
            className={`p-4 rounded-xl border text-left flex flex-col justify-between gap-3 transition-all cursor-pointer ${
              settings.theme === "dark"
                ? "border-emerald-600 bg-emerald-50/50 dark:bg-emerald-950/20 ring-2 ring-emerald-500/20"
                : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700 bg-neutral-50/40 dark:bg-neutral-800/20"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="w-8 h-8 rounded-lg bg-neutral-800 text-neutral-100 flex items-center justify-center">
                <Moon className="w-4 h-4" />
              </div>
              {settings.theme === "dark" && (
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                  <Check className="w-3 h-3 stroke-[3]" />
                </span>
              )}
            </div>
            <div>
              <div className="text-sm font-bold text-neutral-900 dark:text-white">
                Dark Theme
              </div>
              <div className="text-xs text-neutral-500 mt-0.5">
                High-contrast dark mode to reduce eye strain
              </div>
            </div>
          </button>

          {/* System Default Card */}
          <button
            type="button"
            onClick={() => handleThemeChange("system")}
            className={`p-4 rounded-xl border text-left flex flex-col justify-between gap-3 transition-all cursor-pointer ${
              settings.theme === "system"
                ? "border-emerald-600 bg-emerald-50/50 dark:bg-emerald-950/20 ring-2 ring-emerald-500/20"
                : "border-neutral-200 dark:border-neutral-800 hover:border-neutral-300 dark:hover:border-neutral-700 bg-neutral-50/40 dark:bg-neutral-800/20"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="w-8 h-8 rounded-lg bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 flex items-center justify-center">
                <Laptop className="w-4 h-4" />
              </div>
              {settings.theme === "system" && (
                <span className="w-5 h-5 rounded-full bg-emerald-600 text-white flex items-center justify-center">
                  <Check className="w-3 h-3 stroke-[3]" />
                </span>
              )}
            </div>
            <div>
              <div className="text-sm font-bold text-neutral-900 dark:text-white">
                System Default
              </div>
              <div className="text-xs text-neutral-500 mt-0.5">
                Automatically matches your OS device preference
              </div>
            </div>
          </button>
        </div>
      </div>

      {/* Content Density Preference */}
      <div className="space-y-3 pt-3 border-t border-neutral-100 dark:border-neutral-800">
        <label className="text-xs font-bold uppercase tracking-wider text-neutral-500 dark:text-neutral-400 block">
          Content Density
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <button
            type="button"
            onClick={() => handleDensityChange("comfortable")}
            className={`p-3.5 rounded-xl border text-left flex items-center justify-between gap-3 transition-colors cursor-pointer ${
              settings.density === "comfortable"
                ? "border-emerald-600 bg-emerald-50/40 dark:bg-emerald-950/20 text-neutral-900 dark:text-white font-semibold"
                : "border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 hover:border-neutral-300"
            }`}
          >
            <div>
              <div className="text-sm font-bold">Comfortable (Standard)</div>
              <div className="text-xs text-neutral-500">Spacious padding and comfortable reading hierarchy</div>
            </div>
            {settings.density === "comfortable" && (
              <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            )}
          </button>

          <button
            type="button"
            onClick={() => handleDensityChange("compact")}
            className={`p-3.5 rounded-xl border text-left flex items-center justify-between gap-3 transition-colors cursor-pointer ${
              settings.density === "compact"
                ? "border-emerald-600 bg-emerald-50/40 dark:bg-emerald-950/20 text-neutral-900 dark:text-white font-semibold"
                : "border-neutral-200 dark:border-neutral-800 text-neutral-600 dark:text-neutral-400 hover:border-neutral-300"
            }`}
          >
            <div>
              <div className="text-sm font-bold">Compact</div>
              <div className="text-xs text-neutral-500">Higher information density for wide laptop displays</div>
            </div>
            {settings.density === "compact" && (
              <Check className="w-4 h-4 text-emerald-600 flex-shrink-0" />
            )}
          </button>
        </div>
      </div>

      {/* Reduced Motion Toggle */}
      <div className="pt-3 border-t border-neutral-100 dark:border-neutral-800 flex items-center justify-between gap-4">
        <div>
          <div className="text-sm font-bold text-neutral-900 dark:text-white">
            Reduced Motion
          </div>
          <div className="text-xs text-neutral-500 max-w-md">
            Minimizes decorative animations and tab transitions across the workspace and oral viva simulator.
          </div>
        </div>

        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={settings.reducedMotion}
            onChange={handleReducedMotionToggle}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-neutral-200 peer-focus:outline-none rounded-full peer dark:bg-neutral-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-neutral-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
        </label>
      </div>
    </div>
  );
};

export default AppearanceSettingsSection;
