import React, { useState } from "react";
import {
  LogOut,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  Home,
  UserPlus,
  X,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import { useClerk } from "@clerk/clerk-react";
import { useAuth } from "../../context/useAuth.ts";

interface AccountActionsSectionProps {
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const AccountActionsSection: React.FC<AccountActionsSectionProps> = ({
  user,
  onNavigate,
}) => {
  const [showSignOutModal, setShowSignOutModal] = useState(false);
  const [showExitGuestModal, setShowExitGuestModal] = useState(false);

  const { signOut } = useClerk();
  const authContext = useAuth();

  const handleConfirmSignOut = async () => {
    try {
      localStorage.removeItem("pracprep_user");
    } catch {
      // Safe fallback
    }
    try {
      await authContext?.logout();
    } catch {
      // Safe fallback
    }
    try {
      await signOut();
    } catch {
      // Safe fallback
    }
    setShowSignOutModal(false);
    onNavigate("/");
  };

  const handleConfirmExitGuest = () => {
    setShowExitGuestModal(false);
    onNavigate("/");
  };

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-7 shadow-xs space-y-6">
      <div className="pb-4 border-b border-neutral-100 dark:border-neutral-800">
        <h3 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-neutral-500 dark:text-neutral-400" />
          Account & Session Actions
        </h3>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
          Manage your current workspace authentication session and security lifecycle.
        </p>
      </div>

      {user.isGuest ? (
        /* Guest Mode Session Actions */
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
            <div className="space-y-1">
              <h4 className="text-xs font-bold text-neutral-900 dark:text-white">
                Temporary Guest Session
              </h4>
              <p className="text-xs text-neutral-500 dark:text-neutral-400 max-w-lg leading-relaxed">
                Guest sessions store your lab preparation locally. Navigating away does not erase your data, but creating an account enables persistent cross-device study.
              </p>
            </div>
            <div className="flex items-center gap-2.5 flex-shrink-0">
              <button
                type="button"
                onClick={() => onNavigate("/signup")}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                <UserPlus className="w-3.5 h-3.5" />
                Register Account
              </button>
              <button
                type="button"
                onClick={() => setShowExitGuestModal(true)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-neutral-100 dark:bg-neutral-800 hover:bg-neutral-200 dark:hover:bg-neutral-700 text-neutral-700 dark:text-neutral-300 text-xs font-semibold transition-colors"
              >
                <Home className="w-3.5 h-3.5" />
                Exit Guest Mode
              </button>
            </div>
          </div>
        </div>
      ) : (
        /* Authenticated Student Actions */
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
            <div className="space-y-1">
              <h4 className="text-xs font-bold text-neutral-900 dark:text-white">
                Sign Out of Workspace
              </h4>
              <p className="text-xs text-neutral-500 dark:text-neutral-400 max-w-lg leading-relaxed">
                End your active authentication session on this device. Your saved experiments and viva records will remain preserved in browser storage.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowSignOutModal(true)}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-neutral-100 dark:bg-neutral-800 hover:bg-red-50 dark:hover:bg-red-950/40 border border-neutral-200 dark:border-neutral-700 hover:border-red-200 dark:hover:border-red-800 text-neutral-700 dark:text-neutral-300 hover:text-red-700 dark:hover:text-red-400 text-xs font-semibold transition-all flex-shrink-0"
            >
              <LogOut className="w-3.5 h-3.5" />
              Sign Out
            </button>
          </div>

          {/* Account Deletion Notice */}
          <div className="p-4 rounded-xl border border-neutral-200/80 dark:border-neutral-800/80 bg-neutral-50/50 dark:bg-neutral-900/50 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-neutral-400 dark:text-neutral-500 shrink-0 mt-0.5" />
            <div className="space-y-1 text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              <span className="font-semibold text-neutral-800 dark:text-neutral-200">
                Account Deletion Policy:
              </span>{" "}
              PracPrep currently operates as a local-first engineering companion. Centralized cloud account deletion is managed by institutional identity providers. To wipe all local study data, viva transcripts, and experiments from this browser, use the{" "}
              <span className="font-semibold text-neutral-900 dark:text-neutral-100">
                Clear Local Data
              </span>{" "}
              action in the Data & Privacy section.
            </div>
          </div>
        </div>
      )}

      {/* Sign Out Confirmation Modal */}
      {showSignOutModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/50 backdrop-blur-xs animate-in fade-in duration-200"
        >
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 flex items-center justify-center">
                  <LogOut className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                    Sign Out of PracPrep
                  </h3>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    Are you sure you want to exit your session?
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowSignOutModal(false)}
                className="p-1 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
                aria-label="Close modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              Your saved laboratory experiments, checklists, and viva session attempts are preserved on this browser. Any unsaved edits in active forms will be discarded.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowSignOutModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmSignOut}
                className="px-4 py-2 rounded-xl bg-neutral-900 hover:bg-neutral-800 dark:bg-white dark:hover:bg-neutral-100 text-white dark:text-neutral-900 text-xs font-semibold shadow-xs transition-colors"
              >
                Confirm Sign Out
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Exit Guest Confirmation Modal */}
      {showExitGuestModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/50 backdrop-blur-xs animate-in fade-in duration-200"
        >
          <div className="w-full max-w-md rounded-2xl bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 p-6 shadow-2xl space-y-5 animate-in zoom-in-95 duration-200">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 flex items-center justify-center">
                  <Home className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
                    Return to Landing Page
                  </h3>
                  <p className="text-xs text-neutral-500 dark:text-neutral-400">
                    Exit temporary guest session
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setShowExitGuestModal(false)}
                className="p-1 rounded-lg text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200"
                aria-label="Close modal"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
              Your guest experiments and viva transcripts remain stored in this browser session. You can return anytime or create an account to secure permanent access.
            </p>

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowExitGuestModal(false)}
                className="px-4 py-2 rounded-xl text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                Continue Studying
              </button>
              <button
                type="button"
                onClick={handleConfirmExitGuest}
                className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-neutral-900 hover:bg-neutral-800 dark:bg-white dark:hover:bg-neutral-100 text-white dark:text-neutral-900 text-xs font-semibold shadow-xs transition-colors"
              >
                Return Home
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AccountActionsSection;
