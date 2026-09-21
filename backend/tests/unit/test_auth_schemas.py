"""Unit tests for authentication schemas."""

import uuid
import pytest
from pydantic import ValidationError

from app.auth.schemas import LoginRequest, TokenResponse, UserResponse


def test_login_request_schema() -> None:
    """Verify LoginRequest validation."""
    valid_req = LoginRequest(email="officer@crpf.gov.in", password="Password123!")
    assert valid_req.email == "officer@crpf.gov.in"
    assert valid_req.password == "Password123!"

    # Invalid email
    with pytest.raises(ValidationError):
        LoginRequest(email="not-an-email", password="Password123!")


def test_token_response_schema() -> None:
    """Verify TokenResponse schema default values."""
    res = TokenResponse(access_token="sample.jwt.token")
    assert res.access_token == "sample.jwt.token"
    assert res.token_type == "bearer"


def test_user_response_schema() -> None:
    """Verify UserResponse schema."""
    user_id = uuid.uuid4()
    res = UserResponse(
        id=user_id,
        email="officer@crpf.gov.in",
        full_name="Officer Sharma",
        is_active=True,
        roles=["PROCUREMENT_OFFICER"],
        permissions=["TENDER_READ", "TENDER_CREATE"],
    )
    assert res.id == user_id
    assert res.email == "officer@crpf.gov.in"
    assert "TENDER_READ" in res.permissions
