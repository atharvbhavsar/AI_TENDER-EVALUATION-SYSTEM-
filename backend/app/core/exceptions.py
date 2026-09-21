"""Centralized exception handling for the FastAPI application."""

import logging
from typing import Callable
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class NotFoundException(HTTPException):
    """Exception raised when a requested resource is not found (404)."""

    def __init__(self, detail: str = "Resource not found") -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ConflictException(HTTPException):
    """Exception raised when an operation conflicts with current state (409)."""

    def __init__(self, detail: str = "Resource conflict") -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class ForbiddenException(HTTPException):
    """Exception raised when access is forbidden (403)."""

    def __init__(self, detail: str = "Access forbidden") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class BadRequestException(HTTPException):
    """Exception raised for invalid client requests (400)."""

    def __init__(self, detail: str = "Bad request") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:

    """Handle standard HTTP exceptions with consistent response structure."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


from fastapi.encoders import jsonable_encoder


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handle request validation errors cleanly."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation error",
            "errors": jsonable_encoder(exc.errors()),
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected application errors without leaking internal stack traces."""
    logger.exception(
        "Unhandled exception occurred while processing request: %s %s: %s",
        request.method,
        request.url.path,
        str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers and middleware on the FastAPI application."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)

    @app.middleware("http")
    async def catch_unhandled_exceptions_middleware(request: Request, call_next: Callable):
        try:
            return await call_next(request)
        except Exception as exc:
            return await unhandled_exception_handler(request, exc)
