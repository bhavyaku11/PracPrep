import React from "react";
import { FlaskConical, MessageSquareCode, TrendingUp, ChevronRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface QuickAccessItem {
  id: string;
  title: string;
  path: string;
  icon: LucideIcon;
}

interface QuickAccessProps {
  onNavigate: (path: string) => void;
}

const QUICK_ACTIONS: QuickAccessItem[] = [
  {
    id: "my-experiments",
    title: "My Experiments",
    path: "/experiments",
    icon: FlaskConical,
  },
  {
    id: "viva-practice",
    title: "Viva Practice",
    path: "/viva-practice",
    icon: MessageSquareCode,
  },
  {
    id: "progress-revision",
    title: "Progress & Revision",
    path: "/progress",
    icon: TrendingUp,
  },
];

export const QuickAccess: React.FC<QuickAccessProps> = ({ onNavigate }) => {
  return (
    <section aria-labelledby="quick-access-heading" className="space-y-2.5">
      <h2
        id="quick-access-heading"
        className="font-jakarta text-xs font-semibold uppercase tracking-wider text-neutral-500"
      >
        Quick Access
      </h2>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {QUICK_ACTIONS.map((action) => {
          const Icon = action.icon;
          return (
            <button
              key={action.id}
              type="button"
              onClick={() => onNavigate(action.path)}
              className="group flex items-center justify-between gap-2 rounded-xl border border-neutral-200/90 bg-white p-3.5 text-left shadow-2xs transition-all hover:border-neutral-300 hover:bg-neutral-50/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 min-w-0"
            >
              <div className="flex items-center gap-3 min-w-0">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-neutral-100 text-neutral-700 transition-colors group-hover:bg-emerald-50 group-hover:text-emerald-700">
                  <Icon className="h-4 w-4" />
                </div>
                <span className="font-jakarta text-sm font-semibold text-neutral-900 group-hover:text-emerald-800 transition-colors truncate">
                  {action.title}
                </span>
              </div>
              <ChevronRight className="h-4 w-4 shrink-0 text-neutral-400 transition-transform group-hover:translate-x-0.5 group-hover:text-neutral-700" />
            </button>
          );
        })}
      </div>
    </section>
  );
};

export default QuickAccess;
