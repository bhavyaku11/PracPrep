import React, { useState } from "react";
import {
  LayoutDashboard,
  FlaskConical,
  PlusCircle,
  MessageSquareCode,
  TrendingUp,
  Settings,
  ChevronLeft,
  ChevronRight,
  UserCheck,
  User,
  LogOut,
  X,
  ExternalLink,
} from "lucide-react";
import { useClerk } from "@clerk/clerk-react";
import { useAuth } from "../../context/useAuth.ts";
import BrandLogo from "../BrandLogo";
import type { NavItem, UserSession } from "../../types/dashboard";

interface DashboardSidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  currentPath: string;
  onNavigate: (path: string) => void;
  user: UserSession;
}

const NAV_ITEMS: NavItem[] = [
  // Workspace
  { id: "overview", label: "Overview", path: "/dashboard", icon: LayoutDashboard, section: "workspace" },
  { id: "experiments", label: "My Experiments", path: "/experiments", icon: FlaskConical, section: "workspace" },
  { id: "new-experiment", label: "New Experiment", path: "/create-experiment", icon: PlusCircle, section: "workspace" },
  // Learning
  { id: "viva", label: "Viva Practice", path: "/viva-practice", icon: MessageSquareCode, section: "learning" },
  { id: "progress", label: "Progress & Revision", path: "/progress", icon: TrendingUp, section: "learning" },
  // Preferences
  { id: "settings", label: "Settings", path: "/settings", icon: Settings, section: "preferences" },
];

export const DashboardSidebar: React.FC<DashboardSidebarProps> = ({
  collapsed,
  onToggleCollapse,
  mobileOpen,
  onCloseMobile,
  currentPath,
  onNavigate,
  user,
}) => {
  const [profileDropdownOpen, setProfileDropdownOpen] = useState(false);
  const { signOut } = useClerk();
  const authContext = useAuth();

  // Group items
  const workspaceItems = NAV_ITEMS.filter((i) => i.section === "workspace");
  const learningItems = NAV_ITEMS.filter((i) => i.section === "learning");
  const preferenceItems = NAV_ITEMS.filter((i) => i.section === "preferences");

  const isItemActive = (itemPath: string) => {
    if (itemPath === "/dashboard" && (currentPath === "/dashboard" || currentPath === "/guest" || currentPath === "")) {
      return true;
    }
    if (itemPath === "/viva-practice" && (currentPath === "/viva-practice" || currentPath.endsWith("/viva"))) {
      return true;
    }
    if (itemPath === "/experiments" && (currentPath === "/experiments" || (currentPath.startsWith("/experiments/") && !currentPath.endsWith("/viva")))) {
      return true;
    }
    return currentPath === itemPath;
  };

  const handleNavClick = (path: string) => {
    onNavigate(path);
    if (mobileOpen) onCloseMobile();
  };

  const renderNavList = (items: NavItem[], sectionTitle?: string) => (
    <div className="space-y-1">
      {sectionTitle && !collapsed && (
        <div className="px-3 pt-3 pb-1 text-[11px] font-semibold text-neutral-400 uppercase tracking-wider">
          {sectionTitle}
        </div>
      )}
      {items.map((item) => {
        const Icon = item.icon;
        const active = isItemActive(item.path);

        return (
          <button
            key={item.id}
            type="button"
            onClick={() => handleNavClick(item.path)}
            title={collapsed ? item.label : undefined}
            className={`group relative flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-xs sm:text-sm font-medium transition-all outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
              active
                ? "bg-emerald-50/90 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 font-semibold shadow-2xs"
                : "text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100/80 dark:hover:bg-neutral-800/80 hover:text-neutral-900 dark:hover:text-white"
            }`}
          >
            {/* Active Pill Indicator */}
            {active && (
              <span
                className="absolute left-0 top-2 bottom-2 w-1 rounded-r-md bg-emerald-600"
                aria-hidden="true"
              />
            )}

            <Icon
              className={`h-4 w-4 shrink-0 transition-colors ${
                active ? "text-emerald-700 dark:text-emerald-400" : "text-neutral-500 dark:text-neutral-400 group-hover:text-neutral-800 dark:group-hover:text-neutral-200"
              }`}
            />

            {!collapsed && <span className="truncate">{item.label}</span>}
          </button>
        );
      })}
    </div>
  );

  const sidebarContent = (
    <div className="flex h-full flex-col justify-between p-3.5 bg-white dark:bg-neutral-900 text-neutral-900 dark:text-white select-none">
      {/* Top Header & Navigation */}
      <div className="space-y-4">
        {/* Brand / Title Header */}
        <div className="flex items-center justify-between px-1.5 py-1">
          {collapsed ? (
            <button
              type="button"
              onClick={() => handleNavClick("/dashboard")}
              className="flex h-9 w-9 mx-auto items-center justify-center rounded-xl bg-neutral-900 dark:bg-neutral-800 text-white shadow-sm"
              title="PracPrep"
            >
              <FlaskConical className="h-4 w-4 text-emerald-400" />
            </button>
          ) : (
            <div className="flex items-center justify-between w-full">
              <BrandLogo onClick={() => handleNavClick("/dashboard")} />
              {/* Mobile Close Button */}
              {mobileOpen && (
                <button
                  type="button"
                  onClick={onCloseMobile}
                  className="md:hidden flex h-8 w-8 items-center justify-center rounded-lg text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                  aria-label="Close navigation"
                >
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          )}
        </div>

        {/* Navigation Lists */}
        <nav aria-label="Sidebar Navigation" className="space-y-4 pt-1">
          {renderNavList(workspaceItems, "Workspace")}
          {renderNavList(learningItems, "Learning")}
          {renderNavList(preferenceItems, "Preferences")}
        </nav>
      </div>

      {/* Bottom Area: User / Guest Info & Collapse Toggle */}
      <div className="space-y-2 pt-3 border-t border-neutral-200/80 dark:border-neutral-800">
        {/* Guest or User Card */}
        <div className="relative">
          <button
            type="button"
            onClick={() => setProfileDropdownOpen(!profileDropdownOpen)}
            title={collapsed ? (user.isGuest ? "Guest Mode" : user.name || "Student") : undefined}
            className={`group flex w-full items-center gap-3 rounded-xl p-2 text-left transition-colors hover:bg-neutral-100 dark:hover:bg-neutral-800 ${
              collapsed ? "justify-center" : ""
            }`}
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-neutral-900 dark:bg-neutral-800 text-xs font-semibold text-white">
              {user.isGuest ? (
                <UserCheck className="h-4 w-4 text-emerald-400" />
              ) : (
                (user.name ? user.name.charAt(0).toUpperCase() : "S")
              )}
            </div>

            {!collapsed && (
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <span className="truncate text-xs font-semibold text-neutral-900 dark:text-white">
                    {user.isGuest ? "Guest Student" : (user.name || "Student")}
                  </span>
                  {user.isGuest && (
                    <span className="rounded bg-emerald-100 dark:bg-emerald-950 px-1 py-0.5 text-[9px] font-bold text-emerald-800 dark:text-emerald-300 uppercase">
                      Guest
                    </span>
                  )}
                </div>
                <p className="truncate text-[11px] text-neutral-500 dark:text-neutral-400">
                  {user.isGuest ? "Temporary Session" : (user.email || "student@university.edu")}
                </p>
              </div>
            )}
          </button>

          {/* Account Dropdown Menu */}
          {profileDropdownOpen && (
            <div
              className={`absolute bottom-full mb-2 w-56 rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-2 shadow-xl z-50 animate-in fade-in zoom-in-95 duration-100 ${
                collapsed ? "left-full ml-2" : "left-0"
              }`}
            >
              <div className="px-2.5 py-1.5 border-b border-neutral-100 dark:border-neutral-800 mb-1">
                <p className="text-xs font-semibold text-neutral-900 dark:text-white">
                  {user.isGuest ? "Guest Mode" : (user.name || "Student Account")}
                </p>
                <p className="text-[10px] text-neutral-500 dark:text-neutral-400 truncate">
                  {user.isGuest ? "No registration required" : (user.email || "Active")}
                </p>
              </div>

              {user.isGuest ? (
                <button
                  type="button"
                  onClick={() => {
                    setProfileDropdownOpen(false);
                    onNavigate("/signup");
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-semibold text-emerald-800 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/60 transition-colors"
                >
                  <User className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
                  <span>Create Account</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={() => {
                    setProfileDropdownOpen(false);
                    onNavigate("/settings");
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                >
                  <Settings className="h-3.5 w-3.5" />
                  <span>Account Settings</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => {
                  setProfileDropdownOpen(false);
                  onNavigate("/");
                }}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
              >
                <ExternalLink className="h-3.5 w-3.5" />
                <span>Return to Landing</span>
              </button>

              <div className="my-1 border-t border-neutral-100 dark:border-neutral-800" />

              <button
                type="button"
                onClick={async () => {
                  setProfileDropdownOpen(false);
                  try {
                    localStorage.removeItem("pracprep_user");
                  } catch {}
                  try {
                    await authContext?.logout();
                  } catch {}
                  try {
                    await signOut();
                  } catch {}
                  onNavigate("/");
                }}
                className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span>{user.isGuest ? "Exit Guest Mode" : "Sign Out"}</span>
              </button>
            </div>
          )}
        </div>

        {/* Desktop Collapse Button */}
        <div className="hidden md:block">
          <button
            type="button"
            onClick={onToggleCollapse}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="flex w-full items-center justify-center gap-2 rounded-xl py-2 text-xs font-medium text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-white transition-colors"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <>
                <ChevronLeft className="h-4 w-4" />
                <span>Collapse sidebar</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop Persistent Sidebar */}
      <aside
        className={`hidden md:flex flex-col shrink-0 border-r border-neutral-200/80 dark:border-neutral-800 transition-all duration-200 ease-in-out ${
          collapsed ? "w-[4.5rem]" : "w-64"
        }`}
      >
        {sidebarContent}
      </aside>

      {/* Mobile Slide-in Drawer */}
      {mobileOpen && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 flex md:hidden"
        >
          {/* Backdrop */}
          <div
            className="fixed inset-0 bg-neutral-950/40 backdrop-blur-xs animate-in fade-in duration-200"
            onClick={onCloseMobile}
          />
          {/* Drawer Pane */}
          <div className="relative flex w-72 max-w-[85vw] flex-col bg-white dark:bg-neutral-900 shadow-2xl animate-in slide-in-from-left duration-200 z-10">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
};

export default DashboardSidebar;
