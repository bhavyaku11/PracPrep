# PracPrep — Architecture Decision Records (ADRs)

**Project:** PracPrep — From Lab Manual to Lab-Ready  
**Document Version:** 1.0.0  
**Date:** 2026-10-04  
**Author:** Senior Software Architect, Backend Engineer & Technical Lead  
**Status:** Approved Architectural Baseline  

---

## Index of Architectural Decisions

- [ADR-001: Backend Framework & Language Selection](#adr-001-backend-framework--language-selection)
- [ADR-002: Modular Monolith vs. Microservices Architecture](#adr-002-modular-monolith-vs-microservices-architecture)
- [ADR-003: Relational Database & Asynchronous ORM Stack](#adr-003-relational-database--asynchronous-orm-stack)
- [ADR-004: Primary Identifier Generation Strategy](#adr-004-primary-identifier-generation-strategy)
- [ADR-005: Authentication Strategy & Token Lifecycle](#adr-005-authentication-strategy--token-lifecycle)
- [ADR-006: Dual-Mode Storage Architecture for Guest Mode](#adr-006-dual-mode-storage-architecture-for-guest-mode)
- [ADR-007: Pluggable AI Provider Adapter & Circuit-Breaker Fallback](#adr-007-pluggable-ai-provider-adapter--circuit-breaker-fallback)
- [ADR-008: Staged Lab Manual Document Processing Pipeline](#adr-008-staged-lab-manual-document-processing-pipeline)
- [ADR-009: Execution Location for Progress Analytics](#adr-009-execution-location-for-progress-analytics)
- [ADR-010: Standardized JSON Error Response Envelope](#adr-010-standardized-json-error-response-envelope)

---

### ADR-001: Backend Framework & Language Selection
- **Status:** Accepted
- **Context:** PracPrep requires a high-performance backend capable of handling standard CRUD data persistence, asynchronous LLM API calls, binary document uploads, and OCR text processing. The frontend is built in React 19/TypeScript.
- **Decision:** Build the backend using **Python 3.12+** and **FastAPI**.
- **Consequences:**
  - *Positive:* Direct access to the rich Python AI ecosystem (Google GenAI, OpenAI, LangChain/LlamaIndex primitives) and mature document parsing libraries (`pypdf`, `python-docx`, `pytesseract`); high ASGI throughput; native async/await; automatic OpenAPI documentation.
  - *Negative:* Language boundary between TypeScript frontend and Python backend; requires type parity maintenance between TypeScript models and Pydantic schemas.
  - *Neutral:* Standardized tooling using Poetry/Pip and Pytest.

---

### ADR-002: Modular Monolith vs. Microservices Architecture
- **Status:** Accepted
- **Context:** Early architectural planning must balance scalability with operational simplicity, ease of deployment, and developer velocity for an engineering student preparation platform.
- **Decision:** Adopt a **Modular Monolith** architecture within a single FastAPI codebase. Domain boundaries (`auth`, `experiments`, `viva`, `documents`, `users`) will be strictly separated at the folder, service, and schema levels.
- **Consequences:**
  - *Positive:* Single repository, unified database migrations, zero network latency between modules, simplified local Docker Compose development, and atomic transactions.
  - *Negative:* Scaled as a single deployment unit rather than independently scaling CPU-intensive document processing.
  - *Neutral:* Can be easily split into separate services in the future if document processing or AI evaluation demands dedicated worker nodes.

---

### ADR-003: Relational Database & Asynchronous ORM Stack
- **Status:** Accepted
- **Context:** PracPrep entities (Users, Experiments, Viva Sessions, Checklists) have strict relational hierarchies, foreign key dependencies, and cascading deletion requirements. At the same time, preparation checklists, question rubrics, and topic analytics benefit from semi-structured JSON storage.
- **Decision:** Use **PostgreSQL 16+** with **SQLAlchemy 2.0 (Async)** via `asyncpg` and **Alembic** for schema migrations. Semi-structured attributes (`weak_topics`, `key_points`, `preparation_checklist`) will use PostgreSQL native `JSONB`.
- **Consequences:**
  - *Positive:* ACID compliance; strict multi-tenant foreign keys; non-blocking database queries via async IO; JSONB indexing capabilities; rock-solid migration history.
  - *Negative:* Slightly higher connection management complexity compared to synchronous ORMs.
  - *Neutral:* Standard relational hosting available on all cloud providers (AWS RDS, Supabase, Neon).

---

### ADR-004: Primary Identifier Generation Strategy
- **Status:** Accepted
- **Context:** The existing frontend generates identifiers client-side using `exp-${Date.now()}` and `viva-${Date.now()}`. These IDs are collision-prone, leak creation timestamps, and lack cryptographically secure uniqueness.
- **Decision:** Transition to **server-generated UUID v4** identifiers across all database tables and API contracts.
- **Consequences:**
  - *Positive:* Guaranteed uniqueness across concurrent creations and distributed systems; cannot be guessed or traversed sequentially; standard in modern REST APIs.
  - *Negative:* Slightly larger index footprint compared to sequential 64-bit integers.
  - *Neutral:* Frontend interfaces already define `id: string`, ensuring zero breaking changes to component types.

---

### ADR-005: Authentication Strategy & Token Lifecycle
- **Status:** Accepted
- **Context:** The application currently simulates authentication with a 1-second `setTimeout` and writes unverified user objects to `localStorage`. A production-ready identity layer is required.
- **Decision:** Implement stateless **JWT Access Tokens (15-minute expiration)** paired with long-lived **Refresh Tokens (7-day expiration)**. Passwords will be hashed using **Argon2id**.
- **Consequences:**
  - *Positive:* Stateless verification eliminates server session lookups for high-throughput endpoints; short access token lifespan minimizes risk of token theft; Argon2id provides superior resistance to GPU/ASIC attacks compared to legacy bcrypt.
  - *Negative:* Requires token refresh handling logic in the frontend `apiClient.ts`.
  - *Neutral:* Tokens transmitted via standard `Authorization: Bearer <token>` headers.

---

### ADR-006: Dual-Mode Storage Architecture for Guest Mode
- **Status:** Accepted
- **Context:** PracPrep provides an instant, zero-friction "Guest Access" mode at `/guest`. Requiring server authentication before students can test the platform would introduce significant onboarding friction.
- **Decision:** Implement the **Dual-Mode Storage Facade Pattern** in frontend services (`experimentStorage.ts`, `vivaStorage.ts`). When `user.isGuest` is true, operations execute against browser `localStorage`; when authenticated, operations execute against the `/api/v1` REST backend. A one-click batch migration endpoint (`POST /api/v1/users/me/migrate-guest-data`) will allow students to import guest data upon creating an account.
- **Consequences:**
  - *Positive:* Preserves the instant, offline guest experience; zero server load for casual browsers; clean migration path to registered accounts.
  - *Negative:* Frontend services must maintain dual execution paths.
  - *Neutral:* Guest data remains strictly browser-local until explicit migration.

---

### ADR-007: Pluggable AI Provider Adapter & Circuit-Breaker Fallback
- **Status:** Accepted
- **Context:** AI viva question generation and answer evaluation are core product differentiators. However, external LLM APIs (Google Gemini, OpenAI) may experience rate limits, latency spikes, or temporary outages.
- **Decision:** Implement an **Adapter Pattern** with a `BaseAIProvider` interface. The primary provider (Google Gemini) will be wrapped by an `AIProviderFactory` with timeout detection (`>= 4000ms`) and automatic fallback to the deterministic `DemonstrationVivaProvider` engine.
- **Consequences:**
  - *Positive:* 100% uptime for viva practice sessions; seamless offline or low-resource testing; provider portability without touching business logic.
  - *Negative:* Heuristic fallback produces lower quality feedback than live LLMs, though adequate for uninterrupted study.
  - *Neutral:* API responses include `providerMode: "demonstration" | "ai-live"` for full transparency.

---

### ADR-008: Staged Lab Manual Document Processing Pipeline
- **Status:** Accepted
- **Context:** Students upload laboratory manuals as PDF or DOCX files. Some are digital vector PDFs with selectable text, while others are scanned physical booklets requiring Optical Character Recognition (OCR).
- **Decision:** Build a **staged document extraction pipeline**:
  1. Fast digital extraction via `pypdf` / `pdfplumber` / `python-docx`.
  2. OCR fallback via `pytesseract` if extracted text length is under 100 characters.
  3. LLM-assisted section parser returning a structured JSON draft adhering to Pydantic schemas.
  4. Mandatory student review and edit modal in the frontend before final persistence.
- **Consequences:**
  - *Positive:* Handles both digital and scanned manuals; ensures high extraction accuracy; student review step prevents hallucinations or missed apparatus items from corrupting the workspace.
  - *Negative:* OCR requires system-level Tesseract binaries in Docker container; LLM parsing adds 5–10s processing latency.
  - *Neutral:* Upload size capped at 25MB.

---

### ADR-009: Execution Location for Progress Analytics
- **Status:** Accepted
- **Context:** The Progress & Revision Center calculates readiness scores, 30-day performance trends, topic mastery breakdowns, and revision action items across a student's experiments and viva sessions.
- **Decision:** Keep progress analytical computations **client-side** in `src/utils/progressAnalytics.ts` initially, consuming raw experiment and session arrays returned by the backend API.
- **Consequences:**
  - *Positive:* Zero server CPU overhead for graph rendering; instantaneous filter toggling (All vs 30d vs 7d); reuses thoroughly tested existing pure TypeScript functions.
  - *Negative:* Client must fetch all experiment and viva session records for the user.
  - *Neutral:* Can be supplemented with server-side aggregation endpoints in the future if session counts exceed thousands per user.

---

### ADR-010: Standardized JSON Error Response Envelope
- **Status:** Accepted (Implemented in TASK-15.1)
- **Context:** Inconsistent API error shapes across endpoints complicate client-side error handling, form field validation feedback, rate limit retries, and security auditing. Default FastAPI and Starlette error responses leak framework internals or vary between validation errors and HTTP exceptions.
- **Decision:** Enforce a uniform JSON error envelope across all `/api/v1` and core endpoints via centralized FastAPI/Starlette exception handlers (`app.core.errors.register_error_handlers`), preserving dual-compatibility with existing clients:
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
- **Error Codes:**
  - `400`: `BAD_REQUEST`
  - `401`: `UNAUTHORIZED`
  - `403`: `FORBIDDEN`
  - `404`: `NOT_FOUND`
  - `405`: `METHOD_NOT_ALLOWED`
  - `409`: `CONFLICT`
  - `422`: `VALIDATION_ERROR` (with structured field details preserving `loc`, `msg`, `type`, `field`, `issue`)
  - `429`: `RATE_LIMIT_EXCEEDED` (with `Retry-After` response header)
  - `500`: `INTERNAL_SERVER_ERROR` (generic message masking internal exceptions, SQL, stack traces, and filesystem paths)
- **Consequences:**
  - *Positive:* Fully predictable frontend error parsing; centralized form field mapping; zero stack trace leakage on unhandled server crashes; rate limit retry guidance; complete backward compatibility for legacy `detail` consumers.
  - *Negative:* Custom exception handlers must be registered for `StarletteHTTPException`, `RequestValidationError`, `RateLimitExceeded`, and `Exception`.
  - *Neutral:* Dual-compatibility envelope satisfies both strict ADR-010 parsers (`response.error`) and legacy clients (`response.detail`).
