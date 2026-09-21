"""Domain service for Bidders, Submissions, and AI Evidence Extraction & Validation."""

import datetime
import json
import logging
import uuid
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.approval.service import get_approved_criteria
from app.core.config import get_settings
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.document import Document, ProcessingStatus
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.evidence_extraction_run import EvidenceExtractionRun
from app.db.models.extraction_run import ExtractionRunStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.tender import Tender
from app.db.models.tender_criterion import TenderCriterion
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.evidence.llm import BaseEvidenceLLMClient, get_evidence_llm_client
from app.evidence.prompts.v1 import (
    EVIDENCE_EXTRACTION_SYSTEM_PROMPT_V1,
    build_evidence_user_prompt,
)
from app.evidence.schemas import (
    BidderCreate,
    BidderUpdate,
    BidSubmissionCreate,
    RawEvidenceItem,
)
from app.evidence.validation import (
    detect_evidence_conflicts,
    normalize_bidder_legal_name,
    validate_evidence_source_citations,
)
from app.extraction.chunking import create_extraction_chunks
from app.pipeline.schemas import NormalizedDocument
from app.storage.base import ObjectStorageService
from app.storage.service import get_storage_service

logger = logging.getLogger("app.evidence.service")


# --- Bidder Management ---

def create_bidder(
    db: Session,
    tender_id: uuid.UUID,
    data: BidderCreate,
) -> Bidder:
    """Register a new bidder under a tender."""
    tender = db.get(Tender, tender_id)
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender {tender_id} not found.",
        )

    # Check duplicate bidder_code under the same tender
    existing = db.execute(
        select(Bidder).where(
            Bidder.tender_id == tender_id,
            Bidder.bidder_code == data.bidder_code,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Bidder with code '{data.bidder_code}' already exists for this tender.",
        )

    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender_id,
        bidder_code=data.bidder_code,
        legal_name=data.legal_name,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
    )
    db.add(bidder)
    db.commit()
    db.refresh(bidder)
    return bidder


def list_bidders(
    db: Session,
    tender_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[Bidder], int]:
    """List bidders registered for a tender."""
    total = db.execute(
        select(func.count(Bidder.id)).where(Bidder.tender_id == tender_id)
    ).scalar_one()

    stmt = (
        select(Bidder)
        .where(Bidder.tender_id == tender_id)
        .order_by(Bidder.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    items = db.execute(stmt).scalars().all()
    return items, total


def get_bidder(
    db: Session,
    tender_id: uuid.UUID,
    bidder_id: uuid.UUID,
) -> Bidder:
    """Retrieve bidder by ID and verify tender ownership."""
    bidder = db.get(Bidder, bidder_id)
    if not bidder or bidder.tender_id != tender_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Bidder {bidder_id} not found for tender {tender_id}.",
        )
    return bidder


# --- Submission Management ---

def create_submission(
    db: Session,
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    bidder_id: uuid.UUID,
    data: BidSubmissionCreate,
) -> BidSubmission:
    """Create a submission response for a bidder against a specific tender version."""
    tender_version = db.get(TenderVersion, version_id)
    if not tender_version or tender_version.tender_id != tender_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TenderVersion {version_id} not found for tender {tender_id}.",
        )

    bidder = get_bidder(db=db, tender_id=tender_id, bidder_id=bidder_id)

    # Check duplicate submission reference
    existing = db.execute(
        select(BidSubmission).where(
            BidSubmission.tender_version_id == version_id,
            BidSubmission.bidder_id == bidder_id,
            BidSubmission.submission_reference == data.submission_reference,
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Submission reference '{data.submission_reference}' already exists for this bidder and version.",
        )

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version_id,
        bidder_id=bidder_id,
        submission_reference=data.submission_reference,
        status=SubmissionStatus.RECEIVED,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)
    return submission


def list_submissions(
    db: Session,
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    bidder_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[BidSubmission], int]:
    """List submissions for a bidder under a specific tender version."""
    # Validate relationships
    get_bidder(db=db, tender_id=tender_id, bidder_id=bidder_id)

    total = db.execute(
        select(func.count(BidSubmission.id)).where(
            BidSubmission.tender_version_id == version_id,
            BidSubmission.bidder_id == bidder_id,
        )
    ).scalar_one()

    stmt = (
        select(BidSubmission)
        .where(
            BidSubmission.tender_version_id == version_id,
            BidSubmission.bidder_id == bidder_id,
        )
        .order_by(BidSubmission.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    items = db.execute(stmt).scalars().all()
    return items, total


def get_submission(
    db: Session,
    submission_id: uuid.UUID,
) -> BidSubmission:
    """Retrieve submission entity by ID."""
    submission = db.get(BidSubmission, submission_id)
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Submission {submission_id} not found.",
        )
    return submission


# --- Evidence Extraction Pipeline ---

async def extract_submission_evidence(
    db: Session,
    submission_id: uuid.UUID,
    current_user: User,
    criterion_id: Optional[uuid.UUID] = None,
    storage: Optional[ObjectStorageService] = None,
    llm_client: Optional[BaseEvidenceLLMClient] = None,
) -> EvidenceExtractionRun:
    """
    Execute AI evidence extraction against bidder submission documents targeting APPROVED criteria:
    1. Validates submission and retrieves tender version.
    2. Fetches approved criteria for that exact tender version.
    3. Retrieves completed submission documents and their normalized artifacts.
    4. Runs LLM evidence extraction chunk-by-chunk.
    5. Validates citations and detects conflicting evidence across documents.
    6. Persists extraction run and auditable evidence records atomically.
    """
    settings = get_settings()
    storage = storage or get_storage_service()
    llm_client = llm_client or get_evidence_llm_client()

    submission = get_submission(db=db, submission_id=submission_id)
    tender_version_id = submission.tender_version_id

    # 1. Fetch APPROVED criteria only (Rule from Phase 8)
    all_approved = get_approved_criteria(db=db, tender_version_id=tender_version_id)
    if criterion_id:
        target_criteria = [c for c in all_approved if c.id == criterion_id]
        if not target_criteria:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Criterion {criterion_id} is not an APPROVED criterion for tender version {tender_version_id}.",
            )
    else:
        target_criteria = all_approved

    if not target_criteria:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No APPROVED tender criteria exist for this tender version. Officer approval required prior to evidence extraction.",
        )

    # 2. Fetch completed submission documents
    doc_stmt = select(Document).where(
        Document.bid_submission_id == submission_id,
        Document.processing_status == ProcessingStatus.COMPLETED,
    )
    docs = db.execute(doc_stmt).scalars().all()
    if not docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No completed documents found for this submission. Upload and process documents before extracting evidence.",
        )

    # 3. Create EvidenceExtractionRun in PENDING state
    extraction_run = EvidenceExtractionRun(
        id=uuid.uuid4(),
        bid_submission_id=submission_id,
        criterion_id=criterion_id,
        model_name=llm_client.model_name,
        model_version=settings.APP_VERSION,
        prompt_version=settings.EXTRACTION_PROMPT_VERSION,
        extractor_version="v1.0",
        status=ExtractionRunStatus.RUNNING,
        evidence_count=0,
        created_by=current_user.id,
    )
    db.add(extraction_run)
    submission.status = SubmissionStatus.PROCESSING
    db.commit()
    db.refresh(extraction_run)

    criteria_by_code = {c.criterion_code: c for c in target_criteria if c.criterion_code}

    try:
        raw_items: List[Tuple[RawEvidenceItem, Document, Optional[NormalizedDocument]]] = []

        # Summarize criteria for prompt
        crit_summary = "\n".join(
            f"- [{c.criterion_code}] {c.name}: {c.description or ''} (Required: {c.required_evidence or 'Evidence document'})"
            for c in target_criteria
        )

        # 4. Extract evidence from each document chunk
        for doc in docs:
            # Find normalized document artifact
            art_stmt = select(ProcessingArtifact).where(
                ProcessingArtifact.document_id == doc.id,
                ProcessingArtifact.artifact_type == ArtifactType.NORMALIZED_CONTENT,
            )
            artifact_record = db.execute(art_stmt).scalar_one_or_none()
            if not artifact_record:
                logger.warning("Document %s missing NORMALIZED_CONTENT artifact, skipping", doc.id)
                continue

            stream = storage.download(artifact_record.storage_key)
            artifact_bytes = stream.read()
            norm_doc_data = json.loads(artifact_bytes.decode("utf-8"))
            normalized_doc = NormalizedDocument.model_validate(norm_doc_data)

            chunks = create_extraction_chunks(normalized_doc)
            for chunk in chunks:
                user_prompt = build_evidence_user_prompt(
                    approved_criteria_summary=crit_summary,
                    document_name=doc.filename,
                    chunk_text=chunk.formatted_text,
                    page_number=chunk.start_page,
                    block_ids=[b.block_id for b in chunk.blocks],
                )
                extraction_resp = await llm_client.extract_evidence(
                    system_prompt=EVIDENCE_EXTRACTION_SYSTEM_PROMPT_V1,
                    user_prompt=user_prompt,
                    chunk=chunk,
                    approved_criteria=target_criteria,
                    document_id=str(doc.id),
                )
                for item in extraction_resp.extracted_items:
                    raw_items.append((item, doc, normalized_doc))

        # 5. Validate source citations & normalize entity names
        validated_items: List[Tuple[RawEvidenceItem, Document]] = []
        for raw_item, doc, norm_doc in raw_items:
            final_status, note = validate_evidence_source_citations(raw_item, norm_doc)
            raw_item.status = final_status
            if note:
                raw_item.ambiguity_reason = (
                    f"{raw_item.ambiguity_reason}; {note}" if raw_item.ambiguity_reason else note
                )
            if raw_item.extracted_bidder_name:
                raw_item.extracted_bidder_name = normalize_bidder_legal_name(raw_item.extracted_bidder_name)
            validated_items.append((raw_item, doc))

        # 6. Detect conflicting evidence across documents
        all_raw_list = [it for it, _ in validated_items]
        detect_evidence_conflicts(all_raw_list)

        # 7. Persist Evidence entities
        found_criteria_ids = set()
        persisted_count = 0

        for raw_item, doc in validated_items:
            crit = criteria_by_code.get(raw_item.criterion_code)
            if not crit:
                continue

            found_criteria_ids.add(crit.id)
            cert_dict = raw_item.certificate_data.model_dump() if raw_item.certificate_data else None
            exp_dict = raw_item.experience_data.model_dump() if raw_item.experience_data else None

            evidence_record = Evidence(
                id=uuid.uuid4(),
                criterion_id=crit.id,
                bid_submission_id=submission_id,
                document_id=doc.id,
                extraction_run_id=extraction_run.id,
                evidence_type=raw_item.evidence_type,
                extracted_text=raw_item.extracted_text,
                extracted_value=raw_item.extracted_value,
                normalized_value=raw_item.normalized_value,
                unit=raw_item.unit,
                currency=raw_item.currency,
                period=raw_item.period,
                date_value=raw_item.date_value,
                certificate_data=cert_dict,
                experience_data=exp_dict,
                extracted_bidder_name=raw_item.extracted_bidder_name,
                status=raw_item.status,
                confidence=raw_item.confidence,
                source_page=raw_item.source_page,
                source_block_id=raw_item.source_block_id,
                source_table_reference=raw_item.source_table_reference,
                bbox=raw_item.bbox,
                validation_notes=raw_item.ambiguity_reason,
                extractor_version=extraction_run.extractor_version,
            )
            db.add(evidence_record)
            persisted_count += 1

        # 8. Record placeholder MISSING evidence for approved criteria with 0 evidence found
        for crit in target_criteria:
            if crit.id not in found_criteria_ids:
                missing_record = Evidence(
                    id=uuid.uuid4(),
                    criterion_id=crit.id,
                    bid_submission_id=submission_id,
                    document_id=None,
                    extraction_run_id=extraction_run.id,
                    evidence_type="DOCUMENT",
                    extracted_text=None,
                    extracted_value=None,
                    normalized_value=None,
                    status=EvidenceStatus.MISSING,
                    confidence=1.0,
                    validation_notes=f"Required evidence '{crit.required_evidence or crit.name}' not found in any submission documents.",
                    extractor_version=extraction_run.extractor_version,
                )
                db.add(missing_record)
                persisted_count += 1

        # 9. Finalize ExtractionRun & Submission Status
        finish_time = datetime.datetime.now(datetime.timezone.utc)
        extraction_run.status = ExtractionRunStatus.COMPLETED
        extraction_run.completed_at = finish_time
        extraction_run.evidence_count = persisted_count
        submission.status = SubmissionStatus.READY

        db.commit()
        db.refresh(extraction_run)
        logger.info(
            "Evidence extraction completed for submission %s: %d evidence items persisted",
            submission_id,
            persisted_count,
        )
        return extraction_run

    except Exception as exc:
        db.rollback()
        logger.error("Evidence extraction failed for submission %s: %s", submission_id, str(exc))
        fail_time = datetime.datetime.now(datetime.timezone.utc)
        extraction_run.status = ExtractionRunStatus.FAILED
        extraction_run.completed_at = fail_time
        extraction_run.error_code = "EVIDENCE_EXTRACTION_FAILURE"
        extraction_run.error_message = str(exc)[:500]
        submission.status = SubmissionStatus.REVIEW
        try:
            db.add(extraction_run)
            db.commit()
            db.refresh(extraction_run)
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence extraction failed: {str(exc)}",
        )


# --- Evidence Retrieval ---

def list_submission_evidence(
    db: Session,
    submission_id: uuid.UUID,
    criterion_id: Optional[uuid.UUID] = None,
    evidence_status: Optional[EvidenceStatus] = None,
    document_id: Optional[uuid.UUID] = None,
    skip: int = 0,
    limit: int = 50,
) -> Tuple[List[Evidence], int]:
    """Retrieve filtered evidence items for a submission."""
    query = select(Evidence).where(Evidence.bid_submission_id == submission_id)

    if criterion_id:
        query = query.where(Evidence.criterion_id == criterion_id)
    if evidence_status:
        query = query.where(Evidence.status == evidence_status)
    if document_id:
        query = query.where(Evidence.document_id == document_id)

    total = db.execute(
        select(func.count(Evidence.id)).where(Evidence.bid_submission_id == submission_id)
    ).scalar_one()

    items = db.execute(
        query.order_by(Evidence.created_at.asc()).offset(skip).limit(limit)
    ).scalars().all()

    return items, total


def get_evidence_by_id(
    db: Session,
    evidence_id: uuid.UUID,
) -> Evidence:
    """Retrieve single evidence record with full traceability."""
    evidence = db.get(Evidence, evidence_id)
    if not evidence:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence {evidence_id} not found.",
        )
    return evidence
