import React, { useState, useEffect, useMemo } from "react";
import WelcomeSection from "./WelcomeSection";
import PrimaryActionCard from "./PrimaryActionCard";
import QuickAccess from "./QuickAccess";
import RecentExperiments from "./RecentExperiments";
import PreparationSnapshot from "./PreparationSnapshot";
import type { UserSession, ExperimentSummary } from "../../types/dashboard";
import { vivaStorage } from "../../services/vivaStorage";

interface DashboardOverviewProps {
  user: UserSession;
  experiments: ExperimentSummary[];
  onNavigate: (path: string) => void;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  user,
  experiments,
  onNavigate,
}) => {
  const [vivaRevision, setVivaRevision] = useState(0);

  useEffect(() => {
    const unsub = vivaStorage.subscribe(() => {
      setVivaRevision((r) => r + 1);
    });
    return unsub;
  }, []);

  const vivaSessions = useMemo(() => {
    void vivaRevision;
    return vivaStorage.getSessions(user);
  }, [user, vivaRevision]);

  const completedVivaCount = useMemo(() => {
    return vivaSessions.filter((s) => s.isCompleted).length;
  }, [vivaSessions]);

  const revisionCount = useMemo(() => {
    const weakTopicsSet = new Set<string>();
    vivaSessions.forEach((s) => {
      if (s.isCompleted && s.weakTopics) {
        s.weakTopics.forEach((t) => weakTopicsSet.add(t));
      }
    });
    return weakTopicsSet.size;
  }, [vivaSessions]);

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 sm:space-y-8 pb-12">
      {/* 1. Welcome Area */}
      <WelcomeSection user={user} onNavigate={onNavigate} />

      {/* 2. Primary Action — New Experiment */}
      <PrimaryActionCard onNavigate={onNavigate} />

      {/* 3. Quick Access Shortcuts */}
      <QuickAccess onNavigate={onNavigate} />

      {/* 4. Recent Experiments with Intentional Empty State */}
      <RecentExperiments experiments={experiments} onNavigate={onNavigate} />

      {/* 5. Preparation Snapshot (Live derived metrics, no fabricated numbers) */}
      <PreparationSnapshot
        experimentsCount={experiments.length}
        vivaCount={completedVivaCount}
        revisionCount={revisionCount}
      />
    </div>
  );
};

export default DashboardOverview;
