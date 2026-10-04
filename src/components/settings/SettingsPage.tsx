import React, { useState, useEffect } from "react";
import {
  User,
  Palette,
  BookOpen,
  Shield,
  Info,
  SlidersHorizontal,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import type { UserSettings } from "../../types/settings";
import { settingsStorage } from "../../services/settingsStorage";
import ProfileSettingsSection from "./ProfileSettingsSection";
import AppearanceSettingsSection from "./AppearanceSettingsSection";
import StudyPreferencesSection from "./StudyPreferencesSection";
import DataPrivacySection from "./DataPrivacySection";
import AccountActionsSection from "./AccountActionsSection";
import AboutSettingsSection from "./AboutSettingsSection";

export type SettingsTabId =
  | "profile"
  | "appearance"
  | "study"
  | "data"
  | "about";

interface SettingsPageProps {
  user: UserSession;
  onNavigate: (path: string) => void;
  initialTab?: SettingsTabId;
}

interface TabConfig {
  id: SettingsTabId;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  description: string;
}

const TABS: TabConfig[] = [
  {
    id: "profile",
    label: "Profile",
    icon: User,
    description: "Account details & identity",
  },
  {
    id: "appearance",
    label: "Appearance",
    icon: Palette,
    description: "Theme & content density",
  },
  {
    id: "study",
    label: "Study Preferences",
    icon: BookOpen,
    description: "Viva simulator defaults",
  },
  {
    id: "data",
    label: "Data & Privacy",
    icon: Shield,
    description: "Local storage & export",
  },
  {
    id: "about",
    label: "About PracPrep",
    icon: Info,
    description: "System overview & info",
  },
];

export const SettingsPage: React.FC<SettingsPageProps> = ({
  user,
  onNavigate,
  initialTab = "profile",
}) => {
  const [activeTab, setActiveTab] = useState<SettingsTabId>(initialTab);
  const [settings, setSettings] = useState<UserSettings>(() =>
    settingsStorage.getSettings(user)
  );

  // Synchronize settings if modified externally or via subscriber
  useEffect(() => {
    return settingsStorage.subscribe(() => {
      setSettings(settingsStorage.getSettings(user));
    });
  }, [user]);

  // Synchronize remote settings on mount / user change if authenticated
  useEffect(() => {
    if (user && !user.isGuest) {
      void settingsStorage.syncRemoteSettings(user).catch((err) => {
        console.warn("Initial remote settings sync failed:", err);
      });
    }
  }, [user]);

  const handleUpdateSettings = (newSettings: UserSettings) => {
    setSettings(newSettings);
  };

  return (
    <div className="w-full max-w-5xl mx-auto space-y-6 pb-12 animate-in fade-in duration-150">
      {/* Page Header */}
      <div className="border-b border-neutral-200/80 dark:border-neutral-800 pb-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-neutral-900 dark:text-white flex items-center gap-2.5">
              <SlidersHorizontal className="w-6 h-6 text-neutral-700 dark:text-neutral-300" />
              Settings
            </h1>
            <p className="text-sm text-neutral-500 dark:text-neutral-400 mt-1">
              Manage your account, preferences, and PracPrep experience.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 border border-neutral-200/80 dark:border-neutral-700/80">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
              {user.isGuest ? "Guest Environment" : "Enrolled Student"}
            </span>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mt-6 flex overflow-x-auto no-scrollbar gap-1.5 p-1 rounded-xl bg-neutral-100/80 dark:bg-neutral-800/80 border border-neutral-200/60 dark:border-neutral-700/60">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-semibold whitespace-nowrap transition-all outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
                  isActive
                    ? "bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white shadow-2xs"
                    : "text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-neutral-200 hover:bg-white/50 dark:hover:bg-neutral-700/50"
                }`}
                aria-selected={isActive}
                role="tab"
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-emerald-600 dark:text-emerald-400" : "text-neutral-400"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab Panels */}
      <div className="space-y-6">
        {activeTab === "profile" && (
          <div className="space-y-6 animate-in fade-in duration-150">
            <ProfileSettingsSection user={user} onNavigate={onNavigate} />
            <AccountActionsSection user={user} onNavigate={onNavigate} />
          </div>
        )}

        {activeTab === "appearance" && (
          <div className="animate-in fade-in duration-150">
            <AppearanceSettingsSection
              settings={settings}
              onUpdateSettings={handleUpdateSettings}
            />
          </div>
        )}

        {activeTab === "study" && (
          <div className="animate-in fade-in duration-150">
            <StudyPreferencesSection
              settings={settings}
              onUpdateSettings={handleUpdateSettings}
              user={user}
            />
          </div>
        )}

        {activeTab === "data" && (
          <div className="animate-in fade-in duration-150">
            <DataPrivacySection user={user} />
          </div>
        )}

        {activeTab === "about" && (
          <div className="animate-in fade-in duration-150">
            <AboutSettingsSection onNavigate={onNavigate} />
          </div>
        )}
      </div>
    </div>
  );
};

export default SettingsPage;
