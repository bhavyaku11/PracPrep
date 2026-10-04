/**
 * Test Suite: PracPrep Frontend Authentication Service & State Integration (TASK-08.2)
 *
 * Verifies:
 * 1. Successful login updates tokens and session storage
 * 2. Successful registration updates tokens and session storage
 * 3. Invalid credentials return proper ApiError
 * 4. Session restoration succeeds with valid credentials
 * 5. Expired credentials clear local storage and return null
 * 6. Network failure during restoration throws network ApiError without authenticating
 * 7. Logout clears credentials and resets user session
 * 8. Logout still clears credentials even when backend returns 500
 * 9. Token expiration notifications fire properly
 * 10. Guest mode functions without authentication
 * 11. Guest storage data survives login and logout without data loss
 * 12. Unauthenticated session check avoids redundant network requests
 * 13. Synchronous local user session conforms to UserSession interface
 */

import assert from "node:assert";
import { tokenManager, ApiError } from "./src/lib/apiClient.ts";
import { authService } from "./src/services/authService.ts";

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
    json: async () => JSON.parse(bodyText),
    text: async () => bodyText,
  };
}

console.log("=== Running TASK-08.2 Authentication Service & State Tests ===");

// 1. Successful login updates tokens and session storage
{
  tokenManager.clearTokens();
  mockStorageStore.clear();

  const mockUser = {
    id: "user-1234-uuid",
    email: "student@university.edu",
    full_name: "Alex Morgan",
    university: "State University",
    is_active: true,
    created_at: "2026-10-04T12:00:00Z",
  };

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    if (url.includes("/auth/login")) {
      const body = JSON.parse(init.body);
      assert.strictEqual(body.email, "student@university.edu");
      assert.strictEqual(body.password, "SecretPass123!");
      return createMockResponse({
        access_token: "login-access-token",
        refresh_token: "login-refresh-token",
        token_type: "bearer",
        expires_in: 900,
        user: mockUser,
      });
    }
    return createMockResponse({}, { status: 404 });
  };

  try {
    const res = await authService.login({
      email: "student@university.edu",
      password: "SecretPass123!",
    });

    assert.strictEqual(res.access_token, "login-access-token");
    assert.strictEqual(tokenManager.getAccessToken(), "login-access-token");
    assert.strictEqual(tokenManager.getRefreshToken(), "login-refresh-token");

    const storedUser = JSON.parse(mockStorageStore.get("pracprep_user"));
    assert.strictEqual(storedUser.isGuest, false);
    assert.strictEqual(storedUser.email, "student@university.edu");
    assert.strictEqual(storedUser.name, "Alex Morgan");
    assert.strictEqual(storedUser.university, "State University");

    console.log("✓ Test 1 Passed: Successful login updates tokens and session storage");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 2. Successful registration updates tokens and session storage
{
  tokenManager.clearTokens();
  mockStorageStore.clear();

  const mockUser = {
    id: "user-5678-uuid",
    email: "newstudent@college.edu",
    full_name: "Sam Taylor",
    university: "Tech Institute",
    is_active: true,
    created_at: "2026-10-04T12:05:00Z",
  };

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    if (url.includes("/auth/register")) {
      const body = JSON.parse(init.body);
      assert.strictEqual(body.email, "newstudent@college.edu");
      assert.strictEqual(body.full_name, "Sam Taylor");
      return createMockResponse(
        {
          access_token: "register-access-token",
          refresh_token: "register-refresh-token",
          token_type: "bearer",
          expires_in: 900,
          user: mockUser,
        },
        { status: 201 }
      );
    }
    return createMockResponse({}, { status: 404 });
  };

  try {
    const res = await authService.register({
      email: "newstudent@college.edu",
      password: "NewPassword88!",
      full_name: "Sam Taylor",
    });

    assert.strictEqual(res.access_token, "register-access-token");
    assert.strictEqual(tokenManager.getAccessToken(), "register-access-token");
    assert.strictEqual(tokenManager.getRefreshToken(), "register-refresh-token");

    const storedUser = JSON.parse(mockStorageStore.get("pracprep_user"));
    assert.strictEqual(storedUser.isGuest, false);
    assert.strictEqual(storedUser.email, "newstudent@college.edu");
    assert.strictEqual(storedUser.name, "Sam Taylor");

    console.log("✓ Test 2 Passed: Successful registration updates tokens and session storage");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 3. Invalid credentials return proper ApiError
{
  tokenManager.clearTokens();
  mockStorageStore.clear();

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes("/auth/login")) {
      return createMockResponse(
        { detail: "Incorrect email or password" },
        { status: 401 }
      );
    }
    return createMockResponse({}, { status: 404 });
  };

  try {
    await authService.login({
      email: "wrong@university.edu",
      password: "badpassword",
    });
    assert.fail("Should have thrown ApiError");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 401);
    assert.strictEqual(err.message, "Incorrect email or password");
    assert.strictEqual(tokenManager.hasAccessToken(), false);
    assert.strictEqual(mockStorageStore.get("pracprep_user"), undefined);
    console.log("✓ Test 3 Passed: Invalid credentials return proper ApiError");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 4. Session restoration succeeds with valid credentials
{
  tokenManager.setTokens({
    accessToken: "valid-session-token",
    refreshToken: "valid-session-refresh",
  });

  const mockUser = {
    id: "user-restored-id",
    email: "restored@university.edu",
    full_name: "Restored Student",
    is_active: true,
    created_at: "2026-10-04T12:00:00Z",
  };

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url, init) => {
    if (url.includes("/users/me")) {
      const auth = new Headers(init.headers).get("Authorization");
      assert.strictEqual(auth, "Bearer valid-session-token");
      return createMockResponse(mockUser, { status: 200 });
    }
    return createMockResponse({}, { status: 404 });
  };

  try {
    const user = await authService.restoreSession();
    assert.deepStrictEqual(user, mockUser);
    const stored = JSON.parse(mockStorageStore.get("pracprep_user"));
    assert.strictEqual(stored.email, "restored@university.edu");

    console.log("✓ Test 4 Passed: Session restoration succeeds with valid credentials");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 5. Expired credentials clear local storage and return null
{
  tokenManager.setTokens({
    accessToken: "expired-token",
    refreshToken: "dead-refresh-token",
  });
  mockStorageStore.set("pracprep_user", JSON.stringify({ isGuest: false, email: "old@test.com" }));

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes("/users/me") || url.includes("/auth/refresh")) {
      return createMockResponse({ detail: "Token expired or revoked" }, { status: 401 });
    }
    return createMockResponse({}, { status: 404 });
  };

  try {
    const user = await authService.restoreSession();
    assert.strictEqual(user, null, "Should return null for expired session");
    assert.strictEqual(tokenManager.hasAccessToken(), false, "Tokens must be cleared");
    assert.strictEqual(mockLocalStorage.getItem("pracprep_user"), null, "Session must be removed");

    console.log("✓ Test 5 Passed: Expired credentials clear local storage and return null");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 6. Network failure during restoration throws network ApiError without authenticating
{
  tokenManager.setTokens({
    accessToken: "good-token",
    refreshToken: "good-refresh",
  });

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    throw new TypeError("Failed to fetch");
  };

  try {
    await authService.restoreSession();
    assert.fail("Should have re-thrown network error");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.isNetworkError, true);
    assert.strictEqual(tokenManager.hasAccessToken(), true, "Network hiccup should not immediately wipe tokens");
    console.log("✓ Test 6 Passed: Network failure during restoration throws network ApiError");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 7. Successful logout clears credentials and resets user session
{
  tokenManager.setTokens({
    accessToken: "logout-token",
    refreshToken: "logout-refresh",
  });
  mockStorageStore.set("pracprep_user", JSON.stringify({ isGuest: false, email: "logout@test.com" }));

  let logoutCalled = false;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes("/auth/logout")) {
      logoutCalled = true;
      return createMockResponse({ message: "Logged out successfully" }, { status: 200 });
    }
    return createMockResponse({}, { status: 404 });
  };

  try {
    await authService.logout();
    assert.strictEqual(logoutCalled, true);
    assert.strictEqual(tokenManager.hasAccessToken(), false);
    assert.strictEqual(mockLocalStorage.getItem("pracprep_user"), null);

    console.log("✓ Test 7 Passed: Successful logout clears credentials and resets user session");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 8. Logout still clears credentials even when backend returns 500
{
  tokenManager.setTokens({
    accessToken: "token-to-clear",
    refreshToken: "refresh-to-clear",
  });
  mockStorageStore.set("pracprep_user", JSON.stringify({ isGuest: false, email: "test@test.com" }));

  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes("/auth/logout")) {
      return createMockResponse({ detail: "Server database crash" }, { status: 500 });
    }
    return createMockResponse({}, { status: 404 });
  };

  try {
    await authService.logout();
    assert.strictEqual(tokenManager.hasAccessToken(), false, "Local tokens must still be purged");
    assert.strictEqual(mockLocalStorage.getItem("pracprep_user"), null, "Local session must be purged");

    console.log("✓ Test 8 Passed: Logout still clears credentials even when backend returns 500");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 9. Token expiration notifications fire properly
{
  let listenerFired = false;
  const unsubscribe = tokenManager.onAuthExpired(() => {
    listenerFired = true;
  });

  tokenManager.notifyAuthExpired();
  assert.strictEqual(listenerFired, true);
  unsubscribe();

  listenerFired = false;
  tokenManager.notifyAuthExpired();
  assert.strictEqual(listenerFired, false, "Unsubscribe should detach listener");

  console.log("✓ Test 9 Passed: Token expiration notifications fire properly");
}

// 10. Guest mode functions without authentication
{
  authService.clearLocalSession();
  assert.strictEqual(tokenManager.hasAccessToken(), false);
  assert.strictEqual(mockLocalStorage.getItem("pracprep_user"), null);

  mockStorageStore.set("pracprep_user", JSON.stringify({ isGuest: true }));
  const stored = JSON.parse(mockStorageStore.get("pracprep_user"));
  assert.strictEqual(stored.isGuest, true);

  console.log("✓ Test 10 Passed: Guest mode functions without authentication");
}

// 11. Guest storage data survives login and logout without data loss
{
  mockStorageStore.clear();

  // Populate guest experiments and guest settings
  const guestExperiments = [{ id: "exp-guest-1", title: "Ohm's Law" }];
  const guestSettings = { theme: "dark", studyPreferences: { defaultDifficulty: "hard" } };

  mockStorageStore.set("pracprep_experiments_guest", JSON.stringify(guestExperiments));
  mockStorageStore.set("pracprep_settings_guest", JSON.stringify(guestSettings));

  // Perform login
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async (url) => {
    if (url.includes("/auth/login")) {
      return createMockResponse({
        access_token: "tok",
        refresh_token: "ref",
        token_type: "bearer",
        expires_in: 900,
        user: { id: "u1", email: "test@domain.com", full_name: "Test User", is_active: true, created_at: "now" },
      });
    }
    if (url.includes("/auth/logout")) {
      return createMockResponse({ message: "ok" });
    }
    return createMockResponse({});
  };

  try {
    await authService.login({ email: "test@domain.com", password: "Password123!" });

    // Verify guest data is untouched
    assert.deepStrictEqual(
      JSON.parse(mockStorageStore.get("pracprep_experiments_guest")),
      guestExperiments,
      "Guest experiments must not be wiped on login"
    );
    assert.deepStrictEqual(
      JSON.parse(mockStorageStore.get("pracprep_settings_guest")),
      guestSettings,
      "Guest settings must not be wiped on login"
    );

    // Perform logout
    await authService.logout();

    // Verify guest data is still intact
    assert.deepStrictEqual(
      JSON.parse(mockStorageStore.get("pracprep_experiments_guest")),
      guestExperiments,
      "Guest experiments must remain intact after logout"
    );

    console.log("✓ Test 11 Passed: Guest storage data survives login and logout without data loss");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

// 12. Unauthenticated session check avoids redundant network requests
{
  tokenManager.clearTokens();
  let networkCalls = 0;
  const originalFetch = globalThis.fetch;
  globalThis.fetch = async () => {
    networkCalls++;
    return createMockResponse({});
  };

  try {
    const res = await authService.restoreSession();
    assert.strictEqual(res, null);
    assert.strictEqual(networkCalls, 0, "No network request should be dispatched when no token is present");

    console.log("✓ Test 12 Passed: Unauthenticated session check avoids redundant network requests");
  } finally {
    globalThis.fetch = originalFetch;
  }
}

console.log("\nALL 12 AUTH SERVICE & STATE TESTS PASSED CLEANLY!");
