"""Pydantic schemas for Tender Management and Versioning."""

import datetime
import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.db.models.tender import TenderStatus


class TenderVersionCreate(BaseModel):
    """Payload to create a new version / corrigendum for a tender."""

    version_label: str = Field(
        default="Corrigendum",
        min_length=1,
        max_length=100,
        description="Human-readable label for this version (e.g. Corrigendum 01)",
    )
    change_summary: Optional[str] = Field(
        default=None,
        description="Detailed description of changes introduced in this version",
    )
    effective_at: Optional[datetime.datetime] = Field(
        default=None,
        description="Time at which this version becomes effective (defaults to current time)",
    )


class TenderVersionResponse(BaseModel):
    """Response model for a single tender version."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    version_number: int
    version_label: str
    effective_at: datetime.datetime
    change_summary: Optional[str] = None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime.datetime


class TenderCreate(BaseModel):
    """Payload to create a new tender and its initial Version 1."""

    tender_number: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique identifier for the tender (e.g. CRPF/PROC/2026/001)",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Formal tender title",
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description or scope of procurement",
    )
    issuing_authority: str = Field(
        default="Central Reserve Police Force",
        min_length=1,
        max_length=255,
        description="Procuring entity or authority",
    )
    initial_version_label: str = Field(
        default="Initial Release",
        min_length=1,
        max_length=100,
        description="Label for the automatically created Version 1",
    )
    initial_change_summary: Optional[str] = Field(
        default="Original Tender Specification",
        description="Summary note for Version 1",
    )
    submission_deadline: Optional[datetime.datetime] = Field(
        default=None,
        description="Official submission deadline (UTC)",
    )


class TenderUpdate(BaseModel):
    """Payload to update editable tender metadata."""

    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated tender title",
    )
    description: Optional[str] = Field(
        default=None,
        description="Updated tender description",
    )
    issuing_authority: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated issuing authority",
    )
    status: Optional[TenderStatus] = Field(
        default=None,
        description="Lifecycle status transition (DRAFT, PUBLISHED, CLOSED, CANCELLED)",
    )
    submission_deadline: Optional[datetime.datetime] = Field(
        default=None,
        description="Updated submission deadline (UTC)",
    )


class TenderResponse(BaseModel):
    """Response model for tender details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_number: str
    title: str
    description: Optional[str] = None
    issuing_authority: str
    status: TenderStatus
    submission_deadline: Optional[datetime.datetime] = None
    created_by: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
    active_version: Optional[TenderVersionResponse] = None


class TenderListResponse(BaseModel):
    """Paginated response containing multiple tenders."""

    items: List[TenderResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
