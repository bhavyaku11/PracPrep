# Production Readiness & Logging Architecture

**Document Version:** 1.0.0  
**Status:** Approved / Production-Ready  
**Task Reference:** TASK-15.4 (Production Readiness & Logging)  
**Parent Architecture:** [Backend Architecture Reference](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/docs/architecture/backend-task-tracker.md)

---

## 1. Logging Architecture

PracPrep implements a centralized, zero-external-dependency logging subsystem built on Python's standard `logging` library. The system lives in [`backend/app/core/logging.py`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/backend/app/core/logging.py) and is initialized idempotently during FastAPI application startup within the `lifespan` context manager.

```
                              [Incoming HTTP Request]
                                         │
                                         ▼
                        ┌─────────────────────────────────┐
                        │   RequestCorrelationMiddleware   │
                        │ ─────────────────────────────── │
                        │  - Extract/Generate Request ID  │
                        │  - Set ContextVar context       │
                        │  - Record start_time            │
                        └────────────────┬────────────────┘
                                         │
                                         ▼
                         ┌──────────────────────────────┐
                         │   FastAPI Route / Handler    │
                         │ ──────────────────────────── │
                         │  - App logging via standard  │
                         │    logging.getLogger(...)    │
                         └───────────────┬──────────────┘
                                         │
                                         ▼
                         ┌──────────────────────────────┐
                         │     CorrelationIdFilter      │
                         │ ──────────────────────────── │
                         │  - Attach request_id to      │
                         │    LogRecord                 │
                         │  - Sanitize log messages     │
                         └───────────────┬──────────────┘
                                         │
                                         ▼
                     ┌──────────────────────────────────────┐
                     │              Formatter               │
                     │ ──────────────────────────────────── │
                     │  - JSONLogFormatter (Production)     │
                     │  - DevelopmentLogFormatter (Dev)     │
                     └───────────────────┬──────────────────┘
                                         │
                                         ▼
                            [Standard Output / stderr]
```

### Core Design Principles:
1. **Zero External Logging Frameworks:** Relies on standard library `logging` and standard JSON serialization.
2. **Context Isolation:** Uses Python's `contextvars.ContextVar` to ensure concurrent asynchronous coroutines and tasks never leak correlation IDs into each other.
3. **Idempotent Initialization:** `setup_logging()` removes existing handlers on the root logger before configuring the unified handler, preventing duplicate log records on repeated application creation.
4. **Resilient Error Logging:** Logging failures never break HTTP request execution.
5. **Log Noise Suppression:** Successful periodic health checks (HTTP 2xx to `/health`, `/health/live`, `/health/ready`) are logged only at `DEBUG` level, eliminating container orchestration log spam while preserving all warnings and errors.

---

## 2. Development vs. Production Log Formats

Log formatting is determined by `LOG_FORMAT` in conjunction with `ENVIRONMENT`:

| Mode | Format Specifier | Output Appearance | Description |
|---|---|---|---|
| **Development** | `LOG_FORMAT=text` or `LOG_FORMAT=auto` with `ENVIRONMENT=development` | `2026-10-04 18:39:52.728 [INFO] [app.main] [req:fd4eac169ef3] Application startup initialized...` | High-readability colored/aligned console logs with truncated request IDs. |
| **Production** | `LOG_FORMAT=json` or `LOG_FORMAT=auto` with `ENVIRONMENT=production` | `{"timestamp": "2026-10-04T18:39:52.728205+00:00", "level": "INFO", "logger": "app.main", "message": "...", "request_id": "fd4eac169ef3"}` | Valid single-line JSON objects ready for Fluentd, Logstash, Datadog, AWS CloudWatch, or Grafana Loki. |

### Development Format Example:
```text
2026-10-04 18:40:08.215 [INFO] [app.access] [req:test-custom-correlation-id-1234] HTTP GET /api/v1/auth/login 405 in 14.96ms
```

### Production JSON Format Example:
```json
{"timestamp": "2026-10-04T18:40:08.215500+00:00", "level": "INFO", "logger": "app.access", "message": "HTTP GET /api/v1/auth/login 405 in 14.96ms", "request_id": "test-custom-correlation-id-1234", "method": "GET", "path": "/api/v1/auth/login", "status_code": 405, "duration_ms": 14.96}
```

When an unhandled exception occurs, standard tracebacks are formatted into the `exception` JSON property:
```json
{"timestamp": "2026-10-04T18:41:00.123456+00:00", "level": "ERROR", "logger": "app.middleware", "message": "Unhandled exception processing request GET /api/v1/resource", "request_id": "9a8b7c6d5e4f", "exception": "Traceback (most recent call last):\n  ..."}
```

---

## 3. Log Levels and Environment Variables

The logging system is configured via environment variables read by [`app/core/config.py`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/backend/app/core/config.py):

| Environment Variable | Allowed Values | Default | Description |
|---|---|---|---|
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` | Root logging threshold. In production, `INFO` captures lifecycle and access events; `DEBUG` is reserved for troubleshooting. |
| `LOG_FORMAT` | `auto`, `json`, `text` | `auto` | When `auto`, evaluates to `json` if `ENVIRONMENT=production`, and `text` otherwise. |
| `DATABASE_CONNECT_TIMEOUT_SECONDS` | Float > 0 | `2.0` | Maximum seconds allowed for readiness probe database ping (`SELECT 1`) before timing out and returning 503. |

---

## 4. Request Correlation ID Behavior

Every HTTP request passing through the FastAPI gateway is assigned a unique correlation ID handled by [`RequestCorrelationMiddleware`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/backend/app/core/middleware.py):

1. **Header Identification:** Checks the incoming HTTP header `X-Request-ID`.
2. **Format Validation:** 
   - A valid incoming ID consists of 1 to 64 ASCII alphanumeric characters or hyphens (`^[a-zA-Z0-9_\-]{1,64}$`).
   - Any ID with newlines, spaces, control characters, or non-whitelisted symbols is rejected to prevent log injection (CRLF attacks).
3. **Generation Fallback:** If absent or invalid, the middleware generates a new 32-character hexadecimal UUID (`uuid.uuid4().hex`).
4. **ContextVar Storage:** The validated ID is assigned to a coroutine-local `ContextVar` (`request_id_ctx_var`). Concurrency tests demonstrate that simultaneous asynchronous requests in separate tasks maintain total isolation.
5. **Response Header Propagation:** The final ID is returned to the client in the `X-Request-ID` response header.
6. **Log Injection:** The custom `CorrelationIdFilter` inspects the active `ContextVar` and automatically binds `record.request_id` to every log statement emitted during the request lifespan.
7. **Cleanup:** In a `finally` block, the ContextVar token is reset to ensure clean execution across worker reuse.

---

## 5. Sensitive-Data Logging Policy

PracPrep maintains a strict zero-leakage security policy regarding operational logs.

### Enforced Redactions:
- **Authorization Tokens:** Bearer tokens, JWT strings, and session IDs are stripped from logs.
- **Passwords & Credentials:** User passwords, password hashes, and database passwords are prohibited from log messages.
- **API Keys:** Google Gemini API keys and other vendor credentials are automatically scrubbed via regex sanitizers (`AIza[0-9A-Za-z-_]{35}`).
- **Body Redaction:** Request and response bodies (including student viva answers, generated questions, and uploaded lab manual text) are **never** logged by access middleware.
- **Query Parameter Scrubbing:** Query strings are not emitted into production access logs to prevent token leakage via URLs.
- **Masked Internal Errors:** As dictated by ADR-010, internal exception details, stack traces, and database connection strings are logged server-side only and never exposed in client JSON error envelopes.

---

## 6. Liveness and Readiness Endpoint Semantics

PracPrep separates process health into two explicit probes defined in [`app/main.py`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/backend/app/main.py):

```
                        HTTP GET /health OR /health/live
                                        │
                                        ▼
                             Is process running?
                                ├── Yes ──> 200 OK {"status": "alive" | "healthy"}
                                └── No  ──> Connection Refused / Process Dead

                        HTTP GET /health/ready
                                        │
                                        ▼
                        Ping Database (SELECT 1)
                        Timeout: DATABASE_CONNECT_TIMEOUT_SECONDS
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
              Success                       Failure
          200 OK                        503 Service Unavailable
          {"status": "ready",           {"status": "not_ready",
           "database": "connected"}      "database": "disconnected"}
```

### Liveness Probe (`/health` and `/health/live`)
- **Semantics:** Indicates whether the Python/Uvicorn process is alive, responding to HTTP traffic, and capable of executing coroutines.
- **External Dependencies:** Zero dependency checks. Does **not** query PostgreSQL or external AI APIs.
- **Failure Condition:** Fails only if the process crashes, encounters an unhandled deadlock in the event loop, or runs out of OS memory.
- **Backward Compatibility:** `/health` is preserved for legacy Docker healthchecks and monitoring tools.

### Readiness Probe (`/health/ready`)
- **Semantics:** Indicates whether the application is fully initialized and capable of servicing incoming user requests.
- **Dependency Checks:** Executes an asynchronous ping (`SELECT 1`) against the PostgreSQL database using [`check_database_health()`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/backend/app/core/database.py).
- **Bounded Timeout:** Uses `asyncio.wait_for` capped at `DATABASE_CONNECT_TIMEOUT_SECONDS` (default: 2.0s). If the database is unreachable or unresponsive, the probe aborts quickly and returns HTTP 503 rather than hanging requests.
- **Zero Information Leakage:** On failure, responses return generic indicators (`"database": "disconnected"`) with zero connection strings, credentials, or internal topology details.

---

## 7. Health-Check Response Examples

### Successful Liveness (`GET /health`):
```http
HTTP/1.1 200 OK
content-type: application/json
x-request-id: 9a8b7c6d5e4f3a2b1c0d9e8f7a6b5c4d

{
  "status": "healthy"
}
```

### Successful Liveness (`GET /health/live`):
```http
HTTP/1.1 200 OK
content-type: application/json
x-request-id: 11223344556677889900aabbccddeeff

{
  "status": "alive"
}
```

### Successful Readiness (`GET /health/ready`):
```http
HTTP/1.1 200 OK
content-type: application/json
x-request-id: aabbccddeeff00112233445566778899

{
  "status": "ready",
  "database": "connected"
}
```

### Failed Readiness (`GET /health/ready` when DB is unreachable):
```http
HTTP/1.1 503 Service Unavailable
content-type: application/json
x-request-id: ffeeddccbbaa99887766554433221100

{
  "status": "not_ready",
  "database": "disconnected"
}
```

---

## 8. Production Configuration Requirements

Before traffic is served in production (`ENVIRONMENT=production`), [`validate_production_configuration()`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/backend/app/core/config.py) runs during application creation and enforces strict operational criteria:

1. **Debug Mode:** `DEBUG` must be `False`. If set to `True`, application startup halts immediately with `ValueError`.
2. **Cryptographic Secret Strength:** `JWT_SECRET_KEY` must contain at least 32 characters and cannot match known development placeholders (`insecure-dev-secret-key...`, `your-secret-key-here...`).
3. **Safe CORS Whitelist:** `CORS_ORIGINS` must be explicit. Wildcards (`*`) are prohibited in production to prevent credential and session token theft.
4. **Security Headers:** Automatic enforcement of HSTS (1 year + subdomains), `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, and restricted `Content-Security-Policy`.
5. **Rate Limiting:** `slowapi` rate limiting remains active on authentication, AI endpoints, and file upload routes.
6. **File Upload Boundaries:** `MAX_UPLOAD_SIZE_BYTES` strictly enforces file quotas (default: 25MB) with UUID isolation.

---

## 9. Graceful Shutdown & Resource Lifecycle

FastAPI lifespan management guarantees deterministic resource cleanup when SIGTERM or SIGINT is received:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize logging and validate settings
    setup_logging()
    validate_production_configuration(app_settings)
    logger.info("Application startup initialized...")
    yield
    # Shutdown: Cleanly dispose of SQLAlchemy connection pool
    logger.info("Application shutdown initiated: Disposing database connections...")
    await dispose_app_engine()
    logger.info("Database engine connections closed successfully.")
```

- **Connection Pool Disposal:** [`dispose_app_engine()`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/backend/app/core/database.py) executes `await async_engine.dispose()`, closing all checked-in asyncpg connections and releasing socket descriptors cleanly.
- **In-Flight Requests:** Uvicorn finishes servicing active HTTP requests within its graceful termination window before completing shutdown.

---

## 10. Docker Health-Check Integration

In [`docker-compose.yml`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/docker-compose.yml):

```yaml
  db:
    image: postgres:16-alpine
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER:-postgres} -d $${POSTGRES_DB:-pracprep}"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  backend:
    depends_on:
      db:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "curl -f http://localhost:8000/health/ready || exit 1"]
      interval: 5s
      timeout: 5s
      retries: 5
      start_period: 10s

  frontend:
    depends_on:
      backend:
        condition: service_healthy
    healthcheck:
      test: ["CMD-SHELL", "wget -q --spider http://127.0.0.1/ || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
```

### Dependency Chain:
1. `db` starts and waits until `pg_isready` reports healthy.
2. `backend` starts once `db` is healthy; its healthcheck polls `/health/ready`, confirming that database queries succeed.
3. `frontend` (Nginx reverse proxy) marks itself healthy and accepts client traffic once `backend` reports healthy.

---

## 11. Operational Troubleshooting

| Symptom | Diagnostic Command | Root Cause & Resolution |
|---|---|---|
| **Readiness probe returns 503** | `docker exec pracprep-backend curl -i http://localhost:8000/health/ready` | PostgreSQL is unreachable or connection timed out (> 2s). Check database container logs (`docker logs pracprep-db`) and verify `DATABASE_URL`. |
| **Startup fails with ValueError** | `docker logs pracprep-backend` | Production configuration check failed (e.g. `DEBUG=True`, weak `JWT_SECRET_KEY`, or `CORS_ORIGINS=*`). Check `.env` and set secure configuration. |
| **Log output is unformatted** | Inspect environment setting: `echo $LOG_FORMAT` | If `LOG_FORMAT=auto` in development, output is colored text. Set `LOG_FORMAT=json` for JSON output. |
| **Missing Request IDs in logs** | Inspect client request headers: `curl -H "X-Request-ID: test-id"` | Ensure reverse proxy does not strip `X-Request-ID`. Check that incoming request IDs contain only valid characters (`[a-zA-Z0-9_\-]`). |
| **Container marked unhealthy** | `docker inspect --format='{{json .State.Health}}' pracprep-backend` | Check if `/health/ready` is returning 503 or failing curl execution. |

---

## 12. Remaining Production Limitations

1. **Distributed Rate Limiting:** The current rate limiter uses an in-memory backend (`slowapi.Limiter(key_func=...)`). For multi-instance clustered deployments, rate limiting state is local to each replica. Distributed Redis rate limiting is deferred to future multi-node scaling tasks.
2. **Log Shipping Agent:** The application emits structured JSON directly to `stdout`/`stderr`. In a production cluster (Kubernetes, AWS ECS, GCP Cloud Run), a log aggregation agent (Vector, FluentBit, CloudWatch Agent) must be configured to forward logs to central storage.
3. **Database Migration Automation:** Database migrations (`alembic upgrade head`) are decoupled from process startup to prevent race conditions during rolling multi-container deployments. Migrations must be run via pre-deploy jobs or container entrypoint scripts.
