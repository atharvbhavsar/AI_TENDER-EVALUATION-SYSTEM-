"""Pydantic schemas for authentication and RBAC."""

import uuid
from typing import List
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    """Credentials payload for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=1, description="Account password")


class TokenResponse(BaseModel):
    """Authentication token response payload."""

    access_token: str = Field(..., description="Signed JWT access token")
    token_type: str = Field(default="bearer", description="Token authorization type")


class UserResponse(BaseModel):
    """Public user details response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    is_active: bool
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)


class PermissionResponse(BaseModel):
    """Permission detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None


class RoleResponse(BaseModel):
    """Role detail response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    permissions: List[str] = Field(default_factory=list)
