import React, { useState } from "react";
import {
  Database,
  Download,
  Trash2,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  FileText,
  Clock,
  HardDrive,
  X,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import { experimentStorage } from "../../services/experimentStorage";
import { vivaStorage } from "../../services/vivaStorage";
import { settingsStorage } from "../../services/settingsStorage";

interface DataPrivacySectionProps {
  user: UserSession;
}

export const DataPrivacySection: React.FC<DataPrivacySectionProps> = ({ user }) => {
  const [experimentsCount, setExperimentsCount] = useState(() =>
    experimentStorage.getExperiments(user).length
  );
  const [sessionsCount, setSessionsCount] = useState(() =>
    vivaStorage.getSessions(user).filter((s) => s.isCompleted).length
  );

  const [showClearConfirm, setShowClearConfirm] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [clearSuccess, setClearSuccess] = useState(false);
  const [exportSuccess, setExportSuccess] = useState(false);

  const handleExportData = () => {
    try {
      const payload = settingsStorage.exportUserData(user);
      const jsonString = `data:text/json;charset=utf-8,${encodeURIComponent(
        JSON.stringify(payload, null, 2)
      )}`;

      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", jsonString);
      const dateStr = new Date().toISOString().split("T")[0];
      const scopeName = user.isGuest ? "guest" : (user.name || "student").toLowerCase().replace(/\s+/g, "_");
      downloadAnchor.setAttribute("download", `pracprep_${scopeName}_export_${dateStr}.json`);
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();

      setExportSuccess(true);
      setTimeout(() => setExportSuccess(false), 3500);
    } catch (err) {
      console.error("Export failed:", err);
    }
  };

  const handleConfirmClear = () => {
    setClearing(true);
    setTimeout(() => {
      settingsStorage.clearAllUserData(user);
      setExperimentsCount(0);
      setSessionsCount(0);
      setClearing(false);
      setShowClearConfirm(false);
      setClearSuccess(true);
      setTimeout(() => setClearSuccess(false), 4000);
    }, 400);
  };

  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-7 shadow-sm space-y-7">
      <div className="pb-4 border-b border-neutral-100 dark:border-neutral-800">
        <h2 className="text-lg font-bold text-neutral-900 dark:text-white flex items-center gap-2">
          <Database className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
          Data Management & Storage Privacy
        </h2>
        <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
          Review stored records, export your learning data, or clear local browser storage
        </p>
      </div>

      {clearSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>Local storage cleared successfully for this session. All experiment and viva records have been reset.</span>
        </div>
      )}

      {exportSuccess && (
        <div className="p-3.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 text-xs text-emerald-800 dark:text-emerald-300 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-emerald-600" />
          <span>Data package downloaded to your device as JSON.</span>
        </div>
      )}

      {/* Storage Overview Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
        <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-neutral-500 mb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Saved Experiments
            </span>
            <FileText className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-neutral-900 dark:text-white">
            {experimentsCount}
          </div>
          <p className="text-[11px] text-neutral-500 mt-0.5">Stored in active session</p>
        </div>

        <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-neutral-500 mb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Completed Vivas
            </span>
            <Clock className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <div className="text-xl font-bold text-neutral-900 dark:text-white">
            {sessionsCount}
          </div>
          <p className="text-[11px] text-neutral-500 mt-0.5">Evaluated sessions recorded</p>
        </div>

        <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center justify-between text-neutral-500 mb-1">
            <span className="text-[11px] font-semibold uppercase tracking-wider">
              Storage Architecture
            </span>
            <HardDrive className="w-3.5 h-3.5 text-neutral-400" />
          </div>
          <div className="text-xs font-bold text-neutral-900 dark:text-white truncate">
            {user.isGuest ? "Guest Local Storage" : "Session Scoped"}
          </div>
          <p className="text-[11px] text-neutral-500 mt-0.5">Browser client-side only</p>
        </div>
      </div>

      {/* Export & Clear Actions */}
      <div className="space-y-4 pt-2">
        {/* Export Data */}
        <div className="p-4 rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50/40 dark:bg-neutral-800/20 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-neutral-900 dark:text-white flex items-center gap-1.5">
              <Download className="w-4 h-4 text-emerald-600" />
              Export My Learning Data
            </h3>
            <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5 max-w-lg">
              Download a complete JSON export of your experiment manuals, preparation checklists, oral viva evaluation scores, and study preferences.
            </p>
          </div>

          <button
            onClick={handleExportData}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold text-neutral-800 dark:text-neutral-200 bg-white dark:bg-neutral-800 border border-neutral-300 dark:border-neutral-700 rounded-xl hover:bg-neutral-50 dark:hover:bg-neutral-700 shadow-2xs transition-colors flex-shrink-0 cursor-pointer"
          >
            <Download className="w-3.5 h-3.5 text-emerald-600" />
            Download JSON Export
          </button>
        </div>

        {/* Clear Data */}
        <div className="p-4 rounded-xl border border-red-200 dark:border-red-900/30 bg-red-50/30 dark:bg-red-950/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-bold text-red-900 dark:text-red-300 flex items-center gap-1.5">
              <Trash2 className="w-4 h-4 text-red-600" />
              Clear Local PracPrep Data
            </h3>
            <p className="text-xs text-red-800/80 dark:text-red-400/80 mt-0.5 max-w-lg">
              Erases all experiment records, checklist progress, and viva session history saved for this {user.isGuest ? "guest session" : "student account"} on this browser.
            </p>
          </div>

          <button
            onClick={() => setShowClearConfirm(true)}
            className="inline-flex items-center justify-center gap-1.5 px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-xl shadow-2xs transition-colors flex-shrink-0 cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear Local Data
          </button>
        </div>
      </div>

      {/* Privacy Notice */}
      <div className="p-4 rounded-xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800 space-y-1.5 text-xs text-neutral-600 dark:text-neutral-400">
        <div className="flex items-center gap-2 font-bold text-neutral-900 dark:text-white">
          <ShieldCheck className="w-4 h-4 text-emerald-600" />
          PracPrep Privacy Policy & Storage Transparency
        </div>
        <p className="leading-relaxed">
          PracPrep uses local-first architecture. All uploaded lab manuals, preparation notes, checklists, and oral examination answers are stored directly in your browser's private local storage. No lab manual documents or evaluation transcripts are sent to third-party ad networks or tracking servers.
        </p>
      </div>

      {/* Confirmation Modal for Clearing Data */}
      {showClearConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs"
          role="dialog"
          aria-modal="true"
        >
          <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-start justify-between">
              <div className="w-10 h-10 rounded-xl bg-red-100 dark:bg-red-950 text-red-600 flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <button
                onClick={() => setShowClearConfirm(false)}
                className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-2">
              <h3 className="text-base font-bold text-neutral-900 dark:text-white">
                Clear All Local Data for this Session?
              </h3>
              <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
                This will permanently delete <strong>{experimentsCount} experiment records</strong> and <strong>{sessionsCount} completed viva sessions</strong> stored for your session.
              </p>
              <div className="p-3 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 text-[11px] text-amber-800 dark:text-amber-300">
                Warning: This action cannot be undone unless you have already downloaded a JSON backup via "Export My Data".
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-neutral-100 dark:border-neutral-800">
              <button
                onClick={() => setShowClearConfirm(false)}
                disabled={clearing}
                className="px-3 py-1.5 text-xs font-semibold text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 rounded-lg transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmClear}
                disabled={clearing}
                className="px-4 py-2 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-xl shadow-sm transition-colors cursor-pointer"
              >
                {clearing ? "Clearing..." : "Yes, Permanently Clear Data"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataPrivacySection;
