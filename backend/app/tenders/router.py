"""FastAPI router for Tender Management and Versioning."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permissions
from app.db.models.tender import TenderStatus
from app.db.models.user import User
from app.db.session import get_db
from app.tenders.schemas import (
    TenderCreate,
    TenderListResponse,
    TenderResponse,
    TenderUpdate,
    TenderVersionCreate,
    TenderVersionResponse,
)
from app.tenders import service

router = APIRouter(prefix="/tenders", tags=["Tenders"])


@router.post(
    "",
    response_model=TenderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Tender",
    description="Create a new procurement tender and initialize Version 1 atomically.",
)
async def create_tender(
    payload: TenderCreate,
    current_user: User = Depends(require_permissions("TENDER_CREATE")),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Create tender endpoint requiring TENDER_CREATE permission."""
    try:
        tender = service.create_tender(db, payload=payload, user_id=current_user.id)
        return TenderResponse.model_validate(tender)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        )


@router.get(
    "",
    response_model=TenderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Tenders",
    description="Retrieve a paginated list of tenders with optional status filtering.",
)
async def list_tenders(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Page size"),
    status: Optional[TenderStatus] = Query(default=None, description="Filter by tender status"),
    current_user: User = Depends(require_permissions("TENDER_READ")),
    db: Session = Depends(get_db),
) -> TenderListResponse:
    """List tenders endpoint requiring TENDER_READ permission."""
    items, total, total_pages = service.list_tenders(
        db, page=page, page_size=page_size, status_filter=status
    )
    return TenderListResponse(
        items=[TenderResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Tender Details",
    description="Retrieve full tender details including current active version and creator metadata.",
)
async def get_tender(
    tender_id: uuid.UUID,
    current_user: User = Depends(require_permissions("TENDER_READ")),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Get tender details endpoint."""
    tender = service.get_tender(db, tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found",
        )
    return TenderResponse.model_validate(tender)


@router.patch(
    "/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Tender Metadata",
    description="Update editable tender metadata (title, description, authority, status).",
)
async def update_tender(
    tender_id: uuid.UUID,
    payload: TenderUpdate,
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Update tender endpoint requiring TENDER_UPDATE permission."""
    try:
        tender = service.update_tender(db, tender_id=tender_id, payload=payload)
        return TenderResponse.model_validate(tender)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found",
        )


@router.post(
    "/{tender_id}/versions",
    response_model=TenderVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create New Tender Version",
    description="Create a new sequential tender version (Corrigendum) while preserving historical versions.",
)
async def create_tender_version(
    tender_id: uuid.UUID,
    payload: TenderVersionCreate,
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
    db: Session = Depends(get_db),
) -> TenderVersionResponse:
    """Create tender version endpoint requiring TENDER_UPDATE permission."""
    try:
        version = service.create_tender_version(
            db, tender_id=tender_id, payload=payload, user_id=current_user.id
        )
        return TenderVersionResponse.model_validate(version)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found",
        )


@router.get(
    "/{tender_id}/versions",
    response_model=List[TenderVersionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Tender Versions",
    description="Retrieve all historical and active versions belonging to a tender.",
)
async def list_tender_versions(
    tender_id: uuid.UUID,
    current_user: User = Depends(require_permissions("TENDER_READ")),
    db: Session = Depends(get_db),
) -> List[TenderVersionResponse]:
    """List tender versions endpoint."""
    try:
        versions = service.list_tender_versions(db, tender_id=tender_id)
        return [TenderVersionResponse.model_validate(v) for v in versions]
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found",
        )


@router.get(
    "/{tender_id}/versions/{version_number}",
    response_model=TenderVersionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Specific Tender Version",
    description="Retrieve a specific historical version number of a tender.",
)
async def get_tender_version(
    tender_id: uuid.UUID,
    version_number: int,
    current_user: User = Depends(require_permissions("TENDER_READ")),
    db: Session = Depends(get_db),
) -> TenderVersionResponse:
    """Get specific tender version endpoint."""
    tender = service.get_tender(db, tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found",
        )

    version = service.get_tender_version(
        db, tender_id=tender_id, version_number=version_number
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_number} for Tender '{tender_id}' not found",
        )
    return TenderVersionResponse.model_validate(version)
