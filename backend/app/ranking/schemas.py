"""Pydantic schemas for Multi-Bidder Tender Evaluation and Deterministic Ranking."""

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.tender_evaluation_method import EvaluationMethodType, RankingDirection
from app.db.models.bidder_ranking import RankingStatus


class TenderEvaluationMethodCreate(BaseModel):
    """Payload to configure or override the tender evaluation methodology."""

    method_type: EvaluationMethodType = Field(
        default=EvaluationMethodType.L1,
        description="Evaluation method: L1, QCBS, TECHNICAL_SCORE, WEIGHTED_TECHNICAL_FINANCIAL, or TENDER_DEFINED",
    )
    description: Optional[str] = Field(
        default=None, description="Detailed description or tender clause reference"
    )
    financial_weight: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Financial weight for QCBS (e.g. 0.30)"
    )
    technical_weight: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Technical weight for QCBS (e.g. 0.70)"
    )
    minimum_technical_score: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Minimum qualifying technical score"
    )
    ranking_direction: RankingDirection = Field(
        default=RankingDirection.ASCENDING,
        description="Ranking direction: ASCENDING (lowest price first) or DESCENDING (highest score first)",
    )
    currency: str = Field(default="INR", max_length=10)
    tie_breaker_rule: Optional[str] = Field(
        default="HUMAN_REVIEW", description="Deterministic tie-breaker policy"
    )


class TenderEvaluationMethodResponse(BaseModel):
    """Schema representing an active tender evaluation method."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tender_id: uuid.UUID
    tender_version_id: uuid.UUID
    method_type: EvaluationMethodType
    description: Optional[str] = None
    financial_weight: Optional[float] = None
    technical_weight: Optional[float] = None
    minimum_technical_score: Optional[float] = None
    ranking_direction: RankingDirection
    currency: str
    tie_breaker_rule: Optional[str] = None
    version: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


class BidderRankingItem(BaseModel):
    """Auditable ranking result for an individual bidder."""

    model_config = ConfigDict(from_attributes=True)

    id: Optional[uuid.UUID] = None
    bidder_id: uuid.UUID
    bidder_name: str
    bid_submission_id: uuid.UUID
    eligibility_status: EvaluationResult
    quoted_price: Optional[float] = None
    evaluated_price: Optional[float] = None
    technical_score: Optional[float] = None
    financial_score: Optional[float] = None
    combined_score: Optional[float] = None
    rank: Optional[int] = None
    rank_label: Optional[str] = None
    ranking_status: RankingStatus
    calculation_details: Dict[str, Any] = Field(default_factory=dict)
    provenance_metadata: Dict[str, Any] = Field(default_factory=dict)


class ComparativeEvaluationRequest(BaseModel):
    """Request to trigger deterministic comparative evaluation across all bidders."""

    evaluation_method: Optional[EvaluationMethodType] = None
    description: Optional[str] = None
    financial_weight: Optional[float] = None
    technical_weight: Optional[float] = None
    tie_breaker_rule: Optional[str] = None


class ComparativeEvaluationResponse(BaseModel):
    """Complete comparative evaluation report across all participating bidders."""

    model_config = ConfigDict(from_attributes=True)

    tender_id: uuid.UUID
    tender_version_id: uuid.UUID
    evaluation_run_id: uuid.UUID
    evaluation_method: EvaluationMethodType
    method_description: Optional[str] = None
    evaluation_date: datetime.datetime
    total_bidders: int
    eligible_count: int
    not_eligible_count: int
    manual_review_count: int
    ranked_count: int
    has_ties: bool = False
    rankings: List[BidderRankingItem]
    audit_event_id: Optional[uuid.UUID] = None
