"""API routes for AI Criterion Extraction."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.tender_criterion import (
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
)
from app.db.models.user import User
from app.db.session import get_db
from app.extraction.schemas import (
    CriterionSourceReferenceResponse,
    ExtractionRunResponse,
    TenderCriterionListResponse,
    TenderCriterionResponse,
)
from app.extraction.service import (
    extract_criteria_for_tender_version,
    get_criterion_by_id,
    get_latest_extraction_run,
    list_criteria_for_version,
)
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

router = APIRouter(prefix="/tenders/{tender_id}/versions/{version_id}/criteria", tags=["Criteria Extraction"])


@router.post(
    "/extract",
    response_model=ExtractionRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger AI Criterion Extraction for a Tender Version",
)
async def trigger_criteria_extraction(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> ExtractionRunResponse:
    """Trigger AI extraction of candidate eligibility criteria from processed tender documents."""
    run = await extract_criteria_for_tender_version(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        user=current_user,
        storage=storage,
    )
    return ExtractionRunResponse.model_validate(run)


@router.get(
    "/extraction-status",
    response_model=ExtractionRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Status of Latest AI Extraction Run",
)
def get_extraction_status(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> ExtractionRunResponse:
    """Retrieve status, model metadata, and criteria count for latest extraction run."""
    run = get_latest_extraction_run(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
    )
    return ExtractionRunResponse.model_validate(run)


@router.get(
    "",
    response_model=TenderCriterionListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Candidate Eligibility Criteria",
)
def list_criteria(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    category: Optional[CriterionCategory] = Query(None, description="Filter by criterion category"),
    requirement_type: Optional[RequirementType] = Query(None, description="Filter by requirement type"),
    extraction_status: Optional[ExtractionStatus] = Query(None, description="Filter by extraction status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> TenderCriterionListResponse:
    """List extracted candidate criteria for a specific tender version."""
    offset = (page - 1) * size
    items, total = list_criteria_for_version(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        category=category,
        requirement_type=requirement_type,
        extraction_status=extraction_status,
        limit=size,
        offset=offset,
    )
    return TenderCriterionListResponse(
        items=[TenderCriterionResponse.model_validate(i) for i in items],
        total=total,
        page=page,
        size=size,
    )


@router.get(
    "/{criterion_id}",
    response_model=TenderCriterionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Detailed Criterion Record with Source Traceability",
)
def get_criterion_detail(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    criterion_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
) -> TenderCriterionResponse:
    """Retrieve structured criterion detail including source clause and location references."""
    criterion = get_criterion_by_id(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        criterion_id=criterion_id,
    )
    return TenderCriterionResponse.model_validate(criterion)
