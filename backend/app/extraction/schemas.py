"""Pydantic schemas for AI criterion extraction and API responses."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models.extraction_run import ExtractionRunStatus
from app.db.models.tender_criterion import (
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
)


class ExtractedSourceRefRaw(BaseModel):
    """Raw source reference extracted from document content."""

    page_number: Optional[int] = None
    section: Optional[str] = None
    block_id: Optional[str] = None
    table_reference: Optional[str] = None
    bbox: Optional[Dict[str, Any]] = None
    source_text: str = Field(..., min_length=1)


class ExtractedCriterionRaw(BaseModel):
    """Raw structured criterion extracted by the LLM or rules engine before persistence."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="Tender requirement", min_length=1)
    category: CriterionCategory = CriterionCategory.COMPLIANCE
    requirement_type: RequirementType = RequirementType.MANDATORY
    condition_text: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[float] = None
    threshold_text: Optional[str] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    mandatory: Optional[bool] = None
    required_evidence: Optional[List[str]] = None
    source_clause: str = Field(default="Extracted from tender document", min_length=1)
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    source_block_id: Optional[str] = None
    source_table_reference: Optional[str] = None
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    extraction_status: ExtractionStatus = ExtractionStatus.EXTRACTED
    explanation: Optional[str] = None
    additional_sources: List[ExtractedSourceRefRaw] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sanitize_raw_llm_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            name = data.get("name") or "Procurement Requirement"
            if not data.get("name"):
                data["name"] = name
            if not data.get("description"):
                data["description"] = name
            if not data.get("source_clause"):
                data["source_clause"] = data.get("description") or name
            if not data.get("category"):
                data["category"] = "COMPLIANCE"
            if not data.get("requirement_type"):
                data["requirement_type"] = "MANDATORY"
        return data


class RawExtractionResponse(BaseModel):
    """Schema representing structured output produced from LLM for a context chunk."""

    criteria: List[ExtractedCriterionRaw] = Field(default_factory=list)


class CriterionSourceReferenceResponse(BaseModel):
    """API response schema for criterion source attribution."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    criterion_id: uuid.UUID
    document_id: uuid.UUID
    page_number: Optional[int] = None
    section: Optional[str] = None
    block_id: Optional[str] = None
    table_reference: Optional[str] = None
    bbox: Optional[Dict[str, Any]] = None
    source_text: str
    created_at: datetime.datetime


class TenderCriterionResponse(BaseModel):
    """API response schema for a structured tender criterion."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_version_id: uuid.UUID
    extraction_run_id: Optional[uuid.UUID] = None
    criterion_code: str
    name: str
    description: str
    category: CriterionCategory
    requirement_type: RequirementType
    condition_text: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[float] = None
    threshold_text: Optional[str] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    period: Optional[str] = None
    mandatory: Optional[bool] = None
    required_evidence: Optional[List[str]] = None
    source_clause: str
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    source_block_id: Optional[str] = None
    source_table_reference: Optional[str] = None
    confidence: float
    extraction_status: ExtractionStatus
    explanation: Optional[str] = None
    model_name: str
    model_version: str
    prompt_version: str

    # Phase 8: Approval Lifecycle Fields
    approval_status: str
    approved_by: Optional[uuid.UUID] = None
    approved_at: Optional[datetime.datetime] = None
    rejection_reason: Optional[str] = None
    is_corrected: bool = False

    # Original AI Extraction Snapshot
    original_name: Optional[str] = None
    original_description: Optional[str] = None
    original_category: Optional[CriterionCategory] = None
    original_requirement_type: Optional[RequirementType] = None
    original_operator: Optional[str] = None
    original_threshold_value: Optional[float] = None
    original_threshold_text: Optional[str] = None
    original_unit: Optional[str] = None
    original_currency: Optional[str] = None
    original_period: Optional[str] = None
    original_mandatory: Optional[bool] = None
    original_required_evidence: Optional[List[str]] = None
    original_source_clause: Optional[str] = None

    created_at: datetime.datetime
    updated_at: datetime.datetime
    source_references: List[CriterionSourceReferenceResponse] = Field(default_factory=list)


class TenderCriterionListResponse(BaseModel):
    """API paginated response for candidate criteria."""

    items: List[TenderCriterionResponse]
    total: int
    page: int
    size: int


class ExtractionRunResponse(BaseModel):
    """API response schema for an extraction run."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_version_id: uuid.UUID
    model_name: str
    model_version: str
    prompt_version: str
    extractor_version: str
    status: ExtractionRunStatus
    criteria_count: int
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_by: uuid.UUID
    created_at: datetime.datetime


class TriggerExtractionRequest(BaseModel):
    """Request payload to initiate AI extraction for a tender version."""

    model_name: Optional[str] = None
    prompt_version: Optional[str] = None
