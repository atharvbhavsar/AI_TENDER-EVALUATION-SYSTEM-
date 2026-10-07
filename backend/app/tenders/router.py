"""FastAPI router for Tender Management and Versioning."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
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
    "/public",
    response_model=TenderListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Public Tenders",
    description="Retrieve a paginated list of publicly visible tenders (PUBLISHED or CLOSED) without authentication.",
)
async def list_public_tenders(
    search: Optional[str] = Query(default=None, description="Search by tender number or title"),
    status: Optional[TenderStatus] = Query(default=None, description="Filter by tender status (PUBLISHED or CLOSED)"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=10, ge=1, le=100, description="Page size"),
    db: Session = Depends(get_db),
) -> TenderListResponse:
    """Public tenders listing endpoint accessible without authentication."""
    items, total, total_pages = service.list_public_tenders(
        db, search=search, status_filter=status, page=page, page_size=page_size
    )
    return TenderListResponse(
        items=[TenderResponse.model_validate(t) for t in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get(
    "/public/{tender_id}",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Public Tender Details",
    description="Retrieve details of a published or closed tender without authentication. Draft tenders return 404.",
)
async def get_public_tender(
    tender_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Public tender detail endpoint."""
    tender = service.get_public_tender(db, tender_id=tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender is not publicly available or does not exist.",
        )
    return TenderResponse.model_validate(tender)


@router.get(
    "/public/{tender_id}/documents",
    status_code=status.HTTP_200_OK,
    summary="List Public Tender Documents",
    description="List publicly downloadable documents (NIT, specifications) for a published tender.",
)
async def list_public_tender_documents(
    tender_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """List public tender documents."""
    tender = service.get_public_tender(db, tender_id=tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender is not publicly available or does not exist.",
        )
    from app.documents.service import list_documents_for_version

    active_version = tender.active_version
    if not active_version:
        return {"items": [], "total": 0}

    docs, total = list_documents_for_version(
        db=db,
        tender_id=tender.id,
        tender_version_id=active_version.id,
    )
    return {
        "items": [
            {
                "id": str(d.id),
                "filename": d.filename,
                "file_extension": d.file_extension,
                "file_size": d.file_size,
                "document_type": d.document_type.value,
                "created_at": d.created_at.isoformat(),
            }
            for d in docs
        ],
        "total": total,
    }


@router.get(
    "/public/{tender_id}/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download Public Tender Document",
    description="Securely download a published procurement document without exposing storage credentials.",
)
async def download_public_tender_document(
    tender_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Stream public tender document."""
    tender = service.get_public_tender(db, tender_id=tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tender is not publicly available.",
        )
    from app.documents import service as doc_service
    from app.storage.service import get_storage_service

    storage = get_storage_service()
    document, stream = doc_service.get_document_file_stream(
        db=db,
        document_id=document_id,
        storage=storage,
    )
    if document.tender_id != tender.id or document.bid_submission_id is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requested document is not a public tender document.",
        )

    def iter_stream():
        if hasattr(stream, "read"):
            while chunk := stream.read(64 * 1024):
                yield chunk
        elif hasattr(stream, "__iter__"):
            for chunk in stream:
                yield chunk

    headers = {
        "Content-Disposition": f'attachment; filename="{document.filename}"',
        "Content-Length": str(document.file_size),
    }
    return StreamingResponse(
        content=iter_stream(),
        media_type=document.content_type,
        headers=headers,
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


@router.post(
    "/{tender_id}/publish",
    response_model=TenderResponse,
    status_code=status.HTTP_200_OK,
    summary="Publish Tender",
    description="Transition tender status from DRAFT to PUBLISHED making it publicly visible to prospective bidders.",
)
async def publish_tender(
    tender_id: uuid.UUID,
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
    db: Session = Depends(get_db),
) -> TenderResponse:
    """Publish tender endpoint requiring TENDER_UPDATE permission."""
    try:
        tender = service.publish_tender(db, tender_id=tender_id)
        return TenderResponse.model_validate(tender)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


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
