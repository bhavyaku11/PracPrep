# ==============================================================================
# PracPrep Backend Dockerfile (Multi-Stage Build)
# Python 3.12 / FastAPI / Uvicorn / AsyncPG / Alembic
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Build Dependencies
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build-time dependencies for native C extensions (asyncpg, argon2-cffi, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Install dependencies into isolated installation directory
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ------------------------------------------------------------------------------
# Stage 2: Runtime Environment
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install runtime dependencies:
# - tesseract-ocr: OCR engine for scanned PDF/image manual extraction
# - poppler-utils: pdftoppm utility for rendering PDF pages as images
# - curl: Lightweight HTTP client for container health checks
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pre-built Python packages from builder stage
COPY --from=builder /install /usr/local

# Create unprivileged system user and group (UID/GID 1001)
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup appuser

# Copy application code, configuration, and migrations
COPY --chown=appuser:appgroup alembic.ini /app/
COPY --chown=appuser:appgroup alembic /app/alembic
COPY --chown=appuser:appgroup app /app/app

# Ensure uploads directory structure exists with non-root ownership
RUN mkdir -p /app/uploads/documents && \
    chown -R appuser:appgroup /app

# Switch to unprivileged user
USER appuser

# Configure Python runtime behavior
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 8000

# Container health check using the zero-dependency /health endpoint
HEALTHCHECK --interval=10s --timeout=5s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

# Start Uvicorn ASGI server binding to 0.0.0.0
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
