import React, { useState } from "react";
import {
  User,
  Mail,
  Check,
  UserCheck,
  Building,
  Save,
  RotateCcw,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import { settingsStorage } from "../../services/settingsStorage";

interface ProfileSettingsSectionProps {
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const ProfileSettingsSection: React.FC<ProfileSettingsSectionProps> = ({
  user,
  onNavigate,
}) => {
  const [name, setName] = useState(user.name || "Student");
  const [university, setUniversity] = useState(user.university || "Engineering Faculty");
  const [isEditing, setIsEditing] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getInitials = (text?: string) => {
    if (!text) return "ST";
    const parts = text.trim().split(/\s+/);
    if (parts.length >= 2) {
      return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
    }
    return text.slice(0, 2).toUpperCase();
  };

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setError("Name cannot be empty.");
      return;
    }

    settingsStorage.updateUserProfile({
      name: name.trim(),
      university: university.trim(),
    });

    setError(null);
    setIsEditing(false);
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  const handleCancel = () => {
    setName(user.name || "Student");
    setUniversity(user.university || "Engineering Faculty");
    setError(null);
    setIsEditing(false);
  };

  if (user.isGuest) {
    return (
      <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-7 shadow-sm space-y-6">
        <div>
          <h2 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <UserCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            Guest Profile
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-1">
            You are currently exploring PracPrep in a session-scoped guest mode.
          </p>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center gap-4 p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
          <div className="w-14 h-14 rounded-full bg-neutral-200 dark:bg-neutral-700 flex items-center justify-center text-neutral-700 dark:text-neutral-200 font-bold text-lg flex-shrink-0">
            GP
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-neutral-900 dark:text-white">
                Guest Student
              </span>
              <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
                Active Session
              </span>
            </div>
            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              Your experiments, checklists, and oral viva attempts are saved locally on this computer. To sync your preparation across devices or lock in your records, create a full account.
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3 pt-2">
          <button
            onClick={() => onNavigate("/signup")}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 text-xs font-semibold hover:bg-neutral-800 dark:hover:bg-neutral-100 transition-colors shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5 text-emerald-400 dark:text-emerald-600" />
            Create Account
          </button>
          <button
            onClick={() => onNavigate("/login")}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-xl text-xs font-semibold text-neutral-700 dark:text-neutral-300 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
          >
            Sign In with Existing Account
            <ArrowRight className="w-3 h-3 text-neutral-400" />
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-7 shadow-sm space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <User className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            Student Profile
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Manage your personal details and academic identification
          </p>
        </div>

        {saveSuccess && (
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-semibold bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">
            <Check className="w-3.5 h-3.5 text-emerald-600" />
            Profile updated successfully
          </span>
        )}
      </div>

      {/* Avatar and Identity Preview */}
      <div className="flex items-center gap-4 p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
        <div className="w-14 h-14 rounded-full bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border-2 border-emerald-500 flex items-center justify-center font-bold text-lg flex-shrink-0">
          {getInitials(name)}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
              {name}
            </h3>
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300">
              Verified Student
            </span>
          </div>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            {user.email || "student@university.edu"} • {university}
          </p>
        </div>
      </div>

      {/* Profile Form */}
      <form onSubmit={handleSave} className="space-y-4">
        {error && (
          <div className="p-3 rounded-xl bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 text-xs text-red-700 dark:text-red-300">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Display Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-neutral-700 dark:text-neutral-300 block">
              Display Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                setIsEditing(true);
              }}
              placeholder="e.g. Alex Morgan"
              className="w-full px-3.5 py-2 text-sm rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 text-neutral-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          {/* Academic Department / Faculty */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-neutral-700 dark:text-neutral-300 flex items-center gap-1.5">
              <Building className="w-3.5 h-3.5 text-neutral-400" />
              University / Faculty
            </label>
            <input
              type="text"
              value={university}
              onChange={(e) => {
                setUniversity(e.target.value);
                setIsEditing(true);
              }}
              placeholder="e.g. Department of Mechanical Engineering"
              className="w-full px-3.5 py-2 text-sm rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-950 text-neutral-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>
        </div>

        {/* Read-Only Email Field */}
        <div className="space-y-1.5">
          <label className="text-xs font-bold text-neutral-700 dark:text-neutral-300 flex items-center gap-1.5">
            <Mail className="w-3.5 h-3.5 text-neutral-400" />
            Institutional Email Address
          </label>
          <div className="relative">
            <input
              type="email"
              value={user.email || "student@university.edu"}
              readOnly
              disabled
              className="w-full px-3.5 py-2 text-sm rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-100 dark:bg-neutral-800/60 text-neutral-500 cursor-not-allowed"
            />
            <span className="absolute right-3 top-2.5 text-[10px] uppercase font-bold text-neutral-400">
              Read-Only
            </span>
          </div>
          <p className="text-[11px] text-neutral-500 leading-normal">
            Your login email is managed by your university authentication profile and cannot be modified directly in local preferences.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-3 border-t border-neutral-100 dark:border-neutral-800">
          {isEditing && (
            <button
              type="button"
              onClick={handleCancel}
              className="inline-flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-neutral-600 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white rounded-xl transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Cancel Changes
            </button>
          )}

          <button
            type="submit"
            disabled={!isEditing}
            className={`inline-flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-semibold shadow-sm transition-all ${
              isEditing
                ? "bg-neutral-900 dark:bg-white text-white dark:text-neutral-900 hover:bg-neutral-800 dark:hover:bg-neutral-100 cursor-pointer"
                : "bg-neutral-200 dark:bg-neutral-800 text-neutral-400 cursor-not-allowed"
            }`}
          >
            <Save className="w-3.5 h-3.5" />
            Save Profile
          </button>
        </div>
      </form>
    </div>
  );
};

export default ProfileSettingsSection;
