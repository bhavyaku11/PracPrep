import React from "react";
import { Search, X, ArrowUpDown, Filter, RotateCcw } from "lucide-react";
import type { SortField } from "../../types/experiment";

interface ExperimentToolbarProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  statusFilter: string;
  onStatusFilterChange: (status: string) => void;
  sortBy: SortField;
  onSortByChange: (sort: SortField) => void;
  onClearFilters: () => void;
  hasActiveFilters: boolean;
  totalFilteredCount: number;
  totalCount: number;
  availableStatuses: { id: string; label: string; count: number }[];
}

export const ExperimentToolbar: React.FC<ExperimentToolbarProps> = ({
  searchQuery,
  onSearchChange,
  statusFilter,
  onStatusFilterChange,
  sortBy,
  onSortByChange,
  onClearFilters,
  hasActiveFilters,
  totalFilteredCount,
  totalCount,
  availableStatuses,
}) => {
  return (
    <div className="space-y-3">
      {/* Top row: Search input + Sort dropdown + Clear filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
        {/* Search input with immediate update & clear button */}
        <div className="relative flex-1 min-w-0">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-neutral-400 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder="Search by title, subject, or experiment number..."
            className="w-full h-10 pl-9 pr-9 rounded-xl border border-neutral-200/90 bg-white text-xs sm:text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600/30 shadow-2xs"
            aria-label="Search experiments"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => onSearchChange("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 p-1 text-neutral-400 hover:text-neutral-700 rounded-md transition-colors"
              aria-label="Clear search input"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Right controls: Sort dropdown & Clear Filters */}
        <div className="flex items-center gap-2 shrink-0">
          {/* Sort dropdown */}
          <div className="relative flex items-center">
            <ArrowUpDown className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-neutral-400 pointer-events-none" />
            <select
              value={sortBy}
              onChange={(e) => onSortByChange(e.target.value as SortField)}
              className="h-10 pl-8 pr-7 rounded-xl border border-neutral-200/90 bg-white text-xs font-medium text-neutral-700 outline-none transition-all hover:bg-neutral-50 focus:border-emerald-600 focus:ring-1 focus:ring-emerald-600/30 cursor-pointer shadow-2xs appearance-none"
              aria-label="Sort experiments by"
            >
              <option value="created">Recently Created</option>
              <option value="updated">Recently Updated</option>
              <option value="title_asc">Name: A–Z</option>
              <option value="title_desc">Name: Z–A</option>
            </select>
          </div>

          {/* Reset Filters button if any filter is active */}
          {hasActiveFilters && (
            <button
              type="button"
              onClick={onClearFilters}
              className="inline-flex h-10 items-center justify-center gap-1.5 rounded-xl border border-neutral-300 bg-white px-3 text-xs font-medium text-neutral-700 hover:bg-neutral-50 hover:text-neutral-900 transition-colors shadow-2xs shrink-0"
              title="Reset search and filters"
            >
              <RotateCcw className="h-3.5 w-3.5 text-neutral-400" />
              <span className="hidden sm:inline">Clear</span>
            </button>
          )}
        </div>
      </div>

      {/* Bottom row: Status filter tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-neutral-100">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="hidden sm:inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider text-neutral-400 mr-1.5">
            <Filter className="h-3 w-3" />
            Status:
          </span>

          {availableStatuses.map((tab) => {
            const isSelected = statusFilter === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onStatusFilterChange(tab.id)}
                className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-all ${
                  isSelected
                    ? "bg-neutral-900 text-white shadow-xs"
                    : "bg-white text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900 border border-neutral-200/80 shadow-2xs"
                }`}
              >
                <span>{tab.label}</span>
                <span
                  className={`rounded px-1.5 py-0.2 text-[10px] font-semibold ${
                    isSelected
                      ? "bg-neutral-800 text-neutral-200"
                      : "bg-neutral-100 text-neutral-500"
                  }`}
                >
                  {tab.count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Filter count indicator */}
        {hasActiveFilters && (
          <p className="text-[11px] text-neutral-500 font-medium">
            Showing {totalFilteredCount} of {totalCount}
          </p>
        )}
      </div>
    </div>
  );
};

export default ExperimentToolbar;
