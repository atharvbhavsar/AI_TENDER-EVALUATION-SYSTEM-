"""Pydantic schemas and DTOs for Bidder, Submission, and Evidence domain."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.db.models.bid_submission import SubmissionStatus
from app.db.models.evidence import EvidenceStatus
from app.db.models.extraction_run import ExtractionRunStatus


# --- Bidder Schemas ---

class BidderBase(BaseModel):
    """Base fields for a Bidder."""

    bidder_code: str = Field(..., min_length=2, max_length=50, description="Unique code for bidder within tender")
    legal_name: str = Field(..., min_length=2, max_length=255, description="Official legal entity name")
    contact_email: Optional[str] = Field(None, max_length=255, description="Official contact email")
    contact_phone: Optional[str] = Field(None, max_length=50, description="Contact phone number")


class BidderCreate(BidderBase):
    """Payload to create a new bidder for a tender."""

    pass


class BidderUpdate(BaseModel):
    """Payload to update an existing bidder."""

    legal_name: Optional[str] = Field(None, min_length=2, max_length=255)
    contact_email: Optional[str] = Field(None, max_length=255)
    contact_phone: Optional[str] = Field(None, max_length=50)


class BidderResponse(BidderBase):
    """Response DTO for Bidder entity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime


class BidderListResponse(BaseModel):
    """Paginated/listed bidders response."""

    items: List[BidderResponse]
    total: int


# --- Submission Schemas ---

class BidSubmissionCreate(BaseModel):
    """Payload to submit a bid response against a tender version."""

    submission_reference: str = Field(..., min_length=3, max_length=100, description="Unique submission reference")


class BidSubmissionResponse(BaseModel):
    """Response DTO for BidSubmission entity."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_version_id: uuid.UUID
    bidder_id: uuid.UUID
    submission_reference: str
    status: SubmissionStatus
    document_count: Optional[int] = 0
    created_at: datetime.datetime
    updated_at: datetime.datetime


class BidSubmissionListResponse(BaseModel):
    """Paginated/listed submissions response."""

    items: List[BidSubmissionResponse]
    total: int


# --- Raw LLM Extraction Schemas ---

class CertificateDetailsRaw(BaseModel):
    """Extracted certificate metadata."""

    certificate_name: Optional[str] = None
    certificate_number: Optional[str] = None
    issuing_authority: Optional[str] = None
    issue_date: Optional[str] = None
    expiry_date: Optional[str] = None
    holder_name: Optional[str] = None
    scope: Optional[str] = None


class ExperienceDetailsRaw(BaseModel):
    """Extracted project/work order experience metadata."""

    project_name: Optional[str] = None
    client_name: Optional[str] = None
    work_order_number: Optional[str] = None
    project_value: Optional[float] = None
    currency: Optional[str] = None
    completion_date: Optional[str] = None
    duration_months: Optional[int] = None


class RawEvidenceItem(BaseModel):
    """Structured evidence item candidate extracted by LLM."""

    criterion_code: str = Field(..., description="Target approved criterion code (e.g. FIN-001)")
    evidence_found: bool = Field(..., description="Whether evidence was identified")
    evidence_type: str = Field(default="DOCUMENT", description="DOCUMENT / FINANCIAL / CERTIFICATE / EXPERIENCE")
    extracted_text: Optional[str] = Field(None, description="Exact verbatim text snippet from document")
    extracted_value: Optional[float] = Field(None, description="Numeric threshold value if applicable")
    normalized_value: Optional[str] = Field(None, description="Standardized string representation of the value")
    unit: Optional[str] = Field(None, description="Measurement unit (e.g. Crore, Lakh, Year)")
    currency: Optional[str] = Field(None, description="ISO Currency code (INR, USD)")
    period: Optional[str] = Field(None, description="Period or Financial Year (e.g. FY 2023-24)")
    date_value: Optional[str] = Field(None, description="ISO-formatted date string if applicable")
    certificate_data: Optional[CertificateDetailsRaw] = None
    experience_data: Optional[ExperienceDetailsRaw] = None
    extracted_bidder_name: Optional[str] = Field(None, description="Entity name mentioned on the evidence document")
    status: EvidenceStatus = Field(default=EvidenceStatus.FOUND, description="FOUND / MISSING / UNREADABLE / CONFLICTING / AMBIGUOUS / INVALID")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence score (0.0 to 1.0)")
    source_page: Optional[int] = Field(None, description="Page number where evidence appears")
    source_block_id: Optional[str] = Field(None, description="Block ID in processed document")
    source_table_reference: Optional[str] = Field(None, description="Table reference if evidence extracted from a table")
    bbox: Optional[List[float]] = Field(None, description="Bounding box [x1, y1, x2, y2]")
    ambiguity_reason: Optional[str] = Field(None, description="Explanation if evidence is ambiguous, unreadable, or missing")


class RawEvidenceExtractionResponse(BaseModel):
    """Top-level structured output schema for evidence extraction from document chunks."""

    extracted_items: List[RawEvidenceItem] = Field(default_factory=list)


# --- API DTOs for Evidence & Runs ---

class EvidenceResponse(BaseModel):
    """Response DTO for a single Evidence record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    criterion_id: uuid.UUID
    bid_submission_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    document_name: Optional[str] = None
    criterion_code: Optional[str] = None
    criterion_name: Optional[str] = None
    evidence_type: str
    extracted_text: Optional[str] = None
    extracted_value: Optional[float] = None
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    date_value: Optional[str] = None
    certificate_data: Optional[Dict[str, Any]] = None
    experience_data: Optional[Dict[str, Any]] = None
    extracted_bidder_name: Optional[str] = None
    status: EvidenceStatus
    confidence: float
    source_page: Optional[int] = None
    source_block_id: Optional[str] = None
    source_table_reference: Optional[str] = None
    bbox: Optional[List[float]] = None
    validation_notes: Optional[str] = None
    extraction_run_id: uuid.UUID
    extractor_version: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class EvidenceListResponse(BaseModel):
    """Response DTO for list of evidence records."""

    items: List[EvidenceResponse]
    total: int


class EvidenceExtractionTriggerRequest(BaseModel):
    """Request payload to trigger evidence extraction for a submission."""

    criterion_id: Optional[uuid.UUID] = Field(
        None, description="Optional specific approved criterion ID; if omitted, extracts against all approved criteria"
    )


class EvidenceExtractionRunResponse(BaseModel):
    """Response DTO for an EvidenceExtractionRun."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bid_submission_id: uuid.UUID
    criterion_id: Optional[uuid.UUID] = None
    model_name: str
    model_version: str
    prompt_version: str
    extractor_version: str
    status: ExtractionRunStatus
    evidence_count: int
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime
