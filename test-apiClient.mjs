/**
 * Test Suite: PracPrep Frontend API Client & Token Interceptors (TASK-08.1)
 *
 * Verifies URL normalization, auth injection, single-flight refresh concurrency,
 * retry limit, error parsing, multipart handling, and guest mode.
 */

import assert from "node:assert";
import { ApiClient, ApiError, TokenManager } from "./src/lib/apiClient.ts";

// Helper mock storage
function createMockStorage() {
  const store = new Map();
  return {
    getItem: (k) => store.get(k) ?? null,
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
}

// Helper mock response
function createMockResponse(body, init = {}) {
  const status = init.status ?? 200;
  const statusText = init.statusText ?? (status === 200 ? "OK" : status === 204 ? "No Content" : "Error");
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

console.log("=== Running TASK-08.1 API Client & Interceptor Tests ===");

// 1. Correct API base URL construction & query params
{
  const client = new ApiClient({ baseUrl: "http://api.pracprep.local", apiPrefix: "/api/v1" });

  assert.strictEqual(
    client.buildUrl("/experiments"),
    "http://api.pracprep.local/api/v1/experiments",
    "Should append /api/v1 to root endpoint"
  );

  assert.strictEqual(
    client.buildUrl("experiments"),
    "http://api.pracprep.local/api/v1/experiments",
    "Should handle endpoints without leading slash"
  );

  const clientWithTrailingSlash = new ApiClient({ baseUrl: "http://api.pracprep.local/" });
  assert.strictEqual(
    clientWithTrailingSlash.buildUrl("/viva/sessions"),
    "http://api.pracprep.local/api/v1/viva/sessions",
    "Should normalize trailing slashes on base URL"
  );

  const clientWithPrefixInBase = new ApiClient({ baseUrl: "http://api.pracprep.local/api/v1" });
  assert.strictEqual(
    clientWithPrefixInBase.buildUrl("/auth/login"),
    "http://api.pracprep.local/api/v1/auth/login",
    "Should not duplicate /api/v1 if already in baseUrl"
  );

  assert.strictEqual(
    client.buildUrl("https://external.cdn/asset.json"),
    "https://external.cdn/asset.json",
    "Should preserve absolute URLs"
  );

  const relativeClient = new ApiClient({ baseUrl: "" });
  assert.strictEqual(
    relativeClient.buildUrl("/experiments"),
    "/api/v1/experiments",
    "Should support relative same-origin API URLs when baseUrl is empty"
  );

  const urlWithParams = client.buildUrl("/experiments", {
    page: 2,
    pageSize: 20,
    status: "ready",
    empty: null,
    undef: undefined,
  });
  assert.strictEqual(
    urlWithParams,
    "http://api.pracprep.local/api/v1/experiments?page=2&pageSize=20&status=ready",
    "Should serialize query params and omit null/undefined"
  );

  console.log("✓ Test 1 Passed: Correct API base URL construction and normalization");
}

// 2. Authorization header injection
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage);
  tokenMgr.setAccessToken("valid-access-token-123");

  let recordedHeaders = null;
  const mockFetch = async (url, init) => {
    recordedHeaders = new Headers(init.headers);
    return createMockResponse({ data: "ok" });
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });
  await client.get("/users/me");

  assert.strictEqual(
    recordedHeaders.get("Authorization"),
    "Bearer valid-access-token-123",
    "Should inject Authorization header from TokenManager"
  );

  console.log("✓ Test 2 Passed: Authorization header injection");
}

// 3. Public requests without authorization
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage);
  tokenMgr.setAccessToken("do-not-send-this-token");

  let recordedHeaders = null;
  const mockFetch = async (url, init) => {
    recordedHeaders = new Headers(init.headers);
    return createMockResponse({ public: true });
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });
  await client.get("/health", { requiresAuth: false });

  assert.strictEqual(
    recordedHeaders.get("Authorization"),
    null,
    "Public request must NOT include Authorization header"
  );

  console.log("✓ Test 3 Passed: Public requests without authorization");
}

// 4. Successful JSON & 204 responses
{
  const mockFetch = async (url) => {
    if (url.includes("/items/204")) {
      return createMockResponse("", { status: 204, statusText: "No Content" });
    }
    return createMockResponse({ id: "item-1", name: "Sample Item" }, { status: 200 });
  };

  const client = new ApiClient({ fetchFn: mockFetch });
  const data = await client.get("/items/1");
  assert.deepStrictEqual(data, { id: "item-1", name: "Sample Item" });

  const emptyData = await client.delete("/items/204");
  assert.strictEqual(emptyData, null, "Status 204 should return null cleanly");

  console.log("✓ Test 4 Passed: Successful JSON and 204 No Content responses");
}

// 5. Successful multipart form requests
{
  let recordedHeaders = null;
  let recordedBody = null;
  const mockFetch = async (url, init) => {
    recordedHeaders = new Headers(init.headers);
    recordedBody = init.body;
    return createMockResponse({ uploaded: true });
  };

  const client = new ApiClient({ fetchFn: mockFetch });
  const formData = new FormData();
  formData.append("file", "content");

  await client.post("/upload", formData);

  assert.strictEqual(
    recordedHeaders.get("Content-Type"),
    null,
    "FormData request must not manually set Content-Type so fetch sets boundary"
  );
  assert.strictEqual(recordedBody, formData);

  console.log("✓ Test 5 Passed: Multipart FormData upload without manual Content-Type boundary");
}

// 6. Consistent handling of HTTP 400 and 422 errors
{
  const mockFetch = async (url) => {
    if (url.includes("/bad-request")) {
      return createMockResponse({ detail: "Invalid request payload format" }, { status: 400 });
    }
    if (url.includes("/validation-error")) {
      return createMockResponse(
        {
          detail: [
            { loc: ["body", "questionCount"], msg: "Input should be greater than or equal to 1", type: "greater_than_equal" },
          ],
        },
        { status: 422 }
      );
    }
    return createMockResponse({});
  };

  const client = new ApiClient({ fetchFn: mockFetch });

  // 400 check
  try {
    await client.get("/bad-request");
    assert.fail("Should have thrown ApiError");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 400);
    assert.strictEqual(err.message, "Invalid request payload format");
  }

  // 422 check
  try {
    await client.post("/validation-error", { questionCount: -1 });
    assert.fail("Should have thrown ApiError");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 422);
    assert.strictEqual(err.code, "VALIDATION_ERROR");
    assert(err.message.includes("questionCount"));
    assert.strictEqual(err.validationErrors.length, 1);
  }

  console.log("✓ Test 6 Passed: Consistent handling of HTTP 400 and 422 validation errors");
}

// 7. Consistent handling of HTTP 500 errors
{
  const mockFetch = async (url) => {
    if (url.includes("/500-json")) {
      return createMockResponse({ detail: "Database connection failed" }, { status: 500 });
    }
    return createMockResponse("Internal Server Error", {
      status: 500,
      statusText: "Internal Server Error",
      headers: { "content-type": "text/plain" },
    });
  };

  const client = new ApiClient({ fetchFn: mockFetch });

  try {
    await client.get("/500-json");
    assert.fail("Should have thrown");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 500);
    assert.strictEqual(err.code, "SERVER_ERROR");
    assert.strictEqual(err.message, "Database connection failed");
  }

  try {
    await client.get("/500-text");
    assert.fail("Should have thrown");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 500);
    assert.strictEqual(err.message, "Internal Server Error");
  }

  console.log("✓ Test 7 Passed: Consistent handling of HTTP 500 server errors");
}

// 8. Network failure handling
{
  const mockFetch = async () => {
    throw new TypeError("Failed to fetch");
  };

  const client = new ApiClient({ fetchFn: mockFetch });

  try {
    await client.get("/offline");
    assert.fail("Should have thrown");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 0);
    assert.strictEqual(err.isNetworkError, true);
    assert.strictEqual(err.code, "NETWORK_ERROR");
    assert.strictEqual(err.message, "Failed to fetch");
  }

  console.log("✓ Test 8 Passed: Network failure handling");
}

// 9 & 10. Successful access-token refresh and request retry
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage);
  tokenMgr.setAccessToken("expired-token");
  tokenMgr.setRefreshToken("valid-refresh-token");

  let protectedCalls = 0;
  let refreshCalls = 0;

  const mockFetch = async (url, init) => {
    if (url.includes("/auth/refresh")) {
      refreshCalls++;
      const body = JSON.parse(init.body);
      assert.strictEqual(body.refresh_token, "valid-refresh-token");
      return createMockResponse({
        access_token: "refreshed-access-token",
        refresh_token: "valid-refresh-token",
        token_type: "bearer",
        expires_in: 900,
      });
    }

    if (url.includes("/viva/sessions")) {
      protectedCalls++;
      const auth = new Headers(init.headers).get("Authorization");
      if (auth === "Bearer expired-token") {
        return createMockResponse({ detail: "Token expired" }, { status: 401 });
      }
      if (auth === "Bearer refreshed-access-token") {
        return createMockResponse({ sessions: [{ id: "sess-1" }] }, { status: 200 });
      }
    }

    return createMockResponse({});
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });
  const result = await client.get("/viva/sessions");

  assert.strictEqual(protectedCalls, 2, "Original request should be attempted twice (first 401, second 200)");
  assert.strictEqual(refreshCalls, 1, "Refresh endpoint should be called exactly once");
  assert.strictEqual(tokenMgr.getAccessToken(), "refreshed-access-token", "Token manager should have new token");
  assert.deepStrictEqual(result, { sessions: [{ id: "sess-1" }] });

  console.log("✓ Tests 9 & 10 Passed: Successful token refresh and original request retry");
}

// 11. Failed refresh clears authentication credentials and triggers auth expired
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage);
  tokenMgr.setAccessToken("expired-token");
  tokenMgr.setRefreshToken("invalid-refresh-token");

  let authExpiredCalled = false;
  tokenMgr.onAuthExpired(() => {
    authExpiredCalled = true;
  });

  const mockFetch = async (url) => {
    if (url.includes("/auth/refresh")) {
      return createMockResponse({ detail: "Could not validate credentials" }, { status: 401 });
    }
    return createMockResponse({ detail: "Token expired" }, { status: 401 });
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });

  try {
    await client.get("/protected-endpoint");
    assert.fail("Should have thrown AUTH_EXPIRED");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 401);
    assert.strictEqual(err.code, "AUTH_EXPIRED");
    assert.strictEqual(err.isAuthError, true);
  }

  assert.strictEqual(tokenMgr.getAccessToken(), null, "Access token should be cleared");
  assert.strictEqual(tokenMgr.getRefreshToken(), null, "Refresh token should be cleared");
  assert.strictEqual(authExpiredCalled, true, "onAuthExpired callback should be notified");

  console.log("✓ Test 11 Passed: Failed refresh clears tokens and notifies auth expiration");
}

// 12. Refresh endpoint does not recursively trigger refresh
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage);
  tokenMgr.setRefreshToken("bad-refresh");

  let refreshCallCount = 0;
  const mockFetch = async (url) => {
    if (url.includes("/auth/refresh")) {
      refreshCallCount++;
      return createMockResponse({ detail: "Invalid refresh token" }, { status: 401 });
    }
    return createMockResponse({});
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });

  try {
    await client.post("/auth/refresh", { refresh_token: "bad-refresh" });
    assert.fail("Should have thrown 401");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 401);
  }

  assert.strictEqual(refreshCallCount, 1, "Refresh endpoint must not call refresh recursively");

  console.log("✓ Test 12 Passed: Refresh endpoint does not recursively trigger refresh");
}

// 13. Original request retried no more than once
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage);
  tokenMgr.setAccessToken("token-1");
  tokenMgr.setRefreshToken("refresh-1");

  let attemptCount = 0;
  let refreshCount = 0;

  const mockFetch = async (url) => {
    if (url.includes("/auth/refresh")) {
      refreshCount++;
      return createMockResponse({ access_token: "token-2", token_type: "bearer", expires_in: 900 });
    }
    attemptCount++;
    // Continuously returns 401 even after new token
    return createMockResponse({ detail: "Account suspended" }, { status: 401 });
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });

  try {
    await client.get("/user/profile");
    assert.fail("Should have thrown");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 401);
  }

  assert.strictEqual(attemptCount, 2, "Request should be retried exactly once (total 2 attempts)");
  assert.strictEqual(refreshCount, 1, "Refresh should only be invoked once");

  console.log("✓ Test 13 Passed: Original request is retried no more than once");
}

// 14. Concurrent 401 responses share a single refresh operation (Single-flight mutex)
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage);
  tokenMgr.setAccessToken("stale-token");
  tokenMgr.setRefreshToken("shared-refresh-token");

  let refreshCallCount = 0;
  let protectedEndpointCalls = 0;

  const mockFetch = async (url, init) => {
    if (url.includes("/auth/refresh")) {
      refreshCallCount++;
      // Simulate real network delay for token exchange
      await new Promise((resolve) => setTimeout(resolve, 30));
      return createMockResponse({
        access_token: "shiny-new-token",
        token_type: "bearer",
        expires_in: 900,
      });
    }

    protectedEndpointCalls++;
    const auth = new Headers(init.headers).get("Authorization");
    if (auth === "Bearer stale-token") {
      return createMockResponse({ detail: "Token expired" }, { status: 401 });
    }
    if (auth === "Bearer shiny-new-token") {
      return createMockResponse({ success: true, url }, { status: 200 });
    }
    return createMockResponse({ detail: "Unknown" }, { status: 400 });
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });

  // Fire 5 simultaneous requests that all receive 401 initially
  const results = await Promise.all([
    client.get("/api/res1"),
    client.get("/api/res2"),
    client.get("/api/res3"),
    client.get("/api/res4"),
    client.get("/api/res5"),
  ]);

  assert.strictEqual(refreshCallCount, 1, "All 5 concurrent 401s must share exactly ONE refresh call");
  assert.strictEqual(protectedEndpointCalls, 10, "5 initial attempts + 5 retries = 10 total requests");
  assert.strictEqual(results.length, 5);
  results.forEach((r) => assert.strictEqual(r.success, true));

  console.log("✓ Test 14 Passed: Concurrent 401 responses share a single refresh operation");
}

// 15. Guest-mode requests work without authentication
{
  const storage = createMockStorage();
  const tokenMgr = new TokenManager(storage); // No token set

  let headerCaptured = null;
  const mockFetch = async (url, init) => {
    headerCaptured = new Headers(init.headers).get("Authorization");
    return createMockResponse({ mode: "guest", allowed: true });
  };

  const client = new ApiClient({ tokenManager: tokenMgr, fetchFn: mockFetch });

  // Public/guest request
  const guestData = await client.get("/public/catalog", { requiresAuth: false });
  assert.deepStrictEqual(guestData, { mode: "guest", allowed: true });
  assert.strictEqual(headerCaptured, null, "Guest request should not transmit authorization header");

  // Request where requiresAuth is not specified and no token exists
  const unauthData = await client.get("/public/catalog");
  assert.deepStrictEqual(unauthData, { mode: "guest", allowed: true });
  assert.strictEqual(headerCaptured, null, "Request without token should proceed cleanly for public endpoints");

  // Explicit requiresAuth: true without token should throw before network call
  try {
    await client.get("/secret", { requiresAuth: true });
    assert.fail("Should have rejected request");
  } catch (err) {
    assert(err instanceof ApiError);
    assert.strictEqual(err.status, 401);
    assert.strictEqual(err.message, "Authentication required");
  }

  console.log("✓ Test 15 Passed: Guest-mode requests work without authentication");
}

console.log("\nALL 15 API CLIENT & INTERCEPTOR TESTS PASSED CLEANLY!");
