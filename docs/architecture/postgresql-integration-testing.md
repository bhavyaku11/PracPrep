# PostgreSQL Integration Testing Guide

**PracPrep Lab Preparation Platform — Architecture & Testing Documentation**  
**Task Reference:** TASK-15.3 (PostgreSQL Integration Testing)

---

## 1. Why PostgreSQL Integration Testing is Needed

PracPrep's fast unit test suite provides extensive coverage using SQLite and in-memory mocks. However, SQLite and mocks cannot validate PostgreSQL-specific database semantics, including:

1. **Native PostgreSQL Constraints & Types:**
   - Native `UUID` primary and foreign key behavior.
   - Native `JSONB` document storage, querying, and mutation semantics (used for checklists, viva metrics, and document extraction outputs).
   - Real PostgreSQL timezone handling (`TIMESTAMP WITH TIME ZONE` / UTC round-trips).
   - Composite unique constraints such as `(user_id, idempotency_key)` on guest migrations.
2. **Transactional Semantics & Foreign Key Cascades:**
   - Real PostgreSQL cascade deletions (`ON DELETE CASCADE`) across `users` -> `user_settings`, `experiments`, `viva_sessions`, and `uploaded_documents`.
   - Real PostgreSQL rollback behavior and `SAVEPOINT` (nested transaction) mechanics.
   - Atomic multi-table guest data migration guarantees without partial write leaks.
3. **Asyncpg & Async ORM Concurrency:**
   - Asynchronous driver behavior (`asyncpg`) under SQLAlchemy 2.0.
   - Detection of `MissingGreenlet` errors when accessing un-loaded relationships asynchronously (validating `selectinload` and eager fetching patterns).
   - Real connection lifecycle, pooling, and disposal.
4. **Migration Correctness:**
   - Verification that the full Alembic migration chain (`alembic upgrade head`) executes cleanly and idempotently from an empty PostgreSQL instance.

---

## 2. Test Environment Architecture

PostgreSQL integration testing runs against an isolated PostgreSQL 16 container that is completely decoupled from local development and production databases.

```
+-----------------------------------------------------------------------+
| Docker Host / Compose Test Profile ("test")                           |
|                                                                       |
|  +---------------------------+       +-----------------------------+  |
|  | pracprep-test-db          |       | pracprep-db (Dev / Local)   |  |
|  | postgres:16-alpine        |       | postgres:16-alpine          |  |
|  | Port: 5433:5432           |       | Port: 5432:5432             |  |
|  | DB: pracprep_test         |       | DB: pracprep                |  |
|  | User: postgres_test       |       | User: postgres              |  |
|  | Storage: tmpfs (RAM)      |       | Storage: named volume       |  |
|  +---------------------------+       +-----------------------------+  |
|               ^                                                       |
+---------------|-------------------------------------------------------+
                |
+---------------|-------------------------------------------------------+
| Pytest Test Runner (Host or Container)                                |
|                                                                       |
|  conftest.py Safety Guard:                                            |
|    1. Verify DB URL contains "test" (pracprep_test)                   |
|    2. Reject if target matches dev DB (pracprep)                      |
|    3. NullPool engine avoids cross-loop event loop pollution          |
|    4. TRUNCATE TABLE ... RESTART IDENTITY CASCADE per test            |
|                                                                       |
|  Test Modules:                                                        |
|    - test_postgres_migrations.py (Area A: Schema & Migrations)        |
|    - test_postgres_users_settings.py (Area B: Users & Settings)       |
|    - test_postgres_experiments_checklists.py (Area C: Experiments)   |
|    - test_postgres_viva.py (Area D: Viva Sessions & Answers)          |
|    - test_postgres_documents.py (Area E: Uploaded Documents)          |
|    - test_postgres_guest_migration.py (Area F: Guest Migration)       |
|    - test_postgres_transactions.py (Area G: Transactions & Rollback)  |
+-----------------------------------------------------------------------+
```

### Key Architectural Characteristics
- **Dedicated Port & Credentials:** Runs on host port `5433` (container port `5432`) with user `postgres_test` and database `pracprep_test`.
- **tmpfs Storage:** Uses an in-memory `tmpfs` mount (`/var/lib/postgresql/data`) for ultra-fast I/O and zero persistent disk accumulation.
- **Compose Profile Isolation:** Configured under `profiles: ["test"]` in `docker-compose.yml`. It will **never** start during default `docker compose up` developer commands.
- **Fail-Safe Preflight Guard:** If `TEST_DATABASE_URL` targets a database without `"test"` in its name or matches `pracprep`, test setup immediately halts with a `RuntimeError` before issuing any query.

---

## 3. Prerequisites

1. **Docker & Docker Compose:** Docker Engine 24+ and Docker Compose v2.
2. **Python Environment:** Python 3.11+ (Python 3.14 compatible) with backend dependencies installed in `backend/.venv`.
3. **Running Test Container:** Container `pracprep-test-db` running and healthy.

---

## 4. Environment Configuration

### Integration Test Environment Variables

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `TEST_DATABASE_URL` | `postgresql+asyncpg://postgres_test:postgres_test_password@localhost:5433/pracprep_test` | Dedicated async PostgreSQL connection URL for tests. |
| `PYTHONPATH` | `backend` | Required when invoking `pytest` from the repository root. |

### Development `.env` Safety
The standard `backend/.env` remains configured for development (`localhost:5432/pracprep`). Integration tests do not read or modify development `.env` files.

---

## 5. How to Start the Test Database

To start the isolated test database service in the background:

```bash
docker compose --profile test up -d test-db
```

To verify the test database is healthy:

```bash
docker ps --filter "name=pracprep-test-db"
```

Expected output:
```
CONTAINER ID   IMAGE                COMMAND                  STATUS                   PORTS                    NAMES
...            postgres:16-alpine   "docker-entrypoint.s…"   Up (healthy)             0.0.0.0:5433->5432/tcp   pracprep-test-db
```

To stop the test database:

```bash
docker compose --profile test down
```

---

## 6. How to Run Migrations Against Test Database

Migrations can be run against the test database using the standard Alembic CLI with `DATABASE_URL` overridden:

```bash
DATABASE_URL="postgresql+asyncpg://postgres_test:postgres_test_password@localhost:5433/pracprep_test" \
./backend/.venv/bin/alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl AsyncPostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 560f2b7c6d76, Create initial schema with all core tables
INFO  [alembic.runtime.migration] Running upgrade 560f2b7c6d76 -> c7e3f1a2b4d5, Add guest migrations idempotency tracking table
```

---

## 7. How to Execute Integration Tests

### Execute All PostgreSQL Integration Tests
```bash
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration -v
```
*or using the registered pytest marker:*
```bash
PYTHONPATH=backend ./backend/.venv/bin/pytest -m integration -v
```

### Execute a Specific Integration Test Area
```bash
# Area A: Schema & Migrations
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration/test_postgres_migrations.py -v

# Area B: Users & Settings Persistence
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration/test_postgres_users_settings.py -v

# Area C: Experiments & Preparation Checklists
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration/test_postgres_experiments_checklists.py -v

# Area D: Viva Sessions & Answers Ordering
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration/test_postgres_viva.py -v

# Area E: Documents & Uploaded Manuals
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration/test_postgres_documents.py -v

# Area F: Guest Data Migration
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration/test_postgres_guest_migration.py -v

# Area G: Transaction & Rollback Behavior
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests/integration/test_postgres_transactions.py -v
```

---

## 8. How to Run the Complete Backend Suite

To run both unit tests and integration tests together:

```bash
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests -v
```

To run fast unit tests only (skipping integration tests):

```bash
PYTHONPATH=backend ./backend/.venv/bin/pytest backend/tests --ignore=backend/tests/integration -v
# OR using mark expression:
PYTHONPATH=backend ./backend/.venv/bin/pytest -m "not integration" -v
```

---

## 9. How Test Data is Isolated and Cleaned Up

1. **Automatic Table Truncation (`clean_database` Fixture):**
   Before and after every single test function, an `autouse` fixture executes:
   ```sql
   TRUNCATE TABLE viva_answers, viva_sessions, uploaded_documents,
                  preparation_checklists, experiments, guest_migrations,
                  user_settings, users RESTART IDENTITY CASCADE;
   ```
   This guarantees that test data does not leak across tests, regardless of test execution order.
2. **NullPool Engine:**
   Integration test engines are instantiated with `poolclass=NullPool`. Connections are never retained in a pool across different event loops, avoiding pytest-asyncio loop collisions.
3. **Session Rollback Safeguards:**
   Every `db_session` fixture automatically rolls back uncommitted changes in its teardown block.
4. **Independent Multi-Session Verification:**
   Tests verifying persistence commit in Session 1, then open a completely separate Session 2 to read the data, confirming that changes were actually flushed and committed to PostgreSQL disks/RAM rather than living in an in-memory session identity map.

---

## 10. Common Connection and Migration Errors

### Error: `[PostgreSQL Safety Violation] Target database 'pracprep' is not a test database.`
- **Cause:** `TEST_DATABASE_URL` was pointed to a production or development database name.
- **Fix:** Ensure the database name in `TEST_DATABASE_URL` contains `"test"`, e.g., `pracprep_test`.

### Error: `[PostgreSQL Integration Preflight Error] Failed to connect to the PostgreSQL integration test database`
- **Cause:** Container `pracprep-test-db` is not running.
- **Fix:** Run `docker compose --profile test up -d test-db`.

### Error: `RuntimeError: asyncio.run() cannot be called from a running event loop`
- **Cause:** Calling synchronous Alembic functions directly inside an async test function.
- **Fix:** Wrap Alembic commands with `await asyncio.to_thread(command.upgrade, alembic_cfg, "head")`.

### Error: `password authentication failed for user "postgres_test"`
- **Cause:** Passing `str(engine.url)` to Alembic config, which masks passwords with `***`.
- **Fix:** Use `engine.url.render_as_string(hide_password=False)`.

---

## 11. Current Coverage and Remaining Limitations

### Current Coverage (31 Integration Tests)
- **Area A (6 tests):** All tables verified, column types (UUID, JSONB, TIMESTAMPTZ), primary keys, foreign keys, unique indexes, and Alembic upgrade idempotency.
- **Area B (6 tests):** User CRUD, unique email constraint enforcement, 1-to-1 UserSettings creation, default study settings, multi-session updates, user isolation, cascade deletion.
- **Area C (5 tests):** Experiment + checklist parent-child persistence, JSONB checklist updates, cascade deletion of checklists, user ownership filtering, `selectinload` async relationship safety.
- **Area D (3 tests):** Viva sessions + answers ordering (`order_by="VivaAnswer.question_number"`), JSONB topic analysis/metrics, cascade delete answers on session deletion, user isolation.
- **Area E (4 tests):** UploadedDocument metadata and status lifecycle, experiment document linkage, foreign key violation rejection, document replacement flow.
- **Area F (4 tests):** Guest migration persistence, relational remapping from client IDs to server UUIDs, composite unique constraint `(user_id, idempotency_key)`, multi-user idempotency isolation, atomic rollback on partial failure.
- **Area G (3 tests):** Transaction rollback leaving no partial writes, `SAVEPOINT` nested transactions, concurrent inserts uniqueness invariant.

### Remaining Limitations & Out of Scope
- **Redis Integration:** Redis is not in scope for TASK-15.3 (no caching or distributed locking tested).
- **External AI Providers:** Document OCR and Viva AI evaluations use structured mock DTOs; live Google Gemini / external API calls are not executed during integration tests.
- **Production Secrets:** Production secret rotation and CI/CD automation remain pending for future tasks (TASK-15.4 / TASK-15.5).
