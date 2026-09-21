"""Unit tests for JWT generation and validation."""

import datetime
import uuid
import pytest
import jwt

from app.auth.jwt import create_access_token, decode_access_token
from app.core.config import get_settings


def test_create_and_decode_valid_jwt() -> None:
    """Verify standard access token creation and decoding."""
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id)
    assert isinstance(token, str)

    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert "exp" in payload
    assert "iat" in payload


def test_expired_jwt_raises_error() -> None:
    """Verify that expired tokens are rejected."""
    user_id = uuid.uuid4()
    # Expire 10 minutes in the past
    token = create_access_token(
        subject=user_id,
        expires_delta=datetime.timedelta(minutes=-10),
    )

    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token(token)


def test_tampered_jwt_raises_error() -> None:
    """Verify that tampered tokens fail validation."""
    user_id = uuid.uuid4()
    token = create_access_token(subject=user_id)

    # Tamper with the token string
    tampered_token = token[:-5] + "ABCDE"

    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token(tampered_token)


def test_wrong_secret_jwt_raises_error() -> None:
    """Verify that tokens signed with a different secret key are rejected."""
    settings = get_settings()
    user_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    fake_token = jwt.encode(
        {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int((now + datetime.timedelta(hours=1)).timestamp())},
        "wrong-secret-key-different-signature",
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(ValueError, match="Invalid access token"):
        decode_access_token(fake_token)
