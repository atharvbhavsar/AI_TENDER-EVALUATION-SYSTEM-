"""Production middleware components: correlation IDs, security headers, and rate limiting."""

import time
import uuid
from collections import defaultdict
from typing import Callable, Dict, List
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.core.logging import correlation_id_ctx, get_logger

logger = get_logger("app.core.middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware that injects and propagates X-Request-ID for distributed tracing and logging."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = correlation_id_ctx.set(req_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            correlation_id_ctx.reset(token)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that attaches security hardening headers to all HTTP responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        response: Response = await call_next(request)

        if settings.SECURITY_HEADERS_ENABLED:
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-XSS-Protection"] = "1; mode=block"

            # In production or HTTPS environments, add HSTS
            if settings.ENVIRONMENT == "production":
                response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    Lightweight, configurable in-memory sliding-window rate limiter for abuse prevention.
    Applies stricter limits to sensitive routes (login, uploads, processing, reports).
    """

    _request_history: Dict[str, List[float]] = defaultdict(list)

    @classmethod
    def reset(cls) -> None:
        """Reset in-memory rate limiting history (for test isolation)."""
        cls._request_history.clear()

    def _get_client_key(self, request: Request) -> str:
        """Extract identifier from Authorization token or client IP."""
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            return f"auth:{auth_header[7:25]}"
        client_ip = request.client.host if request.client else "unknown_ip"
        return f"ip:{client_ip}"

    def _get_rate_limit_for_path(self, path: str, settings) -> int:
        """Determine rate limit per minute based on endpoint sensitivity."""
        if "/auth/login" in path or "/auth/register" in path:
            return settings.RATE_LIMIT_LOGIN_PER_MINUTE
        if "/documents" in path and ("upload" in path or path.endswith("/documents")):
            return settings.RATE_LIMIT_UPLOAD_PER_MINUTE
        if "/reports" in path:
            return settings.RATE_LIMIT_REPORT_PER_MINUTE
        return settings.RATE_LIMIT_DEFAULT_PER_MINUTE

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        path = request.url.path
        if path.startswith("/docs") or path.startswith("/openapi") or "health" in path:
            return await call_next(request)

        client_key = self._get_client_key(request)
        route_key = f"{client_key}:{path}"
        max_requests = self._get_rate_limit_for_path(path, settings)
        now = time.time()
        window_seconds = 60.0

        timestamps = self._request_history[route_key]
        self._request_history[route_key] = [t for t in timestamps if now - t < window_seconds]

        if len(self._request_history[route_key]) >= max_requests:
            logger.warning("Rate limit exceeded for client %s on %s (limit: %d/min)", client_key, path, max_requests)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Rate limit exceeded.",
                    "limit_per_minute": max_requests,
                    "retry_after_seconds": 60,
                },
                headers={"Retry-After": "60"},
            )

        self._request_history[route_key].append(now)
        return await call_next(request)
