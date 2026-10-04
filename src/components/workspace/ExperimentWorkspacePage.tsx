import React, { useState, useEffect, useMemo } from "react";
import {
  LayoutDashboard,
  BookOpen,
  Wrench,
  ListOrdered,
  Table,
  ShieldAlert,
  CheckSquare,
  ArrowLeft,
  FolderX,
} from "lucide-react";
import type { UserSession } from "../../types/dashboard";
import type { ExperimentRecord, WorkspaceTab } from "../../types/experiment";
import { PREPARATION_CHECKLIST_ITEMS } from "../../types/experiment";
import { experimentStorage } from "../../services/experimentStorage";
import ExperimentWorkspaceHeader from "./ExperimentWorkspaceHeader";
import WorkspaceOverviewTab from "./WorkspaceOverviewTab";
import WorkspaceTheoryTab from "./WorkspaceTheoryTab";
import WorkspaceApparatusTab from "./WorkspaceApparatusTab";
import WorkspaceProcedureTab from "./WorkspaceProcedureTab";
import WorkspaceObservationsTab from "./WorkspaceObservationsTab";
import WorkspacePrecautionsTab from "./WorkspacePrecautionsTab";
import WorkspaceChecklistTab from "./WorkspaceChecklistTab";
import EditExperimentModal from "../experiments/EditExperimentModal";

interface ExperimentWorkspacePageProps {
  experimentId: string;
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const ExperimentWorkspacePage: React.FC<ExperimentWorkspacePageProps> = ({
  experimentId,
  user,
  onNavigate,
}) => {
  const [experiment, setExperiment] = useState<ExperimentRecord | null>(() => {
    return experimentStorage.getExperimentById(experimentId, user);
  });

  const [activeTab, setActiveTab] = useState<WorkspaceTab>("overview");
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editModalInitialTab, setEditModalInitialTab] = useState<"basic" | "content">("basic");

  // Subscribe to external storage updates
  useEffect(() => {
    const refresh = () => {
      const exp = experimentStorage.getExperimentById(experimentId, user);
      setExperiment(exp);
    };
    const unsubscribe = experimentStorage.subscribe(refresh);
    return unsubscribe;
  }, [experimentId, user]);

  // Dynamic calculation of checklist progress
  const checklistCount = useMemo(() => {
    const total = PREPARATION_CHECKLIST_ITEMS.length;
    if (!experiment || !experiment.preparationChecklist) {
      return { completed: 0, total, percentage: 0 };
    }
    const completed = PREPARATION_CHECKLIST_ITEMS.filter(
      (item) => experiment.preparationChecklist?.[item.id] === true
    ).length;
    const percentage = Math.round((completed / total) * 100);
    return { completed, total, percentage };
  }, [experiment]);

  const handleToggleChecklistItem = (itemId: string, completed: boolean) => {
    if (!experiment) return;
    const updated = experimentStorage.toggleChecklistItem(experiment.id, itemId, completed, user);
    if (updated) {
      setExperiment(updated);
    }
  };

  const handleOpenEdit = (section: "basic" | "content" = "basic") => {
    setEditModalInitialTab(section);
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = (id: string, updates: Partial<ExperimentRecord>) => {
    const updated = experimentStorage.updateExperiment(id, updates, user);
    if (updated) {
      setExperiment(updated);
    }
  };

  // 1. Not Found State for unknown or deleted experiments
  if (!experiment) {
    return (
      <div className="w-full max-w-4xl mx-auto py-12 px-4">
        <div className="rounded-2xl border border-neutral-200/90 bg-white p-8 sm:p-12 text-center shadow-xs space-y-4">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-600">
            <FolderX className="h-7 w-7 text-neutral-500" />
          </div>

          <div className="space-y-1">
            <h1 className="font-jakarta text-xl font-bold tracking-tight text-neutral-900">
              Experiment not found.
            </h1>
            <p className="max-w-md mx-auto text-xs sm:text-sm text-neutral-500 leading-relaxed">
              This experiment may have been deleted or is no longer available in your workspace.
            </p>
          </div>

          <div className="pt-2">
            <button
              type="button"
              onClick={() => onNavigate("/experiments")}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-neutral-900 px-5 text-xs sm:text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
            >
              <ArrowLeft className="h-4 w-4" />
              <span>Return to My Experiments</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Tab definitions
  const tabs: { id: WorkspaceTab; label: string; icon: React.ComponentType<{ className?: string }>; badge?: string }[] = [
    { id: "overview", label: "Overview", icon: LayoutDashboard },
    { id: "theory", label: "Theory", icon: BookOpen },
    { id: "apparatus", label: "Apparatus", icon: Wrench },
    { id: "procedure", label: "Procedure", icon: ListOrdered },
    { id: "observations", label: "Observations & Data", icon: Table },
    { id: "precautions", label: "Precautions", icon: ShieldAlert },
    {
      id: "checklist",
      label: "Preparation Checklist",
      icon: CheckSquare,
      badge: `${checklistCount.completed}/${checklistCount.total}`,
    },
  ];

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 pb-16">
      {/* 1. Header with breadcrumbs and actions */}
      <ExperimentWorkspaceHeader
        experiment={experiment}
        onNavigate={onNavigate}
        onEdit={() => handleOpenEdit("basic")}
      />

      {/* 2. Horizontal Scrollable Section Navigation Tabs */}
      <div className="border-b border-neutral-200">
        <nav
          aria-label="Workspace Sections"
          className="flex space-x-1 sm:space-x-2 overflow-x-auto no-scrollbar py-1"
        >
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isSelected = activeTab === tab.id;

            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`inline-flex items-center gap-2 px-3 py-2 text-xs sm:text-sm font-semibold rounded-xl whitespace-nowrap transition-all shrink-0 ${
                  isSelected
                    ? "bg-neutral-900 text-white shadow-2xs"
                    : "text-neutral-600 hover:text-neutral-900 hover:bg-neutral-100/80"
                }`}
              >
                <Icon className={`h-4 w-4 ${isSelected ? "text-emerald-400" : "text-neutral-400"}`} />
                <span>{tab.label}</span>
                {tab.badge && (
                  <span
                    className={`text-[10px] font-mono px-1.5 py-0.2 rounded font-bold ${
                      isSelected
                        ? "bg-neutral-800 text-emerald-300"
                        : "bg-neutral-100 text-neutral-600"
                    }`}
                  >
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* 3. Section Content based on active tab */}
      <main className="min-w-0">
        {activeTab === "overview" && (
          <WorkspaceOverviewTab
            experiment={experiment}
            checklistCount={checklistCount}
            onNavigateTab={setActiveTab}
            onEdit={handleOpenEdit}
            user={user}
          />
        )}

        {activeTab === "theory" && (
          <WorkspaceTheoryTab
            experiment={experiment}
            onEdit={() => handleOpenEdit("content")}
          />
        )}

        {activeTab === "apparatus" && (
          <WorkspaceApparatusTab
            experiment={experiment}
            onEdit={() => handleOpenEdit("content")}
          />
        )}

        {activeTab === "procedure" && (
          <WorkspaceProcedureTab
            experiment={experiment}
            onEdit={() => handleOpenEdit("content")}
          />
        )}

        {activeTab === "observations" && (
          <WorkspaceObservationsTab
            experiment={experiment}
            onEdit={() => handleOpenEdit("content")}
          />
        )}

        {activeTab === "precautions" && (
          <WorkspacePrecautionsTab
            experiment={experiment}
            onEdit={() => handleOpenEdit("content")}
          />
        )}

        {activeTab === "checklist" && (
          <WorkspaceChecklistTab
            experiment={experiment}
            onToggleItem={handleToggleChecklistItem}
            onNavigateTab={setActiveTab}
          />
        )}
      </main>

      {/* 4. Edit Experiment Modal */}
      <EditExperimentModal
        experiment={experiment}
        isOpen={isEditModalOpen}
        initialTab={editModalInitialTab}
        onClose={() => setIsEditModalOpen(false)}
        onSave={handleSaveEdit}
      />
    </div>
  );
};

export default ExperimentWorkspacePage;
