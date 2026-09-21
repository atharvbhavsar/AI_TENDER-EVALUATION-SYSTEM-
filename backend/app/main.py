"""FastAPI Application entrypoint for CRPF Tender Evaluation Platform."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import get_logger, setup_logging

settings = get_settings()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifecycle events."""
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info(
        "Starting %s v%s [Environment: %s, Debug: %s]",
        settings.APP_NAME,
        settings.APP_VERSION,
        settings.ENVIRONMENT,
        settings.DEBUG,
    )
    # Ensure document storage bucket exists
    try:
        from app.storage.service import get_storage_service
        storage = get_storage_service()
        storage.ensure_bucket_exists()
    except Exception as exc:
        logger.warning("Storage bucket initialization warning at startup: %s", str(exc))
    yield
    # Shutdown
    logger.info("Shutting down %s", settings.APP_NAME)


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    from fastapi.middleware.cors import CORSMiddleware
    from app.core.middleware import (
        CorrelationIdMiddleware,
        RateLimiterMiddleware,
        SecurityHeadersMiddleware,
    )

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. Correlation ID Middleware (outermost for logging context)
    app.add_middleware(CorrelationIdMiddleware)

    # 2. Security Headers Middleware
    app.add_middleware(SecurityHeadersMiddleware)

    # 3. Rate Limiting Middleware
    app.add_middleware(RateLimiterMiddleware)

    # 4. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS,
        allow_headers=settings.CORS_ALLOW_HEADERS,
    )

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Register API routers
    app.include_router(api_router)

    return app


app = create_application()
