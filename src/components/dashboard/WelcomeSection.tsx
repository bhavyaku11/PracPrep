import React from "react";
import { ArrowRight, UserCheck } from "lucide-react";
import type { UserSession } from "../../types/dashboard";

interface WelcomeSectionProps {
  user: UserSession;
  onNavigate: (path: string) => void;
}

export const WelcomeSection: React.FC<WelcomeSectionProps> = ({ user, onNavigate }) => {
  const greeting = user.isGuest
    ? "Welcome to PracPrep"
    : `Welcome back, ${user.name || "Student"}`;

  return (
    <section aria-label="Dashboard Greeting" className="space-y-2">
      <h1 className="font-jakarta text-xl sm:text-2xl font-bold tracking-tight text-neutral-900 break-words">
        {greeting}
      </h1>

      {user.isGuest && (
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 sm:gap-3 rounded-lg border border-emerald-200/80 bg-emerald-50/50 px-3 py-2 text-xs text-emerald-900">
          <div className="flex items-center gap-2">
            <UserCheck className="h-3.5 w-3.5 text-emerald-700 shrink-0" />
            <span>Guest session data is stored locally.</span>
          </div>
          <button
            type="button"
            onClick={() => onNavigate("/signup")}
            className="inline-flex items-center gap-1 font-semibold text-emerald-700 hover:text-emerald-800 hover:underline shrink-0"
          >
            <span>Create Account</span>
            <ArrowRight className="h-3 w-3" />
          </button>
        </div>
      )}
    </section>
  );
};

export default WelcomeSection;
