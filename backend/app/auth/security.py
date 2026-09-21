"""Password hashing and security utilities using Argon2id."""

import logging
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from app.core.config import get_settings

logger = logging.getLogger("app.auth.security")
settings = get_settings()

# Initialize Argon2id password hasher with secure defaults
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception as exc:
        logger.error("Unexpected error during password verification: %s", str(exc))
        return False


def validate_password_policy(password: str) -> bool:
    """Validate that the password satisfies minimum security requirements."""
    if not password or not isinstance(password, str):
        return False
    if len(password) < settings.MIN_PASSWORD_LENGTH or len(password) > 128:
        return False
    return True


def normalize_email(email: str) -> str:
    """Normalize email address to lowercase and stripped format."""
    return email.strip().lower()
