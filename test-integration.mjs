import assert from "node:assert";

// Mock localStorage and window environment for Node execution
const storageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] ?? null,
    setItem: (key, val) => {
      store[key] = String(val);
    },
    removeItem: (key) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    },
    getStore: () => store,
  };
})();

globalThis.localStorage = storageMock;

const eventListeners = new Map();
globalThis.window = {
  addEventListener: (event, handler) => {
    if (!eventListeners.has(event)) eventListeners.set(event, []);
    eventListeners.get(event).push(handler);
  },
  removeEventListener: (event, handler) => {
    if (eventListeners.has(event)) {
      const filtered = eventListeners.get(event).filter((h) => h !== handler);
      eventListeners.set(event, filtered);
    }
  },
  dispatchEvent: (event) => {
    const handlers = eventListeners.get(event.type) || [];
    handlers.forEach((h) => h(event));
    return true;
  },
  matchMedia: (query) => ({
    matches: false,
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }),
};

let appliedThemeClass = "";
let appliedAttributes = {};

globalThis.document = {
  documentElement: {
    classList: {
      add: (cls) => {
        appliedThemeClass = cls;
      },
      remove: (cls) => {
        if (appliedThemeClass === cls) appliedThemeClass = "";
      },
    },
    setAttribute: (attr, val) => {
      appliedAttributes[attr] = val;
    },
  },
};

globalThis.CustomEvent = class CustomEvent {
  constructor(type, eventInitDict) {
    this.type = type;
    this.detail = eventInitDict?.detail;
  }
};

globalThis.StorageEvent = class StorageEvent {
  constructor(type, eventInitDict) {
    this.type = type;
    this.key = eventInitDict?.key;
    this.newValue = eventInitDict?.newValue;
  }
};

import { experimentStorage } from "./src/services/experimentStorage.ts";
import { vivaStorage } from "./src/services/vivaStorage.ts";
import { settingsStorage, DEFAULT_SETTINGS } from "./src/services/settingsStorage.ts";
import { calculateOverviewMetrics } from "./src/utils/progressAnalytics.ts";

console.log("=== Running Phase 8 E2E Integration & QA Test Suite ===");

// 1. Experiment Lifecycle: Create -> Save -> List -> Update -> Checklist -> Delete
{
  storageMock.clear();
  const user = { isGuest: false, name: "Alice", email: "alice@mit.edu" };

  // Create & Save
  const newExp = experimentStorage.saveExperiment(
    {
      title: "Verification of Thevenin's Theorem",
      subject: "Network Analysis",
      experimentNumber: "EE-101",
      method: "manual",
      objective: "To verify Thevenin equivalent voltage and resistance.",
      apparatus: "DC Power Supply, Resistors, Multimeter",
      theory: "Any linear bilateral active network can be replaced by an equivalent voltage source.",
      procedure: "Connect circuit, Measure Voc, Calculate Rth",
    },
    user
  );

  assert.ok(newExp.id, "Experiment ID should be generated");
  assert.strictEqual(newExp.title, "Verification of Thevenin's Theorem");

  // List
  const list = experimentStorage.getExperiments(user);
  assert.strictEqual(list.length, 1, "Should retrieve 1 experiment for user");
  assert.strictEqual(list[0].id, newExp.id);

  // Toggle Checklist
  const toggled = experimentStorage.toggleChecklistItem(newExp.id, "read_theory", true, user);
  assert.ok(toggled, "Checklist update should succeed");
  assert.strictEqual(toggled.preparationChecklist?.read_theory, true);

  // Update Metadata
  const updatedExp = experimentStorage.updateExperiment(
    newExp.id,
    { status: "in-progress", observations: "Laboratory observations verified with lab instructor" },
    user
  );
  assert.ok(updatedExp, "Update should return updated experiment");
  assert.strictEqual(updatedExp.status, "in-progress");
  assert.strictEqual(updatedExp.observations, "Laboratory observations verified with lab instructor");

  // Verify list reflects updates without duplicates
  const listAfterUpdate = experimentStorage.getExperiments(user);
  assert.strictEqual(listAfterUpdate.length, 1, "Should not duplicate record on update");
  assert.strictEqual(listAfterUpdate[0].status, "in-progress");
  assert.strictEqual(listAfterUpdate[0].preparationChecklist?.read_theory, true);

  // Delete
  const deleted = experimentStorage.deleteExperiment(newExp.id, user);
  assert.strictEqual(deleted, true, "Delete should succeed");
  const listAfterDelete = experimentStorage.getExperiments(user);
  assert.strictEqual(listAfterDelete.length, 0, "List should be empty after deletion");

  console.log("✓ Gate 1 Passed: Complete Experiment Lifecycle (Create, List, Update, Checklist, Delete)");
}

// 2. Viva Session Lifecycle & Completed vs Incomplete Handling
{
  storageMock.clear();
  const user = { isGuest: false, name: "Bob", email: "bob@stanford.edu" };

  const completedSession = {
    id: "viva-sess-1",
    experimentId: "exp-101",
    experimentTitle: "Ohm's Law Verification",
    experimentSubject: "Basic Electrical",
    startedAt: "2026-10-01T10:00:00.000Z",
    completedAt: "2026-10-01T10:15:00.000Z",
    isCompleted: true,
    totalQuestions: 5,
    answeredQuestions: 5,
    averageScore: 8.5,
    correctCount: 4,
    partiallyCorrectCount: 1,
    incorrectCount: 0,
    topicBreakdown: [
      { topic: "Theory & Principles", score: 9.0, totalQuestions: 2 },
      { topic: "Calculations", score: 8.0, totalQuestions: 3 },
    ],
    config: {
      difficulty: "medium",
      questionCount: 5,
      focusArea: "mixed",
    },
    evaluations: [],
  };

  const incompleteSession = {
    id: "viva-sess-2",
    experimentId: "exp-101",
    experimentTitle: "Ohm's Law Verification",
    experimentSubject: "Basic Electrical",
    startedAt: "2026-10-02T11:00:00.000Z",
    isCompleted: false, // Abandoned session
    totalQuestions: 5,
    answeredQuestions: 1,
    averageScore: 2.0,
    correctCount: 0,
    partiallyCorrectCount: 1,
    incorrectCount: 0,
    topicBreakdown: [],
    config: {
      difficulty: "medium",
      questionCount: 5,
      focusArea: "mixed",
    },
    evaluations: [],
  };

  vivaStorage.saveSession(completedSession, user);
  vivaStorage.saveSession(incompleteSession, user);

  const allSessions = vivaStorage.getSessions(user);
  assert.strictEqual(allSessions.length, 2, "Both sessions should be persisted in raw storage");

  // Validate Analytics strictly handles completed vs incomplete
  const dummyExperiments = [
    {
      id: "exp-101",
      title: "Ohm's Law Verification",
      subject: "Basic Electrical",
      method: "manual",
      hasManualFile: false,
      createdAt: "2026-10-01",
      createdAtTimestamp: 1727776800000,
      updatedAt: "2026-10-01",
      status: "in-progress",
      checklistItems: [],
    },
  ];

  const metrics = calculateOverviewMetrics(dummyExperiments, allSessions, "all");
  assert.strictEqual(metrics.vivaSessionsCount, 2, "Total sessions count is 2");
  assert.strictEqual(metrics.completedVivaSessionsCount, 1, "Completed sessions count must be exactly 1");
  assert.strictEqual(metrics.averageVivaScore, 8.5, "Average score must ONLY average completed sessions (8.5, not 5.25)");

  console.log("✓ Gate 2 Passed: Viva Session Persistence & Incomplete vs Completed Analytics Consistency");
}

// 3. User Data Isolation: User A vs User B vs Guest Mode
{
  storageMock.clear();
  const guestUser = { isGuest: true, name: "Guest Student" };
  const userA = { isGuest: false, name: "Alice Cooper", email: "alice@columbia.edu" };
  const userB = { isGuest: false, name: "Bob Martin", email: "bob@cmu.edu" };

  // 1. Experiments isolation
  experimentStorage.saveExperiment({ title: "Guest Physics Lab", subject: "Physics" }, guestUser);
  experimentStorage.saveExperiment({ title: "Alice Chemistry Lab", subject: "Chemistry" }, userA);
  experimentStorage.saveExperiment({ title: "Bob Robotics Lab", subject: "Robotics" }, userB);

  const guestExps = experimentStorage.getExperiments(guestUser);
  const userAExps = experimentStorage.getExperiments(userA);
  const userBExps = experimentStorage.getExperiments(userB);

  assert.strictEqual(guestExps.length, 1);
  assert.strictEqual(guestExps[0].title, "Guest Physics Lab");

  assert.strictEqual(userAExps.length, 1);
  assert.strictEqual(userAExps[0].title, "Alice Chemistry Lab");

  assert.strictEqual(userBExps.length, 1);
  assert.strictEqual(userBExps[0].title, "Bob Robotics Lab");

  // 2. Settings isolation
  settingsStorage.saveSettings(
    { ...DEFAULT_SETTINGS, theme: "dark", studyPreferences: { ...DEFAULT_SETTINGS.studyPreferences, defaultQuestionCount: 10 } },
    userA
  );
  settingsStorage.saveSettings(
    { ...DEFAULT_SETTINGS, theme: "light", studyPreferences: { ...DEFAULT_SETTINGS.studyPreferences, defaultQuestionCount: 3 } },
    userB
  );

  const userASettings = settingsStorage.getSettings(userA);
  const userBSettings = settingsStorage.getSettings(userB);
  const guestSettings = settingsStorage.getSettings(guestUser);

  assert.strictEqual(userASettings.theme, "dark");
  assert.strictEqual(userASettings.studyPreferences.defaultQuestionCount, 10);

  assert.strictEqual(userBSettings.theme, "light");
  assert.strictEqual(userBSettings.studyPreferences.defaultQuestionCount, 3);

  assert.strictEqual(guestSettings.theme, "system");
  assert.strictEqual(guestSettings.studyPreferences.defaultQuestionCount, 5);

  // 3. Clear Scoped Data Isolation
  settingsStorage.clearAllUserData(guestUser);
  assert.strictEqual(experimentStorage.getExperiments(guestUser).length, 0, "Guest data should be cleared");
  assert.strictEqual(experimentStorage.getExperiments(userA).length, 1, "User A data must NOT be cleared when clearing guest");
  assert.strictEqual(experimentStorage.getExperiments(userB).length, 1, "User B data must NOT be cleared when clearing guest");

  console.log("✓ Gate 3 Passed: Multi-Tenant Data Isolation between Distinct Users and Guest Mode");
}

// 4. Data Export Integrity
{
  storageMock.clear();
  const user = { isGuest: false, name: "Diana Prince", email: "diana@themyscira.edu" };

  experimentStorage.saveExperiment({ title: "Aerodynamics Test", subject: "Aeronautics" }, user);
  settingsStorage.saveSettings({ ...DEFAULT_SETTINGS, theme: "dark" }, user);

  const payload = settingsStorage.exportUserData(user);

  assert.strictEqual(payload.exportVersion, "1.0");
  assert.strictEqual(payload.userSession.email, "diana@themyscira.edu");
  assert.strictEqual(payload.experiments.length, 1);
  assert.strictEqual(payload.experiments[0].title, "Aerodynamics Test");
  assert.strictEqual(payload.settings.theme, "dark");
  assert.ok(payload.exportedAt);

  console.log("✓ Gate 4 Passed: Scoped Data Export Payload Correctness");
}

// 5. Corrupt Data Resilience & Safe Fallbacks
{
  storageMock.clear();
  const user = { isGuest: false, name: "Eve", email: "eve@sec.edu" };

  // Inject corrupt non-JSON strings into localStorage
  storageMock.setItem("pracprep_experiments_user_eve_sec_edu", "CORRUPT_JSON{{{[[");
  storageMock.setItem("pracprep_viva_sessions_user_eve_sec_edu", "undefined_NULL_ERR");
  storageMock.setItem("pracprep_settings_user_eve_sec_edu", "###BROKEN##");

  // Call getters - none of them should throw, all should return safe fallbacks
  const safeExps = experimentStorage.getExperiments(user);
  assert.deepStrictEqual(safeExps, [], "Corrupt experiment storage must safely return []");

  const safeViva = vivaStorage.getSessions(user);
  assert.deepStrictEqual(safeViva, [], "Corrupt viva storage must safely return []");

  const safeSettings = settingsStorage.getSettings(user);
  assert.deepStrictEqual(safeSettings, DEFAULT_SETTINGS, "Corrupt settings storage must safely return DEFAULT_SETTINGS");

  console.log("✓ Gate 5 Passed: Corrupt LocalStorage Resilience & Graceful Error Fallbacks");
}

// 6. Cross-Module Sync: Deleted Experiments in Viva History
{
  storageMock.clear();
  const user = { isGuest: false, name: "Frank", email: "frank@tech.edu" };

  const exp = experimentStorage.saveExperiment({ title: "Digital Logic Gates", subject: "ECE" }, user);
  vivaStorage.saveSession(
    {
      id: "viva-gate-1",
      experimentId: exp.id,
      experimentTitle: "Digital Logic Gates",
      experimentSubject: "ECE",
      isCompleted: true,
      totalQuestions: 3,
      answeredQuestions: 3,
      averageScore: 9.0,
      correctCount: 3,
      partiallyCorrectCount: 0,
      incorrectCount: 0,
      topicBreakdown: [],
      config: { difficulty: "easy", questionCount: 3, focusArea: "mixed" },
      evaluations: [],
    },
    user
  );

  // Now delete experiment
  experimentStorage.deleteExperiment(exp.id, user);
  assert.strictEqual(experimentStorage.getExperiments(user).length, 0);

  // Viva session should still be intact and retain title
  const sessions = vivaStorage.getSessions(user);
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].experimentTitle, "Digital Logic Gates");

  // Progress metrics should handle deleted experiment without crash
  const metrics = calculateOverviewMetrics([], sessions, "all");
  assert.strictEqual(metrics.totalExperiments, 0);
  assert.strictEqual(metrics.completedVivaSessionsCount, 1);
  assert.strictEqual(metrics.averageVivaScore, 9.0);

  console.log("✓ Gate 6 Passed: Cross-Module Sync & Historical Viva Resilience after Experiment Deletion");
}

console.log("ALL 6 PHASE 8 E2E INTEGRATION GATES PASSED CLEANLY!\n");
