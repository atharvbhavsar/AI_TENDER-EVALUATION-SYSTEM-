import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.bidders import service
from app.bidders.schemas import (
    ApplicationDetailResponse,
    ApplicationListResponse,
    ApplicationSummaryItem,
    BidderDashboardResponse,
    BidderDocumentResponse,
    BidderProfileResponse,
    DocumentDeleteResponse,
    SubmitApplicationRequest,
    UpdateApplicationDraftRequest,
    UpdateBidderProfileRequest,
)
from app.db.models.bid_submission import SubmissionStatus
from app.db.models.document import DocumentType
from app.db.models.user import User
from app.db.session import get_db
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

router = APIRouter(prefix="/bidder", tags=["Bidder Portal"])


@router.get(
    "/profile",
    response_model=BidderProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Bidder Corporate Profile",
)
def get_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> BidderProfileResponse:
    """Retrieve profile and application metrics for the authenticated bidder."""
    return service.get_bidder_profile(db=db, current_user=current_user)


@router.patch(
    "/profile",
    response_model=BidderProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Bidder Profile",
)
def update_profile(
    payload: UpdateBidderProfileRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> BidderProfileResponse:
    """Update representative name, company name, or contact phone."""
    return service.update_bidder_profile(db=db, current_user=current_user, payload=payload)


@router.get(
    "/dashboard",
    response_model=BidderDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="Bidder Command Center Dashboard Metrics",
)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> BidderDashboardResponse:
    """Retrieve operational dashboard statistics based exclusively on real backend data."""
    return service.get_bidder_dashboard(db=db, current_user=current_user)


@router.get(
    "/applications",
    response_model=ApplicationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List My Applications",
)
def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[SubmissionStatus] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> ApplicationListResponse:
    """Retrieve applications belonging strictly to the authenticated bidder."""
    items, total = service.list_bidder_applications(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        status=status,
    )
    return ApplicationListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Application Details & Checklist",
)
def get_application(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> ApplicationDetailResponse:
    """
    Retrieve application details, tender specs, and mandatory checklist requirements.
    STRICT DATA ISOLATION: Rejects access with HTTP 404 if application belongs to another bidder.
    """
    app_detail = service.get_bidder_application(
        db=db, current_user=current_user, application_id=application_id
    )
    if not app_detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found or access denied.",
        )
    return app_detail


@router.post(
    "/apply/{tender_id}",
    response_model=ApplicationSummaryItem,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for Tender",
)
def apply_to_tender(
    tender_id: uuid.UUID,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> ApplicationSummaryItem:
    """
    Bidder registers an application against an open published tender.
    If an application already exists for this tender, returns the existing record with HTTP 200 OK.
    Fails with HTTP 400 if tender is DRAFT, CLOSED, or expired.
    """
    try:
        submission, is_created = service.apply_for_tender(
            db=db, current_user=current_user, tender_id=tender_id
        )
        if not is_created:
            response.status_code = status.HTTP_200_OK
        return service._build_application_summary(submission)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Save Draft Application Details",
)
def update_application_draft(
    application_id: uuid.UUID,
    payload: UpdateApplicationDraftRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> ApplicationDetailResponse:
    """
    Save draft updates (bidder remarks, commercial quote, declaration).
    Rejects with HTTP 404 for IDOR, or HTTP 400 if locked, expired, or closed.
    """
    try:
        return service.update_bidder_application_draft(
            db=db,
            current_user=current_user,
            application_id=application_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/applications/{application_id}/submit",
    response_model=ApplicationDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Formally Submit Bid Application",
)
def submit_application(
    application_id: uuid.UUID,
    payload: SubmitApplicationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> ApplicationDetailResponse:
    """
    Formally submit and seal the bidder's application.
    Validates server deadline, tender status, and declaration, and permanently locks the application.
    Rejects with HTTP 404 for IDOR, or HTTP 400 if expired, already submitted, or invalid.
    """
    try:
        return service.submit_bidder_application(
            db=db,
            current_user=current_user,
            application_id=application_id,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post(
    "/applications/{application_id}/documents",
    response_model=BidderDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Requirement or Supporting Document for Application",
)
async def upload_application_document(
    application_id: uuid.UUID,
    file: UploadFile = File(...),
    criterion_id: Optional[uuid.UUID] = Form(None),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> BidderDocumentResponse:
    """
    Upload and ingest a document for an application:
    - Strictly isolated to the authenticated bidder (404 on IDOR).
    - Validates file format, MIME type, size limit, and magic bytes.
    - Locks upload if application is submitted or tender deadline has passed.
    - Associates document with tender, version, submission, user, and requirement.
    """
    try:
        doc = await service.upload_bidder_document(
            db=db,
            current_user=current_user,
            application_id=application_id,
            file=file,
            storage=storage,
            criterion_id=criterion_id,
            document_type=document_type,
        )
        return BidderDocumentResponse.model_validate(doc)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/applications/{application_id}/documents",
    response_model=List[BidderDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Documents for an Application",
)
def list_application_documents(
    application_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
) -> List[BidderDocumentResponse]:
    """
    Retrieve all documents associated with an application.
    STRICT DATA ISOLATION: 404 if application does not belong to authenticated bidder.
    """
    try:
        docs = service.list_bidder_documents(
            db=db, current_user=current_user, application_id=application_id
        )
        return [BidderDocumentResponse.model_validate(d) for d in docs]
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/applications/{application_id}/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Securely Stream Application Document Binary",
)
def download_application_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> StreamingResponse:
    """
    Download a document binary stream with strict bidder authorization.
    Rejects with 404 if application or document belongs to another bidder (IDOR safe).
    Never exposes internal storage URLs or credentials.
    """
    try:
        document, stream = service.get_bidder_document_stream(
            db=db,
            current_user=current_user,
            application_id=application_id,
            document_id=document_id,
            storage=storage,
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
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.delete(
    "/applications/{application_id}/documents/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete an Application Document",
)
def delete_application_document(
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("BIDDER_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> DocumentDeleteResponse:
    """
    Delete a document from an application:
    - IDOR safe: 404 if application or document not owned by bidder.
    - Rejects with 400 if application is submitted or deadline passed.
    """
    try:
        return service.delete_bidder_document(
            db=db,
            current_user=current_user,
            application_id=application_id,
            document_id=document_id,
            storage=storage,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


