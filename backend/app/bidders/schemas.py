"""Pydantic schemas for Bidder Portal, Profile, and Applications."""

import datetime
import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models.bid_submission import SubmissionStatus


class BidderProfileResponse(BaseModel):
    """Bidder corporate profile details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    company_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    roles: List[str] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    created_at: datetime.datetime
    active_applications_count: int = 0


class UpdateBidderProfileRequest(BaseModel):
    """Payload to update bidder profile details."""

    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    company_name: Optional[str] = Field(None, min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)


class ApplicationSummaryItem(BaseModel):
    """Summary of a bidder application / submission."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_reference: str
    status: SubmissionStatus
    tender_id: uuid.UUID
    tender_number: str
    tender_title: str
    issuing_authority: str
    tender_status: str
    tender_version_id: uuid.UUID
    version_number: int
    version_label: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    documents_count: int = 0
    bidder_notes: Optional[str] = None
    commercial_quote: Optional[float] = None
    declaration_signed: bool = False
    submitted_at: Optional[datetime.datetime] = None
    is_locked: bool = False
    submission_deadline: Optional[datetime.datetime] = None


class ApplicationListResponse(BaseModel):
    """Paginated list of bidder applications."""

    items: List[ApplicationSummaryItem]
    total: int
    page: int
    page_size: int


class CriterionChecklistItem(BaseModel):
    """Checklist requirement item for prospective bidders."""

    id: uuid.UUID
    criterion_code: str
    name: str
    description: Optional[str] = None
    category: str
    mandatory: bool
    required_evidence: Optional[str] = None


class BidderDocumentResponse(BaseModel):
    """Uploaded procurement document for bidder application."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_version_id: uuid.UUID
    bid_submission_id: Optional[uuid.UUID] = None
    criterion_id: Optional[uuid.UUID] = None
    filename: str
    content_type: str
    file_extension: str
    file_size: int
    sha256_hash: str
    document_type: str
    processing_status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class DocumentDeleteResponse(BaseModel):
    """Confirmation payload for document removal."""

    success: bool = True
    message: str


class ApplicationDetailResponse(BaseModel):
    """Full application details including tender specifications, draft data, requirements checklist, and uploaded documents."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    submission_reference: str
    status: SubmissionStatus
    created_at: datetime.datetime
    updated_at: datetime.datetime

    # Draft / Submission Fields
    bidder_notes: Optional[str] = None
    commercial_quote: Optional[float] = None
    declaration_signed: bool = False
    submitted_at: Optional[datetime.datetime] = None
    is_locked: bool = False

    # Tender Info
    tender_id: uuid.UUID
    tender_number: str
    tender_title: str
    tender_description: Optional[str] = None
    issuing_authority: str
    tender_status: str
    submission_deadline: Optional[datetime.datetime] = None
    is_deadline_passed: bool = False
    can_edit: bool = True
    can_submit: bool = True

    # Version Info
    tender_version_id: uuid.UUID
    version_number: int
    version_label: str

    # Requirements Checklist & Uploaded Documents
    criteria_checklist: List[CriterionChecklistItem] = Field(default_factory=list)
    documents: List[BidderDocumentResponse] = Field(default_factory=list)
    documents_count: int = 0


class UpdateApplicationDraftRequest(BaseModel):
    """Payload to update editable draft application attributes."""

    bidder_notes: Optional[str] = Field(None, max_length=5000, description="Application remarks or technical response notes")
    commercial_quote: Optional[float] = Field(None, ge=0, description="Proposed total commercial quote in INR")
    declaration_signed: Optional[bool] = Field(None, description="Declaration of RFP compliance and accurate disclosures")


class SubmitApplicationRequest(BaseModel):
    """Payload for final application submission confirmation."""

    confirm_declaration: bool = Field(True, description="Explicit statutory affirmation of tender compliance")
    bidder_notes: Optional[str] = Field(None, max_length=5000, description="Final submission remarks")
    commercial_quote: Optional[float] = Field(None, ge=0, description="Final commercial quote in INR")


class BidderDashboardResponse(BaseModel):
    """Summary metrics for bidder command center."""

    company_name: str
    full_name: str
    total_applications: int
    draft_count: int = 0
    submitted_count: int = 0
    received_count: int = 0
    processing_count: int = 0
    ready_count: int = 0
    review_count: int = 0
    available_tenders_count: int
    recent_applications: List[ApplicationSummaryItem] = Field(default_factory=list)

