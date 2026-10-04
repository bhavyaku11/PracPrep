/**
 * Test Suite: PracPrep Remote Viva AI Provider & Dual-Mode Facade (TASK-10.2)
 *
 * Verifies:
 * 1. Authenticated question generation calls POST /api/v1/viva/generate-questions with auth header
 * 2. Authenticated question generation sends experimentId when valid UUID
 * 3. Authenticated question generation sends experimentContext when non-UUID
 * 4. Question generation response maps correctly to VivaQuestion items
 * 5. Gemini provider metadata (ai-live, gemini) is preserved
 * 6. Demonstration fallback metadata (demonstration, demonstration) is preserved
 * 7. HTTP errors in question generation propagate as ApiError (no fake questions)
 * 8. Authenticated answer evaluation calls POST /api/v1/viva/evaluate-answer
 * 9. Answer evaluation payload matches backend schema without client score/verdict
 * 10. Answer evaluation response maps correctly to VivaEvaluation
 * 11. Live AI and demonstration evaluation metadata are preserved
 * 12. HTTP errors in answer evaluation propagate as ApiError (no fake evaluation)
 * 13. Guest mode uses local demonstration engine with zero HTTP requests
 * 14. DualModeVivaAIProvider strictly avoids silent fallback when remote call fails
 * 15. formatVivaApiError translates 401, 422, 429, 502, 503, 504, and network errors
 * 16. analyzeSession executes successfully
 */

import assert from "node:assert";
import { tokenManager, ApiError } from "./src/lib/apiClient.ts";
import {
  RemoteVivaAIProvider,
  DemonstrationVivaProvider,
  DualModeVivaAIProvider,
  vivaAIProvider,
  formatVivaApiError,
} from "./src/services/vivaAIProvider.ts";

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
    json: async () => (bodyText ? JSON.parse(bodyText) : null),
  };
}

let mockFetchHandler = null;
let fetchCallCount = 0;
const recordedRequests = [];

globalThis.fetch = async (url, options = {}) => {
  fetchCallCount++;
  recordedRequests.push({ url: String(url), options });
  if (mockFetchHandler) {
    return await mockFetchHandler(url, options);
  }
  throw new Error(`Unhandled fetch: ${url}`);
};

function resetMocks() {
  mockStorageStore.clear();
  tokenManager.clearTokens();
  mockFetchHandler = null;
  fetchCallCount = 0;
  recordedRequests.length = 0;
}

// Sample Test Data
const SAMPLE_UUID = "3fa85f64-5717-4562-b3fc-2c963f66afa6";

const sampleUuidExperiment = {
  id: SAMPLE_UUID,
  title: "Verification of Ohm's Law",
  subject: "Electrical Engineering",
  experimentNumber: "EE-101",
  description: "Investigating the linear relationship between voltage and current across a metallic conductor.",
  objective: "To determine resistance using V-I characteristics.",
  theory: "Ohm's law states that at constant temperature, current is directly proportional to voltage.",
  apparatus: "Voltmeter (0-10V), Ammeter (0-2A), Rheostat, DC power supply, connecting wires.",
  procedure: "Connect circuit in series. Vary rheostat and record simultaneous V and I readings.",
  observations: "Table of 5 readings recorded.",
  calculations: "R = V / I calculated for each reading.",
  precautions: "Ensure tight connections. Do not exceed meter ratings.",
  createdAt: Date.now(),
  updatedAt: Date.now(),
};

const sampleLocalExperiment = {
  id: "local_exp_999",
  title: "Study of Logic Gates",
  subject: "Digital Electronics",
  objective: "Verify truth tables of AND, OR, NOT, NAND, and NOR gates.",
  theory: "Logic gates are fundamental building blocks of digital integrated circuits.",
  apparatus: "7400, 7402, 7408, 7432 ICs, breadboard, DC supply, LEDs.",
  procedure: "Insert IC into breadboard. Connect inputs to high/low logic switches and outputs to LEDs.",
  createdAt: Date.now(),
  updatedAt: Date.now(),
};

const sampleConfig = {
  questionCount: 5,
  difficulty: "intermediate",
  focus: "mixed",
};

const sampleUser = {
  id: "user_123",
  name: "Bhavya Kumar",
  email: "bhavya@example.com",
  isGuest: false,
};

const sampleGuestUser = {
  id: "guest_session_456",
  name: "Guest Student",
  email: "guest@pracprep.local",
  isGuest: true,
};

console.log("\n========================================================");
console.log("   PRACPREP VIVA AI PROVIDER INTEGRATION TEST SUITE (TASK-10.2)");
console.log("========================================================\n");

async function runTests() {
  let passed = 0;
  let failed = 0;

  async function test(name, fn) {
    try {
      resetMocks();
      await fn();
      console.log(`  ✓ ${name}`);
      passed++;
    } catch (err) {
      console.error(`  ✗ ${name}`);
      console.error(err);
      failed++;
    }
  }

  // ---------------------------------------------------------------------------
  // 1. Question Generation — Authenticated Remote Provider
  // ---------------------------------------------------------------------------

  await test("1. Authenticated question generation calls POST /viva/generate-questions with UUID", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    const mockResponsePayload = {
      questions: [
        {
          id: "q-101",
          questionNumber: 1,
          question: "State the mathematical formulation of Ohm's Law and its primary limitation.",
          topic: "theory",
          difficulty: "intermediate",
          expectedAnswer: "V = IR where R is constant at constant temperature.",
          keyPoints: ["V = IR", "Constant temperature condition", "Ohmic vs non-ohmic conductors"],
          groundedSourceSection: "Theory",
        },
      ],
      providerMode: "ai-live",
      providerId: "gemini",
      totalCount: 1,
    };

    mockFetchHandler = async (url, options) => {
      assert.ok(url.endsWith("/api/v1/viva/generate-questions"));
      const authHeader =
        options.headers instanceof Headers
          ? options.headers.get("authorization")
          : options.headers["Authorization"] || options.headers["authorization"];
      assert.strictEqual(authHeader, "Bearer test-jwt-token");

      const parsedBody = JSON.parse(options.body);
      assert.strictEqual(parsedBody.experimentId, SAMPLE_UUID);
      assert.strictEqual(parsedBody.questionCount, 5);
      assert.strictEqual(parsedBody.difficulty, "intermediate");
      assert.strictEqual(parsedBody.topicFocus, "mixed");
      assert.strictEqual(parsedBody.experimentContext, undefined);

      return createMockResponse(mockResponsePayload);
    };

    const provider = new RemoteVivaAIProvider();
    const questions = await provider.generateQuestions(sampleUuidExperiment, sampleConfig, sampleUser);

    assert.strictEqual(questions.length, 1);
    const q1 = questions[0];
    assert.strictEqual(q1.id, "q-101");
    assert.strictEqual(q1.questionNumber, 1);
    assert.strictEqual(q1.topic, "theory");
    assert.strictEqual(q1.difficulty, "intermediate");
    assert.strictEqual(q1.providerMode, "ai-live");
    assert.strictEqual(q1.providerId, "gemini");
    assert.deepStrictEqual(q1.keyPoints, ["V = IR", "Constant temperature condition", "Ohmic vs non-ohmic conductors"]);
  });

  await test("2. Authenticated question generation sends experimentContext when id is not a UUID", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    const mockResponsePayload = {
      questions: [
        {
          id: "q-201",
          questionNumber: 1,
          question: "How do NAND and NOR gates serve as universal gates in logic circuits?",
          topic: "theory",
          difficulty: "intermediate",
          expectedAnswer: "Any Boolean function can be implemented using only NAND or only NOR gates.",
          keyPoints: ["Universal gate definition", "De Morgan's laws", "Inverter, AND, OR construction"],
          groundedSourceSection: "Theory",
        },
      ],
      providerMode: "ai-live",
      providerId: "gemini",
      totalCount: 1,
    };

    mockFetchHandler = async (url, options) => {
      assert.ok(url.endsWith("/api/v1/viva/generate-questions"));
      const parsedBody = JSON.parse(options.body);
      assert.strictEqual(parsedBody.experimentId, undefined);
      assert.ok(parsedBody.experimentContext);
      assert.strictEqual(parsedBody.experimentContext.title, "Study of Logic Gates");
      assert.strictEqual(parsedBody.experimentContext.subject, "Digital Electronics");
      return createMockResponse(mockResponsePayload);
    };

    const provider = new RemoteVivaAIProvider();
    const questions = await provider.generateQuestions(sampleLocalExperiment, sampleConfig, sampleUser);

    assert.strictEqual(questions.length, 1);
    assert.strictEqual(questions[0].id, "q-201");
    assert.strictEqual(questions[0].providerMode, "ai-live");
  });

  await test("3. Question generation preserves backend demonstration fallback metadata", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    const mockResponsePayload = {
      questions: [
        {
          id: "q-demo-1",
          questionNumber: 1,
          question: "Explain the governing principle of Ohm's Law.",
          topic: "theory",
          difficulty: "intermediate",
          expectedAnswer: "V = IR",
          keyPoints: ["V = IR"],
        },
      ],
      providerMode: "demonstration",
      providerId: "demonstration",
      totalCount: 1,
    };

    mockFetchHandler = async () => createMockResponse(mockResponsePayload);

    const provider = new RemoteVivaAIProvider();
    const questions = await provider.generateQuestions(sampleUuidExperiment, sampleConfig, sampleUser);

    assert.strictEqual(questions.length, 1);
    assert.strictEqual(questions[0].providerMode, "demonstration");
    assert.strictEqual(questions[0].providerId, "demonstration");
  });

  await test("4. Remote question generation propagates HTTP errors as ApiError (no fabricated questions)", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    mockFetchHandler = async () =>
      createMockResponse({ detail: "AI provider rate limit reached" }, { status: 429, statusText: "Too Many Requests" });

    const provider = new RemoteVivaAIProvider();

    await assert.rejects(
      async () => {
        await provider.generateQuestions(sampleUuidExperiment, sampleConfig, sampleUser);
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 429);
        assert.strictEqual(err.detail, "AI provider rate limit reached");
        return true;
      }
    );
  });

  await test("5. Remote question generation rejects empty response with 502 ApiError", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    mockFetchHandler = async () => createMockResponse({ questions: [], providerMode: "ai-live", providerId: "gemini" });

    const provider = new RemoteVivaAIProvider();

    await assert.rejects(
      async () => {
        await provider.generateQuestions(sampleUuidExperiment, sampleConfig, sampleUser);
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 502);
        assert.strictEqual(err.code, "INVALID_RESPONSE");
        return true;
      }
    );
  });

  // ---------------------------------------------------------------------------
  // 2. Answer Evaluation — Authenticated Remote Provider
  // ---------------------------------------------------------------------------

  await test("6. Authenticated answer evaluation calls POST /viva/evaluate-answer with valid schema", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    const questionToEvaluate = {
      id: "q-101",
      questionNumber: 1,
      question: "State the mathematical formulation of Ohm's Law.",
      topic: "theory",
      difficulty: "intermediate",
      expectedAnswer: "V = IR where R is constant at constant temperature.",
      keyPoints: ["V = IR", "Constant temperature condition"],
      groundedSourceSection: "Theory",
    };

    const studentAnswer = "Ohm's law is V = IR, where voltage is proportional to current at constant temperature.";

    const mockResponsePayload = {
      verdict: "correct",
      score: 9,
      feedback: "Accurate statement of Ohm's law with temperature dependency noted.",
      whatYouGotRight: "Correct formula V = IR and recognized temperature condition.",
      whatWasMissing: "Could also mention material resistivity.",
      expectedAnswer: "V = IR where R is constant at constant temperature.",
      improvementTip: "Define physical units (volts, amperes, ohms) in oral responses.",
      providerMode: "ai-live",
      providerId: "gemini",
      keyPointsCovered: ["V = IR", "Constant temperature condition"],
      keyPointsMissed: [],
    };

    mockFetchHandler = async (url, options) => {
      assert.ok(url.endsWith("/api/v1/viva/evaluate-answer"));
      const authHeader =
        options.headers instanceof Headers
          ? options.headers.get("authorization")
          : options.headers["Authorization"] || options.headers["authorization"];
      assert.strictEqual(authHeader, "Bearer test-jwt-token");

      const parsedBody = JSON.parse(options.body);
      assert.strictEqual(parsedBody.studentAnswer, studentAnswer);
      assert.ok(parsedBody.question);
      assert.strictEqual(parsedBody.question.id, "q-101");
      assert.strictEqual(parsedBody.question.questionNumber, 1);
      assert.strictEqual(parsedBody.question.question, questionToEvaluate.question);

      // Verify client did NOT inject a client score or verdict
      assert.strictEqual(parsedBody.score, undefined);
      assert.strictEqual(parsedBody.verdict, undefined);

      return createMockResponse(mockResponsePayload);
    };

    const provider = new RemoteVivaAIProvider();
    const evaluation = await provider.evaluateAnswer(
      questionToEvaluate,
      studentAnswer,
      sampleUuidExperiment,
      { previousAnswers: [], currentQuestionIndex: 0 },
      sampleUser
    );

    assert.strictEqual(evaluation.verdict, "correct");
    assert.strictEqual(evaluation.score, 9);
    assert.strictEqual(evaluation.whatYouGotRight, mockResponsePayload.whatYouGotRight);
    assert.strictEqual(evaluation.whatWasMissing, mockResponsePayload.whatWasMissing);
    assert.strictEqual(evaluation.expectedAnswer, mockResponsePayload.expectedAnswer);
    assert.strictEqual(evaluation.improvementTip, mockResponsePayload.improvementTip);
    assert.strictEqual(evaluation.providerMode, "ai-live");
    assert.strictEqual(evaluation.providerId, "gemini");
    assert.deepStrictEqual(evaluation.keyPointsCovered, ["V = IR", "Constant temperature condition"]);
  });

  await test("7. Answer evaluation preserves backend demonstration fallback metadata", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    const mockResponsePayload = {
      verdict: "partially-correct",
      score: 6,
      whatYouGotRight: "Formula mentioned.",
      whatWasMissing: "Temperature dependency omitted.",
      expectedAnswer: "V = IR",
      improvementTip: "Remember boundary conditions.",
      providerMode: "demonstration",
      providerId: "demonstration",
      keyPointsCovered: ["V = IR"],
      keyPointsMissed: ["Constant temperature"],
    };

    mockFetchHandler = async () => createMockResponse(mockResponsePayload);

    const provider = new RemoteVivaAIProvider();
    const evaluation = await provider.evaluateAnswer(
      { id: "q-1", questionNumber: 1, question: "Q?", topic: "theory", difficulty: "beginner" },
      "V = IR",
      sampleUuidExperiment,
      { previousAnswers: [], currentQuestionIndex: 0 },
      sampleUser
    );

    assert.strictEqual(evaluation.score, 6);
    assert.strictEqual(evaluation.providerMode, "demonstration");
    assert.strictEqual(evaluation.providerId, "demonstration");
  });

  await test("8. Answer evaluation propagates HTTP errors as ApiError (no fabricated evaluation)", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    mockFetchHandler = async () =>
      createMockResponse({ detail: "AI Service Unavailable" }, { status: 503, statusText: "Service Unavailable" });

    const provider = new RemoteVivaAIProvider();

    await assert.rejects(
      async () => {
        await provider.evaluateAnswer(
          { id: "q-1", questionNumber: 1, question: "Q?", topic: "theory", difficulty: "beginner" },
          "My Answer",
          sampleUuidExperiment,
          { previousAnswers: [], currentQuestionIndex: 0 },
          sampleUser
        );
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 503);
        assert.strictEqual(err.detail, "AI Service Unavailable");
        return true;
      }
    );
  });

  // ---------------------------------------------------------------------------
  // 3. Guest Mode & Isolation
  // ---------------------------------------------------------------------------

  await test("9. Guest mode uses local demonstration provider with zero network requests", async () => {
    // Guest user should NEVER trigger any HTTP fetch calls
    const questions = await vivaAIProvider.generateQuestions(
      sampleLocalExperiment,
      sampleConfig,
      sampleGuestUser
    );

    assert.strictEqual(fetchCallCount, 0, "Guest mode must not make any HTTP requests for question generation");
    assert.ok(questions.length > 0);
    assert.strictEqual(questions[0].topic, "theory");

    const evaluation = await vivaAIProvider.evaluateAnswer(
      questions[0],
      "The experiment verifies logic gate operations.",
      sampleLocalExperiment,
      { previousAnswers: [], currentQuestionIndex: 0 },
      sampleGuestUser
    );

    assert.strictEqual(fetchCallCount, 0, "Guest mode must not make any HTTP requests for answer evaluation");
    assert.ok(evaluation.score >= 0 && evaluation.score <= 10);
    assert.ok(evaluation.verdict);
  });

  // ---------------------------------------------------------------------------
  // 4. DualMode Routing & No Silent Fallback
  // ---------------------------------------------------------------------------

  await test("10. Authenticated user uses remote provider via DualModeVivaAIProvider facade", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    const mockQuestionsResponse = {
      questions: [
        {
          id: "q-auth-1",
          questionNumber: 1,
          question: "What is Ohm's law?",
          topic: "theory",
          difficulty: "intermediate",
          expectedAnswer: "V = IR",
          keyPoints: ["V = IR"],
        },
      ],
      providerMode: "ai-live",
      providerId: "gemini",
      totalCount: 1,
    };

    mockFetchHandler = async (url) => {
      if (url.endsWith("/viva/generate-questions")) {
        return createMockResponse(mockQuestionsResponse);
      }
      throw new Error(`Unexpected url: ${url}`);
    };

    const questions = await vivaAIProvider.generateQuestions(
      sampleUuidExperiment,
      sampleConfig,
      sampleUser
    );

    assert.strictEqual(fetchCallCount, 1);
    assert.strictEqual(questions.length, 1);
    assert.strictEqual(questions[0].id, "q-auth-1");
    assert.strictEqual(questions[0].providerMode, "ai-live");
  });

  await test("11. DualModeVivaAIProvider does NOT silently fall back to local engine when remote call fails", async () => {
    tokenManager.setTokens({ accessToken: "test-jwt-token", refreshToken: "test-refresh-token" });

    mockFetchHandler = async () =>
      createMockResponse({ detail: "Gateway Timeout" }, { status: 504, statusText: "Gateway Timeout" });

    // Question generation must reject, NOT silently return demo questions
    await assert.rejects(
      async () => {
        await vivaAIProvider.generateQuestions(sampleUuidExperiment, sampleConfig, sampleUser);
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 504);
        return true;
      }
    );

    // Answer evaluation must reject, NOT silently evaluate locally
    await assert.rejects(
      async () => {
        await vivaAIProvider.evaluateAnswer(
          { id: "q-1", questionNumber: 1, question: "Q?", topic: "theory", difficulty: "beginner" },
          "My Answer",
          sampleUuidExperiment,
          { previousAnswers: [], currentQuestionIndex: 0 },
          sampleUser
        );
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 504);
        return true;
      }
    );
  });

  // ---------------------------------------------------------------------------
  // 5. Error Formatting (formatVivaApiError)
  // ---------------------------------------------------------------------------

  await test("12. formatVivaApiError translates status codes into user-friendly messages", () => {
    // 401 Unauthorized
    const err401 = new ApiError({ message: "Unauthorized", status: 401, isAuthError: true });
    assert.ok(formatVivaApiError(err401).includes("session has expired"));

    // 422 Unprocessable Entity
    const err422 = new ApiError({ message: "Validation error", status: 422, detail: "Invalid question count" });
    assert.strictEqual(formatVivaApiError(err422), "Invalid question count");

    // 429 Rate Limit
    const err429 = new ApiError({ message: "Too Many Requests", status: 429 });
    assert.ok(formatVivaApiError(err429).includes("rate limit exceeded"));

    // 502 Bad Gateway
    const err502 = new ApiError({ message: "Bad Gateway", status: 502 });
    assert.ok(formatVivaApiError(err502).includes("invalid response"));

    // 503 Service Unavailable
    const err503 = new ApiError({ message: "Service Unavailable", status: 503 });
    assert.ok(formatVivaApiError(err503).includes("temporarily unavailable"));

    // 504 Gateway Timeout
    const err504 = new ApiError({ message: "Gateway Timeout", status: 504 });
    assert.ok(formatVivaApiError(err504).includes("timed out"));

    // Network error
    const errNet = new ApiError({ message: "Failed to fetch", isNetworkError: true });
    assert.ok(formatVivaApiError(errNet).includes("Network connection error"));

    // Unknown standard error
    const errStandard = new Error("Something broke");
    assert.strictEqual(formatVivaApiError(errStandard), "Something broke");

    // Completely unknown object
    assert.ok(formatVivaApiError({}, "evaluate your answer").includes("An unexpected error occurred"));
  });

  // ---------------------------------------------------------------------------
  // 6. Session Analysis
  // ---------------------------------------------------------------------------

  await test("13. analyzeSession completes successfully", async () => {
    const mockAnswers = [
      {
        questionId: "q-1",
        questionNumber: 1,
        questionText: "What is Ohm's law?",
        topic: "theory",
        difficulty: "intermediate",
        studentAnswer: "V = IR",
        evaluation: {
          verdict: "correct",
          score: 10,
          whatYouGotRight: "Correct formula",
          whatWasMissing: "",
          expectedAnswer: "V = IR",
          improvementTip: "Good job",
        },
        timestamp: Date.now(),
      },
    ];

    const analysis = await vivaAIProvider.analyzeSession(sampleUuidExperiment, mockAnswers);
    assert.ok(analysis.topicAnalysis);
    assert.ok(analysis.topicAnalysis["theory"]);
    assert.strictEqual(analysis.topicAnalysis["theory"].averageScore, 10);
    assert.ok(Array.isArray(analysis.weakTopics));
    assert.ok(Array.isArray(analysis.strongTopics));
    assert.ok(Array.isArray(analysis.revisionRecommendations));
  });

  // ---------------------------------------------------------------------------
  // 7. 401 Authentication & Malformed Payloads
  // ---------------------------------------------------------------------------

  await test("14. 401 error does NOT switch to guest mode; propagates auth error", async () => {
    tokenManager.setTokens({ accessToken: "expired-token", refreshToken: "refresh-token" });

    mockFetchHandler = async () =>
      createMockResponse({ detail: "Could not validate credentials" }, { status: 401, statusText: "Unauthorized" });

    await assert.rejects(
      async () => {
        await vivaAIProvider.generateQuestions(sampleUuidExperiment, sampleConfig, sampleUser);
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 401);
        assert.ok(err.isAuthError);
        return true;
      }
    );
  });

  await test("15. Evaluation with incomplete payload throws 502 ApiError", async () => {
    tokenManager.setTokens({ accessToken: "valid-token", refreshToken: "refresh-token" });

    // Missing verdict and score
    mockFetchHandler = async () =>
      createMockResponse({ whatYouGotRight: "Missing score" });

    const provider = new RemoteVivaAIProvider();
    await assert.rejects(
      async () => {
        await provider.evaluateAnswer(
          { id: "q-1", questionNumber: 1, question: "Q?", topic: "theory", difficulty: "beginner" },
          "Ans",
          sampleUuidExperiment,
          { previousAnswers: [], currentQuestionIndex: 0 },
          sampleUser
        );
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 502);
        assert.strictEqual(err.code, "INVALID_RESPONSE");
        return true;
      }
    );
  });

  await test("16. Custom mode resolver allows runtime switching and introspection", () => {
    let currentMode = "guest";
    const customResolver = {
      resolveMode: () => currentMode,
    };

    const dualProvider = new DualModeVivaAIProvider(
      new DemonstrationVivaProvider(),
      new RemoteVivaAIProvider(),
      customResolver
    );

    assert.strictEqual(dualProvider.mode, "demonstration");
    assert.ok(dualProvider.displayName.includes("Demonstration"));

    currentMode = "authenticated";
    assert.strictEqual(dualProvider.mode, "ai-live");
    assert.ok(dualProvider.displayName.includes("Remote") || dualProvider.displayName.includes("Live"));
  });

  console.log("\n--------------------------------------------------------");
  console.log(`Results: ${passed} passed, ${failed} failed`);
  console.log("--------------------------------------------------------\n");

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
