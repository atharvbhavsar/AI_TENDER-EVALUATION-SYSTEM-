"""Audit service for append-only, transactional audit recording and querying."""

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session
from app.audit.schemas import AuditLogFilter
from app.db.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """Centralized service for recording and retrieving immutable audit events."""

    @staticmethod
    def record(
        db: Session,
        *,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[str] = None,
        tender_id: Optional[uuid.UUID] = None,
        tender_version_id: Optional[uuid.UUID] = None,
        bidder_id: Optional[uuid.UUID] = None,
        bid_submission_id: Optional[uuid.UUID] = None,
        criterion_id: Optional[uuid.UUID] = None,
        document_id: Optional[uuid.UUID] = None,
        evidence_id: Optional[uuid.UUID] = None,
        evaluation_id: Optional[uuid.UUID] = None,
        review_id: Optional[uuid.UUID] = None,
        document_hash: Optional[str] = None,
        previous_state: Optional[Dict[str, Any]] = None,
        new_state: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source_service: Optional[str] = None,
        metadata_json: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Record a structured audit log entry in the current database transaction.
        Does NOT commit directly, leaving transaction control to the calling business service.
        """
        entry = AuditLog(
            id=uuid.uuid4(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
            action=action.strip().upper(),
            entity_type=entity_type.strip().upper(),
            entity_id=str(entity_id) if entity_id is not None else None,
            actor_id=actor_id,
            actor_role=actor_role,
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            bidder_id=bidder_id,
            bid_submission_id=bid_submission_id,
            criterion_id=criterion_id,
            document_id=document_id,
            evidence_id=evidence_id,
            evaluation_id=evaluation_id,
            review_id=review_id,
            document_hash=document_hash,
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            correlation_id=correlation_id,
            source_service=source_service or "app",
            metadata_json=metadata_json or {},
        )
        db.add(entry)
        db.flush()
        logger.info(
            "Audit record added: action=%s entity=%s:%s actor=%s tender=%s submission=%s doc=%s ev=%s",
            entry.action,
            entry.entity_type,
            entry.entity_id,
            entry.actor_id,
            entry.tender_id,
            entry.bid_submission_id,
            entry.document_id,
            entry.evidence_id,
        )
        return entry

    @staticmethod
    def get_by_id(db: Session, audit_id: uuid.UUID) -> Optional[AuditLog]:
        """Fetch a single audit log by its unique UUID."""
        stmt = select(AuditLog).where(AuditLog.id == audit_id)
        return db.execute(stmt).scalar_one_or_none()

    @staticmethod
    def query_logs(
        db: Session,
        filters: AuditLogFilter,
    ) -> Tuple[List[AuditLog], int]:
        """Query audit logs applying filters and returning (items, total_count)."""
        query: Select = select(AuditLog)
        count_query: Select = select(func.count(AuditLog.id))

        conditions = []
        if filters.tender_id:
            conditions.append(AuditLog.tender_id == filters.tender_id)
        if filters.tender_version_id:
            conditions.append(AuditLog.tender_version_id == filters.tender_version_id)
        if filters.bidder_id:
            conditions.append(AuditLog.bidder_id == filters.bidder_id)
        if filters.bid_submission_id:
            conditions.append(AuditLog.bid_submission_id == filters.bid_submission_id)
        if filters.criterion_id:
            conditions.append(AuditLog.criterion_id == filters.criterion_id)
        if filters.document_id:
            conditions.append(AuditLog.document_id == filters.document_id)
        if filters.evidence_id:
            conditions.append(AuditLog.evidence_id == filters.evidence_id)
        if filters.evaluation_id:
            conditions.append(AuditLog.evaluation_id == filters.evaluation_id)
        if filters.review_id:
            conditions.append(AuditLog.review_id == filters.review_id)
        if filters.actor_id:
            conditions.append(AuditLog.actor_id == filters.actor_id)
        if filters.action:
            conditions.append(AuditLog.action == filters.action.strip().upper())
        if filters.entity_type:
            conditions.append(AuditLog.entity_type == filters.entity_type.strip().upper())
        if filters.entity_id:
            conditions.append(AuditLog.entity_id == str(filters.entity_id))
        if filters.start_time:
            conditions.append(AuditLog.timestamp >= filters.start_time)
        if filters.end_time:
            conditions.append(AuditLog.timestamp <= filters.end_time)

        if conditions:
            query = query.where(*conditions)
            count_query = count_query.where(*conditions)

        total = db.scalar(count_query) or 0
        items = db.scalars(
            query.order_by(AuditLog.timestamp.desc())
            .offset(filters.offset)
            .limit(filters.limit)
        ).all()

        return list(items), total

    @staticmethod
    def get_submission_audit_trail(
        db: Session,
        submission_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[AuditLog], int]:
        """Fetch chronological audit trail for a specific bid submission."""
        return AuditService.query_logs(
            db,
            AuditLogFilter(
                bid_submission_id=submission_id,
                limit=limit,
                offset=offset,
            ),
        )

    @staticmethod
    def get_tender_audit_trail(
        db: Session,
        tender_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[AuditLog], int]:
        """Fetch chronological audit trail for a specific tender."""
        return AuditService.query_logs(
            db,
            AuditLogFilter(
                tender_id=tender_id,
                limit=limit,
                offset=offset,
            ),
        )

    @staticmethod
    def get_document_audit_trail(
        db: Session,
        document_id: uuid.UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[AuditLog], int]:
        """Fetch chronological audit trail for a specific document."""
        return AuditService.query_logs(
            db,
            AuditLogFilter(
                document_id=document_id,
                limit=limit,
                offset=offset,
            ),
        )
