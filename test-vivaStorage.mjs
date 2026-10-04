/**
 * Test Suite: PracPrep Dual-Mode Viva Storage Facade (TASK-08.4)
 *
 * Verifies:
 * 1. Authenticated session creation calls the backend API (POST /api/v1/viva/sessions)
 * 2. Authenticated session listing calls the backend API (GET /api/v1/viva/sessions)
 * 3. Authenticated detail retrieval calls the backend API (GET /api/v1/viva/sessions/{id})
 * 4. Authenticated deletion calls the backend API (DELETE /api/v1/viva/sessions/{id})
 * 5. Guest session creation and persistence in localStorage
 * 6. Guest session listing and retrieval from localStorage
 * 7. Guest updates and deletion preserve existing synchronous behavior
 * 8. Guest data remains strictly isolated from authenticated records
 * 9. Correct DTO mapping between backend schemas and frontend viva types
 * 10. Transcript and answer ordering preserved chronologically
 * 11. Evaluation and analytics preservation
 * 12. Pagination and filtering parameters handled properly
 * 13. API error propagation with structured ApiError instances
 * 14. Authentication expiration handling
 * 15. Zero network requests in guest mode
 * 16. Existing viva UI consumer compatibility (sync getters, reactive subscriptions)
 */

import assert from "node:assert";
import { tokenManager, ApiError } from "./src/lib/apiClient.ts";
import {
  vivaStorage,
  mapBackendVivaSessionToRecord,
  mapBackendAnswerToRecord,
  mapRecordToCreateSessionDto,
} from "./src/services/vivaStorage.ts";

// Setup global mock storage
const mockStorageStore = new Map();
const mockLocalStorage = {
  getItem: (k) => mockStorageStore.get(k) ?? null,
  setItem: (k, v) => mockStorageStore.set(k, String(v)),
  removeItem: (k) => mockStorageStore.delete(k),
  clear: () => mockStorageStore.clear(),
};

globalThis.localStorage = mockLocalStorage;

const eventListeners = new Map();
globalThis.window = {
  localStorage: mockLocalStorage,
  dispatchEvent: (event) => {
    const handlers = eventListeners.get(event.type) || [];
    handlers.forEach((h) => h(event));
    return true;
  },
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

console.log("=== Running TASK-08.4 Dual-Mode Viva Storage Tests ===");

// 1. Authenticated session creation calls the backend API
{
  mockStorageStore.clear();
  vivaStorage.clearCache();
  tokenManager.setAccessToken("test-token-viva-01");
  const authUser = { isGuest: false, name: "Niels Bohr", email: "bohr@quantum.edu" };

  let capturedUrl = "";
  let capturedOptions = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = String(url);
    capturedOptions = options;
    return createMockResponse(
      {
        id: "123e4567-e89b-12d3-a456-426614174001",
        experimentId: "789e0123-e89b-12d3-a456-426614174000",
        experimentTitle: "Atomic Emission Spectra",
        subject: "Physics",
        difficulty: "intermediate",
        questionCount: 5,
        topicFocus: "theory",
        providerMode: "demonstration",
        isCompleted: false,
        totalQuestions: 5,
        questionsAnswered: 0,
        correctCount: 0,
        startedAt: "2026-10-04T12:00:00Z",
        startedAtTimestamp: 1728043200000,
        completedAt: null,
        createdAt: "2026-10-04T12:00:00Z",
        updatedAt: "2026-10-04T12:00:00Z",
      },
      { status: 201 }
    );
  };

  const created = await vivaStorage.createSession(
    {
      experimentId: "789e0123-e89b-12d3-a456-426614174000",
      difficulty: "intermediate",
      questionCount: 5,
      topicFocus: "theory",
    },
    authUser
  );

  assert.strictEqual(
    capturedUrl,
    "http://localhost:8000/api/v1/viva/sessions",
    "Should call POST /api/v1/viva/sessions"
  );
  assert.strictEqual(capturedOptions.method, "POST");
  assert.strictEqual(capturedOptions.headers.get("authorization"), "Bearer test-token-viva-01");

  const sentBody = JSON.parse(capturedOptions.body);
  assert.strictEqual(sentBody.experiment_id, "789e0123-e89b-12d3-a456-426614174000");
  assert.strictEqual(sentBody.difficulty, "intermediate");
  assert.strictEqual(sentBody.question_count, 5);
  assert.strictEqual(sentBody.topic_focus, "theory");

  assert.strictEqual(created.id, "123e4567-e89b-12d3-a456-426614174001");
  assert.strictEqual(created.isCompleted, false);
  assert.strictEqual(created.totalQuestions, 5);
  assert.strictEqual(created.experimentTitle, "Atomic Emission Spectra");

  console.log("✓ Test 1 Passed: Authenticated session creation calls the backend");
}

// 2. Authenticated session listing calls the backend API
{
  vivaStorage.clearCache();
  tokenManager.setAccessToken("test-token-viva-02");
  const authUser = { isGuest: false, name: "Marie Curie", email: "marie@radium.edu" };

  let capturedUrl = "";

  globalThis.fetch = async (url) => {
    capturedUrl = String(url);
    return createMockResponse({
      items: [
        {
          id: "123e4567-e89b-12d3-a456-426614174001",
          experimentId: "789e0123-e89b-12d3-a456-426614174000",
          experimentTitle: "Radioactive Half-Life",
          subject: "Nuclear Physics",
          difficulty: "advanced",
          questionCount: 5,
          topicFocus: "mixed",
          providerMode: "demonstration",
          isCompleted: true,
          totalQuestions: 5,
          questionsAnswered: 5,
          correctCount: 4,
          averageScore: 8.5,
          startedAt: "2026-10-04T11:00:00Z",
          completedAt: "2026-10-04T11:15:00Z",
          createdAt: "2026-10-04T11:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    });
  };

  const sessions = await vivaStorage.getSessionsAsync(authUser);

  assert.strictEqual(
    capturedUrl,
    "http://localhost:8000/api/v1/viva/sessions",
    "Should query GET /api/v1/viva/sessions"
  );
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].id, "123e4567-e89b-12d3-a456-426614174001");
  assert.strictEqual(sessions[0].isCompleted, true);
  assert.strictEqual(sessions[0].averageScore, 8.5);

  console.log("✓ Test 2 Passed: Authenticated session listing calls the backend");
}

// 3. Authenticated detail retrieval calls the backend API
{
  vivaStorage.clearCache();
  tokenManager.setAccessToken("test-token-viva-03");
  const authUser = { isGuest: false, name: "Albert Einstein", email: "albert@relativity.edu" };

  let capturedUrl = "";

  globalThis.fetch = async (url) => {
    capturedUrl = String(url);
    return createMockResponse({
      id: "123e4567-e89b-12d3-a456-426614174003",
      experimentId: "789e0123-e89b-12d3-a456-426614174000",
      experimentTitle: "Photoelectric Effect",
      subject: "Physics",
      difficulty: "intermediate",
      questionCount: 2,
      topicFocus: "theory",
      providerMode: "demonstration",
      isCompleted: true,
      totalQuestions: 2,
      questionsAnswered: 2,
      correctCount: 2,
      averageScore: 9.5,
      startedAt: "2026-10-04T10:00:00Z",
      completedAt: "2026-10-04T10:10:00Z",
      createdAt: "2026-10-04T10:00:00Z",
      updatedAt: "2026-10-04T10:10:00Z",
      answers: [
        {
          id: "ans-001",
          sessionId: "123e4567-e89b-12d3-a456-426614174003",
          questionId: "q-1",
          questionNumber: 1,
          questionText: "What is threshold frequency?",
          topic: "theory",
          difficulty: "intermediate",
          studentAnswer: "Minimum frequency of incident radiation required to eject electrons.",
          score: 10,
          verdict: "correct",
          feedback: "Accurate and clear definition.",
          evaluation: {
            verdict: "correct",
            score: 10,
            whatYouGotRight: "Correct definition of minimum frequency.",
            whatWasMissing: "",
            expectedAnswer: "Threshold frequency is the minimum frequency...",
            improvementTip: "Good job.",
            providerMode: "demonstration",
          },
          createdAt: "2026-10-04T10:03:00Z",
        },
      ],
      topicAnalysis: {
        theory: {
          topic: "theory",
          total: 2,
          correct: 2,
          partiallyCorrect: 0,
          incorrect: 0,
          averageScore: 9.5,
        },
      },
    });
  };

  const detail = await vivaStorage.getSessionByIdAsync(
    "123e4567-e89b-12d3-a456-426614174003",
    authUser
  );

  assert.strictEqual(
    capturedUrl,
    "http://localhost:8000/api/v1/viva/sessions/123e4567-e89b-12d3-a456-426614174003",
    "Should query GET /api/v1/viva/sessions/{id}"
  );
  assert(detail !== null);
  assert.strictEqual(detail.id, "123e4567-e89b-12d3-a456-426614174003");
  assert.strictEqual(detail.answers.length, 1);
  assert.strictEqual(detail.answers[0].studentAnswer, "Minimum frequency of incident radiation required to eject electrons.");
  assert.strictEqual(detail.topicAnalysis.theory.averageScore, 9.5);

  console.log("✓ Test 3 Passed: Authenticated detail retrieval calls the backend");
}

// 4. Authenticated deletion calls the backend API
{
  vivaStorage.clearCache();
  tokenManager.setAccessToken("test-token-viva-04");
  const authUser = { isGuest: false, name: "Max Planck", email: "planck@quanta.edu" };

  let capturedUrl = "";
  let capturedMethod = "";

  globalThis.fetch = async (url, options) => {
    capturedUrl = String(url);
    capturedMethod = options?.method || "GET";
    return createMockResponse(null, { status: 204 });
  };

  const success = await vivaStorage.deleteSessionAsync(
    "123e4567-e89b-12d3-a456-426614174004",
    authUser
  );

  assert.strictEqual(
    capturedUrl,
    "http://localhost:8000/api/v1/viva/sessions/123e4567-e89b-12d3-a456-426614174004",
    "Should call DELETE /api/v1/viva/sessions/{id}"
  );
  assert.strictEqual(capturedMethod, "DELETE");
  assert.strictEqual(success, true);

  console.log("✓ Test 4 Passed: Authenticated deletion calls the backend");
}

// 5. Guest session creation and persistence in localStorage
{
  mockStorageStore.clear();
  const guestUser = { isGuest: true, name: "Guest Student" };

  let fetchCalled = false;
  globalThis.fetch = async () => {
    fetchCalled = true;
    throw new Error("Network should not be called in guest mode");
  };

  const guestRecord = {
    id: "viva-guest-001",
    experimentId: "exp-guest-1",
    experimentTitle: "Ohm's Law Verification",
    subject: "Physics",
    config: { questionCount: 5, difficulty: "beginner", focus: "mixed" },
    startedAt: 1728040000000,
    isCompleted: true,
    answers: [],
    totalQuestions: 5,
    questionsAnswered: 5,
    correctCount: 5,
    partiallyCorrectCount: 0,
    incorrectCount: 0,
    averageScore: 10.0,
    topicAnalysis: {},
    weakTopics: [],
    strongTopics: [],
    revisionRecommendations: [],
    providerMode: "demonstration",
  };

  const saved = vivaStorage.saveSession(guestRecord, guestUser);

  assert.strictEqual(saved.id, "viva-guest-001");
  assert.strictEqual(fetchCalled, false, "Fetch must not be called");

  const storedJson = mockStorageStore.get("pracprep_viva_sessions_guest");
  assert(storedJson, "Must persist to pracprep_viva_sessions_guest");
  const parsed = JSON.parse(storedJson);
  assert.strictEqual(parsed.length, 1);
  assert.strictEqual(parsed[0].id, "viva-guest-001");

  console.log("✓ Test 5 Passed: Guest session creation and persistence in localStorage");
}

// 6. Guest session listing and retrieval from localStorage
{
  const guestUser = { isGuest: true, name: "Guest Student" };

  const sessions = vivaStorage.getSessions(guestUser);
  assert.strictEqual(sessions.length, 1);
  assert.strictEqual(sessions[0].id, "viva-guest-001");

  const found = vivaStorage.getSessionById("viva-guest-001", guestUser);
  assert(found !== null);
  assert.strictEqual(found.experimentTitle, "Ohm's Law Verification");

  const notFound = vivaStorage.getSessionById("non-existent-id", guestUser);
  assert.strictEqual(notFound, null);

  console.log("✓ Test 6 Passed: Guest session listing and retrieval from localStorage");
}

// 7. Guest updates and deletion preserve existing synchronous behavior
{
  const guestUser = { isGuest: true, name: "Guest Student" };

  const updatedRecord = {
    ...vivaStorage.getSessionById("viva-guest-001", guestUser),
    averageScore: 9.0,
  };
  vivaStorage.saveSession(updatedRecord, guestUser);

  const reloaded = vivaStorage.getSessionById("viva-guest-001", guestUser);
  assert.strictEqual(reloaded.averageScore, 9.0);

  const deleted = vivaStorage.deleteSession("viva-guest-001", guestUser);
  assert.strictEqual(deleted, true);

  const remaining = vivaStorage.getSessions(guestUser);
  assert.strictEqual(remaining.length, 0);

  console.log("✓ Test 7 Passed: Guest updates and deletion preserve existing synchronous behavior");
}

// 8. Guest data remains strictly isolated from authenticated records
{
  mockStorageStore.clear();
  vivaStorage.clearCache();
  tokenManager.setAccessToken("test-token-viva-08");

  const guestUser = { isGuest: true, name: "Guest Student" };
  const authUser = { isGuest: false, name: "Richard Feynman", email: "feynman@caltech.edu" };

  vivaStorage.saveSession(
    {
      id: "guest-session-secret",
      experimentId: "exp-guest",
      experimentTitle: "Guest Experiment",
      subject: "Physics",
      config: { questionCount: 5, difficulty: "intermediate", focus: "mixed" },
      startedAt: Date.now(),
      isCompleted: true,
      answers: [],
      totalQuestions: 5,
      questionsAnswered: 5,
      correctCount: 4,
      partiallyCorrectCount: 0,
      incorrectCount: 1,
      averageScore: 8.0,
      topicAnalysis: {},
      weakTopics: [],
      strongTopics: [],
      revisionRecommendations: [],
      providerMode: "demonstration",
    },
    guestUser
  );

  globalThis.fetch = async () => {
    return createMockResponse({
      items: [
        {
          id: "auth-session-uuid",
          experimentId: "789e0123-e89b-12d3-a456-426614174000",
          experimentTitle: "Quantum Electrodynamics",
          subject: "Physics",
          difficulty: "advanced",
          questionCount: 5,
          topicFocus: "theory",
          providerMode: "demonstration",
          isCompleted: true,
          totalQuestions: 5,
          questionsAnswered: 5,
          correctCount: 5,
          averageScore: 10.0,
          startedAt: "2026-10-04T12:00:00Z",
          completedAt: "2026-10-04T12:15:00Z",
          createdAt: "2026-10-04T12:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    });
  };

  const authSessions = await vivaStorage.getSessionsAsync(authUser);
  assert.strictEqual(authSessions.length, 1);
  assert.strictEqual(authSessions[0].id, "auth-session-uuid");

  // Guest storage must not contain authenticated session
  const guestJson = mockStorageStore.get("pracprep_viva_sessions_guest");
  assert(guestJson.includes("guest-session-secret"));
  assert(!guestJson.includes("auth-session-uuid"));

  console.log("✓ Test 8 Passed: Guest data remains strictly isolated from authenticated records");
}

// 9. Correct DTO mapping between backend schemas and frontend viva types
{
  const backendDto = {
    id: "999e0123-e89b-12d3-a456-426614174999",
    experimentId: "789e0123-e89b-12d3-a456-426614174000",
    experimentTitle: "Millikan Oil Drop Experiment",
    subject: "Modern Physics",
    difficulty: "advanced",
    questionCount: 10,
    topicFocus: "procedure",
    providerMode: "demonstration",
    isCompleted: true,
    totalQuestions: 10,
    questionsAnswered: 10,
    correctCount: 8,
    partiallyCorrectCount: 2,
    incorrectCount: 0,
    averageScore: 8.9,
    startedAt: "2026-10-04T14:00:00.000Z",
    completedAt: "2026-10-04T14:30:00.000Z",
    startedAtTimestamp: 1728050400000,
    completedAtTimestamp: 1728052200000,
    createdAt: "2026-10-04T14:00:00.000Z",
    updatedAt: "2026-10-04T14:30:00.000Z",
    config: {
      questionCount: 10,
      difficulty: "advanced",
      focus: "procedure",
    },
    topicAnalysis: {
      procedure: {
        topic: "procedure",
        total: 10,
        correct: 8,
        partiallyCorrect: 2,
        incorrect: 0,
        averageScore: 8.9,
      },
    },
    weakTopics: ["apparatus"],
    strongTopics: ["procedure"],
    revisionRecommendations: [
      {
        topic: "apparatus",
        reason: "Missed atomizer calibration detail",
        suggestedAction: "Review apparatus section",
        workspaceTab: "apparatus",
      },
    ],
  };

  const record = mapBackendVivaSessionToRecord(backendDto);

  assert.strictEqual(record.id, "999e0123-e89b-12d3-a456-426614174999");
  assert.strictEqual(record.config.questionCount, 10);
  assert.strictEqual(record.config.difficulty, "advanced");
  assert.strictEqual(record.config.focus, "procedure");
  assert.strictEqual(record.startedAt, 1728050400000);
  assert.strictEqual(record.completedAt, 1728052200000);
  assert.strictEqual(record.partiallyCorrectCount, 2);
  assert.strictEqual(record.topicAnalysis.procedure.averageScore, 8.9);
  assert.strictEqual(record.weakTopics[0], "apparatus");
  assert.strictEqual(record.revisionRecommendations[0].workspaceTab, "apparatus");

  const createDto = mapRecordToCreateSessionDto({
    experimentId: "789e0123-e89b-12d3-a456-426614174000",
    difficulty: "beginner",
    questionCount: 15,
    topicFocus: "apparatus",
  });

  assert.strictEqual(createDto.experiment_id, "789e0123-e89b-12d3-a456-426614174000");
  assert.strictEqual(createDto.difficulty, "beginner");
  assert.strictEqual(createDto.question_count, 15);
  assert.strictEqual(createDto.topic_focus, "apparatus");

  console.log("✓ Test 9 Passed: Correct DTO mapping between backend schemas and frontend viva types");
}

// 10. Transcript and answer ordering preserved chronologically
{
  const backendAnswer3 = {
    id: "ans-3",
    sessionId: "sess-1",
    questionNumber: 3,
    questionText: "Q3",
    topic: "theory",
    difficulty: "intermediate",
    studentAnswer: "Ans3",
    createdAt: "2026-10-04T12:03:00Z",
  };
  const backendAnswer1 = {
    id: "ans-1",
    sessionId: "sess-1",
    questionNumber: 1,
    questionText: "Q1",
    topic: "theory",
    difficulty: "intermediate",
    studentAnswer: "Ans1",
    createdAt: "2026-10-04T12:01:00Z",
  };
  const backendAnswer2 = {
    id: "ans-2",
    sessionId: "sess-1",
    questionNumber: 2,
    questionText: "Q2",
    topic: "theory",
    difficulty: "intermediate",
    studentAnswer: "Ans2",
    createdAt: "2026-10-04T12:02:00Z",
  };

  const sessionWithUnorderedAnswers = {
    id: "sess-1",
    experimentId: "789e0123-e89b-12d3-a456-426614174000",
    difficulty: "intermediate",
    questionCount: 3,
    topicFocus: "theory",
    providerMode: "demonstration",
    isCompleted: true,
    totalQuestions: 3,
    questionsAnswered: 3,
    correctCount: 3,
    startedAt: "2026-10-04T12:00:00Z",
    createdAt: "2026-10-04T12:00:00Z",
    answers: [backendAnswer3, backendAnswer1, backendAnswer2],
  };

  const record = mapBackendVivaSessionToRecord(sessionWithUnorderedAnswers);
  assert.strictEqual(record.answers.length, 3);
  assert.strictEqual(record.answers[0].questionNumber, 1);
  assert.strictEqual(record.answers[1].questionNumber, 2);
  assert.strictEqual(record.answers[2].questionNumber, 3);

  console.log("✓ Test 10 Passed: Transcript and answer ordering preserved chronologically");
}

// 11. Evaluation and analytics preservation
{
  const answerDto = {
    id: "ans-eval-1",
    sessionId: "sess-1",
    questionId: "q-1",
    questionNumber: 1,
    questionText: "State Faraday's First Law of Electromagnetic Induction.",
    topic: "theory",
    difficulty: "intermediate",
    studentAnswer: "Whenever magnetic flux changes, an EMF is induced.",
    score: 9,
    verdict: "correct",
    evaluation: {
      verdict: "correct",
      score: 9,
      whatYouGotRight: "Correctly stated core relationship between flux change and EMF.",
      whatWasMissing: "Omitted closed circuit condition for current.",
      expectedAnswer: "Whenever the magnetic flux linked with a circuit changes...",
      improvementTip: "Mention the condition of circuit closure.",
      providerMode: "demonstration",
    },
    createdAt: "2026-10-04T10:00:00Z",
  };

  const mappedAnswer = mapBackendAnswerToRecord(answerDto);
  assert.strictEqual(mappedAnswer.evaluation.verdict, "correct");
  assert.strictEqual(mappedAnswer.evaluation.score, 9);
  assert.strictEqual(
    mappedAnswer.evaluation.whatYouGotRight,
    "Correctly stated core relationship between flux change and EMF."
  );
  assert.strictEqual(
    mappedAnswer.evaluation.whatWasMissing,
    "Omitted closed circuit condition for current."
  );
  assert.strictEqual(mappedAnswer.evaluation.improvementTip, "Mention the condition of circuit closure.");

  console.log("✓ Test 11 Passed: Evaluation and analytics preservation");
}

// 12. Pagination and filtering parameters handled properly
{
  vivaStorage.clearCache();
  tokenManager.setAccessToken("test-token-viva-12");
  const authUser = { isGuest: false, name: "Enrico Fermi", email: "fermi@chicago.edu" };

  let capturedUrl = "";

  globalThis.fetch = async (url) => {
    capturedUrl = String(url);
    return createMockResponse({
      items: [],
      total: 0,
      page: 2,
      pageSize: 5,
      totalPages: 0,
    });
  };

  await vivaStorage.getSessionsAsync(authUser, {
    page: 2,
    pageSize: 5,
    status: "completed",
    difficulty: "advanced",
    experimentId: "789e0123-e89b-12d3-a456-426614174000",
  });

  const urlObj = new URL(capturedUrl);
  assert.strictEqual(urlObj.pathname, "/api/v1/viva/sessions");
  assert.strictEqual(urlObj.searchParams.get("page"), "2");
  assert.strictEqual(urlObj.searchParams.get("pageSize"), "5");
  assert.strictEqual(urlObj.searchParams.get("status"), "completed");
  assert.strictEqual(urlObj.searchParams.get("difficulty"), "advanced");
  assert.strictEqual(urlObj.searchParams.get("experimentId"), "789e0123-e89b-12d3-a456-426614174000");

  console.log("✓ Test 12 Passed: Pagination and filtering parameters handled properly");
}

// 13. API error propagation with structured ApiError instances
{
  vivaStorage.clearCache();
  tokenManager.setAccessToken("test-token-viva-13");
  const authUser = { isGuest: false, name: "Werner Heisenberg", email: "heisenberg@uncertainty.edu" };

  globalThis.fetch = async () => {
    return createMockResponse(
      {
        detail: "Validation failed on viva session parameters",
        errors: [{ loc: ["body", "question_count"], msg: "Must be <= 20", type: "value_error" }],
      },
      { status: 422 }
    );
  };

  let caughtError = null;
  try {
    await vivaStorage.createSessionAsync(
      {
        experimentId: "789e0123-e89b-12d3-a456-426614174000",
        questionCount: 25,
      },
      authUser
    );
  } catch (err) {
    caughtError = err;
  }

  assert(caughtError instanceof ApiError, "Should throw an instance of ApiError");
  assert.strictEqual(caughtError.status, 422);
  assert.strictEqual(caughtError.code, "VALIDATION_ERROR");
  assert.strictEqual(caughtError.detail, "Validation failed on viva session parameters");

  console.log("✓ Test 13 Passed: API error propagation with structured ApiError instances");
}

// 14. Authentication expiration handling
{
  vivaStorage.clearCache();
  tokenManager.setAccessToken("expired-viva-token");
  tokenManager.setRefreshToken(null);
  const authUser = { isGuest: false, name: "Paul Dirac", email: "dirac@cambridge.edu" };

  let authExpiredNotified = false;
  const unsub = tokenManager.onAuthExpired(() => {
    authExpiredNotified = true;
  });

  globalThis.fetch = async () => {
    return createMockResponse({ detail: "Access token expired" }, { status: 401 });
  };

  let caughtError = null;
  try {
    await vivaStorage.getSessionsAsync(authUser);
  } catch (err) {
    caughtError = err;
  }

  unsub();
  assert(caughtError instanceof ApiError);
  assert.strictEqual(caughtError.status, 401);
  assert.strictEqual(caughtError.isAuthError, true);
  assert.strictEqual(authExpiredNotified, true, "onAuthExpired callback must be invoked");

  console.log("✓ Test 14 Passed: Authentication expiration handling");
}

// 15. Zero network requests in guest mode
{
  tokenManager.clearTokens();
  mockStorageStore.clear();
  const guestUser = { isGuest: true, name: "Guest Student" };

  let networkCallCount = 0;
  globalThis.fetch = async () => {
    networkCallCount++;
    throw new Error("Guest mode must never make network requests");
  };

  // Perform full guest lifecycle
  const created = vivaStorage.createSession(
    { experimentId: "exp-guest-99", questionCount: 5 },
    guestUser
  );
  assert(created.id.startsWith("viva-"));

  const list = vivaStorage.getSessions(guestUser);
  assert.strictEqual(list.length, 1);

  const byExp = vivaStorage.getSessionsByExperiment("exp-guest-99", guestUser);
  assert.strictEqual(byExp.length, 1);

  const byId = vivaStorage.getSessionById(created.id, guestUser);
  assert(byId !== null);

  vivaStorage.deleteSession(created.id, guestUser);
  assert.strictEqual(vivaStorage.getSessions(guestUser).length, 0);

  assert.strictEqual(networkCallCount, 0, "Network call count must be exactly 0 for guest operations");

  console.log("✓ Test 15 Passed: Zero network requests in guest mode");
}

// 16. Existing viva UI consumer compatibility (sync getters, reactive subscriptions)
{
  tokenManager.clearTokens();
  mockStorageStore.clear();
  vivaStorage.clearCache();
  const user = { isGuest: true, name: "UI Consumer Test" };

  let subscriptionFired = 0;
  const unsubscribe = vivaStorage.subscribe(() => {
    subscriptionFired++;
  });

  // Emulate React component calling sync getter on initial render
  const initialSessions = vivaStorage.getSessions(user);
  assert(Array.isArray(initialSessions), "Must return synchronous array for useState");
  assert.strictEqual(initialSessions.length, 0);

  // Emulate saving a completed session record (e.g. from VivaSimulatorPage)
  const sessionRecord = {
    id: "viva-ui-1",
    experimentId: "exp-ui-1",
    experimentTitle: "Verification of Snell's Law",
    subject: "Optics",
    config: { questionCount: 5, difficulty: "intermediate", focus: "theory" },
    startedAt: Date.now() - 300000,
    completedAt: Date.now(),
    isCompleted: true,
    answers: [],
    totalQuestions: 5,
    questionsAnswered: 5,
    correctCount: 4,
    partiallyCorrectCount: 1,
    incorrectCount: 0,
    averageScore: 8.8,
    topicAnalysis: {},
    weakTopics: [],
    strongTopics: ["theory"],
    revisionRecommendations: [],
    providerMode: "demonstration",
  };

  vivaStorage.saveSession(sessionRecord, user);

  // Subscription should have fired
  assert(subscriptionFired > 0, "Subscriber callback must have fired upon session save");

  // Sync getter should now reflect the saved session
  const updatedSessions = vivaStorage.getSessions(user);
  assert.strictEqual(updatedSessions.length, 1);
  assert.strictEqual(updatedSessions[0].experimentTitle, "Verification of Snell's Law");

  const experimentSessions = vivaStorage.getSessionsByExperiment("exp-ui-1", user);
  assert.strictEqual(experimentSessions.length, 1);

  unsubscribe();
  const firedBefore = subscriptionFired;
  vivaStorage.clearSessions(user);
  assert.strictEqual(subscriptionFired, firedBefore, "Unsubscribed listener must not be called");

  console.log("✓ Test 16 Passed: Existing viva UI consumer compatibility");
}

tokenManager.clearTokens();
mockStorageStore.clear();
vivaStorage.clearCache();

console.log("\nALL 16 DUAL-MODE VIVA STORAGE TESTS PASSED CLEANLY!");
process.exit(0);

