import React from "react";
import { Plus } from "lucide-react";

interface PrimaryActionCardProps {
  onNavigate: (path: string) => void;
}

export const PrimaryActionCard: React.FC<PrimaryActionCardProps> = ({ onNavigate }) => {
  return (
    <section
      aria-label="New Experiment Action"
      className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 rounded-xl border border-neutral-200/90 bg-white p-5 shadow-2xs"
    >
      <div className="space-y-1">
        <h2 className="font-jakarta text-lg font-bold tracking-tight text-neutral-900">
          New Experiment
        </h2>
        <p className="text-xs sm:text-sm text-neutral-500">
          Upload a lab manual or enter details to start preparing.
        </p>
      </div>

      <button
        type="button"
        onClick={() => onNavigate("/create-experiment")}
        className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-neutral-900 px-5 text-xs sm:text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 shrink-0 w-full sm:w-auto"
      >
        <Plus className="h-4 w-4" />
        <span>New Experiment</span>
      </button>
    </section>
  );
};

export default PrimaryActionCard;
