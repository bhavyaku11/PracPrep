import React, { useState, useEffect } from "react";
import DashboardSidebar from "./DashboardSidebar";
import DashboardHeader from "./DashboardHeader";
import DashboardOverview from "./DashboardOverview";
import DashboardModulePlaceholder from "./DashboardModulePlaceholder";
import NewExperimentPage from "../experiment/NewExperimentPage";
import MyExperimentsPage from "../experiments/MyExperimentsPage";
import ExperimentWorkspacePage from "../workspace/ExperimentWorkspacePage";
import VivaSimulatorPage from "../viva/VivaSimulatorPage";
import VivaPracticeHubPage from "../viva/VivaPracticeHubPage";
import ProgressRevisionPage from "../progress/ProgressRevisionPage";
import SettingsPage from "../settings/SettingsPage";
import SearchDialog from "./SearchDialog";
import type { UserSession } from "../../types/dashboard";
import type { ExperimentRecord } from "../../types/experiment";
import { experimentStorage } from "../../services/experimentStorage";
import { USER_UPDATE_EVENT } from "../../services/settingsStorage";

import { useAuth } from "../../context/useAuth.ts";
import { useUser } from "@clerk/clerk-react";

interface DashboardLayoutProps {
  currentPath: string;
  onNavigate: (path: string) => void;
  user?: UserSession;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({
  currentPath,
  onNavigate,
  user: propUser,
}) => {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [userRevision, setUserRevision] = useState(0);

  const authContext = useAuth();
  const { user: clerkUser } = useUser();

  useEffect(() => {
    const handleUserUpdate = () => {
      setUserRevision((r) => r + 1);
    };
    window.addEventListener(USER_UPDATE_EVENT, handleUserUpdate);
    return () => window.removeEventListener(USER_UPDATE_EVENT, handleUserUpdate);
  }, []);

  // Derive user session: check if prop exists, or if currentPath is /guest, or check auth context, or check Clerk, or check localStorage
  const user: UserSession = React.useMemo(() => {
    void userRevision;
    if (propUser) return propUser;
    if (currentPath === "/guest" || authContext?.isGuest) {
      return { isGuest: true };
    }
    if (authContext?.user) {
      return {
        isGuest: false,
        name: authContext.user.full_name,
        email: authContext.user.email,
        university: authContext.user.university || undefined,
        avatar: clerkUser?.imageUrl,
      };
    }
    if (clerkUser) {
      return {
        isGuest: false,
        name: clerkUser.fullName || clerkUser.firstName || "Student",
        email: clerkUser.primaryEmailAddress?.emailAddress || "student@university.edu",
        avatar: clerkUser.imageUrl,
      };
    }
    // Check if stored user exists
    if (typeof window !== "undefined") {
      try {
        const stored = localStorage.getItem("pracprep_user");
        if (stored) {
          return JSON.parse(stored);
        }
      } catch {
        // fallback
      }
    }
    // Default fallback based on path
    return {
      isGuest: false,
      name: "Student",
      email: "student@university.edu",
    };
  }, [propUser, currentPath, userRevision, authContext?.user, authContext?.isGuest, clerkUser]);

  // Experiments state (read from experimentStorage with reactive subscriptions)
  const [experiments, setExperiments] = useState<ExperimentRecord[]>(() => {
    return experimentStorage.getExperiments(user);
  });

  useEffect(() => {
    const unsubscribe = experimentStorage.subscribe(() => {
      setExperiments(experimentStorage.getExperiments(user));
    });
    return unsubscribe;
  }, [user]);

  // Global ⌘K / Ctrl+K keyboard shortcut for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // Determine active section from path
  const getActiveSection = () => {
    if (currentPath.includes("/viva") || currentPath === "/viva-practice") return "viva-practice";
    if (currentPath.startsWith("/experiments")) return "experiments";
    if (currentPath.startsWith("/create-experiment")) return "create-experiment";
    if (currentPath.startsWith("/progress")) return "progress";
    if (currentPath.startsWith("/settings")) return "settings";
    return "overview";
  };

  const activeSection = getActiveSection();

  return (
    <div className="flex h-screen h-[100dvh] w-full overflow-hidden bg-neutral-50/60 dark:bg-neutral-950 font-inter text-neutral-900 dark:text-neutral-100 selection:bg-emerald-100 selection:text-emerald-900">
      {/* 1. Left Sidebar Navigation */}
      <DashboardSidebar
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed(!collapsed)}
        mobileOpen={mobileOpen}
        onCloseMobile={() => setMobileOpen(false)}
        currentPath={currentPath}
        onNavigate={onNavigate}
        user={user}
      />

      {/* 2. Right Side: Top Header + Main Content Area */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Top Header */}
        <DashboardHeader
          user={user}
          activeSection={activeSection}
          onOpenMobileMenu={() => setMobileOpen(true)}
          onOpenSearch={() => setSearchOpen(true)}
          onNavigate={onNavigate}
        />

        {/* Main Dashboard Content Area (scrolls smoothly while sidebar remains fixed) */}
        <main
          id="dashboard-main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6"
        >
          {activeSection === "overview" ? (
            <DashboardOverview
              user={user}
              experiments={experiments}
              onNavigate={onNavigate}
            />
          ) : activeSection === "create-experiment" ? (
            <NewExperimentPage
              user={user}
              onNavigate={onNavigate}
            />
          ) : currentPath === "/experiments" ? (
            <MyExperimentsPage
              user={user}
              onNavigate={onNavigate}
            />
          ) : currentPath.match(/^\/experiments\/([^/]+)\/viva$/) ? (
            <VivaSimulatorPage
              key={currentPath}
              experimentId={currentPath.match(/^\/experiments\/([^/]+)\/viva$/)![1]}
              user={user}
              onNavigate={onNavigate}
            />
          ) : currentPath.startsWith("/experiments/") ? (
            <ExperimentWorkspacePage
              key={currentPath}
              experimentId={currentPath.replace("/experiments/", "")}
              user={user}
              onNavigate={onNavigate}
            />
          ) : currentPath === "/viva-practice" ? (
            <VivaPracticeHubPage
              user={user}
              onNavigate={onNavigate}
            />
          ) : currentPath === "/progress" ? (
            <ProgressRevisionPage
              user={user}
              onNavigate={onNavigate}
            />
          ) : currentPath.startsWith("/settings") ? (
            <SettingsPage
              user={user}
              onNavigate={onNavigate}
            />
          ) : (
            <DashboardModulePlaceholder
              sectionPath={currentPath}
              onNavigate={onNavigate}
            />
          )}
        </main>
      </div>

      {/* Quick Search Modal */}
      <SearchDialog
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        onNavigate={onNavigate}
        experiments={experiments}
      />
    </div>
  );
};

export default DashboardLayout;
