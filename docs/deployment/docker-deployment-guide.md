# PracPrep — Docker Deployment & Containerization Guide

**Document Version:** 1.0.0  
**Date:** 2026-10-04  
**Task:** TASK-15.2: Production Multi-Stage Dockerfile & Compose Stack  
**Target Environment:** Local Developer & Production Multi-Container Docker  

---

## 1. Architecture Overview

PracPrep runs as a three-tier containerized stack orchestrated by Docker Compose:

```
                      Browser / Client
                             │
                             ▼  HTTP (:80)
            ┌──────────────────────────────────┐
            │   pracprep-frontend (Nginx 1.27) │
            │  - Serves static React/Vite SPA  │
            │  - Reverse-proxies /api/ traffic │
            │  - SPA fallback ($uri /index.html│
            └─────────────────┬────────────────┘
                              │
                    Internal Bridge Network
                    (pracprep_bridge_network)
                              │
                              ▼  HTTP (:8000)
            ┌──────────────────────────────────┐
            │   pracprep-backend (FastAPI)     │
            │  - Non-root user (appuser:1001)  │
            │  - Tesseract OCR & Poppler       │
            │  - In-memory slowapi limiter     │
            │  - /health check endpoint        │
            └─────────────────┬────────────────┘
                              │
                    Internal Bridge Network
                              │
                              ▼  TCP (:5432)
            ┌──────────────────────────────────┐
            │       pracprep-db (PostgreSQL 16)│
            │  - Named volume: postgres_data   │
            │  - Healthcheck via pg_isready    │
            └──────────────────────────────────┘
```

### Key Security & Architectural Principles
1. **Zero Public Port Leakage:** By default, only the Nginx frontend port (host port `80`) is exposed. PostgreSQL (`5432`) and FastAPI (`8000`) communicate exclusively over the private bridge network (`pracprep_bridge_network`).
2. **Same-Origin Requests:** Frontend build uses relative API URLs (`VITE_API_BASE_URL=""`). All browser calls go to `/api/v1/...` on the same host, avoiding CORS issues and hardcoded localhost IPs in compiled production bundles.
3. **Non-Root Execution:** The backend container drops privileges to an unprivileged system user (`appuser:appgroup`, UID/GID `1001`).
4. **Resilient Dependency Ordering:** Compose services use health checks (`condition: service_healthy`) rather than mere startup order. FastAPI waits for PostgreSQL to accept connections; Nginx waits for FastAPI to respond to `/health`.

---

## 2. Prerequisites

Ensure your host machine has Docker and Docker Compose installed:

```bash
docker --version          # Docker 20.10+ recommended (tested on 29.8.0)
docker compose version    # Docker Compose v2.0+ recommended (tested on v5.5.1)
```

Verify that the Docker daemon is active:
```bash
docker ps
```

Port `80` must be available on the host machine. (If port `80` is in use by another application, configure `FRONTEND_PORT=3000` or `FRONTEND_PORT=8080` in your `.env` file).

---

## 3. Environment Configuration

Copy the documented template to create your `.env` file:

```bash
cp .env.docker.example .env
```

### Configuration Variables Reference

| Variable | Default Value | Description |
|---|---|---|
| `FRONTEND_PORT` | `80` | Host port on which Nginx serves the web application. |
| `POSTGRES_USER` | `postgres` | Database superuser username. |
| `POSTGRES_PASSWORD` | `postgres_dev_password_change_me` | Database password. Change for production! |
| `POSTGRES_DB` | `pracprep` | Database name. |
| `ENVIRONMENT` | `development` | Runtime environment (`development`, `staging`, `production`). |
| `JWT_SECRET_KEY` | `insecure-dev-secret-key-change-in-production-min32chars` | Secret key for JWT signing. Must be >= 32 chars in production. |
| `CORS_ORIGINS` | `http://localhost,http://localhost:80,http://127.0.0.1,http://127.0.0.1:80` | Allowed CORS origins (comma-separated or JSON list). |
| `RATE_LIMITING_ENABLED` | `true` | Enables slowapi in-memory rate limiting. |
| `DEFAULT_AI_PROVIDER` | `demonstration` | AI provider (`demonstration`, `gemini`, `openai`). |
| `GEMINI_API_KEY` | *(empty)* | Optional Gemini API key for live AI viva evaluation. |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name for viva examination. |
| `MAX_UPLOAD_SIZE_BYTES` | `26214400` | Max upload size in bytes (25 MB default). |

### Production Security Note
When `ENVIRONMENT=production`, PracPrep enforces strict boot-time validation:
- `JWT_SECRET_KEY` must be at least 32 characters long and cannot match known placeholders. Generate a secure key via:
  ```bash
  openssl rand -hex 32
  ```
- Public interactive API documentation (`/docs`, `/redoc`, `/openapi.json`) is disabled.
- Rate limiting ignores `X-Test-Client-Id` headers and derives client identity strictly from `request.client.host`.

---

## 4. Starting the Complete Application Stack

To build all container images and start the stack in detached mode:

```bash
docker compose up --build -d
```

### Checking Service Health
Monitor the startup until all containers transition to `healthy`:

```bash
docker compose ps
```

Expected output:
```
NAME                IMAGE                COMMAND                  SERVICE    STATUS
pracprep-backend    week1-backend        "uvicorn app.main:ap…"   backend    Up (healthy)
pracprep-db         postgres:16-alpine   "docker-entrypoint.s…"   db         Up (healthy)
pracprep-frontend   week1-frontend       "/docker-entrypoint.…"   frontend   Up (healthy)
```

---

## 5. Accessing the Application

- **Frontend Application:**  
  Navigate in your browser to:  
  [http://localhost](http://localhost) (or `http://localhost:<FRONTEND_PORT>`)
- **Backend Health Check:**  
  [http://localhost/health](http://localhost/health)
- **Interactive OpenAPI Documentation (Development Mode Only):**  
  [http://localhost/docs](http://localhost/docs)

---

## 6. Running Database Migrations

Alembic migrations are executed against PostgreSQL inside the running backend container.

### Step 1: Apply All Migrations
Run the upgrade command:
```bash
docker compose exec backend alembic upgrade head
```

Expected output:
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 560f2b7c6d76, create_initial_schema
INFO  [alembic.runtime.migration] Running upgrade 560f2b7c6d76 -> c7e3f1a2b4d5, create_guest_migrations_table
```

### Non-Interactive or CI Execution
If the stack is not yet running, you can run migrations as a one-off task:
```bash
docker compose run --rm backend alembic upgrade head
```

### Checking Current Migration Version
```bash
docker compose exec backend alembic current
```

---

## 7. Viewing Logs

### View All Services (Followed)
```bash
docker compose logs -f
```

### View Individual Service Logs
```bash
docker compose logs -f frontend
docker compose logs -f backend
docker compose logs -f db
```

---

## 8. Stopping the Stack & Managing Data Persistence

> [!IMPORTANT]
> Clearly distinguish between stopping containers and deleting persistent data.

### Stopping Containers (Preserving Data)
To stop and remove containers while **preserving** database tables and uploaded files:
```bash
docker compose down
```
The named volumes (`pracprep_postgres_data` and `pracprep_backend_uploads`) remain intact on disk. When you start the stack again with `docker compose up -d`, all users, experiments, and documents are retained.

### Deleting Persistent Data (Reset to Fresh State)
To stop containers AND **permanently erase** database records and uploaded files:
```bash
docker compose down -v
```
Use this when you want to re-test migrations from scratch on an empty PostgreSQL volume.

---

## 9. Rebuilding After Code Changes

When modifying code:

### Rebuild and Restart All Services
```bash
docker compose up --build -d
```

### Rebuild Only the Backend
```bash
docker compose build backend
docker compose up -d backend
```

### Rebuild Only the Frontend
```bash
docker compose build frontend
docker compose up -d frontend
```

---

## 10. Local Debugging & Direct Port Access

By default, backend port `8000` and database port `5432` are kept internal for security. If you need direct host access during local debugging:

### Option A: Edit `docker-compose.yml`
Uncomment the port mappings in `docker-compose.yml`:
```yaml
  db:
    ports:
      - "5432:5432"

  backend:
    ports:
      - "8000:8000"
```
Then run:
```bash
docker compose up -d
```

### Option B: Use a Docker Compose Override File
Create `docker-compose.override.yml` (automatically merged by Docker Compose):
```yaml
services:
  backend:
    ports:
      - "8000:8000"
  db:
    ports:
      - "5432:5432"
```

---

## 11. Troubleshooting Common Issues

### 1. Port 80 Already in Use
**Error:** `bind: address already in use`  
**Solution:** Change `FRONTEND_PORT` in `.env`:
```bash
FRONTEND_PORT=3000
```
Then restart: `docker compose up -d`. Access the app at `http://localhost:3000`.

### 2. Backend Healthcheck Failing (`unhealthy`)
**Symptom:** `Container pracprep-backend is unhealthy`  
**Investigation:**
```bash
docker compose logs backend
```
**Common Causes:**
- Database not yet ready: Ensure `db` has reached `healthy` status.
- Invalid `CORS_ORIGINS`: Check that `.env` format is valid comma-separated or JSON list.
- Production secret guard rejection: If `ENVIRONMENT=production`, verify `JWT_SECRET_KEY` is at least 32 characters and not a placeholder.

### 3. Database Connection Rejected
**Error:** `ConnectionRefusedError: [Errno 111] Connect call failed ('127.0.0.1', 5432)`  
**Cause:** Attempting to use `localhost:5432` inside container instead of the Docker service hostname `db`.  
**Solution:** Ensure `DATABASE_URL` uses `@db:5432` in container environments.

### 4. File Upload Fails with 413 Payload Too Large
**Cause:** Upload exceeds `client_max_body_size` in Nginx or `MAX_UPLOAD_SIZE_BYTES` in backend.  
**Solution:** The default is configured to 25 MB (`25M` in Nginx and `26214400` in backend). If larger files are needed, update both `deployment/nginx/default.conf` and `MAX_UPLOAD_SIZE_BYTES` in `.env`.
