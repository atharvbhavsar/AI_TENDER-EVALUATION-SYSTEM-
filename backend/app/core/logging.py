"""Centralized logging configuration for the application with security filtering and correlation IDs."""

from contextvars import ContextVar
import logging
import re
import sys
from typing import Any

# Global context variable for request correlation ID
correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="-")

# Regex patterns matching sensitive keys and tokens
SENSITIVE_PATTERNS = [
    re.compile(r"(password|passwd|pwd)[\"']?\s*[:=]\s*[\"']?([^\"'\s,]+)", re.IGNORECASE),
    re.compile(r"(bearer\s+)([a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+)", re.IGNORECASE),
    re.compile(r"(jwt_secret_key|secret_key|api_key|access_key|s3_secret_key)[\"']?\s*[:=]\s*[\"']?([^\"'\s,]+)", re.IGNORECASE),
    re.compile(r"(postgresql(?:\+psycopg)?:\/\/[^:]+:)([^@]+)(@)", re.IGNORECASE),
    re.compile(r"(authorization[\"']?\s*[:=]\s*[\"']?Bearer\s+)([a-zA-Z0-9\-_.]+)", re.IGNORECASE),
]


class SensitiveDataMaskingFilter(logging.Filter):
    """Filter that masks passwords, tokens, JWTs, and database credentials from log messages."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Populate correlation ID on log record
        record.correlation_id = correlation_id_ctx.get()

        # Sanitize message string
        if isinstance(record.msg, str):
            msg = record.msg
            for pattern in SENSITIVE_PATTERNS:
                msg = pattern.sub(r"\1***REDACTED***\3" if pattern.groups == 3 else r"\1***REDACTED***", msg)
            record.msg = msg

        # Sanitize any formatted arguments
        if record.args:
            def _sanitize_val(val: Any) -> Any:
                if isinstance(val, str):
                    s = val
                    for pattern in SENSITIVE_PATTERNS:
                        s = pattern.sub(r"\1***REDACTED***\3" if pattern.groups == 3 else r"\1***REDACTED***", s)
                    return s
                elif isinstance(val, dict):
                    return {
                        k: ("***REDACTED***" if any(s in k.lower() for s in ["password", "secret", "token", "key", "auth"]) else _sanitize_val(v))
                        for k, v in val.items()
                    }
                elif isinstance(val, list):
                    return [_sanitize_val(x) for x in val]
                elif isinstance(val, tuple):
                    return tuple(_sanitize_val(x) for x in val)
                return val

            if isinstance(record.args, dict):
                record.args = _sanitize_val(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(_sanitize_val(x) for x in record.args)

        return True


def setup_logging(log_level: str = "INFO") -> None:
    """Configure standard logging with structured format, correlation IDs, and secret masking."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    log_format = "%(asctime)s | %(levelname)-8s | [%(correlation_id)s] | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    handler.setFormatter(logging.Formatter(fmt=log_format, datefmt=date_format))
    handler.addFilter(SensitiveDataMaskingFilter())

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Avoid duplicate handlers if setup_logging is called multiple times
    root_logger.handlers = [handler]

    # Adjust external loggers if necessary
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.error").handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    """Return a logger instance with the given name."""
    return logging.getLogger(name)
