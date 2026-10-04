/**
 * Test Suite: PracPrep Dual-Mode Experiment Storage Facade (TASK-08.3)
 *
 * Verifies:
 * 1. Authenticated experiment creation calls the backend API
 * 2. Authenticated experiment listing calls the backend API
 * 3. Authenticated detail retrieval calls the backend API
 * 4. Authenticated updates call the backend API
 * 5. Authenticated deletion calls the backend API
 * 6. Guest creation uses localStorage without network requests
 * 7. Guest listing uses localStorage without network requests
 * 8. Guest updates and deletions preserve existing synchronous behavior
 * 9. Guest data remains isolated from authenticated records
 * 10. API failures do not silently fall back to localStorage
 * 11. Backend DTOs map correctly to frontend experiment models
 * 12. Checklist data survives serialization and deserialization
 * 13. UUID identifiers are preserved
 * 14. Pagination and filtering behave correctly
 * 15. Authentication expiration is handled consistently
 * 16. Existing experiment-related UI integrations remain compatible
 */

import assert from "node:assert";
import { tokenManager, ApiError } from "./src/lib/apiClient.ts";
import {
  experimentStorage,
  mapBackendExperimentToRecord,
  mapRecordToCreateDto,
  mapRecordToUpdateDto,
} from "./src/services/experimentStorage.ts";

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

console.log("=== Running TASK-08.3 Dual-Mode Experiment Storage Tests ===");

// 1. Authenticated experiment creation calls the backend
{
  mockStorageStore.clear();
  tokenManager.setAccessToken("test-token-083");
  const authUser = { isGuest: false, name: "Ada Lovelace", email: "ada@example.com" };

  let capturedUrl = "";
  let capturedOptions = null;

  globalThis.fetch = async (url, options) => {
    capturedUrl = String(url);
    capturedOptions = options;
    return createMockResponse(
      {
        id: "789e0123-e89b-12d3-a456-426614174000",
        title: "Photoelectric Effect Experiment",
        subject: "Modern Physics",
        experimentNumber: "EXP-PHY-04",
        courseSemester: "Semester 3",
        creationMethod: "manual",
        hasManualFile: false,
        fileName: null,
        status: "ready",
        description: "Study of electron emission by light photons.",
        objective: "To verify Einstein photoelectric equation.",
        theory: "E = h * nu - phi",
        apparatus: "Photoelectric cell, Monochromatic light source, Microammeter",
        procedure: "Align light beam, vary frequency, record stopping potential",
        observations: "Threshold frequency observed at 4.5e14 Hz",
        calculations: "Slope yields Planck constant h = 6.626e-34 J.s",
        precautions: "Do not expose photocell to ambient stray light",
        checklist: {
          id: "chk-001",
          experimentId: "789e0123-e89b-12d3-a456-426614174000",
          items: {
            objective: false,
            theory: false,
            apparatus: false,
            procedure: false,
            precautions: false,
          },
          createdAt: "2026-10-04T10:00:00Z",
          updatedAt: "2026-10-04T10:00:00Z",
        },
        preparationChecklist: {
          objective: false,
          theory: false,
          apparatus: false,
          procedure: false,
          precautions: false,
        },
        vivaQuestionsCount: 0,
        createdAt: "2026-10-04T10:00:00Z",
        updatedAt: "2026-10-04T10:00:00Z",
      },
      { status: 201 }
    );
  };

  const created = await experimentStorage.createExperiment(
    {
      title: "Photoelectric Effect Experiment",
      subject: "Modern Physics",
      experimentNumber: "EXP-PHY-04",
      courseSemester: "Semester 3",
      method: "manual",
      objective: "To verify Einstein photoelectric equation.",
      theory: "E = h * nu - phi",
      apparatus: "Photoelectric cell, Monochromatic light source, Microammeter",
      procedure: "Align light beam, vary frequency, record stopping potential",
      observations: "Threshold frequency observed at 4.5e14 Hz",
      calculations: "Slope yields Planck constant h = 6.626e-34 J.s",
      precautions: "Do not expose photocell to ambient stray light",
    },
    authUser
  );

  assert.ok(capturedUrl.endsWith("/api/v1/experiments"), "Should target /api/v1/experiments");
  assert.strictEqual(capturedOptions.method, "POST");
  const headers = new Headers(capturedOptions.headers);
  assert.strictEqual(headers.get("authorization"), "Bearer test-token-083");
  assert.strictEqual(created.id, "789e0123-e89b-12d3-a456-426614174000");
  assert.strictEqual(created.title, "Photoelectric Effect Experiment");
  assert.strictEqual(created.method, "manual");
  assert.strictEqual(created.preparationChecklist?.objective, false);
  console.log("✓ Test 1 Passed: Authenticated experiment creation calls the backend");
}

// 2. Authenticated experiment listing calls the backend
{
  tokenManager.setAccessToken("test-token-083");
  const authUser = { isGuest: false, name: "Ada Lovelace", email: "ada@example.com" };

  let listCalled = false;
  globalThis.fetch = async (url, options) => {
    listCalled = true;
    assert.strictEqual(options.method, "GET");
    assert.ok(String(url).includes("/api/v1/experiments"));
    return createMockResponse({
      items: [
        {
          id: "789e0123-e89b-12d3-a456-426614174000",
          title: "Photoelectric Effect Experiment",
          subject: "Modern Physics",
          experimentNumber: "EXP-PHY-04",
          courseSemester: "Semester 3",
          creationMethod: "manual",
          hasManualFile: false,
          fileName: null,
          status: "ready",
          createdAt: "2026-10-04T10:00:00Z",
          updatedAt: "2026-10-04T10:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    });
  };

  const list = await experimentStorage.getExperimentsAsync(authUser);
  assert.ok(listCalled, "Backend list endpoint must be invoked");
  assert.strictEqual(list.length, 1);
  assert.strictEqual(list[0].id, "789e0123-e89b-12d3-a456-426614174000");
  assert.strictEqual(list[0].title, "Photoelectric Effect Experiment");
  console.log("✓ Test 2 Passed: Authenticated experiment listing calls the backend");
}

// 3. Authenticated detail retrieval calls the backend
{
  tokenManager.setAccessToken("test-token-083");
  const authUser = { isGuest: false, name: "Ada Lovelace", email: "ada@example.com" };

  let detailUrl = "";
  globalThis.fetch = async (url) => {
    detailUrl = String(url);
    return createMockResponse({
      id: "789e0123-e89b-12d3-a456-426614174000",
      title: "Photoelectric Effect Experiment",
      subject: "Modern Physics",
      creationMethod: "manual",
      hasManualFile: false,
      status: "ready",
      objective: "To verify Einstein photoelectric equation.",
      theory: "E = h * nu - phi",
      apparatus: "Photoelectric cell, Monochromatic light source",
      procedure: "Measure stopping voltage",
      observations: "Linear V0 vs frequency",
      calculations: "h = 6.626e-34",
      precautions: "Safety goggles",
      preparationChecklist: {
        objective: true,
        theory: false,
        apparatus: true,
        procedure: false,
        precautions: false,
      },
      vivaQuestionsCount: 4,
      createdAt: "2026-10-04T10:00:00Z",
      updatedAt: "2026-10-04T10:30:00Z",
    });
  };

  const exp = await experimentStorage.getExperimentByIdAsync(
    "789e0123-e89b-12d3-a456-426614174000",
    authUser
  );
  assert.ok(detailUrl.endsWith("/api/v1/experiments/789e0123-e89b-12d3-a456-426614174000"));
  assert.ok(exp);
  assert.strictEqual(exp.id, "789e0123-e89b-12d3-a456-426614174000");
  assert.strictEqual(exp.objective, "To verify Einstein photoelectric equation.");
  assert.strictEqual(exp.vivaQuestionsCount, 4);
  assert.strictEqual(exp.preparationChecklist?.objective, true);
  console.log("✓ Test 3 Passed: Authenticated detail retrieval calls the backend");
}

// 4. Authenticated updates call the backend
{
  tokenManager.setAccessToken("test-token-083");
  const authUser = { isGuest: false, name: "Ada Lovelace", email: "ada@example.com" };

  let patchBody = null;
  globalThis.fetch = async (url, options) => {
    assert.strictEqual(options.method, "PATCH");
    assert.ok(String(url).endsWith("/api/v1/experiments/789e0123-e89b-12d3-a456-426614174000"));
    patchBody = JSON.parse(options.body);
    return createMockResponse({
      id: "789e0123-e89b-12d3-a456-426614174000",
      title: "Updated Photoelectric Title",
      subject: "Quantum Physics",
      creationMethod: "manual",
      hasManualFile: false,
      status: "in-progress",
      createdAt: "2026-10-04T10:00:00Z",
      updatedAt: "2026-10-04T11:00:00Z",
    });
  };

  const updated = await experimentStorage.updateExperimentAsync(
    "789e0123-e89b-12d3-a456-426614174000",
    { title: "Updated Photoelectric Title", subject: "Quantum Physics", status: "in-progress" },
    authUser
  );

  assert.strictEqual(patchBody.title, "Updated Photoelectric Title");
  assert.strictEqual(patchBody.subject, "Quantum Physics");
  assert.strictEqual(patchBody.status, "in-progress");
  assert.ok(updated);
  assert.strictEqual(updated.title, "Updated Photoelectric Title");
  assert.strictEqual(updated.status, "in-progress");
  console.log("✓ Test 4 Passed: Authenticated updates call the backend");
}

// 5. Authenticated deletion calls the backend
{
  tokenManager.setAccessToken("test-token-083");
  const authUser = { isGuest: false, name: "Ada Lovelace", email: "ada@example.com" };

  let deleteCalled = false;
  globalThis.fetch = async (url, options) => {
    deleteCalled = true;
    assert.strictEqual(options.method, "DELETE");
    assert.ok(String(url).endsWith("/api/v1/experiments/789e0123-e89b-12d3-a456-426614174000"));
    return createMockResponse(null, { status: 204 });
  };

  const deleted = await experimentStorage.deleteExperimentAsync(
    "789e0123-e89b-12d3-a456-426614174000",
    authUser
  );
  assert.ok(deleteCalled, "DELETE request must be dispatched");
  assert.strictEqual(deleted, true);
  console.log("✓ Test 5 Passed: Authenticated deletion calls the backend");
}

// 6. Guest creation uses localStorage without network requests
{
  mockStorageStore.clear();
  tokenManager.clearTokens();
  const guestUser = { isGuest: true };

  globalThis.fetch = async () => {
    throw new Error("Guest operation must never trigger network request!");
  };

  const guestExp = experimentStorage.saveExperiment(
    {
      title: "Ohm's Law Verification",
      subject: "Basic Electronics",
      method: "manual",
      objective: "To verify V = I * R",
      theory: "Current is directly proportional to potential difference.",
    },
    guestUser
  );

  assert.ok(guestExp.id, "Guest experiment ID generated");
  assert.strictEqual(guestExp.title, "Ohm's Law Verification");
  const storedJson = mockStorageStore.get("pracprep_experiments_guest");
  assert.ok(storedJson, "Data must be saved under pracprep_experiments_guest");
  const storedArr = JSON.parse(storedJson);
  assert.strictEqual(storedArr.length, 1);
  assert.strictEqual(storedArr[0].title, "Ohm's Law Verification");
  console.log("✓ Test 6 Passed: Guest creation uses localStorage without network requests");
}

// 7. Guest listing uses localStorage without network requests
{
  const guestUser = { isGuest: true };
  globalThis.fetch = async () => {
    throw new Error("Guest listing must never trigger network request!");
  };

  const list = experimentStorage.getExperiments(guestUser);
  assert.strictEqual(list.length, 1);
  assert.strictEqual(list[0].title, "Ohm's Law Verification");
  console.log("✓ Test 7 Passed: Guest listing uses localStorage without network requests");
}

// 8. Guest updates and deletions preserve existing synchronous behavior
{
  const guestUser = { isGuest: true };
  globalThis.fetch = async () => {
    throw new Error("Guest mutation must never trigger network request!");
  };

  const list = experimentStorage.getExperiments(guestUser);
  const targetId = list[0].id;

  // Toggle checklist
  const toggled = experimentStorage.toggleChecklistItem(targetId, "theory", true, guestUser);
  assert.ok(toggled);
  assert.strictEqual(toggled.preparationChecklist?.theory, true);

  // Update experiment
  const updated = experimentStorage.updateExperiment(
    targetId,
    { status: "completed", observations: "V/I ratio is constant" },
    guestUser
  );
  assert.ok(updated);
  assert.strictEqual(updated.status, "completed");

  // Delete experiment
  const deleted = experimentStorage.deleteExperiment(targetId, guestUser);
  assert.strictEqual(deleted, true);
  assert.strictEqual(experimentStorage.getExperiments(guestUser).length, 0);
  console.log("✓ Test 8 Passed: Guest updates and deletions preserve existing behavior");
}

// 9. Guest data remains isolated from authenticated records
{
  mockStorageStore.clear();
  tokenManager.clearTokens();

  // Create guest experiment
  const guestExp = experimentStorage.saveExperiment(
    { title: "Guest Pendulum Experiment", subject: "Physics" },
    { isGuest: true }
  );

  // Authenticate user
  tokenManager.setAccessToken("token-user-bob");
  const authBob = { isGuest: false, name: "Bob", email: "bob@univ.edu" };

  globalThis.fetch = async (_url) => {
    return createMockResponse({
      items: [
        {
          id: "bob-exp-uuid-1",
          title: "Bob Quantum Experiment",
          subject: "Physics",
          creationMethod: "manual",
          hasManualFile: false,
          status: "ready",
          createdAt: "2026-10-04T12:00:00Z",
          updatedAt: "2026-10-04T12:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      pageSize: 20,
      totalPages: 1,
    });
  };

  const bobList = await experimentStorage.getExperimentsAsync(authBob);
  const guestList = experimentStorage.getExperiments({ isGuest: true });

  assert.strictEqual(bobList.length, 1);
  assert.strictEqual(bobList[0].id, "bob-exp-uuid-1");
  assert.strictEqual(guestList.length, 1);
  assert.strictEqual(guestList[0].id, guestExp.id);
  assert.notStrictEqual(bobList[0].id, guestList[0].id);

  // Verify guest storage key was not touched by Bob's listing
  const guestStored = JSON.parse(mockStorageStore.get("pracprep_experiments_guest"));
  assert.strictEqual(guestStored[0].title, "Guest Pendulum Experiment");
  console.log("✓ Test 9 Passed: Guest data remains isolated from authenticated records");
}

// 10. API failures do not silently fall back to localStorage
{
  tokenManager.setAccessToken("token-user-carol");
  const authCarol = { isGuest: false, name: "Carol", email: "carol@univ.edu" };

  globalThis.fetch = async () => {
    return createMockResponse({ detail: "Database connection failed" }, { status: 500 });
  };

  let caughtError = null;
  try {
    await experimentStorage.createExperiment(
      { title: "Should Fail Experiment", subject: "Chemistry" },
      authCarol
    );
  } catch (err) {
    caughtError = err;
  }

  assert.ok(caughtError instanceof ApiError, "Should throw ApiError on backend failure");
  assert.strictEqual(caughtError.status, 500);

  // Verify NO data was silently written to localStorage
  const scopedKey = `pracprep_experiments_user_carol_univ_edu`;
  assert.strictEqual(mockStorageStore.get(scopedKey), undefined);
  assert.strictEqual(
    mockStorageStore.get("pracprep_experiments_guest")?.includes("Should Fail Experiment"),
    false
  );
  console.log("✓ Test 10 Passed: API failures do not silently fall back to localStorage");
}

// 11. Backend DTOs map correctly to frontend experiment models
{
  const backendDto = {
    id: "e9b21840-7f28-4444-a021-39e2467d5891",
    title: "Faraday's Law of Induction",
    subject: "Electromagnetism",
    experimentNumber: "EXP-EM-02",
    courseSemester: "Semester 2",
    creationMethod: "upload",
    hasManualFile: true,
    fileName: "lab_manual_faraday.pdf",
    status: "in-progress",
    description: "Measurement of induced electromotive force.",
    objective: "To verify induced emf is proportional to rate of change of flux.",
    theory: "emf = -N * (dPhi / dt)",
    apparatus: "Bar magnet, Solenoid coil, Galvanometer",
    procedure: "Thrust magnet into coil at varying speeds",
    observations: "Deflection increases with velocity",
    calculations: "Peak induced voltage computed from oscilloscope trace",
    precautions: "Keep magnetic cards away from bar magnet",
    preparationChecklist: {
      objective: true,
      theory: true,
      apparatus: false,
      procedure: false,
      precautions: false,
    },
    vivaQuestionsCount: 5,
    createdAt: "2026-10-04T08:15:30Z",
    updatedAt: "2026-10-04T09:45:00Z",
  };

  const record = mapBackendExperimentToRecord(backendDto);
  assert.strictEqual(record.id, "e9b21840-7f28-4444-a021-39e2467d5891");
  assert.strictEqual(record.method, "upload");
  assert.strictEqual(record.hasManualFile, true);
  assert.strictEqual(record.fileName, "lab_manual_faraday.pdf");
  assert.strictEqual(record.createdAtTimestamp, new Date("2026-10-04T08:15:30Z").getTime());
  assert.strictEqual(record.updatedAtTimestamp, new Date("2026-10-04T09:45:00Z").getTime());
  assert.strictEqual(record.vivaQuestionsCount, 5);
  assert.strictEqual(record.preparationChecklist?.theory, true);

  // Test mapRecordToCreateDto
  const createDto = mapRecordToCreateDto({
    title: "New Exp",
    subject: "Physics",
    method: "upload",
    hasManualFile: true,
    fileName: "manual.pdf",
    experimentNumber: "EXP-1",
  });
  assert.strictEqual(createDto.title, "New Exp");
  assert.strictEqual(createDto.subject, "Physics");
  assert.strictEqual(createDto.creation_method, "upload");
  assert.strictEqual(createDto.has_manual_file, true);
  assert.strictEqual(createDto.file_name, "manual.pdf");
  assert.strictEqual(createDto.experiment_number, "EXP-1");

  // Test mapRecordToUpdateDto
  const updateDto = mapRecordToUpdateDto({
    status: "completed",
    objective: "Updated objective",
  });
  assert.strictEqual(updateDto.status, "completed");
  assert.strictEqual(updateDto.objective, "Updated objective");
  assert.strictEqual(updateDto.title, undefined);
  console.log("✓ Test 11 Passed: Backend DTOs map correctly to frontend experiment models");
}

// 12. Checklist data survives serialization and deserialization
{
  tokenManager.setAccessToken("test-token-checklist");
  const authUser = { isGuest: false, name: "David", email: "david@mit.edu" };

  let checklistPatchBody = null;
  globalThis.fetch = async (url, options) => {
    assert.strictEqual(options.method, "PATCH");
    assert.ok(String(url).endsWith("/api/v1/experiments/exp-chk-123/checklist"));
    checklistPatchBody = JSON.parse(options.body);
    return createMockResponse({
      id: "chk-uuid-456",
      experimentId: "exp-chk-123",
      items: {
        objective: true,
        theory: true,
        apparatus: false,
        procedure: false,
        precautions: true,
      },
      createdAt: "2026-10-04T10:00:00Z",
      updatedAt: "2026-10-04T10:05:00Z",
    });
  };

  const result = await experimentStorage.updateChecklistAsync(
    "exp-chk-123",
    { objective: true, theory: true, precautions: true },
    authUser
  );

  assert.strictEqual(checklistPatchBody.objective, true);
  assert.strictEqual(checklistPatchBody.theory, true);
  assert.strictEqual(checklistPatchBody.precautions, true);
  assert.strictEqual(result.objective, true);
  assert.strictEqual(result.theory, true);
  assert.strictEqual(result.precautions, true);
  assert.strictEqual(result.apparatus, false);
  console.log("✓ Test 12 Passed: Checklist data survives serialization and deserialization");
}

// 13. UUID identifiers are preserved
{
  const canonicalUuid = "550e8400-e29b-41d4-a716-446655440000";
  const mapped = mapBackendExperimentToRecord({
    id: canonicalUuid,
    title: "UUID Preservation Test",
    subject: "CS",
    creationMethod: "manual",
    hasManualFile: false,
    status: "ready",
    createdAt: "2026-10-04T12:00:00Z",
    updatedAt: "2026-10-04T12:00:00Z",
  });
  assert.strictEqual(mapped.id, canonicalUuid, "UUID string must be preserved exactly");
  console.log("✓ Test 13 Passed: UUID identifiers are preserved");
}

// 14. Pagination and filtering behave correctly
{
  tokenManager.setAccessToken("test-token-pagination");
  const authUser = { isGuest: false, name: "Grace", email: "grace@navy.mil" };

  let capturedQueryUrl = "";
  globalThis.fetch = async (url) => {
    capturedQueryUrl = String(url);
    return createMockResponse({
      items: [],
      total: 0,
      page: 2,
      pageSize: 5,
      totalPages: 0,
    });
  };

  await experimentStorage.getExperimentsAsync(authUser, {
    page: 2,
    pageSize: 5,
    subject: "Physics",
    status: "ready",
    search: "quantum",
  });

  const parsedUrl = new URL(capturedQueryUrl);
  assert.strictEqual(parsedUrl.searchParams.get("page"), "2");
  assert.strictEqual(parsedUrl.searchParams.get("pageSize"), "5");
  assert.strictEqual(parsedUrl.searchParams.get("subject"), "Physics");
  assert.strictEqual(parsedUrl.searchParams.get("status"), "ready");
  assert.strictEqual(parsedUrl.searchParams.get("search"), "quantum");
  console.log("✓ Test 14 Passed: Pagination and filtering behave correctly");
}

// 15. Authentication expiration is handled consistently
{
  tokenManager.setAccessToken("expired-token");
  tokenManager.setRefreshToken(null); // No refresh token available to trigger expiration
  const authUser = { isGuest: false, name: "Heidi", email: "heidi@univ.edu" };

  let expiredNotified = false;
  const unsub = tokenManager.onAuthExpired(() => {
    expiredNotified = true;
  });

  globalThis.fetch = async () => {
    return createMockResponse({ detail: "Token expired" }, { status: 401 });
  };

  let thrown = null;
  try {
    await experimentStorage.createExperiment({ title: "Expired Test", subject: "Math" }, authUser);
  } catch (err) {
    thrown = err;
  }

  unsub();
  assert.strictEqual(expiredNotified, true, "Auth expired listener should be notified");
  assert.ok(thrown instanceof ApiError, "Should throw ApiError on expired session");
  assert.strictEqual(thrown.status, 401);
  assert.strictEqual(thrown.isAuthError, true);
  console.log("✓ Test 15 Passed: Authentication expiration is handled consistently");
}

// 16. Existing experiment-related UI integrations remain compatible
{
  tokenManager.clearTokens();
  const guestUser = { isGuest: true };

  let subscriberFired = false;
  const unsubscribe = experimentStorage.subscribe(() => {
    subscriberFired = true;
  });

  const saved = experimentStorage.saveExperiment(
    { title: "UI Compatibility Exp", subject: "Engineering" },
    guestUser
  );

  assert.ok(saved);
  assert.strictEqual(subscriberFired, true, "Subscriber must be notified on experiment mutation");

  const byId = experimentStorage.getExperimentById(saved.id, guestUser);
  assert.ok(byId);
  assert.strictEqual(byId.title, "UI Compatibility Exp");

  unsubscribe();
  console.log("✓ Test 16 Passed: Existing experiment-related UI integrations remain compatible");
}

console.log("\nALL 16 DUAL-MODE EXPERIMENT STORAGE TESTS PASSED CLEANLY!");
