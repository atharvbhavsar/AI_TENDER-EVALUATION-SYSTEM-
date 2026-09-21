"""Report orchestration service managing lifecycle, object storage, and audit."""

import datetime
import hashlib
import io
import logging
import re
import uuid
from typing import Any, BinaryIO, Dict, List, Optional, Tuple
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from app.audit.service import AuditService
from app.core.exceptions import ConflictException, NotFoundException
from app.db.models.bid_submission import BidSubmission
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation
from app.db.models.evaluation_report import EvaluationReport, ReportStatus, ReportType
from app.db.models.tender import Tender
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.reports.explanation_service import ExplanationService
from app.reports.pdf_generator import PDFReportGenerator
from app.reports.schemas import ReportCreateRequest
from app.storage.base import ObjectStorageService

logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """Sanitize string to produce a safe filesystem and header-safe filename."""
    if not name or not name.strip():
        return "unnamed"
    # Remove directory traversal sequences
    cleaned = re.sub(r"\.\.+", "", name)
    # Replace whitespace and unsafe symbols with underscore
    cleaned = re.sub(r"[^\w\-]", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "unnamed"


class ReportService:
    """Orchestrates formal report generation, object storage persistence, versioning, and secure retrieval."""

    @staticmethod
    def generate_safe_filename(
        tender_number: str,
        bidder_name: Optional[str],
        report_version: int,
        report_type: ReportType,
    ) -> str:
        """Construct safe, standardized report filename."""
        safe_tender = sanitize_filename(tender_number)
        safe_bidder = sanitize_filename(bidder_name or "Consolidated")
        type_str = "bidder_report" if report_type == ReportType.BIDDER_EVALUATION_REPORT else "consolidated_report"
        return f"{safe_tender}_{safe_bidder}_{type_str}_v{report_version}.pdf"

    @staticmethod
    def generate_bidder_report(
        db: Session,
        submission_id: uuid.UUID,
        current_user: User,
        request: ReportCreateRequest,
        storage: ObjectStorageService,
    ) -> EvaluationReport:
        """
        Generate, hash, store, and record an immutable Bidder Evaluation Report.
        Validates that required evaluation records exist before generation.
        """
        submission = db.get(BidSubmission, submission_id)
        if not submission:
            raise NotFoundException(f"Bid submission '{submission_id}' not found")

        # Verify evaluation records exist
        ce_count = db.scalar(
            select(func.count(CriterionEvaluation.id)).where(
                CriterionEvaluation.bid_submission_id == submission_id
            )
        )
        if not ce_count or ce_count == 0:
            raise ConflictException(
                f"Submission '{submission_id}' has not been evaluated. Evaluation records must exist before generating a formal report."
            )

        # Determine next report version for this submission
        v_query: Select = select(func.coalesce(func.max(EvaluationReport.report_version), 0)).where(
            EvaluationReport.bid_submission_id == submission_id,
            EvaluationReport.report_type == ReportType.BIDDER_EVALUATION_REPORT,
        )
        next_version = int(db.scalar(v_query) or 0) + 1

        # Fetch authoritative explanation data & audit history
        explanation = ExplanationService.get_bidder_explanation(db, submission_id)
        raw_audit_logs, _ = AuditService.get_submission_audit_trail(db, submission_id, limit=20)
        audit_summary = [
            {
                "timestamp": str(al.timestamp),
                "action": al.action,
                "entity_type": al.entity_type,
                "entity_id": al.entity_id,
                "actor_id": str(al.actor_id) if al.actor_id else None,
                "reason": al.reason,
            }
            for al in raw_audit_logs
        ]

        title = request.title or f"Bidder Evaluation Report - {explanation.bidder_name} (v{next_version})"
        report_id = uuid.uuid4()
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        report = EvaluationReport(
            id=report_id,
            tender_id=explanation.tender_id,
            tender_version_id=explanation.tender_version_id,
            bidder_id=explanation.bidder_id,
            bid_submission_id=submission.id,
            evaluation_run_id=explanation.evaluation_run_id,
            overall_evaluation_id=explanation.overall_evaluation_id,
            report_type=ReportType.BIDDER_EVALUATION_REPORT,
            report_version=next_version,
            status=ReportStatus.GENERATING,
            title=title,
            mime_type="application/pdf",
            generated_by=current_user.id,
            generation_metadata={
                "tender_number": explanation.tender_number,
                "bidder_name": explanation.bidder_name,
                "automated_result": explanation.automated_overall_result.value,
                "human_decision": explanation.human_overall_decision.value if explanation.human_overall_decision else None,
                "final_decision_state": explanation.final_decision_state.value,
                "total_criteria": explanation.total_criteria,
            },
        )
        db.add(report)
        db.flush()

        try:
            report_meta = {
                "report_id": report_id,
                "generated_at": now_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "report_version": next_version,
            }

            # Generate PDF binary
            pdf_bytes = PDFReportGenerator.generate_bidder_report(
                explanation=explanation,
                audit_summary=audit_summary if request.include_audit_summary else None,
                include_source_snippets=request.include_source_snippets,
                report_meta=report_meta,
            )

            # Compute SHA-256 hash of the exact PDF binary
            file_hash = hashlib.sha256(pdf_bytes).hexdigest()
            file_size = len(pdf_bytes)

            # Upload to private object storage
            safe_filename = ReportService.generate_safe_filename(
                explanation.tender_number,
                explanation.bidder_name,
                next_version,
                ReportType.BIDDER_EVALUATION_REPORT,
            )
            storage_key = f"reports/{explanation.tender_id}/{explanation.tender_version_id}/bidder/{submission.id}_v{next_version}_{report_id}_{safe_filename}"
            storage.upload(
                key=storage_key,
                data=io.BytesIO(pdf_bytes),
                content_type="application/pdf",
            )

            # Update report record
            report.status = ReportStatus.COMPLETED
            report.storage_key = storage_key
            report.file_hash = file_hash
            report.file_size_bytes = file_size

            # Record system audit event
            AuditService.record(
                db,
                action="REPORT_GENERATED",
                entity_type="REPORT",
                entity_id=str(report.id),
                actor_id=current_user.id,
                actor_role=getattr(current_user, "role", "OFFICER"),
                tender_id=explanation.tender_id,
                tender_version_id=explanation.tender_version_id,
                bidder_id=explanation.bidder_id,
                bid_submission_id=submission.id,
                document_hash=file_hash,
                metadata_json={
                    "report_type": report.report_type.value,
                    "report_version": report.report_version,
                    "storage_key": storage_key,
                    "file_size_bytes": file_size,
                    "file_name": safe_filename,
                },
            )
            db.commit()
            db.refresh(report)
            return report

        except Exception as exc:
            db.rollback()
            logger.exception("Failed generating bidder evaluation report: %s", exc)
            report.status = ReportStatus.FAILED
            report.error_message = str(exc)
            db.add(report)
            db.commit()
            db.refresh(report)
            return report

    @staticmethod
    def generate_consolidated_report(
        db: Session,
        tender_id: uuid.UUID,
        version_id: uuid.UUID,
        current_user: User,
        request: ReportCreateRequest,
        storage: ObjectStorageService,
    ) -> EvaluationReport:
        """
        Generate, hash, store, and record a Consolidated Tender Evaluation Report.
        Strictly factual: no ranking, scoring, or winner recommendation.
        """
        tender = db.get(Tender, tender_id)
        if not tender:
            raise NotFoundException(f"Tender '{tender_id}' not found")

        version = db.get(TenderVersion, version_id)
        if not version or version.tender_id != tender_id:
            raise NotFoundException(f"Tender version '{version_id}' not found for tender '{tender_id}'")

        # Determine next report version
        v_query: Select = select(func.coalesce(func.max(EvaluationReport.report_version), 0)).where(
            EvaluationReport.tender_version_id == version_id,
            EvaluationReport.report_type == ReportType.CONSOLIDATED_TENDER_REPORT,
        )
        next_version = int(db.scalar(v_query) or 0) + 1

        # Fetch all submissions for this tender version
        sub_query: Select = select(BidSubmission).where(BidSubmission.tender_version_id == version_id)
        submissions = list(db.scalars(sub_query).all())

        bidders_explanations = [
            ExplanationService.get_bidder_explanation(db, sub.id) for sub in submissions
        ]

        tender_meta = {
            "tender_number": tender.tender_number,
            "title": tender.title,
            "version_number": version.version_number,
        }

        title = request.title or f"Consolidated Tender Evaluation Report - {tender.tender_number} (v{next_version})"
        report_id = uuid.uuid4()
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        report = EvaluationReport(
            id=report_id,
            tender_id=tender_id,
            tender_version_id=version_id,
            report_type=ReportType.CONSOLIDATED_TENDER_REPORT,
            report_version=next_version,
            status=ReportStatus.GENERATING,
            title=title,
            mime_type="application/pdf",
            generated_by=current_user.id,
            generation_metadata={
                "tender_number": tender.tender_number,
                "submission_count": len(submissions),
            },
        )
        db.add(report)
        db.flush()

        try:
            report_meta = {
                "report_id": report_id,
                "generated_at": now_dt.strftime("%Y-%m-%d %H:%M:%S UTC"),
                "report_version": next_version,
            }

            pdf_bytes = PDFReportGenerator.generate_consolidated_report(
                tender_meta=tender_meta,
                bidders_explanations=bidders_explanations,
                report_meta=report_meta,
            )

            file_hash = hashlib.sha256(pdf_bytes).hexdigest()
            file_size = len(pdf_bytes)

            safe_filename = ReportService.generate_safe_filename(
                tender.tender_number,
                None,
                next_version,
                ReportType.CONSOLIDATED_TENDER_REPORT,
            )
            storage_key = f"reports/{tender_id}/{version_id}/consolidated/{report_id}_{safe_filename}"
            storage.upload(
                key=storage_key,
                data=io.BytesIO(pdf_bytes),
                content_type="application/pdf",
            )

            report.status = ReportStatus.COMPLETED
            report.storage_key = storage_key
            report.file_hash = file_hash
            report.file_size_bytes = file_size

            AuditService.record(
                db,
                action="REPORT_GENERATED",
                entity_type="REPORT",
                entity_id=str(report.id),
                actor_id=current_user.id,
                actor_role=getattr(current_user, "role", "OFFICER"),
                tender_id=tender_id,
                tender_version_id=version_id,
                document_hash=file_hash,
                metadata_json={
                    "report_type": report.report_type.value,
                    "report_version": report.report_version,
                    "storage_key": storage_key,
                    "file_size_bytes": file_size,
                    "file_name": safe_filename,
                },
            )
            db.commit()
            db.refresh(report)
            return report

        except Exception as exc:
            db.rollback()
            logger.exception("Failed generating consolidated report: %s", exc)
            report.status = ReportStatus.FAILED
            report.error_message = str(exc)
            db.add(report)
            db.commit()
            db.refresh(report)
            return report

    @staticmethod
    def get_report(db: Session, report_id: uuid.UUID) -> EvaluationReport:
        """Fetch report metadata by ID."""
        report = db.get(EvaluationReport, report_id)
        if not report:
            raise NotFoundException(f"Evaluation report '{report_id}' not found")
        return report

    @staticmethod
    def list_reports(
        db: Session,
        tender_id: Optional[uuid.UUID] = None,
        tender_version_id: Optional[uuid.UUID] = None,
        bidder_id: Optional[uuid.UUID] = None,
        bid_submission_id: Optional[uuid.UUID] = None,
        report_type: Optional[ReportType] = None,
        status: Optional[ReportStatus] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[EvaluationReport], int]:
        """Query reports with filtering and pagination."""
        query: Select = select(EvaluationReport)
        count_query: Select = select(func.count(EvaluationReport.id))

        conditions = []
        if tender_id:
            conditions.append(EvaluationReport.tender_id == tender_id)
        if tender_version_id:
            conditions.append(EvaluationReport.tender_version_id == tender_version_id)
        if bidder_id:
            conditions.append(EvaluationReport.bidder_id == bidder_id)
        if bid_submission_id:
            conditions.append(EvaluationReport.bid_submission_id == bid_submission_id)
        if report_type:
            conditions.append(EvaluationReport.report_type == report_type)
        if status:
            conditions.append(EvaluationReport.status == status)

        if conditions:
            query = query.where(*conditions)
            count_query = count_query.where(*conditions)

        total = db.scalar(count_query) or 0
        items = db.scalars(
            query.order_by(EvaluationReport.created_at.desc())
            .offset(offset)
            .limit(limit)
        ).all()

        return list(items), total

    @staticmethod
    def download_report_stream(
        db: Session,
        report_id: uuid.UUID,
        storage: ObjectStorageService,
        current_user: User,
    ) -> Tuple[BinaryIO, str, str, str]:
        """Download report binary stream from object storage and record access audit."""
        report = ReportService.get_report(db, report_id)
        if report.status != ReportStatus.COMPLETED or not report.storage_key:
            raise ConflictException("Report is not ready or failed to generate")

        stream = storage.download(report.storage_key)
        safe_title = sanitize_filename(report.title)
        filename = f"{safe_title}.pdf"

        # Record download audit event
        AuditService.record(
            db,
            action="REPORT_DOWNLOADED",
            entity_type="REPORT",
            entity_id=str(report.id),
            actor_id=current_user.id,
            actor_role=getattr(current_user, "role", "OFFICER"),
            tender_id=report.tender_id,
            tender_version_id=report.tender_version_id,
            bidder_id=report.bidder_id,
            bid_submission_id=report.bid_submission_id,
            document_hash=report.file_hash,
            metadata_json={
                "report_id": str(report.id),
                "report_type": report.report_type.value,
                "report_version": report.report_version,
            },
        )
        db.commit()

        return stream, filename, report.mime_type, report.file_hash or ""
