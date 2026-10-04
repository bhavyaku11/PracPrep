import type { LucideIcon } from "lucide-react";

export interface UserSession {
  isGuest: boolean;
  name?: string;
  email?: string;
  university?: string;
}

export interface NavItem {
  id: string;
  label: string;
  path: string;
  icon: LucideIcon;
  badge?: string;
  section: "workspace" | "learning" | "preferences";
}

export interface QuickActionItem {
  id: string;
  title: string;
  description: string;
  path: string;
  icon: LucideIcon;
  badge?: string;
}

export interface ExperimentSummary {
  id: string;
  title: string;
  subject: string;
  updatedAt: string;
  status: "ready" | "analyzing" | "draft" | "in-progress" | "completed";
  vivaQuestionsCount: number;
}

export interface SnapshotMetric {
  id: string;
  label: string;
  value: number | string;
  hint: string;
  icon: LucideIcon;
}
