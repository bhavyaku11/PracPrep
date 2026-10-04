# PracPrep — Frontend Architecture Audit & Backend Integration Mapping

**Project:** PracPrep — From Lab Manual to Lab-Ready  
**Audit Date:** 2026-10-04  
**Auditor Role:** Senior Software Architect (read-only analysis)  
**Scope:** Complete frontend codebase inspection  
**Status:** No source files were created, modified, or deleted during this audit.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Verified Project Structure](#2-verified-project-structure)
3. [File-by-File Inventory](#3-file-by-file-inventory)
4. [Page and Feature Analysis](#4-page-and-feature-analysis)
5. [Data Storage and State Management](#5-data-storage-and-state-management)
6. [Frontend Data Models and Types](#6-frontend-data-models-and-types)
7. [Existing Backend Connectivity](#7-existing-backend-connectivity)
8. [Backend Integration Mapping](#8-backend-integration-mapping)
9. [Functionality to Keep Frontend-Only](#9-functionality-to-keep-frontend-only)
10. [Risks and Architectural Observations](#10-risks-and-architectural-observations)
11. [Recommended Backend Implementation Sequence](#11-recommended-backend-implementation-sequence)
12. [Open Questions](#12-open-questions)

---

## 1. Executive Summary

PracPrep is a complete, fully functional **laboratory preparation companion** implemented entirely as a client-side React SPA with **no backend integration of any kind**.

The application has **8 distinct functional modules** implemented across **71 relevant source files**. Every feature — experiment storage, viva simulation, progress analytics, user authentication, and settings — runs entirely in the browser using `localStorage` as the persistence layer.

**Key findings:**

- **No backend exists.** Zero `fetch`, `axios`, or WebSocket calls are present anywhere in the source. There are no environment variables for API endpoints, no proxy configuration, and no authentication tokens.
- **Authentication is simulated.** The sign-in/sign-up flows accept any credentials, write a fake user object to `localStorage`, and redirect after a 1-second `setTimeout`. No real identity verification occurs.
- **The viva AI engine is a demonstration provider.** It uses deterministic keyword-matching algorithms, not any external AI API. The class is explicitly named `DemonstrationVivaProvider`.
- **All user data is localStorage-scoped.** Experiments, viva sessions, and settings are stored in browser localStorage, scoped by email-derived key for authenticated users or a `_guest` suffix for guests.
- **The frontend is integration-ready.** The storage layer is abstracted behind three service modules with a consistent CRUD interface that can be replaced with API calls without touching any component code.

---

## 2. Verified Project Structure

```
Week 1/                          (project root)
├── index.html
├── vite.config.ts               Vite 8, React plugin, Tailwind v4, @/ alias
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── package.json                 React 19, Tailwind 4, framer-motion, gsap, lucide-react
├── components.json              shadcn/ui config (neutral base, cssVariables, @/ alias)
├── .oxlintrc.json
├── test-progressAnalytics.mjs
├── test-settingsStorage.mjs
├── test-integration.mjs
├── public/
└── src/
    ├── main.tsx
    ├── App.tsx                  Manual History API router
    ├── index.css                Tailwind v4, font utilities, global reset
    ├── config/site.ts
    ├── lib/utils.ts             cn() helper
    ├── types/
    │   ├── dashboard.ts
    │   ├── experiment.ts
    │   ├── viva.ts
    │   ├── progress.ts
    │   └── settings.ts
    ├── services/
    │   ├── experimentStorage.ts
    │   ├── vivaStorage.ts
    │   ├── settingsStorage.ts
    │   └── vivaAIProvider.ts    DemonstrationVivaProvider (no AI API)
    ├── utils/progressAnalytics.ts
    ├── pages/AuthPage.tsx       Simulated auth (setTimeout mock)
    └── components/
        ├── BrandLogo.tsx / ErrorBoundary.tsx / HeroSection.tsx / Navbar.tsx
        ├── dashboard/           11 files
        ├── experiment/          7 files   — New Experiment flow
        ├── experiments/         9 files   — My Experiments list
        ├── workspace/           9 files   — Experiment Workspace
        ├── viva/                6 files   — Viva Simulator
        ├── progress/            9 files   — Progress & Revision Center
        ├── settings/            7 files   — Settings & Personalization
        └── ui/                  7 files   — Shared UI primitives
```

**Tech stack (verified from package.json and config files):**

| Tool | Version | Purpose |
|------|---------|---------|
| React | 19.2.8 | UI framework |
| Vite | 8.3.0 | Dev server and bundler |
| TypeScript | 6.0.2 | Static typing |
| Tailwind CSS | 4.3.3 | Utility-first CSS |
| framer-motion | 14.0.0 | Animation (auth page, 404) |
| gsap | 3.15.0 | Canvas animation (CrowdCanvas) |
| lucide-react | 1.50.0 | Icons |
| clsx + tailwind-merge | 2.1.1 / 3.7.0 | Class management |
| oxlint | 1.81.0 | Linter |

**No testing framework is installed.** Three `.mjs` files run via `node --experimental-strip-types`.

---

## 3. File-by-File Inventory

### 3.1 Entry & Shell

| File | Purpose | Backend Relevance | Action |
|------|---------|-------------------|--------|
| `main.tsx` | App entry; wraps in ErrorBoundary | None | Keep as-is |
| `App.tsx` | Manual pushState router; routes to Landing/Auth/Dashboard/404 | Auth guard needed | Add auth guard on integration |
| `index.css` | Tailwind v4, font utilities, body reset | None | Keep as-is |
| `lib/utils.ts` | `cn()` helper | None | Keep as-is |
| `config/site.ts` | App name, tagline, named route paths | None | Keep as-is |

### 3.2 TypeScript Types

| File | Key Types | Backend Notes |
|------|-----------|---------------|
| `types/dashboard.ts` | `UserSession`, `NavItem`, `ExperimentSummary`, `SnapshotMetric` | `UserSession` needs `userId` / token field |
| `types/experiment.ts` | `ExperimentRecord`, `ExperimentFormData`, `ExperimentStatus`, `PREPARATION_CHECKLIST_ITEMS` | Core backend entity |
| `types/viva.ts` | `VivaQuestion`, `VivaEvaluation`, `VivaSessionRecord`, `VivaAnswerRecord`, `TopicPerformance` | Backend must persist session records |
| `types/progress.ts` | `ProgressOverviewMetrics`, `ExperimentReadinessItem`, `TopicAggregatedPerformance`, all analytics result types | Computed types — not stored |
| `types/settings.ts` | `UserSettings`, `ThemePreference`, `DensityPreference`, `StudyPreferences`, `ExportDataPayload` | Study prefs should sync to backend |

### 3.3 Services

| File | Key Methods | Storage Keys | Backend Action |
|------|-------------|--------------|----------------|
| `services/experimentStorage.ts` | `getExperiments()`, `getExperimentById()`, `saveExperiment()`, `updateExperiment()`, `deleteExperiment()`, `clearExperiments()`, `toggleChecklistItem()`, `subscribe()` | `pracprep_experiments_guest`, `pracprep_experiments_user_{email}`, `pracprep_experiments` (legacy) | Replace method bodies with REST API calls |
| `services/vivaStorage.ts` | `getSessions()`, `getSessionsByExperiment()`, `saveSession()`, `deleteSession()`, `clearSessions()`, `subscribe()` | `pracprep_viva_sessions_guest`, `pracprep_viva_sessions_user_{email}` | Replace method bodies with REST API calls |
| `services/settingsStorage.ts` | `getSettings()`, `saveSettings()`, `clearSettings()`, `applyTheme()`, `initTheme()`, `updateUserProfile()`, `exportUserData()`, `clearAllUserData()` | `pracprep_settings_guest`, `pracprep_settings_user_{email}`, `pracprep_user` | Split: keep theme/density local; sync study prefs + profile to backend |
| `services/vivaAIProvider.ts` | `generateQuestions()`, `evaluateAnswer()`, `analyzeSession()` via `DemonstrationVivaProvider` implementing `IVivaAIProvider` | In-memory only | Create `LiveAIVivaProvider` implementing same interface |

### 3.4 Utilities

| File | Key Functions | Backend Notes |
|------|---------------|---------------|
| `utils/progressAnalytics.ts` | `calculateOverviewMetrics()`, `calculateExperimentReadiness()`, `extractPerformanceTrendPoints()`, `aggregateTopicPerformance()`, `extractRevisionPriorities()`, `extractStrongTopics()`, `generateRecommendedNextSteps()` | All pure functions; stays client-side initially |

### 3.5 Authentication (Pages)

| File | Current State | Backend Action |
|------|--------------|----------------|
| `pages/AuthPage.tsx` (943 lines) | Sign-in/up handler contains explicit `// Simulate authentication request` comment. Uses `setTimeout(..., 1000)` to write fake user to localStorage. Google SSO fires `alert()`. Forgot password fires `alert()`. | Full replacement with real auth API |

### 3.6 Dashboard (11 files)

| File | Data Source | Backend Relevance |
|------|-------------|-------------------|
| `DashboardLayout.tsx` | `localStorage["pracprep_user"]` + `experimentStorage.subscribe()` | Needs auth context + JWT |
| `DashboardOverview.tsx`, `WelcomeSection.tsx`, `PrimaryActionCard.tsx`, `QuickAccess.tsx` | Props / static | None |
| `DashboardSidebar.tsx`, `DashboardHeader.tsx` | `user` prop | None |
| `RecentExperiments.tsx`, `PreparationSnapshot.tsx` | `experiments[]` prop | Reactive with API data |
| `SearchDialog.tsx` | `experiments[]` prop | Will search API-backed data |
| `DashboardModulePlaceholder.tsx` | Static | None |

### 3.7 New Experiment (7 files)

| File | Data Source | Critical Gap | Backend Action |
|------|-------------|-------------|----------------|
| `NewExperimentPage.tsx` | Local form state → `experimentStorage.saveExperiment()` | — | `POST /experiments` |
| `LabManualUploader.tsx` | `File` object in React state only | **File is never uploaded or parsed.** `ExperimentRecord` created with `hasManualFile: true` but all content sections `undefined`. | Needs file upload + parsing API |
| `ManualExperimentForm.tsx` | Local form state | — | Content becomes API payload |
| `CreationMethodSelector.tsx`, `ExperimentDetailsForm.tsx`, `ExperimentFormActions.tsx`, `PreparationPreview.tsx` | UI state or props | None | Keep as-is |

### 3.8 My Experiments (9 files)

| File | Data Source | Backend Action |
|------|-------------|----------------|
| `MyExperimentsPage.tsx` | `experimentStorage.getExperiments()` + `vivaStorage.getSessions()` | Replace with API |
| `ExperimentTable.tsx`, `ExperimentCardsList.tsx`, `ExperimentToolbar.tsx`, `ExperimentStatusBadge.tsx`, `ExperimentSummaryRow.tsx`, `ExperimentEmptyState.tsx` | Props | Keep as-is |
| `EditExperimentModal.tsx` | `experimentStorage.updateExperiment()` | `PATCH /experiments/{id}` |
| `DeleteExperimentModal.tsx` | `experimentStorage.deleteExperiment()` | `DELETE /experiments/{id}` |

### 3.9 Experiment Workspace (9 files)

| File | Data Source | Backend Action |
|------|-------------|----------------|
| `ExperimentWorkspacePage.tsx` | `experimentStorage.getExperimentById()` + `toggleChecklistItem()` | `GET /experiments/{id}`, `PATCH /experiments/{id}/checklist` |
| `ExperimentWorkspaceHeader.tsx`, all `Workspace*Tab.tsx` | `experiment` prop | Keep as-is |

### 3.10 Viva Simulator (6 files)

| File | Data Source | Backend Action |
|------|-------------|----------------|
| `VivaSimulatorPage.tsx` | `experimentStorage.getExperimentById()` + `vivaStorage.saveSession()` | `GET /experiments/{id}`, `POST /viva-sessions` |
| `VivaSetupScreen.tsx` | `settingsStorage.getSettings()` | Keep form; submit config to API |
| `VivaActiveSession.tsx` | `vivaAIProvider.generateQuestions()` + `evaluateAnswer()` | **Swap provider to real AI API** |
| `VivaResultsScreen.tsx`, `VivaReviewAnswers.tsx` | In-memory session results | Read from API after save |
| `VivaPracticeHubPage.tsx` | `experimentStorage` + `vivaStorage` | `GET /experiments`, `GET /viva-sessions` |

### 3.11 Progress & Revision Center (9 files)

| File | Data Source | Backend Action |
|------|-------------|----------------|
| `ProgressRevisionPage.tsx` | All localStorage services + all analytics functions | Replace data fetch with API; analytics stays client-side |
| All other progress components | Computed analytics result props | Keep as-is |

### 3.12 Settings (7 files)

| File | Data Source | Backend Action |
|------|-------------|----------------|
| `ProfileSettingsSection.tsx` | `settingsStorage.updateUserProfile()` → `pracprep_user` localStorage | `PATCH /users/{id}/profile` |
| `AppearanceSettingsSection.tsx` | `settingsStorage.saveSettings()` | Keep local (device preference) |
| `StudyPreferencesSection.tsx` | `settingsStorage.saveSettings()` | Sync to backend for cross-device |
| `DataPrivacySection.tsx` | `settingsStorage.exportUserData()` + `clearAllUserData()` | `GET /users/{id}/export`, `DELETE /users/{id}/data` |
| `AccountActionsSection.tsx` | Clears `pracprep_user`, navigates to `/login` | Invalidate server session token |
| `SettingsPage.tsx` | `settingsStorage.getSettings()` | Needs API sync |
| `AboutSettingsSection.tsx` | Static | None |

### 3.13 Shared UI Primitives (7 files)

All files in `components/ui/` — `ghost-404-page.tsx`, `skiper39.tsx`, `auth-switch.tsx`, `flow-button.tsx`, `demo-auth.tsx`, `demo.tsx`, `ghost-404-demo.tsx` — are presentational components with no data dependencies. No backend relevance.

---

## 4. Page and Feature Analysis

### Landing Page (`/`)
Static. `Navbar.tsx` + `HeroSection.tsx` + CrowdCanvas GSAP animation. No data source, no backend required.

### Sign-In / Sign-Up (`/login`, `/signup`)
Form validation is real (client-side). Authentication is simulated: both handlers write a hardcoded `{ isGuest: false, name, email }` object to `localStorage["pracprep_user"]` after `setTimeout(fn, 1000)`. Complete backend replacement required.

### Guest Access (`/guest`)
`DashboardLayout.tsx` detects path `/guest` → sets `user = { isGuest: true }`. All data scoped to `_guest` localStorage keys. Whether guest data persists to backend is a design decision (see [Open Questions](#12-open-questions)).

### Dashboard Overview (`/dashboard`)
Reads `experimentStorage.getExperiments(user)`. Subscribed to `pracprep_experiments_changed` custom event for reactive updates. Read-only display.

### New Experiment (`/create-experiment`)
**Upload path is non-functional** — the `File` object is held in state but never sent to a server. Created experiments have `hasManualFile: true` but all content sections (`theory`, `apparatus`, etc.) are `undefined`. Manual entry works correctly and produces a populated `ExperimentRecord`.

### My Experiments (`/experiments`)
Reads `experimentStorage.getExperiments()` + `vivaStorage.getSessions()`. Inline search/filter/sort is client-side. Edit and delete write to localStorage. Full CRUD replacement needed.

### Experiment Workspace (`/experiments/{id}`)
Reads single experiment by ID. 7 tabs display content fields. Checklist toggles write `preparationChecklist: Record<string, boolean>` back to experiment record. Edit modal available. Backend needs `GET` + `PATCH` per experiment.

### Viva Practice Hub (`/viva-practice`)
Aggregates experiments and viva sessions. Links to viva simulator per experiment. Session history display. Both data sources from localStorage.

### Viva Simulator (`/experiments/{id}/viva`)
Session lifecycle: Setup → Active → Results → Review. `DemonstrationVivaProvider` generates questions from experiment field content using templates; evaluates answers via keyword-matching against `keyPoints[]`. Provider interface `IVivaAIProvider` cleanly separates concern from implementation. Completed sessions saved to localStorage.

### Progress & Revision Center (`/progress`)
All 7 analytics functions in `progressAnalytics.ts` run over localStorage data. Custom SVG trend chart (no chart library). Period filter (All/30d/7d) is client-side. No mocked data — all real user data is used.

### Settings (`/settings`)
Full CRUD for profile, appearance, study preferences. Data export generates JSON from localStorage. "Clear all data" removes all scoped localStorage keys. "Sign out" deletes `pracprep_user` and navigates to `/login`.

### 404 Page
Static with framer-motion animation. No data dependencies.

---

## 5. Data Storage and State Management

### 5.1 Verified localStorage Keys

| Key | Type | Scope | Written By | Read By |
|-----|------|-------|------------|---------|
| `pracprep_user` | `UserSession` JSON object | Global | `AuthPage.tsx`, `settingsStorage.updateUserProfile()`, `AccountActionsSection` | `DashboardLayout.tsx`, `settingsStorage` |
| `pracprep_experiments_guest` | `ExperimentRecord[]` | Guest | `experimentStorage` (all writes) | `experimentStorage.getExperiments()` |
| `pracprep_experiments_user_{safeEmail}` | `ExperimentRecord[]` | Per user | `experimentStorage` | `experimentStorage.getExperiments()` |
| `pracprep_experiments` | `ExperimentRecord[]` | Legacy | `experimentStorage` (guest writes here too) | `experimentStorage` (fallback) |
| `pracprep_viva_sessions_guest` | `VivaSessionRecord[]` | Guest | `vivaStorage` | `vivaStorage.getSessions()` |
| `pracprep_viva_sessions_user_{safeEmail}` | `VivaSessionRecord[]` | Per user | `vivaStorage` | `vivaStorage.getSessions()` |
| `pracprep_settings_guest` | `UserSettings` | Guest | `settingsStorage` | `settingsStorage.getSettings()` |
| `pracprep_settings_user_{safeEmail}` | `UserSettings` | Per user | `settingsStorage` | `settingsStorage.getSettings()` |

### 5.2 Custom Event Bus

| Event Name | Fired By | Purpose |
|-----------|---------|---------|
| `pracprep_experiments_changed` | `experimentStorage` on any write | Refresh experiments in `DashboardLayout` |
| `pracprep_viva_sessions_changed` | `vivaStorage` on any write | Cross-tab viva sync (no active subscribers in current code) |
| `pracprep_settings_changed` | `settingsStorage` on save/clear | Refresh settings in `SettingsPage` |
| `pracprep_user_changed` | `settingsStorage.notifyUserUpdate()` | Trigger user re-read in `DashboardLayout` |
| `storage` (native browser) | Browser cross-tab | All three `subscribe()` methods listen for this |

### 5.3 Data That Should Move to Backend

| Data | Reason |
|------|--------|
| `ExperimentRecord[]` | Core content; must survive browser clears and be cross-device |
| `VivaSessionRecord[]` | Performance history; must be permanent |
| `UserSession` (authenticated) | Must come from verified identity |
| `UserSettings.studyPreferences` | Cross-device consistency |
| Profile fields (name, university) | Must match verified account |

### 5.4 Data That Should Stay Local

| Data | Reason |
|------|--------|
| `theme`, `density`, `reducedMotion` | Device-specific; instant feedback required |
| `collapsed` (sidebar) | Ephemeral UI state |
| Form draft state | Transient |
| Guest session data | Ephemeral by definition |

---

## 6. Frontend Data Models and Types

### 6.1 UserSession
```ts
interface UserSession {
  isGuest: boolean;
  name?: string;
  email?: string;
  university?: string;
}
```
**Backend issue:** No `userId` / UUID field. Email is used as the storage partition key, making it immutable in the current design. Backend must add a stable `userId`.

### 6.2 ExperimentRecord
```ts
interface ExperimentRecord {
  id: string;                    // "exp-{Date.now()}" — needs UUID on backend
  title: string;
  subject: string;
  experimentNumber?: string;
  courseSemester?: string;
  method?: "upload" | "manual";
  hasManualFile?: boolean;
  fileName?: string;             // filename only — no URL, no parsed content
  createdAt: string;             // human-readable — backend uses ISO timestamps
  createdAtTimestamp: number;
  updatedAt: string;
  updatedAtTimestamp: number;
  status: "draft" | "in-progress" | "completed" | "ready" | "analyzing";
  vivaQuestionsCount: number;
  description?: string;
  objective?: string;
  theory?: string;
  apparatus?: string;
  procedure?: string;
  observations?: string;
  calculations?: string;
  precautions?: string;
  preparationChecklist?: Record<string, boolean>;
}
```

### 6.3 VivaSessionRecord (key fields)
```ts
interface VivaSessionRecord {
  id: string;
  experimentId: string;
  experimentTitle: string;       // denormalized copy
  config: VivaSessionConfig;
  startedAt: number;
  completedAt?: number;
  isCompleted: boolean;
  answers: VivaAnswerRecord[];   // contains VivaEvaluation per answer
  averageScore: number;
  weakTopics: string[];
  strongTopics: string[];
  revisionRecommendations: RevisionRecommendation[];
  providerMode: "demonstration" | "ai-live";
}
```

### 6.4 UserSettings
```ts
interface UserSettings {
  theme: "light" | "dark" | "system";
  density: "comfortable" | "compact";
  reducedMotion: boolean;
  studyPreferences: {
    defaultDifficulty: VivaDifficulty;
    defaultQuestionCount: 5 | 10 | 15;
    preferredFocus: VivaTopic;
  };
}
```
Theme/density/reducedMotion → stay local. `studyPreferences` → sync to backend.

### 6.5 Progress Types
All types in `types/progress.ts` are **computed output types**, not stored entities. They are computed from `ExperimentRecord[]` and `VivaSessionRecord[]` by pure functions. Backend stores the inputs; analytics computation stays on the client.

---

## 7. Existing Backend Connectivity

**Finding: No backend connection of any kind exists in this codebase.**

| Category | Verified Finding |
|----------|-----------------|
| `fetch` calls | **Zero** occurrences in any `.ts`/`.tsx` source file |
| `axios` | **Not installed** (absent from `package.json`) |
| `XMLHttpRequest` | **Zero** occurrences |
| `WebSocket` / `EventSource` | **Zero** occurrences |
| `VITE_*` environment variables | **Zero** occurrences; no `.env` file at project root |
| `import.meta.env` | **Zero** occurrences |
| API base URL | **Not defined** anywhere |
| Vite proxy config | **None** in `vite.config.ts` |
| Auth tokens | **None** — session is a plain JSON object in localStorage |
| External HTTP CDN resources | Two CDN image URLs in UI components (`21st.dev` CDN for 404 ghost image and animation illustration) |

The `vivaAIProvider.ts` file uses `setTimeout(resolve, 350)` and `setTimeout(resolve, 400)` to simulate async AI processing. No network calls are made.

---

## 8. Backend Integration Mapping

| Frontend Feature | Current Implementation | Backend Endpoint(s) Needed | Frontend Files | Priority |
|-----------------|----------------------|---------------------------|----------------|----------|
| **User Authentication** | `setTimeout` mock + localStorage write | `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` | `AuthPage.tsx`, `DashboardLayout.tsx`, `AccountActionsSection.tsx`, `settingsStorage.ts` | 🔴 P0 |
| **Google SSO** | `alert()` placeholder | OAuth 2.0 Google token exchange | `AuthPage.tsx` | 🟡 P2 |
| **User Profile** | Plain JSON in `pracprep_user` localStorage | `PATCH /users/{id}/profile` | `ProfileSettingsSection.tsx`, `settingsStorage.updateUserProfile()` | 🔴 P0 |
| **Create Experiment (manual)** | `experimentStorage.saveExperiment()` → localStorage | `POST /experiments` | `NewExperimentPage.tsx`, `ManualExperimentForm.tsx` | 🔴 P0 |
| **Create Experiment (upload)** | File held in state; never uploaded | `POST /experiments/upload` (multipart), doc parsing service | `LabManualUploader.tsx`, `NewExperimentPage.tsx` | 🟡 P2 |
| **List All Experiments** | `experimentStorage.getExperiments()` | `GET /experiments?userId={id}` | `DashboardLayout.tsx`, `MyExperimentsPage.tsx`, `VivaPracticeHubPage.tsx`, `ProgressRevisionPage.tsx` | 🔴 P0 |
| **Get Single Experiment** | `experimentStorage.getExperimentById()` | `GET /experiments/{id}` | `ExperimentWorkspacePage.tsx`, `VivaSimulatorPage.tsx` | 🔴 P0 |
| **Update Experiment** | `experimentStorage.updateExperiment()` | `PATCH /experiments/{id}` | `EditExperimentModal.tsx`, `ExperimentWorkspacePage.tsx` | 🔴 P0 |
| **Delete Experiment** | `experimentStorage.deleteExperiment()` | `DELETE /experiments/{id}` | `DeleteExperimentModal.tsx` | 🔴 P0 |
| **Preparation Checklist** | `experimentStorage.toggleChecklistItem()` | `PATCH /experiments/{id}/checklist` | `WorkspaceChecklistTab.tsx` | 🟠 P1 |
| **Viva Question Generation** | `DemonstrationVivaProvider.generateQuestions()` (templates) | `POST /viva/generate-questions` (AI proxy) | `VivaActiveSession.tsx`, `vivaAIProvider.ts` | 🟠 P1 |
| **Answer Evaluation** | Keyword-matching heuristic | `POST /viva/evaluate-answer` (AI proxy) | `VivaActiveSession.tsx`, `vivaAIProvider.ts` | 🟠 P1 |
| **Session Analysis** | Pure in-memory computation | Optional: `POST /viva/analyze-session`; or keep client-side | `VivaSimulatorPage.tsx` | 🟢 P3 |
| **Save Viva Session** | `vivaStorage.saveSession()` → localStorage | `POST /viva-sessions` | `VivaSimulatorPage.tsx` | 🔴 P0 |
| **List Viva Sessions** | `vivaStorage.getSessions()` | `GET /viva-sessions?userId={id}` | `VivaPracticeHubPage.tsx`, `ProgressRevisionPage.tsx`, `SessionHistoryTable.tsx` | 🔴 P0 |
| **Delete Viva Session** | `vivaStorage.deleteSession()` | `DELETE /viva-sessions/{id}` | `SessionHistoryTable.tsx` | 🟠 P1 |
| **Progress Analytics** | Pure functions over localStorage data | Inputs come from experiment + viva APIs; computation stays client | `ProgressRevisionPage.tsx`, `progressAnalytics.ts` | 🟢 P3 |
| **Sync Study Preferences** | `settingsStorage.saveSettings()` → localStorage | `PATCH /users/{id}/settings` | `StudyPreferencesSection.tsx` | 🟡 P2 |
| **Export User Data** | Reads localStorage, returns JSON blob | `GET /users/{id}/export` | `DataPrivacySection.tsx` | 🟠 P1 |
| **Clear All User Data** | Removes localStorage keys | `DELETE /users/{id}/data` | `DataPrivacySection.tsx` | 🟠 P1 |
| **Sign Out** | Removes `pracprep_user`, navigates to `/login` | `POST /auth/logout` (token revocation) | `AccountActionsSection.tsx` | 🔴 P0 |
| **Delete Account** | Clears localStorage after confirm | `DELETE /users/{id}` (cascade) | `AccountActionsSection.tsx` | 🟠 P1 |
| **Guest-to-Account Migration** | Not implemented | Accept optional `guestData` on `POST /auth/register` | `AuthPage.tsx` (sign-up) | 🟡 P2 |

---

## 9. Functionality to Keep Frontend-Only

| Feature | Location | Reason |
|---------|----------|--------|
| Theme switching (light/dark/system) | `AppearanceSettingsSection`, `settingsStorage.applyTheme()` | Instant feedback; device preference |
| Density mode | `settingsStorage.applyDisplayPreferences()` | Layout preference |
| Reduced motion toggle | `settingsStorage`, CSS `data-reduced-motion` | Accessibility |
| Sidebar collapse/expand | `DashboardLayout.tsx` local state | Ephemeral UI |
| Mobile menu, search dialog open state | `DashboardLayout.tsx` local state | Ephemeral UI |
| ⌘K keyboard shortcut | `DashboardLayout.tsx` keydown handler | Client event |
| Tab switching in workspace | `ExperimentWorkspacePage.tsx` `activeTab` | Ephemeral nav |
| Form field input state | All form components | Transient |
| Sign-in/up animation | `AuthPage.tsx` CSS `::before` bubble | Pure CSS |
| Inline form validation | All form components | Pre-submit client validation |
| Client-side search/filter/sort | `MyExperimentsPage.tsx`, `ExperimentToolbar.tsx` | Appropriate for small datasets after API fetch |
| Progress analytics computation | `progressAnalytics.ts` (7 functions) | Pure derivations; no server advantage at current scale |
| Error boundary display | `ErrorBoundary.tsx` | Runtime error handling |
| Hero CrowdCanvas, 404 ghost animation | `skiper39.tsx`, `ghost-404-page.tsx` | GSAP / framer-motion UI |

---

## 10. Risks and Architectural Observations

**A. No authentication layer.** Any URL under `/dashboard`, `/experiments`, `/settings`, etc. is directly accessible without authentication. No route guard exists.

**B. ID collision.** Experiment IDs are `exp-${Date.now()}`. Two experiments created within the same millisecond will collide. Backend should use UUID.

**C. File upload is non-functional.** "Upload Lab Manual" creates an experiment with `hasManualFile: true` but all content fields `undefined`. No file is ever transmitted. There is no user feedback that extraction did not occur.

**D. Email as storage partition key.** The localStorage scoping formula uses `email.replace(/[^a-z0-9]/g, "_")`. If a user changes their email, they permanently lose access to their localStorage data. Backend integration must use `userId` as the partition key instead.

**E. No storage versioning.** When `ExperimentRecord` shape changes, there is no migration path. `normalizeRecord()` provides partial backwards compatibility but has no version identifier.

**F. localStorage quota risk.** Experiments with full text content plus many viva sessions with complete `answers[]` arrays can fill the ~5–10MB browser quota. No quota management or graceful overflow handling exists.

**G. `vivaStorage.subscribe()` has no active callers.** The subscription for viva session changes is defined but not called by any component. Viva session list views read on mount only and do not react to updates.

**H. `vivaStorage` subscriber gap causes stale session lists.** When a viva session is saved, `VivaPracticeHubPage` and `SessionHistoryTable` do not automatically refresh because they are not subscribed to `pracprep_viva_sessions_changed`.

**I. Tight coupling: user resolution in `DashboardLayout`.** `DashboardLayout.tsx` reads `localStorage["pracprep_user"]` directly in a `useMemo`. This must be replaced with an auth context / hook when a backend is added.

**J. `ExperimentSummaryRow` computes session counts on every render.** Both `experiments[]` and `vivaSessions[]` are iterated via `.filter()` inline. This will require memoization or server-side aggregation at scale.

**K. `AuthPage.tsx` is 943 lines with embedded CSS animation in a JSX string.** The `::before` bubble animation is defined in a `<style>{...}</style>` block inside the component. Fragile and difficult to maintain.

---

## 11. Recommended Backend Implementation Sequence

### Phase 1 — Identity & Core Data (Unblocks all other phases)

1. **Auth API:** `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`. Add React auth context; protect dashboard routes. Update `AuthPage.tsx`.
2. **Experiment CRUD:** `POST`, `GET`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`. Replace `experimentStorage` method bodies.
3. **Viva Session CRUD:** `POST /viva-sessions`, `GET /viva-sessions`, `DELETE /viva-sessions/{id}`. Replace `vivaStorage` method bodies.
4. **User profile:** `PATCH /users/{id}/profile`, `DELETE /users/{id}`.

### Phase 2 — AI Integration (Core product differentiator)

5. **AI Viva Engine:** `POST /viva/generate-questions`, `POST /viva/evaluate-answer`. Create `LiveAIVivaProvider implements IVivaAIProvider`. Add `VITE_AI_PROVIDER_URL` environment variable.
6. **Lab Manual Parsing:** `POST /experiments/upload` (multipart). Wire `LabManualUploader.tsx` to this endpoint. Return extracted content sections.

### Phase 3 — Sync & Cross-Device

7. **Settings sync:** `PATCH /users/{id}/settings` for `studyPreferences`.
8. **Checklist as dedicated endpoint:** `PATCH /experiments/{id}/checklist`.
9. **Data export:** `GET /users/{id}/export`.

### Phase 4 — Guest Migration (Optional)

10. On `POST /auth/register`, accept optional `guestData` payload. Frontend: detect guest localStorage at sign-up time and include in request body.

---

## 12. Open Questions

1. **Guest data permanence.** Should guest sessions be ephemeral (browser-only) or given a temporary server token with expiry? Currently lost on browser clear.

2. **Lab manual parsing service.** Which AI/OCR service will extract sections from uploaded PDF/DOCX? This determines latency, accuracy, and the upload API design.

3. **AI provider architecture.** Will the backend proxy AI calls (keeping API keys server-side), or will the frontend call AI APIs directly with client-exposed keys?

4. **Checklist storage granularity.** Embedded JSON blob in `ExperimentRecord.preparationChecklist` vs. a dedicated `checklist_completions` join table.

5. **Session concurrency.** Can a user start multiple viva sessions for the same experiment simultaneously? The current frontend handles it by array ordering.

6. **Email mutability.** If a user changes their email post-registration, the current localStorage scoping key breaks. Backend integration must use `userId` (UUID) as the primary data key.

7. **Data retention on `clearAllUserData()`.** Should the backend perform a hard delete or a soft delete with a retention window?

---

*End of Audit Report*

*This report was produced through read-only inspection of the PracPrep source code. No application source files were created, modified, deleted, or renamed. The final document is saved at `docs/frontend-architecture-audit.md`.*
