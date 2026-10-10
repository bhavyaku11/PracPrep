import asyncio
from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator, Optional
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import Settings, get_settings, validate_production_configuration
from app.core.database import async_engine, check_database_health, dispose_app_engine
from app.core.errors import register_error_handlers
from app.core.limiter import limiter
from app.core.logging import setup_logging
from app.core.middleware import RequestCorrelationMiddleware, SecurityHeadersMiddleware
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.experiments.router import router as experiments_router
from app.modules.viva.router import router as viva_router
from app.modules.documents.router import router as documents_router

# Import all SQLAlchemy models to ensure declarative mappings and relationships are configured
import app.modules.auth.models  # noqa: F401
import app.modules.users.models  # noqa: F401
import app.modules.experiments.models  # noqa: F401
import app.modules.viva.models  # noqa: F401
import app.modules.documents.models  # noqa: F401


logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application startup and shutdown lifecycles cleanly."""
    app_settings: Settings = app.state.settings

    # Initialize structured or console logging
    setup_logging(
        log_level=app_settings.LOG_LEVEL,
        log_format=app_settings.LOG_FORMAT,
        environment=app_settings.ENVIRONMENT,
    )
    logger.info(
        "Application startup initialized: %s v%s [env=%s, log_level=%s]",
        app_settings.PROJECT_NAME,
        app_settings.VERSION,
        app_settings.ENVIRONMENT,
        app_settings.LOG_LEVEL,
    )

    yield

    logger.info("Application shutdown initiated: disposing database engine resources")
    await dispose_app_engine()
    logger.info("Application shutdown complete")


def create_app(settings_override: Optional[Settings] = None) -> FastAPI:
    """Application factory for PracPrep backend.

    Args:
        settings_override: Optional custom Settings instance for testing.

    Returns:
        Configured FastAPI application instance.
    """
    app_settings = settings_override or get_settings()

    # Enforce production startup validation guards (secrets, debug mode, CORS)
    validate_production_configuration(app_settings)

    # Configure logging synchronously for immediate use before ASGI lifespan starts
    setup_logging(
        log_level=app_settings.LOG_LEVEL,
        log_format=app_settings.LOG_FORMAT,
        environment=app_settings.ENVIRONMENT,
    )

    is_production = app_settings.ENVIRONMENT == "production"

    app = FastAPI(
        title=app_settings.PROJECT_NAME,
        version=app_settings.VERSION,
        docs_url=None if is_production else "/docs",
        redoc_url=None if is_production else "/redoc",
        openapi_url=None if is_production else f"{app_settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Store application settings in state for middleware and rate limiting
    app.state.settings = app_settings

    # Configure centralized in-memory rate limiter state
    limiter.enabled = app_settings.RATE_LIMITING_ENABLED
    limiter.reset()
    app.state.limiter = limiter

    # Request correlation ID and HTTP access logging middleware
    app.add_middleware(RequestCorrelationMiddleware)

    # Defensive Security Headers Middleware (always active)
    app.add_middleware(SecurityHeadersMiddleware, is_production=is_production)

    # CORS Middleware configuration
    if app_settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=app_settings.CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

    # Centralized standardized error envelope exception handlers (ADR-010)
    register_error_handlers(app)

    # Health & Liveness Check Endpoints
    @app.get("/health", tags=["Health"], summary="Basic application health check")
    async def health_check() -> dict[str, str]:
        """Return the basic health status of the application.

        Maintains backward compatibility with Docker health checks and existing clients.
        Does not require external dependencies or database connection.
        """
        return {"status": "healthy"}

    @app.get("/health/live", tags=["Health"], summary="Liveness probe")
    async def liveness_check() -> dict[str, str]:
        """Return process liveness indicating the application process is running."""
        return {"status": "alive"}

    @app.get("/health/ready", tags=["Health"], summary="Readiness probe verifying database connectivity")
    async def readiness_check(response: Response) -> dict[str, str]:
        """Verify application readiness by assessing database connectivity with bounded timeout."""
        timeout_sec = app_settings.DATABASE_CONNECT_TIMEOUT_SECONDS
        try:
            await asyncio.wait_for(check_database_health(), timeout=timeout_sec)
            return {"status": "ready", "database": "connected"}
        except Exception as exc:
            logger.warning(
                "Readiness probe failed: database unreachable or timed out (%s)",
                type(exc).__name__,
            )
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            return {"status": "not_ready", "database": "disconnected"}

    # Authentication router registration
    app.include_router(
        auth_router,
        prefix=f"{app_settings.API_V1_STR}/auth",
        tags=["Authentication"],
    )

    # Users profile router registration
    app.include_router(
        users_router,
        prefix=f"{app_settings.API_V1_STR}/users",
        tags=["Users"],
    )

    # Experiments router registration
    app.include_router(
        experiments_router,
        prefix=f"{app_settings.API_V1_STR}/experiments",
        tags=["Experiments"],
    )

    # Viva Voce router registration
    app.include_router(
        viva_router,
        prefix=f"{app_settings.API_V1_STR}/viva",
        tags=["Viva Voce"],
    )

    # Documents manual upload router registration
    app.include_router(
        documents_router,
        prefix=f"{app_settings.API_V1_STR}/experiments",
        tags=["Documents"],
    )

    return app


# ASGI entrypoint instance
app = create_app()
