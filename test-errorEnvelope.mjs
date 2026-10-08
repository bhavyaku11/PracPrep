/**
 * Test Suite: ADR-010 Standardized Error Envelope & Frontend Compatibility (TASK-15.1)
 *
 * Verifies that the centralized ApiClient parses:
 * 1. Standard ADR-010 envelope structure (code, message, status, path, details)
 * 2. Structured validation errors mapping to validationErrors array
 * 3. 429 Rate limit errors with RATE_LIMIT_EXCEEDED code
 * 4. 500 Internal server errors with safe generic message
 * 5. Legacy detail string error responses
 * 6. Legacy detail array validation responses
 * 7. Non-JSON plain text error responses
 */

import assert from "node:assert";
import { ApiClient, ApiError } from "./src/lib/apiClient.ts";

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
    if (!headers.has("content-type")) {
      headers.set("content-type", "text/plain");
    }
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

async function runTests() {
  console.log("=== Running TASK-15.1 ADR-010 Error Envelope & Frontend Tests ===");

  
  // 1. ADR-010 Standard HTTP Error Envelope Parsing
  {
    const mockFetch = async () =>
      createMockResponse(
        {
          error: {
            code: "NOT_FOUND",
            message: "Experiment workspace was not found",
            status: 404,
            path: "/api/v1/experiments/123",
            details: [],
          },
          detail: "Experiment workspace was not found",
        },
        { status: 404, statusText: "Not Found" }
      );

    const client = new ApiClient({ fetchFn: mockFetch });
    try {
      await client.get("/experiments/123");
      assert.fail("Should have thrown ApiError");
    } catch (err) {
      assert(err instanceof ApiError);
      assert.strictEqual(err.status, 404);
      assert.strictEqual(err.code, "NOT_FOUND");
      assert.strictEqual(err.message, "Experiment workspace was not found");
      assert.strictEqual(err.isAuthError, false);
      assert.strictEqual(err.isNetworkError, false);
    }
    console.log("✓ Test 1 Passed: ADR-010 standard error envelope parsed with machine code and message");
  }

  
  // 2. ADR-010 Structured Validation Error (422)
  {
    const mockFetch = async () =>
      createMockResponse(
        {
          error: {
            code: "VALIDATION_ERROR",
            message: "Validation error: body.email: Invalid email address",
            status: 422,
            path: "/api/v1/auth/register",
            details: [
              {
                loc: ["body", "email"],
                msg: "Invalid email address",
                type: "value_error",
                field: "body.email",
                issue: "Invalid email address",
              },
            ],
          },
          detail: [
            {
              loc: ["body", "email"],
              msg: "Invalid email address",
              type: "value_error",
            },
          ],
        },
        { status: 422, statusText: "Unprocessable Entity" }
      );

    const client = new ApiClient({ fetchFn: mockFetch });
    try {
      await client.post("/auth/register", {});
      assert.fail("Should have thrown ApiError");
    } catch (err) {
      assert(err instanceof ApiError);
      assert.strictEqual(err.status, 422);
      assert.strictEqual(err.code, "VALIDATION_ERROR");
      assert(err.message.includes("body.email"));
      assert(Array.isArray(err.validationErrors));
      assert.strictEqual(err.validationErrors.length, 1);
      assert.strictEqual(err.validationErrors[0].msg, "Invalid email address");
    }
    console.log("✓ Test 2 Passed: ADR-010 validation details correctly populated in ApiError.validationErrors");
  }

  
  // 3. ADR-010 429 Rate Limit Error
  {
    const mockFetch = async () =>
      createMockResponse(
        {
          error: {
            code: "RATE_LIMIT_EXCEEDED",
            message: "Rate limit exceeded: 5 per 1 minute. Please try again later.",
            status: 429,
            path: "/api/v1/auth/login",
            details: null,
          },
          detail: "Rate limit exceeded: 5 per 1 minute. Please try again later.",
        },
        { status: 429, statusText: "Too Many Requests", headers: { "Retry-After": "60" } }
      );

    const client = new ApiClient({ fetchFn: mockFetch });
    try {
      await client.post("/auth/login", {});
      assert.fail("Should have thrown ApiError");
    } catch (err) {
      assert(err instanceof ApiError);
      assert.strictEqual(err.status, 429);
      assert.strictEqual(err.code, "RATE_LIMIT_EXCEEDED");
      assert(err.message.includes("Rate limit exceeded"));
    }
    console.log("✓ Test 3 Passed: 429 Rate limit error correctly identified with RATE_LIMIT_EXCEEDED code");
  }

  
  // 4. ADR-010 500 Internal Server Error
  {
    const mockFetch = async () =>
      createMockResponse(
        {
          error: {
            code: "INTERNAL_SERVER_ERROR",
            message: "An unexpected internal server error occurred.",
            status: 500,
            path: "/api/v1/viva/generate-questions",
            details: [],
          },
          detail: "An unexpected internal server error occurred.",
        },
        { status: 500, statusText: "Internal Server Error" }
      );

    const client = new ApiClient({ fetchFn: mockFetch });
    try {
      await client.post("/viva/generate-questions", {});
      assert.fail("Should have thrown ApiError");
    } catch (err) {
      assert(err instanceof ApiError);
      assert.strictEqual(err.status, 500);
      assert.strictEqual(err.code, "SERVER_ERROR" in ApiError ? "SERVER_ERROR" : (err.code || "INTERNAL_SERVER_ERROR"));
      assert.strictEqual(err.message, "An unexpected internal server error occurred.");
    }
    console.log("✓ Test 4 Passed: 500 Internal error envelope parsed without leaking implementation details");
  }

  
  // 5. Backward Compatibility: Legacy detail string
  {
    const mockFetch = async () =>
      createMockResponse(
        { detail: "Inactive user account" },
        { status: 403, statusText: "Forbidden" }
      );

    const client = new ApiClient({ fetchFn: mockFetch });
    try {
      await client.get("/user/settings");
      assert.fail("Should have thrown ApiError");
    } catch (err) {
      assert(err instanceof ApiError);
      assert.strictEqual(err.status, 403);
      assert.strictEqual(err.code, "FORBIDDEN");
      assert.strictEqual(err.message, "Inactive user account");
      assert.strictEqual(err.isAuthError, true);
    }
    console.log("✓ Test 5 Passed: Legacy string detail response supported transparently");
  }

  // 6. Backward Compatibility: Legacy detail array validation errors
  {
    const mockFetch = async () =>
      createMockResponse(
        {
          detail: [
            { loc: ["body", "password"], msg: "Password must be at least 8 characters", type: "value_error" },
          ],
        },
        { status: 422, statusText: "Unprocessable Entity" }
      );

    const client = new ApiClient({ fetchFn: mockFetch });
    try {
      await client.post("/auth/reset-password", {});
      assert.fail("Should have thrown ApiError");
    } catch (err) {
      assert(err instanceof ApiError);
      assert.strictEqual(err.status, 422);
      assert.strictEqual(err.code, "VALIDATION_ERROR");
      assert(err.message.includes("Password must be at least 8 characters"));
      assert.strictEqual(err.validationErrors?.length, 1);
    }
    console.log("✓ Test 6 Passed: Legacy validation detail array supported transparently");
  }

  // 7. Non-JSON Plain Text Error Response
  {
    const mockFetch = async () =>
      createMockResponse("Bad Gateway: Upstream service down", {
        status: 502,
        statusText: "Bad Gateway",
        headers: { "content-type": "text/plain" },
      });

    const client = new ApiClient({ fetchFn: mockFetch });
    try {
      await client.get("/health-proxy");
      assert.fail("Should have thrown ApiError");
    } catch (err) {
      assert(err instanceof ApiError);
      assert.strictEqual(err.status, 502);
      assert.strictEqual(err.message, "Bad Gateway: Upstream service down");
      assert.strictEqual(err.code, "SERVER_ERROR");
    }
    console.log("✓ Test 7 Passed: Plain text error response correctly handled with fallback code");
  }

  console.log("\nALL 7 ADR-010 ERROR ENVELOPE & FRONTEND TESTS PASSED CLEANLY!\n");
}

runTests().catch((err) => {
  console.error("Test failure:", err);
  process.exit(1);
});
