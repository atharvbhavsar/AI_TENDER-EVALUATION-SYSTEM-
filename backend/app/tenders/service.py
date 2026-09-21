"""Service layer for Tender Management and Versioning."""

import datetime
import logging
import math
import uuid
from typing import List, Optional, Tuple
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_version import TenderVersion
from app.tenders.schemas import TenderCreate, TenderUpdate, TenderVersionCreate

logger = logging.getLogger("app.tenders.service")


def get_tender_by_number(db: Session, tender_number: str) -> Optional[Tender]:
    """Retrieve a tender by its unique tender number."""
    stmt = select(Tender).where(Tender.tender_number == tender_number.strip())
    return db.execute(stmt).scalar_one_or_none()


def get_tender(db: Session, tender_id: uuid.UUID) -> Optional[Tender]:
    """Retrieve a tender by its primary key UUID."""
    stmt = select(Tender).where(Tender.id == tender_id)
    return db.execute(stmt).scalar_one_or_none()


def create_tender(
    db: Session,
    payload: TenderCreate,
    user_id: uuid.UUID,
) -> Tender:
    """Create a new tender along with its initial Version 1 atomically."""
    clean_number = payload.tender_number.strip()
    if get_tender_by_number(db, clean_number):
        raise ValueError(f"Tender with number '{clean_number}' already exists")

    tender = Tender(
        tender_number=clean_number,
        title=payload.title.strip(),
        description=payload.description.strip() if payload.description else None,
        issuing_authority=payload.issuing_authority.strip(),
        status=TenderStatus.DRAFT,
        created_by=user_id,
    )

    try:
        db.add(tender)
        db.flush()  # Generate tender.id

        # Automatically initialize Version 1
        initial_version = TenderVersion(
            tender_id=tender.id,
            version_number=1,
            version_label=payload.initial_version_label.strip(),
            change_summary=payload.initial_change_summary.strip() if payload.initial_change_summary else None,
            is_active=True,
            created_by=user_id,
        )
        db.add(initial_version)
        db.commit()
        db.refresh(tender)
        return tender
    except Exception:
        db.rollback()
        raise


def list_tenders(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    status_filter: Optional[TenderStatus] = None,
) -> Tuple[List[Tender], int, int]:
    """Return paginated list of tenders, total count, and total pages."""
    base_query = select(Tender)
    count_query = select(func.count(Tender.id))

    if status_filter:
        base_query = base_query.where(Tender.status == status_filter)
        count_query = count_query.where(Tender.status == status_filter)

    total = db.execute(count_query).scalar_one()
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    offset = (page - 1) * page_size
    stmt = (
        base_query
        .order_by(Tender.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    items = db.execute(stmt).scalars().all()
    return list(items), total, total_pages


def update_tender(
    db: Session,
    tender_id: uuid.UUID,
    payload: TenderUpdate,
) -> Tender:
    """Update editable tender metadata."""
    tender = get_tender(db, tender_id)
    if not tender:
        raise KeyError(f"Tender '{tender_id}' not found")

    if payload.title is not None:
        tender.title = payload.title.strip()
    if payload.description is not None:
        tender.description = payload.description.strip() if payload.description else None
    if payload.issuing_authority is not None:
        tender.issuing_authority = payload.issuing_authority.strip()
    if payload.status is not None:
        tender.status = payload.status

    try:
        db.commit()
        db.refresh(tender)
        return tender
    except Exception:
        db.rollback()
        raise


def create_tender_version(
    db: Session,
    tender_id: uuid.UUID,
    payload: TenderVersionCreate,
    user_id: uuid.UUID,
) -> TenderVersion:
    """Create a sequential tender version and transition previous versions to inactive."""
    # Lock tender record to prevent concurrent race condition during version increment
    tender = db.execute(
        select(Tender).where(Tender.id == tender_id).with_for_update()
    ).scalar_one_or_none()

    if not tender:
        raise KeyError(f"Tender '{tender_id}' not found")

    # Determine next version number
    max_v_stmt = select(func.max(TenderVersion.version_number)).where(
        TenderVersion.tender_id == tender_id
    )
    current_max = db.execute(max_v_stmt).scalar() or 0
    next_version = current_max + 1

    try:
        # Set all existing versions for this tender to inactive
        db.execute(
            update(TenderVersion)
            .where(TenderVersion.tender_id == tender_id)
            .values(is_active=False)
        )

        effective_time = (
            payload.effective_at
            if payload.effective_at
            else datetime.datetime.now(datetime.timezone.utc)
        )

        new_version = TenderVersion(
            tender_id=tender_id,
            version_number=next_version,
            version_label=payload.version_label.strip(),
            change_summary=payload.change_summary.strip() if payload.change_summary else None,
            effective_at=effective_time,
            is_active=True,
            created_by=user_id,
        )

        db.add(new_version)
        db.commit()
        db.refresh(new_version)
        return new_version
    except Exception:
        db.rollback()
        raise


def list_tender_versions(
    db: Session,
    tender_id: uuid.UUID,
) -> List[TenderVersion]:
    """Retrieve all historical and active versions for a tender ordered by version number DESC."""
    tender = get_tender(db, tender_id)
    if not tender:
        raise KeyError(f"Tender '{tender_id}' not found")

    stmt = (
        select(TenderVersion)
        .where(TenderVersion.tender_id == tender_id)
        .order_by(TenderVersion.version_number.desc())
    )
    return list(db.execute(stmt).scalars().all())


def get_tender_version(
    db: Session,
    tender_id: uuid.UUID,
    version_number: int,
) -> Optional[TenderVersion]:
    """Retrieve a specific version number of a tender."""
    stmt = select(TenderVersion).where(
        TenderVersion.tender_id == tender_id,
        TenderVersion.version_number == version_number,
    )
    return db.execute(stmt).scalar_one_or_none()
