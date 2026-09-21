"""Audit Pydantic schemas for Phase 16."""

import datetime
import enum
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class IntegrityStatus(str, enum.Enum):
    """Controlled document integrity verification status."""

    VERIFIED = "VERIFIED"
    MISMATCH = "MISMATCH"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"


class DocumentIntegrityResponse(BaseModel):
    """Schema for document cryptographic SHA-256 integrity verification results."""

    model_config = ConfigDict(from_attributes=True)

    document_id: uuid.UUID
    filename: str
    stored_sha256: str
    computed_sha256: Optional[str] = None
    integrity_status: IntegrityStatus
    verified_at: datetime.datetime
    message: str


class AuditLogResponse(BaseModel):
    """Schema for returning structured audit log records."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime.datetime
    actor_id: Optional[uuid.UUID] = None
    actor_role: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    tender_id: Optional[uuid.UUID] = None
    tender_version_id: Optional[uuid.UUID] = None
    bidder_id: Optional[uuid.UUID] = None
    bid_submission_id: Optional[uuid.UUID] = None
    criterion_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    evidence_id: Optional[uuid.UUID] = None
    evaluation_id: Optional[uuid.UUID] = None
    review_id: Optional[uuid.UUID] = None
    document_hash: Optional[str] = None
    previous_state: Optional[Dict[str, Any]] = None
    new_state: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    correlation_id: Optional[str] = None
    source_service: Optional[str] = None
    metadata_json: Dict[str, Any] = Field(default_factory=dict)


class AuditLogFilter(BaseModel):
    """Filter parameters for querying audit records."""

    tender_id: Optional[uuid.UUID] = None
    tender_version_id: Optional[uuid.UUID] = None
    bidder_id: Optional[uuid.UUID] = None
    bid_submission_id: Optional[uuid.UUID] = None
    criterion_id: Optional[uuid.UUID] = None
    document_id: Optional[uuid.UUID] = None
    evidence_id: Optional[uuid.UUID] = None
    evaluation_id: Optional[uuid.UUID] = None
    review_id: Optional[uuid.UUID] = None
    actor_id: Optional[uuid.UUID] = None
    action: Optional[str] = None
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class AuditListResponse(BaseModel):
    """Paginated response for audit logs."""

    items: List[AuditLogResponse]
    total: int
    limit: int
    offset: int


# Provenance Lineage Schemas

class EvidenceProvenanceDetail(BaseModel):
    """Detailed provenance for an evidence record."""

    evidence_id: uuid.UUID
    criterion_id: uuid.UUID
    document_id: Optional[uuid.UUID] = None
    document_filename: Optional[str] = None
    document_sha256: Optional[str] = None
    extracted_text: Optional[str] = None
    extracted_value: Optional[float] = None
    normalized_value: Optional[str] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    source_page: Optional[int] = None
    source_block_id: Optional[str] = None
    source_table_reference: Optional[str] = None
    bbox: Optional[List[float]] = None
    status: str
    confidence: float
    extractor_version: str
    created_at: datetime.datetime


class CriterionProvenanceDetail(BaseModel):
    """Detailed provenance for an approved criterion in evaluation."""

    criterion_id: uuid.UUID
    code: str
    title: str
    criterion_type: str
    is_mandatory: bool
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    source_clause: Optional[str] = None
    source_block_id: Optional[str] = None
    rule_version: Optional[str] = None
    policy_version: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[float] = None
    threshold_unit: Optional[str] = None
    threshold_currency: Optional[str] = None
    evaluation_result: Optional[str] = None
    evidence_items: List[EvidenceProvenanceDetail] = Field(default_factory=list)


class DecisionProvenanceDetail(BaseModel):
    """Provenance for human officer override/confirm decision."""

    review_case_id: uuid.UUID
    decision: str
    system_result: str
    final_verdict: Optional[str] = None
    reason: str
    officer_id: uuid.UUID
    officer_name: Optional[str] = None
    created_at: datetime.datetime


class DocumentProvenanceDetail(BaseModel):
    """Provenance for an uploaded document."""

    document_id: uuid.UUID
    filename: str
    content_type: str
    file_size: int
    sha256_hash: str
    storage_key: str
    processing_status: str
    uploaded_by: uuid.UUID
    uploaded_at: datetime.datetime


class SubmissionProvenanceResponse(BaseModel):
    """Complete end-to-end lineage and provenance graph for a bid submission."""

    submission_id: uuid.UUID
    submission_number: str
    tender_id: uuid.UUID
    tender_title: str
    tender_version_id: uuid.UUID
    tender_version_number: int
    bidder_id: uuid.UUID
    bidder_name: str
    submission_status: str
    submitted_at: datetime.datetime
    overall_evaluation_result: Optional[str] = None
    documents: List[DocumentProvenanceDetail] = Field(default_factory=list)
    criteria: List[CriterionProvenanceDetail] = Field(default_factory=list)
    human_decisions: List[DecisionProvenanceDetail] = Field(default_factory=list)
    audit_events_count: int
