import React, { useState, useEffect, useMemo } from "react";
import { Plus, UserCheck, ArrowRight } from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import type { ExperimentRecord, SortField } from "../../types/experiment";
import { experimentStorage } from "../../services/experimentStorage";
import ExperimentSummaryRow from "./ExperimentSummaryRow";
import ExperimentToolbar from "./ExperimentToolbar";
import ExperimentTable from "./ExperimentTable";
import ExperimentCardsList from "./ExperimentCardsList";
import EditExperimentModal from "./EditExperimentModal";
import DeleteExperimentModal from "./DeleteExperimentModal";
import ExperimentEmptyState from "./ExperimentEmptyState";

interface MyExperimentsPageProps {
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const MyExperimentsPage: React.FC<MyExperimentsPageProps> = ({ user, onNavigate }) => {
  const [experiments, setExperiments] = useState<ExperimentRecord[]>(() => {
    return experimentStorage.getExperiments(user);
  });

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<SortField>("created");
  const [editingExperiment, setEditingExperiment] = useState<ExperimentRecord | null>(null);
  const [deletingExperiment, setDeletingExperiment] = useState<ExperimentRecord | null>(null);

  // Subscribe to reactive storage changes
  useEffect(() => {
    const refresh = () => {
      setExperiments(experimentStorage.getExperiments(user));
    };
    const unsubscribe = experimentStorage.subscribe(refresh);
    return unsubscribe;
  }, [user]);

  // Compute status counts for toolbar filter tabs
  const availableStatuses = useMemo(() => {
    const total = experiments.length;
    const drafts = experiments.filter((e) => e.status === "draft").length;
    const inProgress = experiments.filter(
      (e) => e.status === "in-progress" || e.status === "ready" || e.status === "analyzing"
    ).length;
    const completed = experiments.filter((e) => e.status === "completed").length;

    const tabs = [
      { id: "all", label: "All", count: total },
      { id: "draft", label: "Draft", count: drafts },
      { id: "in-progress", label: "In Progress", count: inProgress },
      { id: "completed", label: "Completed", count: completed },
    ];

    return tabs;
  }, [experiments]);

  // Filter & Sort experiments
  const filteredAndSortedExperiments = useMemo(() => {
    return experiments
      .filter((exp) => {
        // Status filter
        if (statusFilter !== "all") {
          if (statusFilter === "in-progress") {
            const isInProgress =
              exp.status === "in-progress" || exp.status === "ready" || exp.status === "analyzing";
            if (!isInProgress) return false;
          } else if (exp.status !== statusFilter) {
            return false;
          }
        }

        // Search query filter (title, subject, experiment number)
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase().trim();
          const matchTitle = exp.title.toLowerCase().includes(q);
          const matchSubject = exp.subject.toLowerCase().includes(q);
          const matchNumber = exp.experimentNumber
            ? exp.experimentNumber.toLowerCase().includes(q)
            : false;

          if (!matchTitle && !matchSubject && !matchNumber) {
            return false;
          }
        }

        return true;
      })
      .sort((a, b) => {
        switch (sortBy) {
          case "updated":
            return b.updatedAtTimestamp - a.updatedAtTimestamp;
          case "title_asc":
            return a.title.localeCompare(b.title);
          case "title_desc":
            return b.title.localeCompare(a.title);
          case "created":
          default:
            return b.createdAtTimestamp - a.createdAtTimestamp;
        }
      });
  }, [experiments, statusFilter, searchQuery, sortBy]);

  const hasActiveFilters = searchQuery.trim() !== "" || statusFilter !== "all";

  const handleClearFilters = () => {
    setSearchQuery("");
    setStatusFilter("all");
  };

  const handleOpenWorkspace = (id: string) => {
    onNavigate(`/experiments/${id}`);
  };

  const handleSaveEdit = (id: string, updates: Partial<ExperimentRecord>) => {
    const updated = experimentStorage.updateExperiment(id, updates, user);
    if (updated) {
      setExperiments(experimentStorage.getExperiments(user));
    }
  };

  const handleConfirmDelete = (id: string) => {
    const success = experimentStorage.deleteExperiment(id, user);
    if (success) {
      setExperiments(experimentStorage.getExperiments(user));
    }
  };

  const getStatusLabel = (filterId: string) => {
    switch (filterId) {
      case "in-progress":
        return "In Progress";
      case "completed":
        return "Completed";
      case "draft":
        return "Draft";
      default:
        return filterId;
    }
  };

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 pb-16">
      {/* 1. Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <h1 className="font-jakarta text-2xl font-bold tracking-tight text-neutral-900">
            My Experiments
          </h1>
          <p className="text-xs sm:text-sm text-neutral-500">
            All your lab experiments, organized in one place.
          </p>
        </div>

        <button
          type="button"
          onClick={() => onNavigate("/create-experiment")}
          className="inline-flex h-10 w-full sm:w-auto items-center justify-center gap-2 rounded-xl bg-neutral-900 px-5 text-xs sm:text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 shrink-0"
        >
          <Plus className="h-4 w-4" />
          <span>New Experiment</span>
        </button>
      </div>

      {/* Guest Mode Indicator Banner */}
      {user.isGuest && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 rounded-xl border border-emerald-200/80 bg-emerald-50/50 p-3.5 text-xs text-emerald-950">
          <div className="flex items-center gap-2.5">
            <UserCheck className="h-4 w-4 text-emerald-700 shrink-0" />
            <span>
              Guest session: Experiments are stored locally in this browser. Create an account to permanently sync across devices.
            </span>
          </div>
          <button
            type="button"
            onClick={() => onNavigate("/signup")}
            className="inline-flex items-center gap-1 font-semibold text-emerald-800 hover:text-emerald-950 hover:underline shrink-0"
          >
            <span>Create Account</span>
            <ArrowRight className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* 2. Experiment Overview Summary Row */}
      <ExperimentSummaryRow experiments={experiments} />

      {/* 3. Search, Filter, and Sort Controls */}
      <ExperimentToolbar
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        statusFilter={statusFilter}
        onStatusFilterChange={setStatusFilter}
        sortBy={sortBy}
        onSortByChange={setSortBy}
        onClearFilters={handleClearFilters}
        hasActiveFilters={hasActiveFilters}
        totalFilteredCount={filteredAndSortedExperiments.length}
        totalCount={experiments.length}
        availableStatuses={availableStatuses}
      />

      {/* 4. Experiments List / Table / Empty States */}
      {experiments.length === 0 ? (
        /* Empty State A: No experiments at all */
        <ExperimentEmptyState
          type="no-experiments"
          onAction={() => onNavigate("/create-experiment")}
        />
      ) : filteredAndSortedExperiments.length === 0 ? (
        searchQuery.trim() !== "" ? (
          /* Empty State B: No search match */
          <ExperimentEmptyState
            type="no-search-results"
            onAction={handleClearFilters}
          />
        ) : (
          /* Empty State C: No filter match */
          <ExperimentEmptyState
            type="no-filter-results"
            statusLabel={getStatusLabel(statusFilter)}
            onAction={handleClearFilters}
          />
        )
      ) : (
        /* Content: Desktop Table + Mobile Cards */
        <>
          {/* Desktop Table View */}
          <div className="hidden md:block">
            <ExperimentTable
              experiments={filteredAndSortedExperiments}
              onOpen={handleOpenWorkspace}
              onEdit={setEditingExperiment}
              onDelete={setDeletingExperiment}
            />
          </div>

          {/* Mobile / Tablet Cards View */}
          <div className="md:hidden">
            <ExperimentCardsList
              experiments={filteredAndSortedExperiments}
              onOpen={handleOpenWorkspace}
              onEdit={setEditingExperiment}
              onDelete={setDeletingExperiment}
            />
          </div>
        </>
      )}

      {/* 5. Modals */}
      <EditExperimentModal
        experiment={editingExperiment}
        isOpen={!!editingExperiment}
        onClose={() => setEditingExperiment(null)}
        onSave={handleSaveEdit}
      />

      <DeleteExperimentModal
        experiment={deletingExperiment}
        isOpen={!!deletingExperiment}
        onClose={() => setDeletingExperiment(null)}
        onConfirmDelete={handleConfirmDelete}
      />
    </div>
  );
};

export default MyExperimentsPage;
