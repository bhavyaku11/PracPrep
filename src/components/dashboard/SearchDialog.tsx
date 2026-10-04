import React, { useEffect, useState, useRef, useMemo } from "react";
import { Search, X, FlaskConical, MessageSquareCode, TrendingUp, Settings, Plus, ArrowRight, BookOpen } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface SearchDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigate: (path: string) => void;
  experiments?: ExperimentRecord[];
}

interface SearchItem {
  id: string;
  title: string;
  category: string;
  path: string;
  icon: React.ElementType;
  subtitle?: string;
}

const STATIC_SEARCH_ITEMS: SearchItem[] = [
  { id: "new", title: "New Experiment (Upload Manual)", category: "Action", path: "/create-experiment", icon: Plus },
  { id: "exp", title: "My Experiments", category: "Workspace", path: "/experiments", icon: FlaskConical },
  { id: "viva", title: "Viva Practice & Conceptual Prep", category: "Learning", path: "/viva-practice", icon: MessageSquareCode },
  { id: "progress", title: "Progress & Revision Notes", category: "Learning", path: "/progress", icon: TrendingUp },
  { id: "settings", title: "Workspace & Profile Settings", category: "Preferences", path: "/settings", icon: Settings },
];

export const SearchDialog: React.FC<SearchDialogProps> = ({
  isOpen,
  onClose,
  onNavigate,
  experiments = [],
}) => {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [isOpen]);

  const handleClose = React.useCallback(() => {
    setQuery("");
    onClose();
  }, [onClose]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        handleClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, handleClose]);

  const allItems: SearchItem[] = useMemo(() => {
    const experimentItems: SearchItem[] = experiments.map((exp) => ({
      id: `exp-${exp.id}`,
      title: exp.title,
      category: `Experiment (${exp.subject || "Lab"})`,
      path: `/experiments/${exp.id}`,
      icon: BookOpen,
      subtitle: exp.objective ? exp.objective.slice(0, 60) + "..." : undefined,
    }));

    return [...STATIC_SEARCH_ITEMS, ...experimentItems];
  }, [experiments]);

  if (!isOpen) return null;

  const q = query.trim().toLowerCase();
  const filteredItems = q
    ? allItems.filter(
        (item) =>
          item.title.toLowerCase().includes(q) ||
          item.category.toLowerCase().includes(q) ||
          (item.subtitle && item.subtitle.toLowerCase().includes(q))
      )
    : STATIC_SEARCH_ITEMS;

  const handleSelect = (path: string) => {
    setQuery("");
    onNavigate(path);
    onClose();
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Search Workspace"
      className="fixed inset-0 z-50 flex items-start justify-center pt-20 sm:pt-24 px-4 bg-neutral-950/50 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={handleClose}
    >
      <div
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 shadow-2xl animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Bar */}
        <div className="flex items-center border-b border-neutral-200 dark:border-neutral-800 px-4 py-3">
          <Search className="h-4 w-4 text-neutral-400 shrink-0 mr-3" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search experiments, viva topics, actions..."
            className="w-full bg-transparent text-sm text-neutral-900 dark:text-white placeholder:text-neutral-400 dark:placeholder:text-neutral-500 outline-none"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="text-neutral-400 hover:text-neutral-600 dark:hover:text-neutral-200 p-1"
              aria-label="Clear search input"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <kbd className="hidden sm:inline-block ml-2 rounded border border-neutral-200 dark:border-neutral-700 bg-neutral-100 dark:bg-neutral-800 px-1.5 py-0.5 text-[10px] font-medium text-neutral-500 dark:text-neutral-400">
            ESC
          </kbd>
        </div>

        {/* Results List */}
        <div className="max-h-72 overflow-y-auto p-2">
          {filteredItems.length > 0 ? (
            <div className="space-y-1">
              <div className="px-2 py-1 text-[10px] font-semibold text-neutral-400 uppercase tracking-wider">
                {query ? "Search Results" : "Suggested Navigation"}
              </div>
              {filteredItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => handleSelect(item.path)}
                    className="flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-950 dark:hover:text-white transition-colors group"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-neutral-100 dark:bg-neutral-800 group-hover:bg-white dark:group-hover:bg-neutral-700 text-neutral-600 dark:text-neutral-400 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 shrink-0">
                        <Icon className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="font-medium text-xs sm:text-sm truncate">{item.title}</p>
                        {item.subtitle && (
                          <p className="text-[10px] text-neutral-400 dark:text-neutral-500 truncate">
                            {item.subtitle}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-[11px] text-neutral-400 dark:text-neutral-500 group-hover:text-neutral-600 dark:group-hover:text-neutral-300">
                        {item.category}
                      </span>
                      <ArrowRight className="h-3 w-3 text-neutral-400 opacity-0 group-hover:opacity-100 transition-opacity" />
                    </div>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-neutral-500 dark:text-neutral-400">
              No matching modules or experiments found for &quot;{query}&quot;.
            </div>
          )}
        </div>

        {/* Footer info */}
        <div className="border-t border-neutral-100 dark:border-neutral-800 bg-neutral-50/70 dark:bg-neutral-900/90 px-4 py-2 text-[11px] text-neutral-500 dark:text-neutral-400 flex items-center justify-between">
          <span>Search PracPrep Student Workspace</span>
          <span>Quick Navigation</span>
        </div>
      </div>
    </div>
  );
};

export default SearchDialog;
