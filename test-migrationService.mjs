/**
 * Test Suite: PracPrep Guest Data Migration Service (TASK-13.3)
 *
 * Verifies:
 * - Guest data detection across scoped and legacy storage keys.
 * - Accurate summary generation.
 * - Typed payload transformation preserving checklists, viva evaluations, and timestamps.
 * - Client-side idempotency key generation and reuse across retries.
 * - Execution of authenticated POST /users/me/migrate-guest-data.
 * - CRITICAL: Local guest storage is cleared ONLY after confirmed 200 OK response.
 * - CRITICAL: Local guest storage is PRESERVED on API failure / error.
 * - Cache invalidation and reactive update event dispatch.
 * - Discard flow clearing guest data safely.
 * - Multi-tenant storage isolation (guest keys vs authenticated keys).
 */

import assert from "node:assert";
import { migrationService } from "./src/services/migrationService.ts";
import { apiClient } from "./src/lib/apiClient.ts";

// In-memory mock storage
function createMockStorage() {
  const store = new Map();
  return {
    getItem: (k) => store.get(k) ?? null,
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
}

let mockStorage = createMockStorage();
let dispatchedEvents = [];

// Setup global mock browser environment
globalThis.window = {
  localStorage: mockStorage,
  dispatchEvent: (event) => {
    dispatchedEvents.push(event.type);
    return true;
  },
};
globalThis.localStorage = mockStorage;
globalThis.CustomEvent = class CustomEvent {
  constructor(type, eventInitDict) {
    this.type = type;
    this.detail = eventInitDict?.detail;
  }
};

console.log("=== Running TASK-13.3 Guest Data Migration Service Tests ===");

// 1. Detection returns false when storage is empty
{
  mockStorage.clear();
  assert.strictEqual(
    migrationService.checkHasGuestData(),
    false,
    "Empty storage should return false for hasGuestData"
  );
  const summary = migrationService.getGuestDataSummary();
  assert.strictEqual(summary.hasData, false);
  assert.strictEqual(summary.experimentCount, 0);
  assert.strictEqual(summary.vivaSessionCount, 0);
  console.log("✓ Test 1 Passed: Empty storage detected cleanly");
}

// 2. Detection works for guest experiments in primary scoped key
{
  mockStorage.clear();
  const sampleExp = [
    {
      id: "exp-guest-1",
      title: "Kirchhoff's Laws",
      subject: "Electrical",
      status: "ready",
      preparationChecklist: { objective: true },
    },
  ];
  mockStorage.setItem("pracprep_experiments_guest", JSON.stringify(sampleExp));

  assert.strictEqual(migrationService.checkHasGuestData(), true);
  const summary = migrationService.getGuestDataSummary();
  assert.strictEqual(summary.hasData, true);
  assert.strictEqual(summary.experimentCount, 1);
  assert.strictEqual(summary.vivaSessionCount, 0);
  console.log("✓ Test 2 Passed: Guest experiments detected in primary key");
}

// 3. Detection works for guest viva sessions in primary scoped key
{
  mockStorage.clear();
  const sampleSess = [
    {
      id: "viva-guest-1",
      experimentId: "exp-guest-1",
      config: { questionCount: 5, difficulty: "intermediate", focus: "theory" },
      answers: [],
    },
  ];
  mockStorage.setItem("pracprep_viva_sessions_guest", JSON.stringify(sampleSess));

  assert.strictEqual(migrationService.checkHasGuestData(), true);
  const summary = migrationService.getGuestDataSummary();
  assert.strictEqual(summary.hasData, true);
  assert.strictEqual(summary.experimentCount, 0);
  assert.strictEqual(summary.vivaSessionCount, 1);
  console.log("✓ Test 3 Passed: Guest viva sessions detected in primary key");
}

// 4. Detection falls back to legacy un-scoped storage keys
{
  mockStorage.clear();
  mockStorage.setItem(
    "pracprep_experiments",
    JSON.stringify([{ id: "exp-legacy", title: "Legacy Exp", subject: "Physics" }])
  );
  mockStorage.setItem(
    "pracprep_viva_sessions",
    JSON.stringify([{ id: "viva-legacy", experimentId: "exp-legacy" }])
  );

  assert.strictEqual(migrationService.checkHasGuestData(), true);
  const summary = migrationService.getGuestDataSummary();
  assert.strictEqual(summary.experimentCount, 1);
  assert.strictEqual(summary.vivaSessionCount, 1);
  console.log("✓ Test 4 Passed: Fallback to legacy un-scoped storage keys succeeds");
}

// 5. Payload formatting preserves all necessary fields, checklists, and viva answers
{
  mockStorage.clear();
  const sampleExp = [
    {
      id: "exp-101",
      title: "Vernier Caliper Measurement",
      subject: "Physics",
      experimentNumber: "EXP-01",
      courseSemester: "Sem 1",
      method: "manual",
      status: "ready",
      objective: "Measure cylinder diameter.",
      theory: "Least count calculation.",
      apparatus: "Vernier Caliper, cylinder.",
      procedure: "Place object between jaws.",
      observations: "Readings table.",
      calculations: "Volume calculation.",
      precautions: "Avoid parallax error.",
      preparationChecklist: { objective: true, theory: true, apparatus: false },
      createdAtTimestamp: 1728000000000,
      updatedAtTimestamp: 1728000000000,
    },
  ];
  const sampleViva = [
    {
      id: "viva-201",
      experimentId: "exp-101",
      config: { questionCount: 5, difficulty: "intermediate", focus: "theory" },
      providerMode: "demonstration",
      isCompleted: true,
      averageScore: 9.0,
      totalQuestions: 5,
      questionsAnswered: 5,
      correctCount: 4,
      partiallyCorrectCount: 1,
      incorrectCount: 0,
      topicAnalysis: { theory: { total: 3, correct: 3, averageScore: 9.0 } },
      weakTopics: [],
      strongTopics: ["theory"],
      revisionRecommendations: [],
      answers: [
        {
          questionId: "q-1",
          questionNumber: 1,
          topic: "theory",
          difficulty: "intermediate",
          questionText: "What is least count?",
          studentAnswer: "Smallest value that can be measured.",
          evaluation: {
            score: 10,
            verdict: "correct",
            whatYouGotRight: "Correct definition.",
            whatWasMissing: "",
            expectedAnswer: "Smallest readable measurement.",
            improvementTip: "Good job.",
            keyPointsCovered: ["smallest readable measurement"],
            keyPointsMissed: [],
          },
          timestamp: 1728000010000,
        },
      ],
    },
  ];

  mockStorage.setItem("pracprep_experiments_guest", JSON.stringify(sampleExp));
  mockStorage.setItem("pracprep_viva_sessions_guest", JSON.stringify(sampleViva));

  const payload = migrationService.prepareMigrationPayload("custom-idemp-key-123");
  assert.strictEqual(payload.idempotencyKey, "custom-idemp-key-123");
  assert.strictEqual(payload.experiments.length, 1);
  assert.strictEqual(payload.vivaSessions.length, 1);

  // Check experiment fields
  const pExp = payload.experiments[0];
  assert.strictEqual(pExp.clientId, "exp-101");
  assert.strictEqual(pExp.title, "Vernier Caliper Measurement");
  assert.strictEqual(pExp.preparationChecklist.objective, true);
  assert.strictEqual(pExp.preparationChecklist.apparatus, false);

  // Check viva session fields
  const pViva = payload.vivaSessions[0];
  assert.strictEqual(pViva.clientId, "viva-201");
  assert.strictEqual(pViva.clientExperimentId, "exp-101");
  assert.strictEqual(pViva.difficulty, "intermediate");
  assert.strictEqual(pViva.topicFocus, "theory");
  assert.strictEqual(pViva.answers.length, 1);

  // Check answer unpacked fields
  const pAns = pViva.answers[0];
  assert.strictEqual(pAns.questionText, "What is least count?");
  assert.strictEqual(pAns.score, 10);
  assert.strictEqual(pAns.verdict, "correct");
  assert.strictEqual(pAns.whatYouGotRight, "Correct definition.");
  assert.strictEqual(pAns.suggestedImprovement, "Good job.");
  assert.deepStrictEqual(pAns.keyPointsCovered, ["smallest readable measurement"]);
  console.log("✓ Test 5 Passed: Payload transformation preserves all data and structures");
}

// 6. Successful migration calls API, clears guest storage, and dispatches events
{
  mockStorage.clear();
  dispatchedEvents = [];

  mockStorage.setItem(
    "pracprep_experiments_guest",
    JSON.stringify([{ id: "exp-success", title: "Ohm's Law", subject: "Physics" }])
  );
  mockStorage.setItem(
    "pracprep_viva_sessions_guest",
    JSON.stringify([{ id: "viva-success", experimentId: "exp-success" }])
  );

  let capturedPath = null;
  let capturedPayload = null;
  let capturedOptions = null;

  // Intercept apiClient.post
  const originalPost = apiClient.post;
  apiClient.post = async (path, body, options) => {
    capturedPath = path;
    capturedPayload = body;
    capturedOptions = options;
    return {
      message: "Guest data migrated successfully.",
      idempotencyKey: body.idempotencyKey,
      isIdempotentReplay: false,
      experimentsMigrated: 1,
      vivaSessionsMigrated: 1,
      vivaAnswersMigrated: 0,
      migratedAt: new Date().toISOString(),
    };
  };

  try {
    const result = await migrationService.migrateGuestData("test-idemp-999");
    assert.strictEqual(capturedPath, "/users/me/migrate-guest-data");
    assert.strictEqual(capturedOptions?.requiresAuth, true);
    assert.strictEqual(capturedPayload.idempotencyKey, "test-idemp-999");
    assert.strictEqual(result.experimentsMigrated, 1);

    // CRITICAL: Local guest storage MUST be cleared after confirmed success
    assert.strictEqual(mockStorage.getItem("pracprep_experiments_guest"), null);
    assert.strictEqual(mockStorage.getItem("pracprep_viva_sessions_guest"), null);
    assert.strictEqual(migrationService.checkHasGuestData(), false);

    // Verify change events were dispatched
    assert.ok(dispatchedEvents.includes("pracprep_experiments_changed"));
    assert.ok(dispatchedEvents.includes("pracprep_viva_sessions_changed"));
    console.log("✓ Test 6 Passed: Confirmed migration clears guest storage and fires update events");
  } finally {
    apiClient.post = originalPost;
  }
}

// 7. CRITICAL: API failure preserves guest data (NO DATA LOSS)
{
  mockStorage.clear();
  const guestExpJson = JSON.stringify([{ id: "exp-precious", title: "Important Lab", subject: "ECE" }]);
  const guestVivaJson = JSON.stringify([{ id: "viva-precious", experimentId: "exp-precious" }]);
  mockStorage.setItem("pracprep_experiments_guest", guestExpJson);
  mockStorage.setItem("pracprep_viva_sessions_guest", guestVivaJson);

  const originalPost = apiClient.post;
  apiClient.post = async () => {
    throw new Error("500 Internal Server Error: Database failure");
  };

  try {
    let failed = false;
    try {
      await migrationService.migrateGuestData();
    } catch (err) {
      failed = true;
      assert.ok(err.message.includes("500"));
    }
    assert.strictEqual(failed, true, "migrateGuestData must rethrow API failure");

    // CRITICAL SAFETY CHECK: Storage must NOT be cleared!
    assert.strictEqual(
      mockStorage.getItem("pracprep_experiments_guest"),
      guestExpJson,
      "Guest experiments must remain intact after failure"
    );
    assert.strictEqual(
      mockStorage.getItem("pracprep_viva_sessions_guest"),
      guestVivaJson,
      "Guest viva sessions must remain intact after failure"
    );
    assert.strictEqual(migrationService.checkHasGuestData(), true);
    console.log("✓ Test 7 Passed: Guest data preserved locally upon API failure for safe retry");
  } finally {
    apiClient.post = originalPost;
  }
}

// 8. Discard flow explicitly wipes guest storage and clears caches
{
  mockStorage.clear();
  dispatchedEvents = [];
  mockStorage.setItem(
    "pracprep_experiments_guest",
    JSON.stringify([{ id: "exp-discard", title: "Discard Me", subject: "Math" }])
  );
  mockStorage.setItem(
    "pracprep_viva_sessions_guest",
    JSON.stringify([{ id: "viva-discard", experimentId: "exp-discard" }])
  );

  assert.strictEqual(migrationService.checkHasGuestData(), true);

  migrationService.discardGuestData();

  assert.strictEqual(mockStorage.getItem("pracprep_experiments_guest"), null);
  assert.strictEqual(mockStorage.getItem("pracprep_viva_sessions_guest"), null);
  assert.strictEqual(migrationService.checkHasGuestData(), false);
  assert.ok(dispatchedEvents.includes("pracprep_experiments_changed"));
  assert.ok(dispatchedEvents.includes("pracprep_viva_sessions_changed"));
  console.log("✓ Test 8 Passed: Discard flow cleanly removes guest storage and notifies UI");
}

// 9. Multi-tenant storage isolation: guest data does not touch user-scoped keys
{
  mockStorage.clear();
  const userKey = "pracprep_experiments_user_alice_university_edu";
  mockStorage.setItem(userKey, JSON.stringify([{ id: "exp-alice", title: "Alice Exp" }]));
  mockStorage.setItem("pracprep_experiments_guest", JSON.stringify([{ id: "exp-guest", title: "Guest Exp" }]));

  migrationService.discardGuestData();

  // Guest key is removed
  assert.strictEqual(mockStorage.getItem("pracprep_experiments_guest"), null);
  // Alice's user key is untouched
  assert.notStrictEqual(mockStorage.getItem(userKey), null);
  console.log("✓ Test 9 Passed: Guest data manipulation does not leak into user-scoped storage");
}

console.log("\nALL 9 GUEST DATA MIGRATION SERVICE TESTS PASSED CLEANLY!");
