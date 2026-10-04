# CI/CD Pipeline & Automated Integration Workflows

**Document Version:** 1.0.0  
**Status:** Approved / Active CI Pipeline  
**Task Reference:** TASK-15.5 (CI/CD Pipeline & Automated Integration Workflows)  
**Parent Tracker:** [Backend Task Tracker](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/docs/architecture/backend-task-tracker.md)  
**Scope Notice:** This pipeline exclusively performs **Continuous Integration (CI) and quality gating**. Production deployment and artifact registry publishing are strictly out of scope.

---

## 1. Workflow Triggers

The GitHub Actions workflow is located at [`.github/workflows/ci.yml`](file:///Users/bhavyakumar/Documents/Projects/Hacktoberfest%20Challanges/Week%201/.github/workflows/ci.yml). It activates automatically on:

| Trigger Event | Configuration | Purpose |
|---|---|---|
| **Push** | `branches: [main]` | Verifies commits integrated into the main branch to ensure no regressions. |
| **Pull Request** | `branches: [main]` | Gates incoming pull requests targeting the primary branch before merge. |
| **Workflow Dispatch** | `workflow_dispatch:` | Enables manual on-demand execution from the GitHub Actions web interface. |

### Concurrency Control:
In-flight pipeline runs on the same branch or PR are cancelled automatically when a newer commit is pushed (`cancel-in-progress: ${{ github.event_name == 'pull_request' }}`).

---

## 2. Job Structure and Execution Order

The workflow is architected into 4 parallel execution jobs and 1 unified quality gate:

```
                      [Push / PR / Manual Dispatch]
                                    │
         ┌──────────────────────────┼─────────────────────────┬─────────────────────────┐
         ▼                          ▼                         ▼                         ▼
┌──────────────────┐     ┌─────────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│   backend-unit   │     │ postgres-integration│     │     frontend     │     │   docker-build   │
│ ──────────────── │     │ ─────────────────── │     │ ──────────────── │     │ ──────────────── │
│ - Python 3.12    │     │ - Python 3.12       │     │ - Node.js 22     │     │ - Compose Config │
│ - PyCompile check│     │ - Postgres 16 (svc) │     │ - npm ci         │     │ - Backend image  │
│ - 770 unit tests │     │ - Alembic upgrade   │     │ - oxlint         │     │ - Frontend image │
│ - Upload JUnit   │     │ - 31 DB tests       │     │ - 114 tests      │     └─────────┬────────┘
└────────┬─────────┘     │ - Upload JUnit      │     │ - Vite build     │               │
         │               └──────────┬──────────┘     └────────┬─────────┘               │
         │                          │                         │                         │
         └──────────────────────────┼─────────────────────────┴─────────────────────────┘
                                    │
                                    ▼
                         ┌───────────────────────┐
                         │    ci-quality-gate    │
                         │ ───────────────────── │
                         │ - Evaluates results   │
                         │ - Enforces PR status  │
                         └───────────────────────┘
```

1. **`backend-unit`**: Runs independently on `ubuntu-latest`. Executes Python bytecode compilation checks and 770 unit, route, schema, lifecycle, and logging tests.
2. **`postgres-integration`**: Runs in parallel on `ubuntu-latest` with a real PostgreSQL 16 container service. Applies Alembic migrations and executes 31 database integration tests.
3. **`frontend`**: Runs in parallel on `ubuntu-latest`. Installs locked dependencies via `npm ci`, runs the linter (`oxlint`), executes 114 frontend tests, and compiles the Vite production bundle.
4. **`docker-build`**: Runs in parallel on `ubuntu-latest`. Validates `docker-compose.yml` configuration and verifies that both backend and frontend multi-stage Dockerfiles build cleanly.
5. **`ci-quality-gate`**: Evaluates all four upstream jobs. Fails if any job failed or was cancelled; provides the required status check for branch protection rules.

---

## 3. Runtime Versions & System Dependencies

| Component | Target Version | Package / Environment Source | System Dependencies Installed |
|---|---|---|---|
| **Backend Python** | `3.12` | `actions/setup-python@v5` (cache: `pip`) | `tesseract-ocr`, `poppler-utils` (via `apt-get` for PDF/image processing) |
| **Database** | `PostgreSQL 16` | `postgres:16-alpine` (Service Container) | None (alpine image includes `pg_isready`) |
| **Frontend Node.js** | `22` | `actions/setup-node@v4` (cache: `npm`) | Node.js standard runtime supporting `--experimental-strip-types` |
| **Docker Engine** | Latest | `docker/setup-buildx-action@v3` | Docker Buildx, Compose v2 |

---

## 4. Backend Test Commands

### Unit & API Route Tests:
```bash
# Executed by backend-unit job:
python -m py_compile $(find backend/app backend/tests -name "*.py")
pytest backend/tests -m "not integration" -v --junitxml=backend-test-results.xml
```
- **Scope:** 770 tests covering authentication, experiments, checklists, viva sessions, demonstration AI provider, Gemini provider parsing, document processing, settings synchronization, user data export, guest migration, rate limiting, security headers, ADR-010 error envelope, structured logging, and lifecycle validation.
- **Environment:** Relies on default `Settings` configuration (`ENVIRONMENT=development`, `RATE_LIMITING_ENABLED=True`).

---

## 5. PostgreSQL Service Configuration

The `postgres-integration` job provisions a dedicated service container on the runner host:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_USER: postgres_test
      POSTGRES_PASSWORD: postgres_test_password
      POSTGRES_DB: pracprep_test
    ports:
      - 5432:5432
    options: >-
      --health-cmd pg_isready
      --health-interval 5s
      --health-timeout 5s
      --health-retries 5
```

### Execution Steps:
1. **Migration Execution:**
   ```bash
   cd backend && alembic upgrade head
   ```
   *Env:* `DATABASE_URL=postgresql+asyncpg://postgres_test:postgres_test_password@localhost:5432/pracprep_test`
2. **Integration Test Execution:**
   ```bash
   pytest backend/tests/integration -v --junitxml=postgres-integration-results.xml
   ```
   *Env:* `TEST_DATABASE_URL=postgresql+asyncpg://postgres_test:postgres_test_password@localhost:5432/pracprep_test`

### Safety Guards:
- `validate_test_database_safety()` ensures target DB name contains `"test"` and rejects any execution targeting `pracprep`, `production`, or `main`.
- Ephemeral credentials (`postgres_test` / `postgres_test_password`) are scoped exclusively to the CI runner.

---

## 6. Frontend Validation Commands

```bash
# Executed by frontend job:
npm ci
npm run lint
npm test
npm run build
```

- **`npm ci`**: Deterministic dependency installation from committed `package-lock.json`.
- **`npm run lint`**: Static analysis via `oxlint`.
- **`npm test`**: Runs all 11 test suites (114 tests) covering API client, error envelopes, auth services, dual-mode facades, AI provider routing, progress analytics, document parser preview, and guest migration flows.
- **`npm run build`**: Compiles TypeScript (`tsc -b`) and generates production bundle assets (`vite build`).

---

## 7. Docker Build Validation

```bash
# Executed by docker-build job:
docker compose config
docker build -t pracprep-backend:ci ./backend
docker build -t pracprep-frontend:ci .
```

- **Validation:** Verifies Compose file syntax, network definitions, volumes, and service dependencies.
- **Backend Image:** Validates multi-stage Python 3.12 Dockerfile (`builder` -> `runtime`), non-root `appuser:1001`, OCR dependencies, and `/health/ready` check.
- **Frontend Image:** Validates multi-stage Node 20 builder -> Nginx 1.27 runtime with SPA fallback and `/api/` reverse proxy configuration.
- **Registry Push Inaction:** Images are tagged locally for validation only; zero images are pushed to Docker Hub or cloud registries.

---

## 8. Required GitHub Variables and Secrets

**No third-party secrets or environment variables are required.**

- The pipeline is completely self-contained.
- PostgreSQL runs as an ephemeral GitHub Actions service container with disposable local test credentials.
- AI tests run against the deterministic `DemonstrationAIProvider` or mock responses; no live `GEMINI_API_KEY` is required in CI.
- No cloud deployment credentials, registry tokens, or SSH keys are configured.

---

## 9. Inspecting Failed Workflow Runs

When a CI run fails:
1. Navigate to the **Actions** tab in GitHub.
2. Select the failed workflow run from the list.
3. Review the failed job (`backend-unit`, `postgres-integration`, `frontend`, `docker-build`, or `ci-quality-gate`).
4. Click on the failed step to expand the command output and error traces.
5. In the **Artifacts** section at the bottom of the summary page, download:
   - `backend-unit-test-results` (JUnit XML report)
   - `postgres-integration-results` (JUnit XML report)

---

## 10. How to Reproduce CI Checks Locally

To replicate CI validation on a development workstation:

```bash
# 1. Backend unit tests & compilation
python3 -m py_compile $(find backend/app backend/tests -name "*.py")
PYTHONPATH=backend pytest backend/tests -m "not integration" -v

# 2. PostgreSQL integration tests (requires test-db container)
docker compose --profile test up -d test-db
(cd backend && DATABASE_URL=postgresql+asyncpg://postgres_test:postgres_test_password@localhost:5433/pracprep_test alembic upgrade head)
TEST_DATABASE_URL=postgresql+asyncpg://postgres_test:postgres_test_password@localhost:5433/pracprep_test PYTHONPATH=backend pytest backend/tests/integration -v

# 3. Frontend validation
npm ci
npm run lint
npm test
npm run build

# 4. Docker validation
docker compose config
docker build -t pracprep-backend:test ./backend
docker build -t pracprep-frontend:test .
```

---

## 11. Security and Permission Decisions

1. **Least-Privilege Permissions:** Top-level permissions are strictly declared as `permissions: contents: read`. No write or administration privileges are granted.
2. **Pinned Major Action Versions:** Third-party actions are pinned to trusted official versions (`actions/checkout@v4`, `actions/setup-python@v5`, `actions/setup-node@v4`, `actions/upload-artifact@v4`, `docker/setup-buildx-action@v3`).
3. **No Secret Ingestion:** The workflow does not consume or print secrets.
4. **Isolated Test Database:** The test database runs in a disposable container network with non-production credentials, isolated from any deployment environment.
5. **No Networked AI Calls:** CI runs in zero-network demonstration mode, preventing accidental API key leakage or external quota exhaustion.

---

## 12. Current Limitations

1. **No CD (Continuous Deployment):** The pipeline validates code correctness only. Deployment to hosting environments (AWS, GCP, Kubernetes, VPS) must be managed through separate deployment tooling.
2. **No Image Registry Publishing:** Docker images are verified during build, but not published to a container registry (e.g. GitHub Packages or Docker Hub).
3. **No Distributed Performance Testing:** Load testing and concurrent stress testing are not executed within CI to keep workflow execution fast (< 5 minutes).
