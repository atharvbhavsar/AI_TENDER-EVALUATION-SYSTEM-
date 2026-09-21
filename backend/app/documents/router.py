"""Document ingestion, retrieval, and secure download API router."""

import uuid
from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.document import DocumentType
from app.db.models.user import User
from app.db.session import get_db
from app.audit.schemas import DocumentIntegrityResponse
from app.documents import service
from app.documents.schemas import DocumentListResponse, DocumentResponse
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

router = APIRouter(tags=["Documents"])


@router.post(
    "/tenders/{tender_id}/versions/{version_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a procurement document",
)
async def upload_document(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: DocumentType = Form(DocumentType.UNKNOWN),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_UPLOAD")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> DocumentResponse:
    """
    Ingest and store an authorized procurement document:
    - Validates tender and tender_version existence.
    - Validates file format, magic bytes, MIME, and size limits.
    - Stores file binary in S3/MinIO object storage.
    - Persists document metadata in PostgreSQL.
    """
    document = await service.ingest_document(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        file=file,
        current_user=current_user,
        storage=storage,
        document_type=document_type,
    )
    return DocumentResponse.model_validate(document)


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve document metadata",
)
def get_document_metadata(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
) -> DocumentResponse:
    """Retrieve metadata for an ingested document by UUID."""
    document = service.get_document_by_id(db=db, document_id=document_id)
    return DocumentResponse.model_validate(document)


@router.get(
    "/documents/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Securely download document binary file",
)
def download_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> StreamingResponse:
    """
    Download a document binary via backend-mediated secure stream.
    Credentials and direct storage URLs are never exposed to clients.
    """
    document, stream = service.get_document_file_stream(
        db=db,
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


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/documents",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List documents for a tender version",
)
def list_tender_version_documents(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
) -> DocumentListResponse:
    """List all documents ingested under a specific tender version."""
    items, total = service.list_documents_for_version(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        limit=limit,
        offset=offset,
    )
    return DocumentListResponse(
        items=[DocumentResponse.model_validate(doc) for doc in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/documents/{document_id}/verify-integrity",
    response_model=DocumentIntegrityResponse,
    status_code=status.HTTP_200_OK,
    summary="Cryptographically verify document SHA-256 integrity against object storage",
)
def verify_document_integrity_endpoint(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> DocumentIntegrityResponse:
    """
    Verify stored document against raw binary in object storage:
    - Calculates current SHA-256 from object storage stream.
    - Compares against stored metadata hash.
    - Emits audit event for verification / mismatch.
    - Returns structured integrity status (VERIFIED, MISMATCH, UNAVAILABLE).
    """
    from app.documents.integrity import verify_document_integrity
    return verify_document_integrity(
        db=db,
        document_id=document_id,
        storage=storage,
        current_user=current_user,
    )


@router.get(
    "/documents/{document_id}/integrity",
    response_model=DocumentIntegrityResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document cryptographic integrity verification status",
)
def get_document_integrity_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("DOCUMENT_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> DocumentIntegrityResponse:
    """Retrieve document integrity verification result."""
    from app.documents.integrity import verify_document_integrity
    return verify_document_integrity(
        db=db,
        document_id=document_id,
        storage=storage,
        current_user=current_user,
    )

