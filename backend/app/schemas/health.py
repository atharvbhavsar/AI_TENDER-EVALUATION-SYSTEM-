"""Health response schemas."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Schema representing the status of the service and its dependencies."""

    model_config = ConfigDict(extra="allow")

    status: str = Field(default="healthy", description="Status indicator of the application")
    database: str = Field(default="healthy", description="Status indicator of the database connection")


class LivenessResponse(BaseModel):
    """Schema representing basic process liveness."""

    status: str = Field(default="alive", description="Process liveness indicator")


class ReadinessResponse(BaseModel):
    """Schema representing readiness across database, storage, and policy services."""

    status: str = Field(..., description="Overall readiness status ('ready' or 'not_ready')")
    components: Dict[str, Any] = Field(default_factory=dict, description="Component-level health details")
