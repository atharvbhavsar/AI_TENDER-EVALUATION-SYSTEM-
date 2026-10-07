import datetime
import io
import logging
import uuid
from typing import BinaryIO, List, Optional, Tuple
from fastapi import UploadFile
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.audit.events import AuditAction
from app.audit.service import AuditService
from app.bidders.schemas import (
    ApplicationDetailResponse,
    ApplicationSummaryItem,
    BidderDashboardResponse,
    BidderDocumentResponse,
    BidderProfileResponse,
    CriterionChecklistItem,
    DocumentDeleteResponse,
    SubmitApplicationRequest,
    UpdateApplicationDraftRequest,
    UpdateBidderProfileRequest,
)
from app.core.config import get_settings
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import ApprovalStatus, TenderCriterion
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.documents.validators import (
    generate_storage_key,
    validate_and_process_upload_stream,
)
from app.storage.base import ObjectStorageService

logger = logging.getLogger("app.bidders.service")


def get_bidder_profile(db: Session, current_user: User) -> BidderProfileResponse:
    """Retrieve the corporate profile for the authenticated bidder."""
    # Count active applications/submissions associated with this user
    count_stmt = (
        select(func.count(BidSubmission.id))
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            )
        )
    )
    apps_count = db.execute(count_stmt).scalar() or 0

    return BidderProfileResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        company_name=current_user.company_name,
        phone=current_user.phone,
        is_active=current_user.is_active,
        roles=[r.name for r in current_user.roles],
        permissions=sorted(list(current_user.permissions)),
        created_at=current_user.created_at,
        active_applications_count=apps_count,
    )


def update_bidder_profile(
    db: Session, current_user: User, payload: UpdateBidderProfileRequest
) -> BidderProfileResponse:
    """Update profile fields for the authenticated bidder."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.company_name is not None:
        current_user.company_name = payload.company_name.strip()
    if payload.phone is not None:
        current_user.phone = payload.phone.strip()

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return get_bidder_profile(db, current_user)


def _build_application_summary(sub: BidSubmission) -> ApplicationSummaryItem:
    """Helper to transform BidSubmission into ApplicationSummaryItem."""
    tender_ver = sub.tender_version
    tender = tender_ver.tender if tender_ver else None

    return ApplicationSummaryItem(
        id=sub.id,
        submission_reference=sub.submission_reference,
        status=sub.status,
        tender_id=tender.id if tender else uuid.UUID(int=0),
        tender_number=tender.tender_number if tender else "UNKNOWN",
        tender_title=tender.title if tender else "Untitled Tender",
        issuing_authority=tender.issuing_authority if tender else "CRPF",
        tender_status=tender.status.value if tender else "UNKNOWN",
        tender_version_id=tender_ver.id if tender_ver else uuid.UUID(int=0),
        version_number=tender_ver.version_number if tender_ver else 1,
        version_label=tender_ver.version_label if tender_ver else "v1",
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        documents_count=len(sub.documents) if sub.documents else 0,
        bidder_notes=sub.bidder_notes,
        commercial_quote=float(sub.commercial_quote) if sub.commercial_quote is not None else None,
        declaration_signed=sub.declaration_signed,
        submitted_at=sub.submitted_at,
        is_locked=sub.is_locked,
        submission_deadline=tender.submission_deadline if tender else None,
    )


def list_bidder_applications(
    db: Session,
    current_user: User,
    page: int = 1,
    page_size: int = 20,
    status: Optional[SubmissionStatus] = None,
) -> Tuple[List[ApplicationSummaryItem], int]:
    """
    List applications/submissions belonging exclusively to the authenticated bidder.
    Strict isolation enforced via Bidder.user_id or Bidder.contact_email.
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            )
        )
    )

    if status:
        stmt = stmt.where(BidSubmission.status == status)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar() or 0

    # Paginate and order by newest
    stmt = (
        stmt.order_by(BidSubmission.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    submissions = db.execute(stmt).scalars().all()

    items = [_build_application_summary(sub) for sub in submissions]
    return items, total


def get_bidder_application(
    db: Session, current_user: User, application_id: uuid.UUID
) -> Optional[ApplicationDetailResponse]:
    """
    Retrieve single application details strictly isolated to the authenticated bidder.
    Returns None if not found or if application belongs to another bidder (IDOR protection).
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            BidSubmission.id == application_id,
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            ),
        )
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        return None

    tender_ver = sub.tender_version
    tender = tender_ver.tender if tender_ver else None

    # Load approved criteria for the tender version
    criteria_stmt = (
        select(TenderCriterion)
        .where(
            TenderCriterion.tender_version_id == tender_ver.id,
            TenderCriterion.approval_status == ApprovalStatus.APPROVED,
        )
        .order_by(TenderCriterion.mandatory.desc(), TenderCriterion.criterion_code.asc())
    )
    criteria_objs = db.execute(criteria_stmt).scalars().all()

    criteria_items = [
        CriterionChecklistItem(
            id=c.id,
            criterion_code=c.criterion_code,
            name=c.name,
            description=c.description,
            category=c.category,
            mandatory=c.mandatory,
            required_evidence=c.required_evidence,
        )
        for c in criteria_objs
    ]

    now = datetime.datetime.now(datetime.timezone.utc)
    deadline = tender.submission_deadline if tender else None
    is_deadline_passed = bool(deadline and now > deadline)
    is_tender_open = bool(tender and tender.status == TenderStatus.PUBLISHED)
    is_locked = bool(
        sub.is_locked
        or sub.status
        in (
            SubmissionStatus.SUBMITTED,
            SubmissionStatus.PROCESSING,
            SubmissionStatus.READY,
            SubmissionStatus.REVIEW,
        )
    )
    can_edit = bool(is_tender_open and not is_deadline_passed and not is_locked)
    can_submit = bool(is_tender_open and not is_deadline_passed and not is_locked)

    return ApplicationDetailResponse(
        id=sub.id,
        submission_reference=sub.submission_reference,
        status=sub.status,
        created_at=sub.created_at,
        updated_at=sub.updated_at,
        bidder_notes=sub.bidder_notes,
        commercial_quote=float(sub.commercial_quote) if sub.commercial_quote is not None else None,
        declaration_signed=sub.declaration_signed,
        submitted_at=sub.submitted_at,
        is_locked=is_locked,
        tender_id=tender.id if tender else uuid.UUID(int=0),
        tender_number=tender.tender_number if tender else "UNKNOWN",
        tender_title=tender.title if tender else "Untitled Tender",
        tender_description=tender.description if tender else None,
        issuing_authority=tender.issuing_authority if tender else "CRPF",
        tender_status=tender.status.value if tender else "UNKNOWN",
        submission_deadline=deadline,
        is_deadline_passed=is_deadline_passed,
        can_edit=can_edit,
        can_submit=can_submit,
        tender_version_id=tender_ver.id if tender_ver else uuid.UUID(int=0),
        version_number=tender_ver.version_number if tender_ver else 1,
        version_label=tender_ver.version_label if tender_ver else "v1",
        criteria_checklist=criteria_items,
        documents=[
            BidderDocumentResponse(
                id=d.id,
                tender_id=d.tender_id,
                tender_version_id=d.tender_version_id,
                bid_submission_id=d.bid_submission_id,
                criterion_id=d.criterion_id,
                filename=d.filename,
                content_type=d.content_type,
                file_extension=d.file_extension,
                file_size=d.file_size,
                sha256_hash=d.sha256_hash,
                document_type=d.document_type.value if hasattr(d.document_type, "value") else str(d.document_type),
                processing_status=d.processing_status.value if hasattr(d.processing_status, "value") else str(d.processing_status),
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in (sub.documents or [])
        ],
        documents_count=len(sub.documents) if sub.documents else 0,
    )


def get_bidder_dashboard(
    db: Session, current_user: User
) -> BidderDashboardResponse:
    """Generate real aggregated dashboard statistics for the authenticated bidder."""
    # Count open published tenders available in the system
    open_tenders_stmt = select(func.count(Tender.id)).where(
        Tender.status == TenderStatus.PUBLISHED
    )
    available_tenders = db.execute(open_tenders_stmt).scalar() or 0

    # Fetch all submissions for status counts
    sub_stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            )
        )
        .order_by(BidSubmission.created_at.desc())
    )
    submissions = db.execute(sub_stmt).scalars().all()

    total = len(submissions)
    draft = sum(1 for s in submissions if s.status == SubmissionStatus.DRAFT)
    submitted = sum(1 for s in submissions if s.status == SubmissionStatus.SUBMITTED)
    received = sum(1 for s in submissions if s.status in (SubmissionStatus.RECEIVED, SubmissionStatus.DRAFT))
    processing = sum(1 for s in submissions if s.status == SubmissionStatus.PROCESSING)
    ready = sum(1 for s in submissions if s.status == SubmissionStatus.READY)
    review = sum(1 for s in submissions if s.status == SubmissionStatus.REVIEW)

    recent_items = [_build_application_summary(s) for s in submissions[:5]]

    return BidderDashboardResponse(
        company_name=current_user.company_name or current_user.full_name,
        full_name=current_user.full_name,
        total_applications=total,
        draft_count=draft,
        submitted_count=submitted,
        received_count=received,
        processing_count=processing,
        ready_count=ready,
        review_count=review,
        available_tenders_count=available_tenders,
        recent_applications=recent_items,
    )


def apply_for_tender(
    db: Session, current_user: User, tender_id: uuid.UUID
) -> Tuple[BidSubmission, bool]:
    """
    Handle bidder applying to a tender:
    - Verifies tender exists and status is PUBLISHED (cannot apply to DRAFT or CLOSED).
    - Ensures Bidder entity exists for (tender_id, user_id).
    - Ensures BidSubmission exists for the active tender version.
    Returns (submission, is_created).
    """
    tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
    if not tender:
        raise ValueError("Tender does not exist.")

    if tender.status != TenderStatus.PUBLISHED:
        raise ValueError(
            f"Cannot apply: Tender is currently {tender.status.value}. Only PUBLISHED tenders accept applications."
        )

    # Server-side deadline check
    now = datetime.datetime.now(datetime.timezone.utc)
    if tender.submission_deadline and now > tender.submission_deadline:
        raise ValueError("Submission deadline has passed. Tender is closed for applications.")

    # Active version
    active_version = None
    for ver in tender.versions:
        if ver.is_active:
            active_version = ver
            break
    if not active_version and tender.versions:
        active_version = tender.versions[0]

    if not active_version:
        raise ValueError("Tender does not have an active specification version.")

    # Find or create Bidder record
    bidder_stmt = select(Bidder).where(
        Bidder.tender_id == tender.id,
        or_(
            Bidder.user_id == current_user.id,
            Bidder.contact_email == current_user.email,
        ),
    )
    bidder = db.execute(bidder_stmt).scalar_one_or_none()

    if not bidder:
        company_name = current_user.company_name or current_user.full_name
        code_prefix = "".join(filter(str.isalnum, company_name[:6])).upper() or "BID"
        bidder_code = f"BID-{code_prefix}-{str(current_user.id)[:6].upper()}"

        bidder = Bidder(
            id=uuid.uuid4(),
            tender_id=tender.id,
            user_id=current_user.id,
            bidder_code=bidder_code,
            legal_name=company_name,
            contact_email=current_user.email,
            contact_phone=current_user.phone,
        )
        db.add(bidder)
        db.flush()

    # Find or create BidSubmission
    sub_stmt = select(BidSubmission).where(
        BidSubmission.tender_version_id == active_version.id,
        BidSubmission.bidder_id == bidder.id,
    )
    submission = db.execute(sub_stmt).scalar_one_or_none()
    is_created = False

    if not submission:
        ref_slug = "".join(c if c.isalnum() else "-" for c in tender.tender_number).strip("-")
        submission_ref = f"SUB-{ref_slug}-{str(bidder.id)[:6].upper()}"

        submission = BidSubmission(
            id=uuid.uuid4(),
            tender_version_id=active_version.id,
            bidder_id=bidder.id,
            submission_reference=submission_ref,
            status=SubmissionStatus.DRAFT,
            declaration_signed=False,
            is_locked=False,
        )
        db.add(submission)
        db.commit()
        db.refresh(submission)
        is_created = True
    else:
        db.commit()

    return submission, is_created


def update_bidder_application_draft(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
    payload: UpdateApplicationDraftRequest,
) -> ApplicationDetailResponse:
    """
    Update editable draft application parameters (notes, commercial quote, declaration).
    Enforces strict IDOR protection, deadline validation, and locking rules.
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            BidSubmission.id == application_id,
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            ),
        )
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        raise KeyError("Application not found or access denied.")

    tender_ver = sub.tender_version
    tender = tender_ver.tender if tender_ver else None
    if not tender or tender.status != TenderStatus.PUBLISHED:
        raise ValueError(
            f"Cannot modify application: Tender is currently {tender.status.value if tender else 'UNKNOWN'}. Only PUBLISHED tenders can be edited."
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    if tender.submission_deadline and now > tender.submission_deadline:
        raise ValueError("Submission deadline has passed. Tender is closed for modifications.")

    if sub.is_locked or sub.status in (
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.PROCESSING,
        SubmissionStatus.READY,
        SubmissionStatus.REVIEW,
    ):
        raise ValueError("Cannot edit application: Submission has been submitted and is locked.")

    if payload.bidder_notes is not None:
        sub.bidder_notes = payload.bidder_notes.strip() if payload.bidder_notes else None
    if payload.commercial_quote is not None:
        sub.commercial_quote = payload.commercial_quote
    if payload.declaration_signed is not None:
        sub.declaration_signed = payload.declaration_signed

    db.add(sub)
    db.commit()
    db.refresh(sub)
    detail = get_bidder_application(db, current_user, application_id)
    if not detail:
        raise KeyError("Application not found after update.")
    return detail


def submit_bidder_application(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
    payload: SubmitApplicationRequest,
) -> ApplicationDetailResponse:
    """
    Formally submit the application against the published tender version.
    Validates server-side deadline, ownership, tender status, locking, and declaration.
    Locks the application from subsequent modifications.
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            BidSubmission.id == application_id,
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            ),
        )
        .with_for_update()
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        raise KeyError("Application not found or access denied.")

    tender_ver = sub.tender_version
    tender = tender_ver.tender if tender_ver else None
    if not tender or tender.status != TenderStatus.PUBLISHED:
        raise ValueError(
            f"Cannot submit application: Tender is currently {tender.status.value if tender else 'UNKNOWN'}. Only PUBLISHED tenders accept submissions."
        )

    # Server deadline enforcement
    now = datetime.datetime.now(datetime.timezone.utc)
    if tender.submission_deadline and now > tender.submission_deadline:
        raise ValueError("Submission deadline has passed. Tender is closed for submissions.")

    if sub.is_locked or sub.status in (
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.PROCESSING,
        SubmissionStatus.READY,
        SubmissionStatus.REVIEW,
    ):
        raise ValueError("Application has already been submitted and is locked.")

    if not payload.confirm_declaration and not sub.declaration_signed:
        raise ValueError("Mandatory statutory declaration must be confirmed before submission.")

    if payload.bidder_notes is not None:
        sub.bidder_notes = payload.bidder_notes.strip() if payload.bidder_notes else None
    if payload.commercial_quote is not None:
        sub.commercial_quote = payload.commercial_quote

    sub.declaration_signed = True
    sub.status = SubmissionStatus.SUBMITTED
    sub.submitted_at = now
    sub.is_locked = True

    db.add(sub)
    db.commit()
    db.refresh(sub)
    detail = get_bidder_application(db, current_user, application_id)
    if not detail:
        raise KeyError("Application not found after submission.")
    return detail


async def upload_bidder_document(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
    file: UploadFile,
    storage: ObjectStorageService,
    criterion_id: Optional[uuid.UUID] = None,
    document_type: DocumentType = DocumentType.UNKNOWN,
) -> Document:
    """
    Upload and securely ingest a document for a bidder application:
    - Enforces strict bidder ownership (IDOR safe).
    - Enforces tender status is PUBLISHED.
    - Enforces submission deadline has not passed.
    - Enforces application is not locked/submitted.
    - Validates criterion belongs to the target tender specification.
    - If document already exists for this criterion, cleans up old file and replaces it.
    - Validates file (MIME, magic bytes, size limit, filename sanitization).
    - Stores file binary in S3/MinIO object storage.
    - Persists document metadata in PostgreSQL.
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            BidSubmission.id == application_id,
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            ),
        )
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        raise KeyError("Application not found or access denied.")

    tender_ver = sub.tender_version
    tender = tender_ver.tender if tender_ver else None
    if not tender or tender.status != TenderStatus.PUBLISHED:
        raise ValueError(
            f"Cannot upload documents: Tender is currently {tender.status.value if tender else 'UNKNOWN'}. Only PUBLISHED tenders accept document uploads."
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    if tender.submission_deadline and now > tender.submission_deadline:
        raise ValueError("Submission deadline has passed. Tender is closed for document uploads.")

    if sub.is_locked or sub.status in (
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.PROCESSING,
        SubmissionStatus.READY,
        SubmissionStatus.REVIEW,
    ):
        raise ValueError("Application has already been submitted and is locked against modifications.")

    # Validate criterion belongs to this tender version if provided
    if criterion_id is not None:
        crit_stmt = select(TenderCriterion).where(
            TenderCriterion.id == criterion_id,
            TenderCriterion.tender_version_id == tender_ver.id,
        )
        crit = db.execute(crit_stmt).scalar_one_or_none()
        if not crit:
            raise ValueError("The specified requirement / criterion does not belong to this tender version.")

        # Check if an existing document was uploaded for this criterion on this application -> replace it
        existing_doc_stmt = select(Document).where(
            Document.bid_submission_id == sub.id,
            Document.criterion_id == criterion_id,
        )
        existing_doc = db.execute(existing_doc_stmt).scalar_one_or_none()
        if existing_doc:
            logger.info("Replacing existing document '%s' for criterion '%s'", existing_doc.id, criterion_id)
            try:
                storage.delete(existing_doc.storage_key)
            except Exception as e:
                logger.warning("Could not delete old storage object %s: %s", existing_doc.storage_key, e)
            db.delete(existing_doc)
            db.flush()

    # Stream, sanitize, and validate uploaded file
    settings = get_settings()
    file_bytes, safe_filename, ext, content_type, file_size, sha256_hash = (
        await validate_and_process_upload_stream(file, settings.MAX_UPLOAD_SIZE_MB)
    )

    document_id = uuid.uuid4()
    storage_key = generate_storage_key(tender.id, tender_ver.id, document_id, safe_filename)

    # Upload binary to object storage
    try:
        storage.upload(
            key=storage_key,
            data=io.BytesIO(file_bytes),
            content_type=content_type,
        )
    except Exception as exc:
        logger.error("Object storage upload failed for key '%s': %s", storage_key, exc)
        raise ValueError("Failed to upload document binary to secure storage.")

    # Persist document metadata with rollback cleanup
    try:
        document = Document(
            id=document_id,
            tender_id=tender.id,
            tender_version_id=tender_ver.id,
            bid_submission_id=sub.id,
            criterion_id=criterion_id,
            filename=safe_filename,
            content_type=content_type,
            file_extension=ext,
            file_size=file_size,
            sha256_hash=sha256_hash,
            storage_key=storage_key,
            document_type=document_type,
            processing_status=ProcessingStatus.VALIDATED,
            uploaded_by=current_user.id,
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        # Record audit event
        user_role = current_user.roles[0].name if current_user.roles else "BIDDER"
        AuditService.record(
            db,
            action=AuditAction.DOCUMENT_UPLOADED.value,
            entity_type="DOCUMENT",
            entity_id=str(document.id),
            actor_id=current_user.id,
            actor_role=user_role,
            tender_id=tender.id,
            tender_version_id=tender_ver.id,
            document_id=document.id,
            document_hash=sha256_hash,
            reason="Bidder application document uploaded.",
            source_service="bidder_service",
            metadata_json={
                "application_id": str(sub.id),
                "criterion_id": str(criterion_id) if criterion_id else None,
                "filename": safe_filename,
                "file_size": file_size,
                "storage_key": storage_key,
            },
        )
        return document
    except Exception as exc:
        db.rollback()
        logger.error("Database save failed for document '%s', cleaning up storage: %s", document_id, exc)
        try:
            storage.delete(storage_key)
        except Exception:
            pass
        raise ValueError("Failed to record document metadata.")


def list_bidder_documents(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
) -> List[Document]:
    """
    List documents belonging strictly to an application of the authenticated bidder.
    IDOR-safe: Rejects with KeyError if application does not belong to current user.
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            BidSubmission.id == application_id,
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            ),
        )
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        raise KeyError("Application not found or access denied.")

    doc_stmt = (
        select(Document)
        .where(Document.bid_submission_id == application_id)
        .order_by(Document.created_at.asc())
    )
    return list(db.execute(doc_stmt).scalars().all())


def get_bidder_document_stream(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    storage: ObjectStorageService,
) -> Tuple[Document, BinaryIO]:
    """
    Retrieve document record and download binary stream for the authenticated bidder.
    IDOR-safe: Validates that both application and document belong to the user.
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            BidSubmission.id == application_id,
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            ),
        )
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        raise KeyError("Application not found or access denied.")

    doc_stmt = select(Document).where(
        Document.id == document_id,
        Document.bid_submission_id == application_id,
    )
    document = db.execute(doc_stmt).scalar_one_or_none()
    if not document:
        raise KeyError("Document not found on this application.")

    try:
        stream = storage.download(document.storage_key)
        return document, stream
    except FileNotFoundError:
        raise KeyError("Document binary file not found in storage.")
    except Exception as exc:
        logger.error("Failed to stream document '%s': %s", document_id, exc)
        raise ValueError("Failed to retrieve document binary stream.")


def delete_bidder_document(
    db: Session,
    current_user: User,
    application_id: uuid.UUID,
    document_id: uuid.UUID,
    storage: ObjectStorageService,
) -> DocumentDeleteResponse:
    """
    Delete document belonging to an application:
    - Enforces IDOR security.
    - Enforces application is not locked or submitted.
    - Enforces deadline has not passed.
    - Deletes from storage and removes database row.
    """
    stmt = (
        select(BidSubmission)
        .join(Bidder, BidSubmission.bidder_id == Bidder.id)
        .where(
            BidSubmission.id == application_id,
            or_(
                Bidder.user_id == current_user.id,
                Bidder.contact_email == current_user.email,
            ),
        )
    )
    sub = db.execute(stmt).scalar_one_or_none()
    if not sub:
        raise KeyError("Application not found or access denied.")

    tender_ver = sub.tender_version
    tender = tender_ver.tender if tender_ver else None
    now = datetime.datetime.now(datetime.timezone.utc)
    if tender and tender.submission_deadline and now > tender.submission_deadline:
        raise ValueError("Submission deadline has passed. Documents cannot be removed.")

    if sub.is_locked or sub.status in (
        SubmissionStatus.SUBMITTED,
        SubmissionStatus.PROCESSING,
        SubmissionStatus.READY,
        SubmissionStatus.REVIEW,
    ):
        raise ValueError("Application has already been submitted and is locked.")

    doc_stmt = select(Document).where(
        Document.id == document_id,
        Document.bid_submission_id == application_id,
    )
    document = db.execute(doc_stmt).scalar_one_or_none()
    if not document:
        raise KeyError("Document not found on this application.")

    filename = document.filename
    storage_key = document.storage_key

    # Delete from DB
    db.delete(document)
    db.commit()

    # Delete from storage
    try:
        storage.delete(storage_key)
    except Exception as exc:
        logger.warning("Could not delete object '%s' from storage: %s", storage_key, exc)

    return DocumentDeleteResponse(
        success=True,
        message=f"Document '{filename}' successfully removed.",
    )


