"""API endpoints for Explainability, Audit, and Formal Reports."""

import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.audit.schemas import AuditListResponse, AuditLogResponse
from app.audit.service import AuditService
from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.evaluation_report import ReportStatus, ReportType
from app.db.models.user import User
from app.db.session import get_db
from app.reports.explanation_service import ExplanationService
from app.reports.schemas import (
    BidderExplanationResponse,
    CriterionExplanationResponse,
    EvaluationReportResponse,
    ReportCreateRequest,
    ReportListResponse,
)
from app.reports.service import ReportService
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

router = APIRouter(tags=["Reports & Explainability"])


@router.get(
    "/criterion-evaluations/{id}/explanation",
    response_model=CriterionExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get criterion-level explanation and provenance",
)
def get_criterion_explanation(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
) -> CriterionExplanationResponse:
    """Retrieve 20-point factual provenance and explanation for an individual criterion evaluation."""
    return ExplanationService.get_criterion_explanation(db, id)


@router.get(
    "/submissions/{id}/explanation",
    response_model=BidderExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get bidder-level aggregated explanation",
)
def get_bidder_explanation(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
) -> BidderExplanationResponse:
    """Retrieve consolidated bidder-level explanation comparing automated results with human officer decisions."""
    return ExplanationService.get_bidder_explanation(db, id)


@router.get(
    "/submissions/{id}/audit",
    response_model=AuditListResponse,
    status_code=status.HTTP_200_OK,
    summary="Get submission audit trail",
)
def get_submission_audit(
    id: uuid.UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
) -> AuditListResponse:
    """Fetch chronological audit history tied to a specific bid submission."""
    items, total = AuditService.get_submission_audit_trail(db, id, limit=limit, offset=offset)
    return AuditListResponse(
        items=[AuditLogResponse.model_validate(i) for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/submissions/{id}/reports",
    response_model=EvaluationReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Bidder Evaluation Report",
)
def generate_bidder_report(
    id: uuid.UUID,
    request: ReportCreateRequest = ReportCreateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REPORT_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> EvaluationReportResponse:
    """Generate, hash, and persist a formal PDF evaluation report for a bidder submission."""
    report = ReportService.generate_bidder_report(
        db, submission_id=id, current_user=current_user, request=request, storage=storage
    )
    return EvaluationReportResponse.model_validate(report)


@router.get(
    "/submissions/{id}/reports",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List reports for a submission",
)
def list_submission_reports(
    id: uuid.UUID,
    report_type: Optional[ReportType] = Query(None),
    status_filter: Optional[ReportStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REPORT_READ")),
) -> ReportListResponse:
    """List historical reports generated for a specific bid submission."""
    items, total = ReportService.list_reports(
        db,
        bid_submission_id=id,
        report_type=report_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ReportListResponse(
        items=[EvaluationReportResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/reports/{id}",
    response_model=EvaluationReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get evaluation report metadata",
)
def get_report(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REPORT_READ")),
) -> EvaluationReportResponse:
    """Retrieve metadata for a generated evaluation report."""
    report = ReportService.get_report(db, id)
    return EvaluationReportResponse.model_validate(report)


@router.get(
    "/reports/{id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download report PDF artifact",
)
def download_report(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REPORT_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> StreamingResponse:
    """Download the formal evaluation report PDF with access auditing and SHA-256 integrity header."""
    stream, filename, mime_type, file_hash = ReportService.download_report_stream(
        db, report_id=id, storage=storage, current_user=current_user
    )
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Report-SHA256": file_hash,
    }
    return StreamingResponse(stream, media_type=mime_type, headers=headers)


@router.get(
    "/reports",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all evaluation reports with filtering",
)
def list_reports(
    tender_id: Optional[uuid.UUID] = Query(None),
    tender_version_id: Optional[uuid.UUID] = Query(None),
    bidder_id: Optional[uuid.UUID] = Query(None),
    bid_submission_id: Optional[uuid.UUID] = Query(None),
    report_type: Optional[ReportType] = Query(None),
    status_filter: Optional[ReportStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REPORT_READ")),
) -> ReportListResponse:
    """List evaluation reports with multi-criteria filtering and pagination."""
    items, total = ReportService.list_reports(
        db,
        tender_id=tender_id,
        tender_version_id=tender_version_id,
        bidder_id=bidder_id,
        bid_submission_id=bid_submission_id,
        report_type=report_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ReportListResponse(
        items=[EvaluationReportResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/reports",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List reports for a tender version",
)
def list_tender_version_reports(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    report_type: Optional[ReportType] = Query(None),
    status_filter: Optional[ReportStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REPORT_READ")),
) -> ReportListResponse:
    """List all evaluation reports generated for a specific tender version."""
    items, total = ReportService.list_reports(
        db,
        tender_id=tender_id,
        tender_version_id=version_id,
        report_type=report_type,
        status=status_filter,
        limit=limit,
        offset=offset,
    )
    return ReportListResponse(
        items=[EvaluationReportResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/tenders/{tender_id}/versions/{version_id}/reports",
    response_model=EvaluationReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate Consolidated Tender Evaluation Report",
)
def generate_consolidated_report(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    request: ReportCreateRequest = ReportCreateRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("REPORT_READ")),
    storage: ObjectStorageService = Depends(get_storage_service),
) -> EvaluationReportResponse:
    """Generate, hash, and persist a Consolidated Tender Report comparing all submissions for a version."""
    report = ReportService.generate_consolidated_report(
        db, tender_id=tender_id, version_id=version_id, current_user=current_user, request=request, storage=storage
    )
    return EvaluationReportResponse.model_validate(report)
