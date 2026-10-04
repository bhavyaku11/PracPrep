import React from "react";
import { UploadCloud, PenLine } from "lucide-react";
import type { CreationMethod } from "../../types/experiment";

interface CreationMethodSelectorProps {
  selectedMethod: CreationMethod;
  onSelectMethod: (method: CreationMethod) => void;
}

export const CreationMethodSelector: React.FC<CreationMethodSelectorProps> = ({
  selectedMethod,
  onSelectMethod,
}) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
      {/* Option 1: Upload Lab Manual */}
      <button
        type="button"
        onClick={() => onSelectMethod("upload")}
        aria-pressed={selectedMethod === "upload"}
        className={`group flex items-center justify-between gap-2 rounded-xl border p-3.5 text-left transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 min-w-0 ${
          selectedMethod === "upload"
            ? "border-emerald-600 bg-emerald-50/40 ring-1 ring-emerald-600 shadow-2xs"
            : "border-neutral-200/90 bg-white hover:border-neutral-300 hover:bg-neutral-50/50"
        }`}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors ${
              selectedMethod === "upload"
                ? "bg-emerald-100 text-emerald-800"
                : "bg-neutral-100 text-neutral-600"
            }`}
          >
            <UploadCloud className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h3 className="font-jakarta text-sm font-semibold text-neutral-900 truncate">
              Upload Lab Manual
            </h3>
            <p className="text-xs text-neutral-500 truncate">PDF, DOCX, or text file</p>
          </div>
        </div>

        <span className="shrink-0 rounded-full bg-emerald-100/90 px-2 py-0.5 text-[10px] font-semibold text-emerald-800">
          Recommended
        </span>
      </button>

      {/* Option 2: Enter Details Manually */}
      <button
        type="button"
        onClick={() => onSelectMethod("manual")}
        aria-pressed={selectedMethod === "manual"}
        className={`group flex items-center justify-between rounded-xl border p-3.5 text-left transition-all duration-150 outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
          selectedMethod === "manual"
            ? "border-emerald-600 bg-emerald-50/40 ring-1 ring-emerald-600 shadow-2xs"
            : "border-neutral-200/90 bg-white hover:border-neutral-300 hover:bg-neutral-50/50"
        }`}
      >
        <div className="flex items-center gap-3">
          <div
            className={`flex h-9 w-9 items-center justify-center rounded-lg transition-colors ${
              selectedMethod === "manual"
                ? "bg-emerald-100 text-emerald-800"
                : "bg-neutral-100 text-neutral-600"
            }`}
          >
            <PenLine className="h-4 w-4" />
          </div>
          <div>
            <h3 className="font-jakarta text-sm font-semibold text-neutral-900">
              Enter Details Manually
            </h3>
            <p className="text-xs text-neutral-500">Structured form input</p>
          </div>
        </div>
      </button>
    </div>
  );
};

export default CreationMethodSelector;
