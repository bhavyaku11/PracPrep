export type CreationMethod = "upload" | "manual";

export interface UploadedFileMeta {
  file: File;
  name: string;
  size: number;
  type: string;
  formattedSize: string;
  uploadedAt: Date;
}

export interface ExperimentFormData {
  method: CreationMethod;
  title: string;
  subject: string;
  experimentNumber: string;
  courseSemester: string;
  description: string;
  file: UploadedFileMeta | null;
  // Manual entry fields
  objective: string;
  theory: string;
  apparatus: string;
  procedure: string;
  precautions: string;
}

export interface FormValidationErrors {
  title?: string;
  subject?: string;
  file?: string;
  objective?: string;
  general?: string;
}

export type ExperimentStatus = "draft" | "in-progress" | "completed" | "ready" | "analyzing";

export interface CreatedExperimentResult {
  id: string;
  title: string;
  subject: string;
  experimentNumber?: string;
  courseSemester?: string;
  method: CreationMethod;
  hasManualFile: boolean;
  fileName?: string;
  createdAt: string;
  status: ExperimentStatus;
}

export interface ExperimentRecord {
  id: string;
  title: string;
  subject: string;
  experimentNumber?: string;
  courseSemester?: string;
  method?: CreationMethod;
  hasManualFile?: boolean;
  fileName?: string;
  createdAt: string;
  createdAtTimestamp: number;
  updatedAt: string;
  updatedAtTimestamp: number;
  status: ExperimentStatus;
  vivaQuestionsCount: number;
  description?: string;

  // Detailed Workspace Sections (Phase 4)
  objective?: string;
  theory?: string;
  apparatus?: string;
  procedure?: string;
  observations?: string;
  calculations?: string;
  precautions?: string;
  preparationChecklist?: Record<string, boolean>;
}

export type WorkspaceTab =
  | "overview"
  | "theory"
  | "apparatus"
  | "procedure"
  | "observations"
  | "precautions"
  | "checklist";

export interface PreparationChecklistItem {
  id: string;
  label: string;
  description: string;
  tabTarget?: WorkspaceTab;
}

export const PREPARATION_CHECKLIST_ITEMS: PreparationChecklistItem[] = [
  {
    id: "objective",
    label: "Read the experiment objective.",
    description: "Understand the core engineering objective and expected experimental outcome.",
    tabTarget: "overview",
  },
  {
    id: "theory",
    label: "Understand the underlying theory.",
    description: "Review physical laws, equations, assumptions, and circuit/system principles.",
    tabTarget: "theory",
  },
  {
    id: "apparatus",
    label: "Review the required apparatus.",
    description: "Verify equipment ratings, component counts, meters, and connection leads.",
    tabTarget: "apparatus",
  },
  {
    id: "procedure",
    label: "Study the procedure.",
    description: "Walk through sequential steps and safety checkpoints before touching hardware.",
    tabTarget: "procedure",
  },
  {
    id: "precautions",
    label: "Review the precautions.",
    description: "Identify hazard warnings, voltage/current limits, and handling guidelines.",
    tabTarget: "precautions",
  },
];

export type SortField = "created" | "updated" | "title_asc" | "title_desc";

export interface ExperimentFilterState {
  searchQuery: string;
  statusFilter: "all" | "draft" | "in-progress" | "completed" | "ready";
  sortBy: SortField;
}
