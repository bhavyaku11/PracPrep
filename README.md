# PracPrep — From Lab Manual to Lab-Ready

An AI-powered laboratory preparation companion for engineering students. PracPrep bridges the gap between static laboratory manuals and hands-on laboratory readiness through automated manual digestion, interactive experiment workspaces, conceptual viva voce practice, performance analytics, and personalized revision planning.

---

## 1. Project Overview & Features

PracPrep is structured across eight integrated modules:

| Module | Route | Description |
|---|---|---|
| **Landing & Onboarding** | `/`, `/login`, `/signup`, `/guest` | Interactive landing hero, guest sandbox access, and student authentication. |
| **Dashboard Shell** | `/dashboard` | Centralized laboratory cockpit displaying preparation snapshots, viva scores, recent activity, and quick navigation. |
| **Experiment Creation** | `/create-experiment` | Dual-mode entry via PDF manual upload parsing or structured manual data entry (title, subject, apparatus, theory, procedure). |
| **My Experiments** | `/experiments` | Filterable, searchable, and sortable registry of student laboratory practicals with status indicators and quick actions. |
| **Experiment Workspace** | `/experiments/:id` | Dedicated study hub containing overview, apparatus specifications, procedure steps, interactive preparation checklist, formulas, and observations. |
| **AI Viva Voce Simulator** | `/viva-practice`, `/experiments/:id/viva` | Oral examination simulator generating conceptual viva questions tailored to experiments, instant rubric-based evaluation, and performance analysis. |
| **Progress & Revision Center** | `/progress` | Comprehensive learning analytics, readiness scores, weak-topic identification, and targeted revision recommendations. |
| **Settings & Personalization** | `/settings` | Student identity management, theme preferences (Light / Dark / System), motion controls, scoped data export (JSON), and isolated data clearing. |

---

## 2. Technology Stack & Architecture

- **Core**: React 19, TypeScript (~6.0), Vite 8
- **Styling**: Tailwind CSS v4, CSS custom tokens, full Dark Mode support
- **Icons & Animation**: Lucide React, GSAP animations, accessible reduced-motion support
- **Resilience**: Global Error Boundary with diagnostic logging and crash recovery
- **Persistence**: Session-scoped local-first persistence (`localStorage`)
  - Authenticated student data: scoped by sanitized user email (`pracprep_*_user_<email>`)
  - Guest mode: isolated sandbox (`pracprep_*_guest`)
  - Cross-tab reactive synchronization via `CustomEvent` and `StorageEvent` listeners

---

## 3. Getting Started

### Prerequisites

- Node.js 18+ (tested on Node v20/v24)
- npm or pnpm

### Installation

```bash
# Clone the repository and install dependencies
npm install
```

### Development Server

```bash
# Start local Vite development server
npm run dev
```

The application will be available at `http://localhost:5173` (or the port specified by Vite).

### Running Tests & Quality Checks

PracPrep includes comprehensive automated test suites covering analytics, settings persistence, and end-to-end integration:

```bash
# Run all automated unit and integration test suites
npm test

# Run code linter
npm run lint

# Run TypeScript type check
npx tsc --noEmit

# Run production build
npm run build
```

---

## 4. Architectural Boundaries & Known Limitations

1. **Demonstration Mode for AI Viva Evaluation**:
   The viva simulator operates with an Academic Evaluation Engine running in Demonstration Mode. It analyzes student responses locally against question rubrics, expected keywords, and technical depth. It does not connect to an external live LLM cloud backend.
2. **Local-First Storage**:
   All experiment manuals, checklist states, settings, and viva session records are stored in browser `localStorage`. No remote server or external database is required. Clearing browser cache or switching devices will reset local state.
3. **Browser Automation Testing**:
   Automated verification relies on Node.js integration test suites (`test-integration.mjs`, `test-progressAnalytics.mjs`, `test-settingsStorage.mjs`) alongside static analysis (`oxlint`, `tsc`). In environments without pre-installed browser binaries (such as Playwright ARM64 offline), manual browser validation or headless verification is used.

---

## 5. Deployment Guide

PracPrep compiles to a static single-page application (SPA).

```bash
npm run build
```

The production bundle is generated in the `dist/` directory.

### SPA Client-Side Routing

Since PracPrep uses client-side routing (`/dashboard`, `/experiments`, `/viva-practice`, `/progress`, `/settings`, etc.), web servers and hosting providers must be configured to rewrite all 404 requests back to `index.html`.

- **Vercel / Netlify**: Automatic with standard SPA presets or `_redirects` (`/*  /index.html  200`).
- **Nginx**:
  ```nginx
  location / {
    try_files $uri $uri/ /index.html;
  }
  ```
- **Apache**: Standard `.htaccess` rewrite rule to `index.html`.

---

## 6. License

Academic and educational use under Hacktoberfest Challenges.
