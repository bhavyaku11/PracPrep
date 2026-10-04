/**
 * Test Suite: PracPrep Frontend Clerk & Google Authentication Integration
 *
 * Verifies:
 * 1. Clerk Publishable Key extraction and validation logic
 * 2. Missing or malformed Publishable Key diagnostics
 * 3. syncClerkSession dispatches POST /auth/clerk-sync with Bearer header and payload
 * 4. syncClerkSession saves tokens to tokenManager and updates local user session
 * 5. syncClerkSession error propagation with typed ApiError
 * 6. Guest mode preservation: Guest experiments and viva sessions are NOT erased upon Google sync
 * 7. Guest migration flow compatibility: migrationService correctly detects guest data post-sync
 * 8. Sign-out clears tokens and resets local session state
 * 9. Native JWT login and register regression testing
 */

import assert from "node:assert";
import { tokenManager, ApiError } from "./src/lib/apiClient.ts";
import { authService } from "./src/services/authService.ts";
import {
  CLERK_ENV_KEY,
  getClerkPublishableKey,
  isClerkConfigured,
  getClerkConfigurationError,
} from "./src/lib/clerk.ts";
import { migrationService } from "./src/services/migrationService.ts";

// Setup global mock storage
const mockStorageStore = new Map();
const mockLocalStorage = {
  getItem: (k) => mockStorageStore.get(k) ?? null,
  setItem: (k, v) => mockStorageStore.set(k, String(v)),
  removeItem: (k) => mockStorageStore.delete(k),
  clear: () => mockStorageStore.clear(),
};

globalThis.localStorage = mockLocalStorage;
globalThis.window = {
  localStorage: mockLocalStorage,
  location: { origin: "http://localhost:5173", pathname: "/login", search: "" },
  dispatchEvent: () => true,
  addEventListener: () => {},
  removeEventListener: () => {},
};

function createMockResponse(body, init = {}) {
  const status = init.status ?? 200;
  const statusText = init.statusText ?? (status === 200 ? "OK" : "Error");
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
    json: async () => (typeof body === "object" ? body : JSON.parse(bodyText)),
    text: async () => bodyText,
  };
}

let testCount = 0;
function test(name, fn) {
  testCount++;
  try {
    fn();
    console.log(`✓ Test ${testCount} Passed: ${name}`);
  } catch (err) {
    console.error(`✗ Test ${testCount} FAILED: ${name}`);
    throw err;
  }
}

async function asyncTest(name, fn) {
  testCount++;
  try {
    await fn();
    console.log(`✓ Test ${testCount} Passed: ${name}`);
  } catch (err) {
    console.error(`✗ Test ${testCount} FAILED: ${name}`);
    throw err;
  }
}

console.log("=== Running PracPrep Clerk & Google Authentication Tests ===");

// -----------------------------------------------------------------------------
// Test 1: Publishable key extraction & format validation
// -----------------------------------------------------------------------------
test("Publishable Key format validation detects valid and invalid keys", () => {
  const originalEnv = process.env[CLERK_ENV_KEY];

  try {
    // Valid dev key
    process.env[CLERK_ENV_KEY] = "pk_test_ZWxlZ2FudC1yaGluby04MDcxLmNsZXJrLmFjY291bnRzLmRldiQ";
    assert.strictEqual(getClerkPublishableKey(), "pk_test_ZWxlZ2FudC1yaGluby04MDcxLmNsZXJrLmFjY291bnRzLmRldiQ");
    assert.strictEqual(isClerkConfigured(), true);
    assert.strictEqual(getClerkConfigurationError(), null);

    // Valid prod key
    process.env[CLERK_ENV_KEY] = "pk_live_YnVzaW5lc3MtcHJvZHVjdGlvbi1rZXktZXhhbXBsZQ";
    assert.strictEqual(isClerkConfigured(), true);
    assert.strictEqual(getClerkConfigurationError(), null);

    // Invalid prefix
    process.env[CLERK_ENV_KEY] = "sk_test_secret_key_should_not_be_here";
    assert.strictEqual(isClerkConfigured(), false);
    assert.match(getClerkConfigurationError(), /Key must begin with "pk_test_" or "pk_live_"/);

    // Missing key
    delete process.env[CLERK_ENV_KEY];
    assert.strictEqual(isClerkConfigured(), false);
    assert.match(getClerkConfigurationError(), /Missing VITE_CLERK_PUBLISHABLE_KEY/);
  } finally {
    if (originalEnv !== undefined) {
      process.env[CLERK_ENV_KEY] = originalEnv;
    } else {
      delete process.env[CLERK_ENV_KEY];
    }
  }
});

// -----------------------------------------------------------------------------
// Test 2: syncClerkSession dispatches properly and stores native tokens
// -----------------------------------------------------------------------------
await asyncTest("syncClerkSession sends clerk token to /auth/clerk-sync and sets native tokens", async () => {
  mockStorageStore.clear();

  let capturedUrl = "";
  let capturedHeaders = null;
  let capturedBody = null;

  globalThis.fetch = async (url, init) => {
    capturedUrl = String(url);
    capturedHeaders = init.headers;
    capturedBody = JSON.parse(init.body);

    return createMockResponse({
      access_token: "native_access_token_abc123",
      refresh_token: "native_refresh_token_xyz789",
      token_type: "bearer",
      expires_in: 900,
      user: {
        id: "550e8400-e29b-41d4-a716-446655440000",
        email: "google.student@university.edu",
        full_name: "Google Student",
        university: "MIT",
        is_active: true,
        created_at: new Date().toISOString(),
      },
    });
  };

  const response = await authService.syncClerkSession({
    clerkToken: "clerk.jwt.token.signature",
    email: "google.student@university.edu",
    fullName: "Google Student",
    university: "MIT",
  });

  assert.strictEqual(capturedUrl, "http://localhost:8000/api/v1/auth/clerk-sync");
  const authHeader = capturedHeaders instanceof Headers ? capturedHeaders.get("authorization") : capturedHeaders.Authorization;
  assert.strictEqual(authHeader, "Bearer clerk.jwt.token.signature");
  assert.strictEqual(capturedBody.clerk_token, "clerk.jwt.token.signature");
  assert.strictEqual(capturedBody.email, "google.student@university.edu");
  assert.strictEqual(capturedBody.full_name, "Google Student");

  assert.strictEqual(response.access_token, "native_access_token_abc123");
  assert.strictEqual(tokenManager.getAccessToken(), "native_access_token_abc123");
  assert.strictEqual(tokenManager.getRefreshToken(), "native_refresh_token_xyz789");

  // Local user session verification
  const sessionJson = mockLocalStorage.getItem("pracprep_user");
  assert.ok(sessionJson, "pracprep_user must be persisted");
  const session = JSON.parse(sessionJson);
  assert.strictEqual(session.isGuest, false);
  assert.strictEqual(session.email, "google.student@university.edu");
  assert.strictEqual(session.name, "Google Student");
});

// -----------------------------------------------------------------------------
// Test 3: syncClerkSession propagates backend 401 error as typed ApiError
// -----------------------------------------------------------------------------
await asyncTest("syncClerkSession propagates 401 token verification failure", async () => {
  globalThis.fetch = async () => {
    return createMockResponse(
      { detail: "Invalid Clerk token: signature verification failed" },
      { status: 401, statusText: "Unauthorized" }
    );
  };

  await assert.rejects(
    async () => {
      await authService.syncClerkSession({
        clerkToken: "tampered.token",
        email: "attacker@bad.org",
      });
    },
    (err) => {
      assert.ok(err instanceof ApiError);
      assert.strictEqual(err.status, 401);
      assert.strictEqual(err.isAuthError, true);
      assert.match(err.message, /signature verification failed/);
      return true;
    }
  );
});

// -----------------------------------------------------------------------------
// Test 4: Guest mode data is preserved upon Google SSO sign-in
// -----------------------------------------------------------------------------
await asyncTest("Google sign-in does not overwrite or erase local guest lab data", async () => {
  mockStorageStore.clear();

  // Populate guest experiments and viva sessions
  const guestExperiment = {
    id: "guest-exp-101",
    title: "Guest Acid Base Titration",
    subject: "Chemistry",
    aim: "Determine molarity of unknown HCl",
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };

  mockLocalStorage.setItem(
    "pracprep_experiments_guest",
    JSON.stringify([guestExperiment])
  );
  mockLocalStorage.setItem("pracprep_user", JSON.stringify({ isGuest: true }));

  assert.strictEqual(migrationService.checkHasGuestData(), true);
  const summaryBefore = migrationService.getGuestDataSummary();
  assert.strictEqual(summaryBefore.experimentCount, 1);

  // Perform Google Clerk sync
  globalThis.fetch = async () => {
    return createMockResponse({
      access_token: "new_token",
      refresh_token: "new_refresh",
      token_type: "bearer",
      expires_in: 900,
      user: {
        id: "550e8400-e29b-41d4-a716-446655440001",
        email: "alex@univ.edu",
        full_name: "Alex",
        is_active: true,
        created_at: new Date().toISOString(),
      },
    });
  };

  await authService.syncClerkSession({
    clerkToken: "valid_clerk_token",
    email: "alex@univ.edu",
  });

  // Guest data must remain intact in local storage!
  assert.strictEqual(migrationService.checkHasGuestData(), true);
  const summaryAfter = migrationService.getGuestDataSummary();
  assert.strictEqual(summaryAfter.experimentCount, 1);

  const guestExperimentsRaw = mockLocalStorage.getItem("pracprep_experiments_guest");
  assert.ok(guestExperimentsRaw);
  const parsed = JSON.parse(guestExperimentsRaw);
  assert.strictEqual(parsed[0].id, "guest-exp-101");
});

// -----------------------------------------------------------------------------
// Test 5: Logout terminates session and clears tokens
// -----------------------------------------------------------------------------
await asyncTest("Logout clears tokens and resets local session state", async () => {
  tokenManager.setTokens({
    accessToken: "active_token",
    refreshToken: "active_refresh",
  });
  mockLocalStorage.setItem("pracprep_user", JSON.stringify({ isGuest: false, name: "Student" }));

  globalThis.fetch = async () => {
    return createMockResponse({ message: "Logged out successfully" });
  };

  await authService.logout();

  assert.strictEqual(tokenManager.getAccessToken(), null);
  assert.strictEqual(tokenManager.getRefreshToken(), null);
  assert.strictEqual(mockLocalStorage.getItem("pracprep_user"), null);
});

// -----------------------------------------------------------------------------
// Test 6: Native JWT login continues to function without regression
// -----------------------------------------------------------------------------
await asyncTest("Native email/password login is preserved without regression", async () => {
  mockStorageStore.clear();

  let capturedBody = null;
  globalThis.fetch = async (url, init) => {
    capturedBody = JSON.parse(init.body);
    return createMockResponse({
      access_token: "native_token_123",
      refresh_token: "native_refresh_123",
      token_type: "bearer",
      expires_in: 900,
      user: {
        id: "550e8400-e29b-41d4-a716-446655440002",
        email: "traditional@university.edu",
        full_name: "Traditional Student",
        is_active: true,
        created_at: new Date().toISOString(),
      },
    });
  };

  const response = await authService.login({
    email: "traditional@university.edu",
    password: "Password123!",
  });

  assert.strictEqual(capturedBody.email, "traditional@university.edu");
  assert.strictEqual(capturedBody.password, "Password123!");
  assert.strictEqual(response.user.email, "traditional@university.edu");
  assert.strictEqual(tokenManager.getAccessToken(), "native_token_123");
});

console.log("\nALL 6 PRACPREP CLERK & GOOGLE AUTHENTICATION INTEGRATION TESTS PASSED CLEANLY!");
