# TASK-15.1 Security Hardening & Error Envelope Report

**Project:** PracPrep — From Lab Manual to Lab-Ready  
**Task:** TASK-15.1: Rate Limiting, Security Headers & Standardized Error Envelope  
**Date:** 2026-10-04  
**Status:** Completed & Verified  

---

## 1. Executive Summary

TASK-15.1 hardens PracPrep's FastAPI backend against brute-force attacks, clickjacking, MIME-sniffing, injection vectors, and information disclosure while delivering a standardized, machine-readable error response contract (ADR-010). The solution preserves 100% backward compatibility with existing frontend error handling and test suites.

Key deliverables completed:
1. **In-Memory Rate Limiting:** Centralized `slowapi` limiter protecting authentication (`/register`, `/login`, `/refresh`), viva AI endpoints (`/generate-questions`, `/evaluate-answer`), and lab manual uploads (`/upload-manual`).
2. **Security Headers Middleware:** Pure ASGI middleware injecting `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Content-Security-Policy`, and environment-aware `Strict-Transport-Security` (HTTPS production only).
3. **Production Secret Startup Guard:** Boot-time validator rejecting missing, empty, short (< 32 characters), or known placeholder secrets when `ENVIRONMENT=production`, preventing credential leakage in logs or exceptions.
4. **Standardized Error Envelope (ADR-010):** Centralized exception handlers for `StarletteHTTPException`, `RequestValidationError`, `RateLimitExceeded`, and unhandled `Exception`, providing a structured machine-readable error envelope with top-level `detail` backward compatibility.
5. **Frontend Error Client (`apiClient.ts`):** Enhanced error parser extracting `code`, `message`, `status`, `path`, and structured field validation items (`validationErrors`), handling HTTP 429 rate limits, and falling back gracefully to legacy response formats.

---

## 2. Rate-Limit Configuration & Endpoint Thresholds

### Implementation Architecture
- **Engine:** `slowapi` with in-memory storage (`limits.storage.MemoryStorage`).
- **Limiter Factory:** `app/core/limiter.py` exports a singleton `limiter` instance configured with `headers_enabled=False` to avoid interfering with Pydantic route response models.
- **Exception Handler:** Registered via `app/core/errors.py` on `RateLimitExceeded`, returning HTTP 429 Too Many Requests with a `Retry-After: 60` response header and ADR-010 error envelope.

### Configured Thresholds
Configurable via environment variables with safe, student-friendly defaults in `app/core/config.py`:
- `RATE_LIMITING_ENABLED`: `True`
- `RATE_LIMIT_AUTH_DEFAULT` (`5/minute`): Applied to:
  - `POST /api/v1/auth/register`
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/refresh`
- `RATE_LIMIT_AI_DEFAULT` (`10/minute`): Applied to:
  - `POST /api/v1/viva/generate-questions`
  - `POST /api/v1/viva/evaluate-answer`
- `RATE_LIMIT_UPLOAD_DEFAULT` (`5/minute`): Applied to:
  - `POST /api/v1/documents/upload-manual`
- `RATE_LIMIT_DEFAULT` (`60/minute`): Default ceiling for general endpoints.

### Rationale
- **Auth (5/min):** Thwarts automated credential stuffing and dictionary attacks while permitting legitimate students to rectify typos or refresh expired tokens.
- **AI Endpoints (10/min):** Protects downstream Gemini/LLM quotas and prevents runaway cost escalation while allowing student viva preparation without interruption.
- **Document Upload (5/min):** Guards disk space and CPU during PDF/DOCX parsing and OCR processing.

---

## 3. Client Identification Strategy & Limitations

### Strategy
Client identification is resolved centrally via `get_client_ip(request: Request)` in `app/core/limiter.py`:
1. **Environment-Gated Test Isolation:** Inspects `X-Test-Client-Id` header **only** when `ENVIRONMENT` is explicitly `"testing"` or `"test"`. In this mode, distinct test callers can run isolated scenarios without cross-test rate-limit contamination.
2. **Development & Production Enforcement:** In `development` and `production` environments, `X-Test-Client-Id` is strictly ignored. The client identity is derived directly from the socket connection host `request.client.host` (falling back to `"127.0.0.1"` if `request.client` is unavailable).
3. **Untrusted Forwarding Headers Defense:** Does not trust raw client-supplied `X-Forwarded-For`, `X-Real-IP`, or other forwarding headers to prevent IP spoofing attacks and rate-limit bypasses until a trusted reverse proxy configuration with CIDR filtering is formally introduced.

### Limitations
- **In-Memory & Process-Local:** Counters reside in Python process memory. In a multi-worker ASGI deployment (e.g. Uvicorn with multiple workers) or horizontal container replicas, counters are not synchronized across workers.
- **Deployment Recommendation:** For the current MVP, run a single ASGI worker process. For multi-replica deployments in future milestones, replace in-memory storage with a shared Redis instance.

---

## 4. Security Headers Middleware

Implemented via `SecurityHeadersMiddleware` in `app/core/middleware.py`:

| Header | Value | Purpose |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing attacks. |
| `X-Frame-Options` | `DENY` | Defends against clickjacking; disallows rendering in iframes. |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Protects privacy while preserving origin on secure requests. |
| `Permissions-Policy` | `accelerometer=(), camera=(), geolocation=(), gyroscope=(), magnetometer=(), microphone=(), payment=(), usb=()` | Disables unnecessary browser APIs. |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' http: https: ws: wss:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` | Restricts script, frame, and connection origins; permits inline styles used by Tailwind CSS and UI components. |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Enforces HTTPS; enabled **only** when `ENVIRONMENT=production` AND request scheme is HTTPS. |

### Environment Behavior
- In local development (`ENVIRONMENT=development`) or over plain HTTP, HSTS is omitted to prevent locking developers out of `http://localhost`.
- Headers are attached at the ASGI response start, ensuring consistent application to successful responses (200), client errors (401, 404, 422, 429), and internal server crashes (500).

---

## 5. Production SECRET_KEY Guard

Implemented via `validate_production_secret_guard(settings)` in `app/core/config.py` and invoked on application startup in `app/main.py:create_app()`:

### Validation Rules in Production (`ENVIRONMENT=production`):
1. **Length Requirement:** Secret must be at least 32 characters long.
2. **Placeholder Rejection:** Explicitly rejects known placeholders, including `insecure-dev-secret-key-change-in-production-min32chars`, `changeme`, `secret`, `placeholder`, `password`, `adminadmin`, and `default-secret`.
3. **Secret Masking:** The secret value itself is never printed or included in exception messages, logs, or HTTP responses.
4. **Development Preservation:** When `ENVIRONMENT=development` (or `testing`), default development secrets are accepted without error, preserving rapid local development.
5. **Key Alias Support:** Accepts either `SECRET_KEY` or `JWT_SECRET_KEY` environment variables via Pydantic `AliasChoices`.

---

## 6. ADR-010 Standardized Error Envelope Contract

Centralized exception handlers in `app/core/errors.py` standardize error responses across all endpoints:

```json
{
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable explanation.",
    "status": 400,
    "path": "/api/v1/...",
    "details": []
  },
  "detail": "Human-readable explanation or legacy validation error list"
}
```

### Standard Error Codes:
- `400`: `BAD_REQUEST`
- `401`: `UNAUTHORIZED`
- `403`: `FORBIDDEN`
- `404`: `NOT_FOUND`
- `405`: `METHOD_NOT_ALLOWED`
- `409`: `CONFLICT`
- `422`: `VALIDATION_ERROR` (with structured field details preserving `loc`, `msg`, `type`, `field`, `issue`)
- `429`: `RATE_LIMIT_EXCEEDED` (with `Retry-After: 60` response header)
- `500`: `INTERNAL_SERVER_ERROR` (generic message masking internal exceptions, SQL statements, stack traces, and filesystem paths)

### Backward Compatibility
By emitting both the new ADR-010 `error` object and the legacy top-level `detail` attribute, all existing frontend services, components, and tests continue functioning without breaking changes.

---

## 7. Frontend Compatibility Changes

Updated `src/lib/apiClient.ts` (`src/services/apiClient.ts` re-exports):
1. **Prioritized ADR-010 Envelope Parsing:** `parseErrorResponse` inspects `parsed.error`, extracting `code`, `message`, `status`, `path`, and structured `details`.
2. **Validation Errors Normalization:** When `parsed.error.details` contains field validation items, they are populated into `ApiError.validationErrors` and formatted cleanly into `ApiError.message` for UI alerts and form field highlights.
3. **Rate Limit Handling:** Explicitly handles HTTP 429 status code, setting `code: 'RATE_LIMIT_EXCEEDED'`.
4. **Fallback Preservation:** Fully supports legacy `{ detail: "..." }` strings, `{ detail: [...] }` arrays, and plain text error responses.
5. **Types Update:** Added `ApiErrorEnvelope` and updated `ApiErrorDetail` in `src/types/api.ts`.

---

## 8. Test Suites Added or Updated

### Backend Tests Added:
1. `backend/tests/test_rate_limiting.py` (4 tests):
   - `test_rate_limiting_register_threshold_and_429`: Threshold enforcement, 429 breach, Retry-After header, and ADR-010 envelope.
   - `test_rate_limiting_client_isolation`: Independent rate limit tracking across different `X-Test-Client-Id` values.
   - `test_rate_limiting_reset_clears_counters`: Validates `limiter.reset()` functionality.
   - `test_rate_limiting_login_and_refresh_limits`: Validates protection on login and token refresh.
2. `backend/tests/test_security_headers.py` (5 tests):
   - `test_security_headers_present_on_200_ok`: Validates nosniff, DENY, referrer policy, CSP, Permissions-Policy, and absence of HSTS on HTTP dev.
   - `test_security_headers_present_on_404_not_found`: Validates headers on 404.
   - `test_security_headers_present_on_401_unauthorized`: Validates headers on 401.
   - `test_security_headers_present_on_422_validation_error`: Validates headers on 422.
   - `test_hsts_behavior_production_https_vs_http`: Validates HSTS on HTTPS in production, and omission on plain HTTP.
3. `backend/tests/test_production_secrets.py` (10 tests):
   - Development mode default secret acceptance.
   - Production mode strong secret acceptance (>= 32 chars).
   - Production mode default secret rejection.
   - Production mode common placeholder rejection (changeme, secret, placeholder, password, admin).
   - Production mode short secret rejection (< 32 chars).
   - Startup failure validation without secret leakage.
4. `backend/tests/test_error_envelope.py` (3 tests):
   - `test_http_exception_envelope_format`: Validates 404 envelope structure.
   - `test_validation_error_envelope_format`: Validates 422 validation structure with field paths.
   - `test_unhandled_exception_does_not_leak_stack_trace_or_internals`: Validates 500 error masking and prevents sensitive leakage.

### Backend Tests Updated:
- `backend/tests/test_experiment_routes.py`: Updated 12 assertions from exact dictionary equality `{"detail": ...}` to `response.json()["detail"] == ...` to be consistent with the rest of the test suite and ADR-010 dual-compatibility envelope.

### Frontend Tests Added:
- `test-errorEnvelope.mjs` (7 tests):
   - Test 1: ADR-010 standard error envelope parsed with machine code and message.
   - Test 2: ADR-010 validation details correctly populated in `ApiError.validationErrors`.
   - Test 3: 429 Rate limit error correctly identified with `RATE_LIMIT_EXCEEDED` code.
   - Test 4: 500 Internal error envelope parsed without leaking implementation details.
   - Test 5: Legacy string detail response supported transparently.
   - Test 6: Legacy validation detail array supported transparently.
   - Test 7: Plain text error response correctly handled with fallback code.

---

## 9. Verification & Execution Results

### Backend Test Suite (Pytest)
```bash
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests
```
**Result:** `743 passed, 152 warnings in 9.50s` (100% PASS)

### Frontend Test Suite (Node / Vitest)
```bash
npm test
```
**Result:** `11 test files executed, 100% PASS` (including all 15 API client tests, 7 error envelope tests, 16 experiment storage tests, 16 viva storage tests, 16 viva AI provider tests, 26 settings storage tests, 6 integration gates, 12 section parser tests, 9 migration tests, and 4 analytics tests).

### Frontend Production Build
```bash
npm run build
```
**Result:** `tsc -b && vite build` succeeded in 472ms with 0 errors.

### Frontend Linting
```bash
npm run lint
```
**Result:** `oxlint` completed with 0 errors.

### Backend Syntax & Bytecode Compilation
```bash
./backend/.venv/bin/python -m compileall backend/app backend/tests
```
**Result:** All modules compiled successfully with 0 syntax or import errors.

---

## 10. Known Limitations & Follow-Up Recommendations

1. **Distributed Rate Limiting:** The in-memory limiter is suitable for the single-worker MVP deployment. When moving to multi-container or distributed worker setups (Phase 16+), migrate the slowapi backend to Redis.
2. **Reverse Proxy Trust:** When deploying behind an AWS ALB, Nginx, or Cloudflare reverse proxy, configure FastAPI's `ProxyHeadersMiddleware` with trusted proxy IPs so that `request.client.host` reflects the real client IP.
3. **CSP Nonces:** For production environments with strict Content Security Policies, consider integrating dynamic CSP script-hashes or nonces if external third-party widgets are added.

---

## 11. Remediation — Secure Rate-Limit Client Identification

### Original Client-Identity Vulnerability
During initial implementation of TASK-15.1, `get_client_ip(request: Request)` inspected `request.headers.get("X-Test-Client-Id")` unconditionally before falling back to `request.client.host`. This introduced a security vulnerability: in development or production environments, a malicious caller could rotate arbitrary values in `X-Test-Client-Id` on each request to generate new client identities, completely bypassing rate limits on authentication, AI viva endpoints, and document upload routes.

### Environment-Specific Correction
The client identification logic was remediated in `backend/app/core/limiter.py` to be strictly environment-controlled:
1. **Application Environment Access:** `create_app()` attaches the active `app_settings` to `app.state.settings`. In `get_client_ip()`, the runtime environment is checked via `request.app.state.settings.ENVIRONMENT` (falling back to `get_settings().ENVIRONMENT` if the app state is not present).
2. **Testing Mode Gate:** The `X-Test-Client-Id` header is honored **only and exclusively** when `ENVIRONMENT.lower() in ("testing", "test")`. This preserves test isolation and parallel test execution without production exposure.
3. **Production & Development Strictness:** When running under `production` or `development`, `X-Test-Client-Id` is completely ignored.
4. **Configuration Safety:** The test behavior is dictated entirely by server-side configuration, not by any request header, query parameter, or client-controlled value. No bypass flags exist in production. Sensitive request data is never logged.

### Behavior of Untrusted Forwarding Headers
1. Client-supplied forwarding headers, including `X-Forwarded-For`, `X-Real-IP`, `CF-Connecting-IP`, and `True-Client-IP`, are intentionally not trusted by default.
2. Without a verified upstream proxy configuration, trusting these headers would allow any client to spoof arbitrary IPs and evade rate limiting.
3. The rate limiter strictly utilizes `request.client.host` (the direct socket connection IP). If `request.client` is unavailable (such as in certain mock ASGI callers), it falls back safely to `"127.0.0.1"`.

### Regression Tests Added
The test suite in `backend/tests/test_rate_limiting.py` was extended to provide unit- and integration-level proof across all environments:
1. **Unit Tests:**
   - `test_get_client_ip_honors_test_header_only_in_test_environment`: Verifies that `X-Test-Client-Id` provides test isolation in `"testing"` mode.
   - `test_get_client_ip_ignores_test_header_in_development`: Verifies that development mode ignores `X-Test-Client-Id` and uses socket client host.
   - `test_get_client_ip_ignores_test_header_and_forwarded_headers_in_production`: Verifies that production mode ignores `X-Test-Client-Id`, `X-Forwarded-For`, and `X-Real-IP`.
   - `test_get_client_ip_fallback_when_client_missing`: Verifies fallback to `"127.0.0.1"` when `request.client` is `None`.
2. **Integration Tests (FastAPI & SlowAPI):**
   - `test_rate_limiting_register_threshold_and_429`: Threshold enforcement (5/min on `/api/v1/auth/register`), 429 response, Retry-After header, and ADR-010 envelope.
   - `test_rate_limiting_client_isolation_in_testing_environment`: Validates that distinct `X-Test-Client-Id` values have separate rate limit buckets when `ENVIRONMENT="testing"`.
   - `test_rate_limiting_production_bypass_prevention` (**Mandatory Regression Test**): Proves that in `production` mode, sending 6 consecutive requests with 6 distinct `X-Test-Client-Id` values (`"attacker-id-1"` through `"attacker-id-6"`) from the same client IP hits the rate limit on request 6 (HTTP 429).
   - `test_rate_limiting_development_mode_ignores_test_header`: Proves that development mode similarly cannot be bypassed via rotating `X-Test-Client-Id` headers.
   - `test_rate_limiting_untrusted_forwarding_headers_cannot_bypass`: Proves that rotating `X-Forwarded-For` and `X-Real-IP` headers cannot circumvent rate limits in production.
   - `test_rate_limiting_reset_clears_counters`: Validates `limiter.reset()` functionality.
   - `test_rate_limiting_login_and_refresh_limits`: Validates limits across `/login` and `/refresh` endpoints.

### Exact Verification Results
- **Focused Rate Limiting Suite:**
  `PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/test_rate_limiting.py -v`
  **Result:** 11/11 passed (100% PASS in 2.07s)
- **Full Backend Regression Suite:**
  `PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests`
  **Result:** 750/750 passed (100% PASS in 9.30s)
- **Backend Bytecode Compilation:**
  `./backend/.venv/bin/python -m compileall backend/app backend/tests`
  **Result:** Clean compilation with 0 syntax or import errors.
- **Frontend Test Suite:**
  `npm test`
  **Result:** 11 test suites passed cleanly (100% PASS).
- **Frontend Linter:**
  `npm run lint`
  **Result:** `oxlint` reported 0 errors on 113 files.
- **Frontend Production Build:**
  `npm run build`
  **Result:** `tsc -b && vite build` succeeded in 522ms with 0 errors.
- **FastAPI Startup & Secret Guard:**
  Verified development mode startup and verified production mode startup rejects weak/default secrets without credential leakage.

