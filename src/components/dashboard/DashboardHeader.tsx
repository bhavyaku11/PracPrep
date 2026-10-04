import React, { useState, useRef, useEffect } from "react";
import {
  Menu,
  Search,
  Bell,
  User,
  LogOut,
  UserCheck,
  ChevronDown,
  CheckCircle2,
  ExternalLink,
} from "lucide-react";
import { useClerk } from "@clerk/clerk-react";
import { useAuth } from "../../context/useAuth.ts";
import type { UserSession } from "../../types/dashboard";

interface DashboardHeaderProps {
  user: UserSession;
  activeSection: string;
  onOpenMobileMenu: () => void;
  onOpenSearch: () => void;
  onNavigate: (path: string) => void;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  user,
  activeSection,
  onOpenMobileMenu,
  onOpenSearch,
  onNavigate,
}) => {
  const [profileOpen, setProfileOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);

  const { signOut } = useClerk();
  const authContext = useAuth();

  const profileRef = useRef<HTMLDivElement>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);

  // Close menus when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false);
      }
      if (notificationsRef.current && !notificationsRef.current.contains(e.target as Node)) {
        setNotificationsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const getBreadcrumbTitle = (section: string) => {
    switch (section) {
      case "experiments":
        return "My Experiments";
      case "create-experiment":
        return "New Experiment";
      case "viva-practice":
        return "Viva Practice";
      case "progress":
        return "Progress & Revision";
      case "settings":
        return "Preferences";
      default:
        return "Overview";
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center border-b border-neutral-200/80 dark:border-neutral-800 bg-white/95 dark:bg-neutral-900/95 px-4 sm:px-6 lg:px-8 backdrop-blur-md">
      <div className="flex w-full max-w-6xl mx-auto items-center justify-between gap-3">
        {/* Left: Mobile Toggle & Breadcrumbs */}
        <div className="flex min-w-0 items-center gap-2.5 sm:gap-3">
          <button
            type="button"
            onClick={onOpenMobileMenu}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-white md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            aria-label="Open sidebar menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-xs sm:text-sm">
            <button
              type="button"
              onClick={() => onNavigate("/dashboard")}
              className="shrink-0 font-medium text-neutral-500 dark:text-neutral-400 hover:text-neutral-900 dark:hover:text-white transition-colors"
            >
              Workspace
            </button>
            <span className="shrink-0 text-neutral-400 dark:text-neutral-500">/</span>
            <span className="truncate font-semibold text-neutral-900 dark:text-white">
              {getBreadcrumbTitle(activeSection)}
            </span>
          </nav>
        </div>

        {/* Right: Search, Notifications & User Profile */}
        <div className="flex shrink-0 items-center gap-2 sm:gap-3">
        {/* Compact Search Trigger */}
        <button
          type="button"
          onClick={onOpenSearch}
          className="flex h-9 items-center gap-2 rounded-lg border border-neutral-200/90 dark:border-neutral-800 bg-neutral-50/80 dark:bg-neutral-900/80 px-2.5 sm:px-3 text-xs text-neutral-500 dark:text-neutral-400 transition-colors hover:border-neutral-300 dark:hover:border-neutral-700 hover:bg-white dark:hover:bg-neutral-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          aria-label="Search workspace (Cmd+K)"
        >
          <Search className="h-3.5 w-3.5 text-neutral-400" />
          <span className="hidden sm:inline">Search experiments...</span>
          <kbd className="hidden md:inline-flex rounded border border-neutral-200 dark:border-neutral-700 bg-white dark:bg-neutral-800 px-1.5 py-0.5 text-[10px] font-medium text-neutral-400 dark:text-neutral-500">
            ⌘K
          </kbd>
        </button>

        {/* Notifications Dropdown */}
        <div className="relative" ref={notificationsRef}>
          <button
            type="button"
            onClick={() => setNotificationsOpen(!notificationsOpen)}
            className="relative flex h-9 w-9 items-center justify-center rounded-lg text-neutral-600 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 hover:text-neutral-900 dark:hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            aria-label="View notifications"
            aria-expanded={notificationsOpen}
          >
            <Bell className="h-4 w-4" />
            <span
              className="absolute top-2 right-2 h-1.5 w-1.5 rounded-full bg-emerald-600"
              aria-hidden="true"
            />
          </button>

          {notificationsOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-3 shadow-xl animate-in fade-in zoom-in-95 duration-100 z-50">
              <div className="flex items-center justify-between border-b border-neutral-100 dark:border-neutral-800 pb-2 mb-2">
                <span className="text-xs font-semibold text-neutral-900 dark:text-white">Notifications</span>
                <span className="text-[10px] text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-full font-medium">
                  System
                </span>
              </div>
              <div className="space-y-2 py-1">
                <div className="flex gap-2.5 rounded-xl bg-neutral-50 dark:bg-neutral-800/50 p-2.5 text-left">
                  <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0 mt-0.5" />
                  <div className="space-y-0.5 text-xs">
                    <p className="font-medium text-neutral-800 dark:text-neutral-200">PracPrep Workspace Ready</p>
                    <p className="text-neutral-500 dark:text-neutral-400 text-[11px] leading-relaxed">
                      Upload your first lab manual to generate viva questions and experiment summaries.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* User / Guest Avatar Dropdown */}
        <div className="relative" ref={profileRef}>
          <button
            type="button"
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2 rounded-lg p-1.5 text-left text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
            aria-label="Account menu"
            aria-expanded={profileOpen}
          >
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-neutral-900 dark:bg-neutral-800 text-[11px] font-semibold text-white">
              {user.isGuest ? (
                <UserCheck className="h-3.5 w-3.5 text-emerald-400" />
              ) : (
                (user.name ? user.name.charAt(0).toUpperCase() : "S")
              )}
            </div>
            <span className="hidden md:inline text-xs font-medium text-neutral-800 dark:text-neutral-200 max-w-[120px] truncate">
              {user.isGuest ? "Guest Mode" : (user.name || "Student")}
            </span>
            <ChevronDown className="hidden md:inline h-3 w-3 text-neutral-400" />
          </button>

          {profileOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-2 shadow-xl animate-in fade-in zoom-in-95 duration-100 z-50">
              <div className="px-3 py-2 border-b border-neutral-100 dark:border-neutral-800 mb-1">
                <p className="text-xs font-semibold text-neutral-900 dark:text-white">
                  {user.isGuest ? "Guest Student" : (user.name || "Enrolled Student")}
                </p>
                <p className="text-[11px] text-neutral-500 dark:text-neutral-400 truncate">
                  {user.isGuest ? "Temporary browser session" : (user.email || "student@university.edu")}
                </p>
              </div>

              <div className="space-y-0.5">
                {user.isGuest ? (
                  <button
                    type="button"
                    onClick={() => {
                      setProfileOpen(false);
                      onNavigate("/signup");
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium text-emerald-700 dark:text-emerald-300 hover:bg-emerald-50 dark:hover:bg-emerald-950/60 transition-colors"
                  >
                    <User className="h-3.5 w-3.5" />
                    <span>Create Full Account</span>
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => {
                      setProfileOpen(false);
                      onNavigate("/settings");
                    }}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                  >
                    <User className="h-3.5 w-3.5" />
                    <span>Profile Settings</span>
                  </button>
                )}

                <button
                  type="button"
                  onClick={() => {
                    setProfileOpen(false);
                    onNavigate("/");
                  }}
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
                >
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>Landing Page</span>
                </button>

                <div className="my-1 border-t border-neutral-100 dark:border-neutral-800" />

                <button
                  type="button"
                  onClick={async () => {
                    setProfileOpen(false);
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
                  className="flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  <span>{user.isGuest ? "Exit Guest Mode" : "Sign Out"}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  </header>
  );
};

export default DashboardHeader;
