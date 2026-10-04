import React from "react";
import { ArrowLeft, Sparkles, Plus, FlaskConical, MessageSquareCode, TrendingUp, Settings } from "lucide-react";

interface DashboardModulePlaceholderProps {
  sectionPath: string;
  onNavigate: (path: string) => void;
}

export const DashboardModulePlaceholder: React.FC<DashboardModulePlaceholderProps> = ({
  sectionPath,
  onNavigate,
}) => {
  const getModuleDetails = (path: string) => {
    switch (path) {
      case "/experiments":
        return {
          title: "My Experiments",
          subtitle: "Manage your ongoing laboratory manuals, active worksheets, and completed experiments.",
          icon: FlaskConical,
          actionText: "Upload First Lab Manual",
          actionTarget: "/create-experiment",
        };
      case "/create-experiment":
        return {
          title: "New Experiment Workspace",
          subtitle: "Enter manual experiment details or upload a syllabus to parse procedure steps and viva questions.",
          icon: Plus,
          actionText: "Create Experiment",
          actionTarget: "/create-experiment",
        };
      case "/viva-practice":
        return {
          title: "Viva Practice Studio",
          subtitle: "Oral examination simulator tailored to your lab experiments and apparatus.",
          icon: MessageSquareCode,
          actionText: "Generate Practice Viva",
          actionTarget: "/viva-practice",
        };
      case "/progress":
        return {
          title: "Progress & Revision",
          subtitle: "Track completed practicals, key observations, formulas, and performance analytics.",
          icon: TrendingUp,
          actionText: "Review Syllabus Checklist",
          actionTarget: "/progress",
        };
      case "/settings":
        return {
          title: "Preferences & Settings",
          subtitle: "Configure academic institution, branch of engineering, and study preferences.",
          icon: Settings,
          actionText: "Open Settings",
          actionTarget: "/settings",
        };
      default:
        if (path.startsWith("/experiments/")) {
          const expId = path.replace("/experiments/", "");
          return {
            title: "Experiment Workspace",
            subtitle: `Active experiment workspace for (${expId}). Detailed manual parsing, interactive viva simulator, and observations.`,
            icon: FlaskConical,
            actionText: "Back to My Experiments",
            actionTarget: "/experiments",
          };
        }
        return {
          title: "Workspace Module",
          subtitle: "This module is configured and ready in your laboratory workspace.",
          icon: Sparkles,
          actionText: "Return to Overview",
          actionTarget: "/dashboard",
        };
    }
  };

  const details = getModuleDetails(sectionPath);
  const Icon = details.icon;

  return (
    <div className="w-full max-w-6xl mx-auto py-8 sm:py-10">
      <div className="max-w-2xl mx-auto rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-6 sm:p-8 shadow-xs space-y-4 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-neutral-100 dark:bg-neutral-800 text-neutral-800 dark:text-neutral-200">
          <Icon className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
        </div>

        <div className="space-y-1.5">
          <span className="inline-block rounded-full bg-emerald-50 dark:bg-emerald-950/60 px-2.5 py-1 text-[11px] font-semibold text-emerald-800 dark:text-emerald-300 uppercase tracking-wider border border-emerald-200/50 dark:border-emerald-800/50">
            Workspace Module
          </span>
          <h1 className="font-jakarta text-xl sm:text-2xl font-bold tracking-tight text-neutral-900 dark:text-white">
            {details.title}
          </h1>
          <p className="text-xs sm:text-sm text-neutral-600 dark:text-neutral-400 leading-relaxed max-w-lg mx-auto">
            {details.subtitle}
          </p>
        </div>

        <div className="rounded-xl border border-dashed border-neutral-300 dark:border-neutral-700 bg-neutral-50/70 dark:bg-neutral-800/40 p-3 text-xs text-neutral-500 dark:text-neutral-400 font-mono">
          Route: {sectionPath}
        </div>

        <div className="pt-2 flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            type="button"
            onClick={() => onNavigate("/dashboard")}
            className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-neutral-900 dark:bg-white px-5 text-xs sm:text-sm font-semibold text-white dark:text-neutral-900 shadow-sm hover:bg-neutral-800 dark:hover:bg-neutral-100 transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            <span>Return to Overview</span>
          </button>

          {sectionPath !== "/create-experiment" && (
            <button
              type="button"
              onClick={() => onNavigate("/create-experiment")}
              className="inline-flex h-10 items-center justify-center gap-2 rounded-xl border border-neutral-300 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-4 text-xs sm:text-sm font-medium text-neutral-700 dark:text-neutral-300 hover:bg-neutral-50 dark:hover:bg-neutral-700 transition-colors"
            >
              <Plus className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              <span>New Experiment</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default DashboardModulePlaceholder;
