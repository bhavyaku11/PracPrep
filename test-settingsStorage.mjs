import assert from "node:assert";

// Mock localStorage and window environment for Node execution
const storageMock = (() => {
  let store = {};
  return {
    getItem: (key) => store[key] || null,
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

const eventListeners = new Map();

globalThis.localStorage = storageMock;
globalThis.window = {
  localStorage: storageMock,
  addEventListener: (event, handler) => {
    if (!eventListeners.has(event)) eventListeners.set(event, []);
    eventListeners.get(event).push(handler);
  },
  removeEventListener: (event, handler) => {
    if (eventListeners.has(event)) {
      eventListeners.set(
        event,
        eventListeners.get(event).filter((h) => h !== handler)
      );
    }
  },
  dispatchEvent: (event) => {
    const handlers = eventListeners.get(event.type) || [];
    for (const handler of handlers) {
      handler(event);
    }
    return true;
  },
  matchMedia: () => ({ matches: false, addEventListener: () => {} }),
};

globalThis.CustomEvent = class CustomEvent {
  constructor(type, init) {
    this.type = type;
    this.detail = init?.detail;
  }
};

globalThis.StorageEvent = class StorageEvent {
  constructor(type, init) {
    this.type = type;
    this.key = init?.key;
    this.newValue = init?.newValue;
  }
};

globalThis.document = {
  documentElement: {
    classList: {
      add: () => {},
      remove: () => {},
    },
    setAttribute: () => {},
  },
};

function createMockResponse(body, init = {}) {
  const status = init.status ?? 200;
  const statusText = init.statusText ?? (status >= 200 && status < 300 ? "OK" : "Error");
  const headers = new Headers(init.headers || {});

  let bodyText = "";
  if (typeof body === "object" && body !== null) {
    bodyText = JSON.stringify(body);
    if (!headers.has("content-type")) {
      headers.set("content-type", "application/json");
    }
  } else if (typeof body === "string") {
    bodyText = body;
  }

  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    headers,
    text: async () => bodyText,
    json: async () => JSON.parse(bodyText || "{}"),
  };
}

import {
  settingsStorage,
  DEFAULT_SETTINGS,
  BASE_SETTINGS_KEY,
  SETTINGS_UPDATE_EVENT,
  ApiError,
  localSettingsAdapter,
} from "./src/services/settingsStorage.ts";
import { experimentStorage } from "./src/services/experimentStorage.ts";
import { vivaStorage } from "./src/services/vivaStorage.ts";
import { tokenManager } from "./src/lib/apiClient.ts";

console.log("=== Running TASK-12.2 Settings Storage & Dual-Mode Facade Tests ===");

// =============================================================================
// I. GUEST BEHAVIOR TESTS (Scenarios 1 - 5)
// =============================================================================

// Scenario 1: Guest settings are stored under pracprep_settings_guest
{
  storageMock.clear();
  const guestUser = { isGuest: true };
  const custom = {
    ...DEFAULT_SETTINGS,
    studyPreferences: {
      defaultDifficulty: "beginner",
      defaultQuestionCount: 5,
      preferredFocus: "theory",
    },
  };

  settingsStorage.saveSettings(custom, guestUser);
  const rawStored = storageMock.getItem(`${BASE_SETTINGS_KEY}_guest`);
  assert.ok(rawStored, "Guest settings must be present under pracprep_settings_guest");
  const parsed = JSON.parse(rawStored);
  assert.strictEqual(parsed.studyPreferences.defaultDifficulty, "beginner");
  console.log("✓ Scenario 1 Passed: Guest settings are stored under pracprep_settings_guest");
}

// Scenario 2: Guest saves issue zero network requests
{
  let networkCalled = false;
  globalThis.fetch = async () => {
    networkCalled = true;
    throw new Error("Network should not be called for guests!");
  };

  const guestUser = { isGuest: true };
  settingsStorage.saveSettings(DEFAULT_SETTINGS, guestUser);
  await settingsStorage.saveSettingsAsync(DEFAULT_SETTINGS, guestUser);
  assert.strictEqual(networkCalled, false, "Guest saves must not make network requests");
  console.log("✓ Scenario 2 Passed: Guest saves issue zero network requests");
}

// Scenario 3: Guest reads remain strictly synchronous
{
  const guestUser = { isGuest: true };
  const result = settingsStorage.getSettings(guestUser);
  assert.strictEqual(result instanceof Promise, false, "getSettings() must return synchronously, not a Promise");
  assert.strictEqual(typeof result.studyPreferences.defaultDifficulty, "string");
  console.log("✓ Scenario 3 Passed: Guest reads remain synchronous");
}

// Scenario 4: Guest display preferences persist locally
{
  storageMock.clear();
  const guestUser = { isGuest: true };
  const displayConfig = {
    ...DEFAULT_SETTINGS,
    theme: "dark",
    density: "compact",
    reducedMotion: true,
  };

  settingsStorage.saveSettings(displayConfig, guestUser);
  const retrieved = settingsStorage.getSettings(guestUser);
  assert.strictEqual(retrieved.theme, "dark");
  assert.strictEqual(retrieved.density, "compact");
  assert.strictEqual(retrieved.reducedMotion, true);
  console.log("✓ Scenario 4 Passed: Guest display preferences persist locally");
}

// Scenario 5: Guest data does not leak into authenticated user caches
{
  storageMock.clear();
  const guestUser = { isGuest: true };
  const authUser = { isGuest: false, name: "Alice", email: "alice@university.edu" };

  settingsStorage.saveSettings(
    {
      ...DEFAULT_SETTINGS,
      studyPreferences: { defaultDifficulty: "beginner", defaultQuestionCount: 5, preferredFocus: "theory" },
    },
    guestUser
  );

  settingsStorage.saveSettings(
    {
      ...DEFAULT_SETTINGS,
      studyPreferences: { defaultDifficulty: "advanced", defaultQuestionCount: 15, preferredFocus: "observations" },
    },
    authUser
  );

  const guestSettings = settingsStorage.getSettings(guestUser);
  const authSettings = settingsStorage.getSettings(authUser);

  assert.strictEqual(guestSettings.studyPreferences.defaultDifficulty, "beginner");
  assert.strictEqual(authSettings.studyPreferences.defaultDifficulty, "advanced");
  assert.notStrictEqual(
    localSettingsAdapter.getScopedSettingsKey(guestUser),
    localSettingsAdapter.getScopedSettingsKey(authUser)
  );
  console.log("✓ Scenario 5 Passed: Guest data does not leak into authenticated user caches");
}

// =============================================================================
// II. AUTHENTICATED BEHAVIOR TESTS (Scenarios 6 - 15)
// =============================================================================

// Scenario 6 & 7: Authenticated updates issue PATCH to /api/v1/users/me/settings with only study preferences
{
  storageMock.clear();
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, name: "Student A", email: "student_a@college.edu" };

  let capturedUrl = "";
  let capturedMethod = "";
  let capturedBody = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = String(url);
    capturedMethod = options.method;
    capturedBody = JSON.parse(options.body);

    return createMockResponse({
      id: "set-001",
      userId: "usr-001",
      defaultDifficulty: capturedBody.defaultDifficulty,
      defaultQuestionCount: capturedBody.defaultQuestionCount,
      preferredFocus: capturedBody.preferredFocus,
      createdAt: "2026-10-04T12:00:00Z",
      updatedAt: "2026-10-04T12:00:00Z",
    });
  };

  const payload = {
    theme: "dark",
    density: "compact",
    reducedMotion: true,
    studyPreferences: {
      defaultDifficulty: "advanced",
      defaultQuestionCount: 15,
      preferredFocus: "observations",
    },
  };

  await settingsStorage.saveSettingsAsync(payload, authUser);

  assert.ok(capturedUrl.includes("/users/me/settings"), `Expected URL to include /users/me/settings, got: ${capturedUrl}`);
  assert.strictEqual(capturedMethod, "PATCH");
  assert.strictEqual(capturedBody.defaultDifficulty, "advanced");
  assert.strictEqual(capturedBody.defaultQuestionCount, 15);
  assert.strictEqual(capturedBody.preferredFocus, "observations");

  // Critical: Display preferences and IDs must NEVER be sent to the backend
  assert.strictEqual(capturedBody.theme, undefined);
  assert.strictEqual(capturedBody.density, undefined);
  assert.strictEqual(capturedBody.reducedMotion, undefined);
  assert.strictEqual(capturedBody.id, undefined);
  assert.strictEqual(capturedBody.userId, undefined);

  console.log("✓ Scenario 6 Passed: Authenticated study preference updates issue PATCH to correct endpoint");
  console.log("✓ Scenario 7 Passed: PATCH payload contains only study preference fields");
}

// Scenario 8 & 9: Remote GET populates local cache and merges without overwriting display preferences
{
  storageMock.clear();
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, name: "Student B", email: "student_b@college.edu" };

  // Set local display preferences beforehand
  settingsStorage.saveSettings(
    {
      ...DEFAULT_SETTINGS,
      theme: "dark",
      density: "compact",
      reducedMotion: true,
      studyPreferences: { defaultDifficulty: "mixed", defaultQuestionCount: 5, preferredFocus: "mixed" },
    },
    authUser
  );

  globalThis.fetch = async (_url, _options) => {
    return createMockResponse({
      id: "set-002",
      userId: "usr-002",
      defaultDifficulty: "intermediate",
      defaultQuestionCount: 10,
      preferredFocus: "procedure",
      createdAt: "2026-10-04T12:00:00Z",
      updatedAt: "2026-10-04T12:00:00Z",
    });
  };

  const synced = await settingsStorage.syncRemoteSettings(authUser);

  // Remote study preferences merged
  assert.strictEqual(synced.studyPreferences.defaultDifficulty, "intermediate");
  assert.strictEqual(synced.studyPreferences.defaultQuestionCount, 10);
  assert.strictEqual(synced.studyPreferences.preferredFocus, "procedure");

  // Local display preferences strictly preserved
  assert.strictEqual(synced.theme, "dark");
  assert.strictEqual(synced.density, "compact");
  assert.strictEqual(synced.reducedMotion, true);

  // Cached settings in storage reflect the merged state
  const cached = settingsStorage.getSettings(authUser);
  assert.strictEqual(cached.studyPreferences.defaultDifficulty, "intermediate");
  assert.strictEqual(cached.theme, "dark");

  console.log("✓ Scenario 8 Passed: Remote GET populates the local cache");
  console.log("✓ Scenario 9 Passed: Remote study preferences merge without overwriting local display preferences");
}

// Scenario 10: Authenticated settings reads remain synchronous
{
  const authUser = { isGuest: false, email: "student_c@college.edu" };
  const syncResult = settingsStorage.getSettings(authUser);
  assert.strictEqual(syncResult instanceof Promise, false, "Authenticated getSettings() must be synchronous");
  assert.strictEqual(typeof syncResult.studyPreferences, "object");
  console.log("✓ Scenario 10 Passed: Authenticated settings reads remain synchronous");
}

// Scenario 11: Switching accounts loads the correct user's settings
{
  storageMock.clear();
  const user1 = { isGuest: false, email: "alice@lab.edu" };
  const user2 = { isGuest: false, email: "bob@lab.edu" };

  settingsStorage.saveSettings(
    {
      ...DEFAULT_SETTINGS,
      studyPreferences: { defaultDifficulty: "beginner", defaultQuestionCount: 5, preferredFocus: "apparatus" },
    },
    user1
  );

  settingsStorage.saveSettings(
    {
      ...DEFAULT_SETTINGS,
      studyPreferences: { defaultDifficulty: "advanced", defaultQuestionCount: 15, preferredFocus: "precautions" },
    },
    user2
  );

  assert.strictEqual(settingsStorage.getSettings(user1).studyPreferences.defaultDifficulty, "beginner");
  assert.strictEqual(settingsStorage.getSettings(user2).studyPreferences.defaultDifficulty, "advanced");
  console.log("✓ Scenario 11 Passed: Switching accounts loads the correct user's settings");
}

// Scenario 12 & 13: Failed PATCH produces structured error and preserves display preferences
{
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, email: "error_test@college.edu" };

  // Set known local state
  settingsStorage.saveSettings(
    {
      ...DEFAULT_SETTINGS,
      theme: "dark",
      studyPreferences: { defaultDifficulty: "mixed", defaultQuestionCount: 5, preferredFocus: "mixed" },
    },
    authUser
  );

  globalThis.fetch = async () => {
    return createMockResponse(
      { detail: "Invalid difficulty value" },
      { status: 422, statusText: "Unprocessable Entity" }
    );
  };

  let threwExpected = false;
  try {
    await settingsStorage.saveSettingsAsync(
      {
        ...DEFAULT_SETTINGS,
        theme: "dark",
        studyPreferences: { defaultDifficulty: "advanced", defaultQuestionCount: 5, preferredFocus: "mixed" },
      },
      authUser
    );
  } catch (err) {
    threwExpected = true;
    assert.ok(err instanceof ApiError, "Error must be instance of ApiError");
    assert.strictEqual(err.status, 422);
  }

  assert.strictEqual(threwExpected, true, "saveSettingsAsync must throw ApiError on failure");
  // Ensure mode did not silently switch to guest
  assert.strictEqual(settingsStorage.getMode(authUser), "authenticated");
  // Ensure display preferences remained uncorrupted
  assert.strictEqual(settingsStorage.getSettings(authUser).theme, "dark");

  console.log("✓ Scenario 12 Passed: Failed PATCH produces a structured ApiError");
  console.log("✓ Scenario 13 Passed: Failed PATCH does not corrupt display preferences or switch modes");
}

// Scenario 14: Successful PATCH reconciles local state with server response
{
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, email: "reconcile@college.edu" };

  globalThis.fetch = async (_url, options) => {
    const body = JSON.parse(options.body);
    return createMockResponse({
      id: "set-confirmed",
      userId: "usr-confirmed",
      defaultDifficulty: body.defaultDifficulty,
      defaultQuestionCount: body.defaultQuestionCount,
      preferredFocus: body.preferredFocus,
      createdAt: "2026-10-04T12:00:00Z",
      updatedAt: "2026-10-04T12:05:00Z",
    });
  };

  const updated = await settingsStorage.saveSettingsAsync(
    {
      ...DEFAULT_SETTINGS,
      studyPreferences: { defaultDifficulty: "advanced", defaultQuestionCount: 15, preferredFocus: "theory" },
    },
    authUser
  );

  assert.strictEqual(updated.studyPreferences.defaultDifficulty, "advanced");
  assert.strictEqual(updated.studyPreferences.defaultQuestionCount, 15);
  assert.strictEqual(settingsStorage.getSettings(authUser).studyPreferences.preferredFocus, "theory");
  console.log("✓ Scenario 14 Passed: Successful PATCH reconciles local state with server response");
}

// Scenario 15: Repeated synchronization does not create unnecessary duplicate requests (deduplication)
{
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, email: "dedupe@college.edu" };

  let networkCalls = 0;
  globalThis.fetch = async () => {
    networkCalls++;
    await new Promise((resolve) => setTimeout(resolve, 30));
    return createMockResponse({
      id: "set-003",
      userId: "usr-003",
      defaultDifficulty: "intermediate",
      defaultQuestionCount: 10,
      preferredFocus: "mixed",
      createdAt: "2026-10-04T12:00:00Z",
      updatedAt: "2026-10-04T12:00:00Z",
    });
  };

  // Dispatch 3 concurrent sync calls
  const [res1, res2, res3] = await Promise.all([
    settingsStorage.syncRemoteSettings(authUser),
    settingsStorage.syncRemoteSettings(authUser),
    settingsStorage.syncRemoteSettings(authUser),
  ]);

  assert.strictEqual(networkCalls, 1, "Concurrent syncs must share a single network request");
  assert.strictEqual(res1.studyPreferences.defaultDifficulty, "intermediate");
  assert.strictEqual(res2.studyPreferences.defaultDifficulty, "intermediate");
  assert.strictEqual(res3.studyPreferences.defaultDifficulty, "intermediate");
  console.log("✓ Scenario 15 Passed: Repeated synchronization does not create unnecessary duplicate requests");
}

// =============================================================================
// III. REACTIVE BEHAVIOR TESTS (Scenarios 16 - 20)
// =============================================================================

// Scenario 16: Settings-change events fire after relevant updates
{
  let eventFired = false;
  const handler = () => {
    eventFired = true;
  };
  globalThis.window.addEventListener(SETTINGS_UPDATE_EVENT, handler);

  settingsStorage.saveSettings(DEFAULT_SETTINGS);
  assert.strictEqual(eventFired, true, "Custom event must fire on settings save");
  globalThis.window.removeEventListener(SETTINGS_UPDATE_EVENT, handler);
  console.log("✓ Scenario 16 Passed: Settings-change events fire after relevant updates");
}

// Scenario 17: Remote synchronization triggers UI notification
{
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, email: "notify@college.edu" };
  let notified = false;

  const unsubscribe = settingsStorage.subscribe(() => {
    notified = true;
  });

  globalThis.fetch = async () => {
    return createMockResponse({
      id: "set-004",
      userId: "usr-004",
      defaultDifficulty: "intermediate",
      defaultQuestionCount: 10,
      preferredFocus: "mixed",
      createdAt: "2026-10-04T12:00:00Z",
      updatedAt: "2026-10-04T12:00:00Z",
    });
  };

  await settingsStorage.syncRemoteSettings(authUser);
  unsubscribe();
  assert.strictEqual(notified, true, "Subscribers must be notified upon remote sync completion");
  console.log("✓ Scenario 17 Passed: Remote synchronization triggers UI notification");
}

// Scenario 18: Storage events update relevant consumers across tabs
{
  let crossTabNotified = false;
  const unsubscribe = settingsStorage.subscribe(() => {
    crossTabNotified = true;
  });

  globalThis.window.dispatchEvent(
    new StorageEvent("storage", { key: `${BASE_SETTINGS_KEY}_guest` })
  );

  unsubscribe();
  assert.strictEqual(crossTabNotified, true, "Storage event for settings key must trigger subscriber");
  console.log("✓ Scenario 18 Passed: Storage events update relevant consumers across tabs");
}

// Scenario 19: Display preference changes apply immediately without network requests
{
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, email: "display_only@college.edu" };

  let networkHit = false;
  globalThis.fetch = async () => {
    networkHit = true;
    throw new Error("Display preferences must not hit the network");
  };

  const initial = settingsStorage.getSettings(authUser);
  const updatedDisplay = {
    ...initial,
    theme: "dark",
    density: "compact",
  };

  // Changing only theme and density
  await settingsStorage.saveSettingsAsync(updatedDisplay, authUser);
  assert.strictEqual(networkHit, false, "Display-only updates must not trigger network calls");
  assert.strictEqual(settingsStorage.getSettings(authUser).theme, "dark");
  assert.strictEqual(settingsStorage.getSettings(authUser).density, "compact");
  console.log("✓ Scenario 19 Passed: Display preference changes apply immediately without network requests");
}

// Scenario 20: Rapid updates and delayed responses maintain consistent cache state
{
  tokenManager.setAccessToken("jwt-token-122");
  const authUser = { isGuest: false, email: "racing@college.edu" };

  let updateCount = 0;
  globalThis.fetch = async (_url, options) => {
    updateCount++;
    const body = JSON.parse(options.body);
    const count = updateCount;

    // Simulate first request being slow (100ms) and second being fast (10ms)
    const delay = count === 1 ? 100 : 10;
    await new Promise((r) => setTimeout(r, delay));

    return createMockResponse({
      id: `set-race-${count}`,
      userId: "usr-race",
      defaultDifficulty: body.defaultDifficulty,
      defaultQuestionCount: body.defaultQuestionCount,
      preferredFocus: body.preferredFocus,
      createdAt: "2026-10-04T12:00:00Z",
      updatedAt: "2026-10-04T12:00:00Z",
    });
  };

  // Update 1: Beginner (slow)
  const p1 = settingsStorage.saveSettingsAsync(
    { ...DEFAULT_SETTINGS, studyPreferences: { ...DEFAULT_SETTINGS.studyPreferences, defaultDifficulty: "beginner" } },
    authUser
  );

  // Update 2: Advanced (fast)
  const p2 = settingsStorage.saveSettingsAsync(
    { ...DEFAULT_SETTINGS, studyPreferences: { ...DEFAULT_SETTINGS.studyPreferences, defaultDifficulty: "advanced" } },
    authUser
  );

  await Promise.all([p1, p2]);

  // Final cache state must be the latest requested update ("advanced"), not the delayed first response
  assert.strictEqual(
    settingsStorage.getSettings(authUser).studyPreferences.defaultDifficulty,
    "advanced",
    "Latest update must prevail over delayed earlier response"
  );
  console.log("✓ Scenario 20 Passed: Rapid updates and delayed responses preserve cache consistency");
}

// =============================================================================
// IV. PRESERVED EXISTING UNIT TESTS (Test Cases 1 - 6)
// =============================================================================

tokenManager.clearTokens();

// Test Case 1: Default Settings Retrieval
{
  storageMock.clear();
  const settings = settingsStorage.getSettings();
  assert.strictEqual(settings.theme, "system");
  assert.strictEqual(settings.density, "comfortable");
  assert.strictEqual(settings.reducedMotion, false);
  assert.strictEqual(settings.studyPreferences.defaultDifficulty, "mixed");
  assert.strictEqual(settings.studyPreferences.defaultQuestionCount, 5);
  assert.strictEqual(settings.studyPreferences.preferredFocus, "mixed");
  console.log("✓ Test Case 1 Passed: Default settings loaded with safe fallbacks");
}

// Test Case 2: Save and Persist Custom Preferences
{
  const custom = {
    theme: "dark",
    density: "compact",
    reducedMotion: true,
    studyPreferences: {
      defaultDifficulty: "advanced",
      defaultQuestionCount: 10,
      preferredFocus: "theory",
    },
  };

  settingsStorage.saveSettings(custom);
  const retrieved = settingsStorage.getSettings();
  assert.strictEqual(retrieved.theme, "dark");
  assert.strictEqual(retrieved.density, "compact");
  assert.strictEqual(retrieved.reducedMotion, true);
  assert.strictEqual(retrieved.studyPreferences.defaultDifficulty, "advanced");
  assert.strictEqual(retrieved.studyPreferences.defaultQuestionCount, 10);
  assert.strictEqual(retrieved.studyPreferences.preferredFocus, "theory");
  console.log("✓ Test Case 2 Passed: Custom preferences persist correctly");
}

// Test Case 3: Resilient to Malformed JSON in LocalStorage
{
  storageMock.setItem(`${BASE_SETTINGS_KEY}_guest`, "{ malformed: json !");
  const fallback = settingsStorage.getSettings();
  assert.deepStrictEqual(fallback, DEFAULT_SETTINGS);
  console.log("✓ Test Case 3 Passed: Corrupt localStorage recovers to DEFAULT_SETTINGS");
}

// Test Case 4: Profile Updates and Persistence
{
  const initialUser = {
    isGuest: false,
    name: "Original Name",
    email: "test@university.edu",
    university: "Old Dept",
  };
  storageMock.setItem("pracprep_user", JSON.stringify(initialUser));

  settingsStorage.updateUserProfile({
    name: "Updated Alex Morgan",
    university: "Aerospace Engineering Dept",
  });

  const updatedStored = JSON.parse(storageMock.getItem("pracprep_user"));
  assert.strictEqual(updatedStored.name, "Updated Alex Morgan");
  assert.strictEqual(updatedStored.university, "Aerospace Engineering Dept");
  assert.strictEqual(updatedStored.email, "test@university.edu"); // Email preserved
  console.log("✓ Test Case 4 Passed: Profile updates correctly without corrupting email/credentials");
}

// Test Case 5: Structured Data Export
{
  const testUser = { isGuest: false, email: "student@university.edu" };
  experimentStorage.saveExperiment(
    {
      title: "Vernier Caliper Measurement",
      aim: "Measure diameter",
      subject: "Physics",
      status: "ready",
      apparatus: "Caliper",
      theory: "Least count",
      procedure: "Align jaws",
      precautions: "Avoid parallax",
    },
    testUser
  );

  vivaStorage.saveSession(
    {
      experimentId: "exp_1",
      experimentTitle: "Vernier Caliper Measurement",
      subject: "Physics",
      difficulty: "intermediate",
      totalQuestions: 1,
      targetFocus: "mixed",
      questions: [],
      answers: [],
      evaluations: [],
      overallScore: 85,
      isCompleted: true,
      weakTopics: [],
      strongTopics: ["apparatus"],
      recommendations: ["Review formulas"],
    },
    testUser
  );

  const exportData = settingsStorage.exportUserData(testUser);
  assert.strictEqual(exportData.exportVersion, "1.0");
  assert.strictEqual(exportData.experimentsCount, 1);
  assert.strictEqual(exportData.vivaSessionsCount, 1);
  assert.strictEqual(exportData.experiments[0].title, "Vernier Caliper Measurement");
  assert.strictEqual(exportData.vivaSessions[0].overallScore, 85);
  assert.ok(exportData.exportedAt);
  console.log("✓ Test Case 5 Passed: Export contains structured session-scoped data and timestamp");
}

// Test Case 6: Scoped Data Clearing
{
  const studentA = { isGuest: false, email: "student_a@test.com" };
  const studentB = { isGuest: false, email: "student_b@test.com" };

  experimentStorage.saveExperiment(
    { title: "Student A Exp", subject: "Chem", status: "draft" },
    studentA
  );
  experimentStorage.saveExperiment(
    { title: "Student B Exp", subject: "Physics", status: "draft" },
    studentB
  );

  assert.strictEqual(experimentStorage.getExperiments(studentA).length, 1);
  assert.strictEqual(experimentStorage.getExperiments(studentB).length, 1);

  // Clear Student A data only
  settingsStorage.clearAllUserData(studentA);

  assert.strictEqual(experimentStorage.getExperiments(studentA).length, 0);
  assert.strictEqual(experimentStorage.getExperiments(studentB).length, 1);
  console.log("✓ Test Case 6 Passed: Scoped clearing isolates user data and avoids cross-user data leakage");
}

console.log("\nALL 20 TASK-12.2 SETTINGS STORAGE & SYNC TESTS AND 6 PRESERVED TESTS PASSED CLEANLY!\n");
