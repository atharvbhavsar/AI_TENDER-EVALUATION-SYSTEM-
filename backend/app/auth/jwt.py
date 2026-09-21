"""JWT creation, decoding, and validation utilities."""

import datetime
import uuid
import jwt
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError, PyJWTError

from app.core.config import get_settings

settings = get_settings()


def create_access_token(
    subject: str | uuid.UUID,
    expires_delta: datetime.timedelta | None = None,
    token_type: str = "access",
) -> str:
    """Create a signed JWT access token."""
    now = datetime.datetime.now(datetime.timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "typ": token_type,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    Enforces exact signing algorithm, required claims (sub, exp, iat), and token type.
    """
    if not token or not isinstance(token, str):
        raise ValueError("Invalid access token: Token must be a non-empty string.")

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={
                "require": ["sub", "exp", "iat"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
            },
        )
        # Validate subject claim
        if not payload.get("sub") or not str(payload.get("sub")).strip():
            raise ValueError("Invalid access token: Missing or empty subject claim.")

        # Validate token type if present
        if payload.get("typ") and payload.get("typ") != "access":
            raise ValueError(f"Invalid access token: Unexpected token type '{payload.get('typ')}'.")

        return payload
    except (ExpiredSignatureError, InvalidTokenError, PyJWTError) as exc:
        raise ValueError(f"Invalid access token: {str(exc)}") from exc
