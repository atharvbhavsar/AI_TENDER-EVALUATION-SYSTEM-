"""AI Tender Criterion Extraction domain service."""

import datetime
import json
import logging
import uuid
from typing import Dict, List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.criterion_source_reference import CriterionSourceReference
from app.db.models.document import Document, ProcessingStatus
from app.db.models.extraction_run import ExtractionRun, ExtractionRunStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.tender import Tender
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.extraction.chunking import create_extraction_chunks
from app.extraction.deduplication import (
    consolidate_candidate_criteria,
    generate_criterion_code,
)
from app.extraction.llm.base import BaseLLMClient
from app.extraction.llm.client import get_llm_client
from app.extraction.prompts.v1 import (
    CRITERION_EXTRACTION_PROMPT_V1,
    build_user_prompt,
)
from app.extraction.schemas import ExtractedCriterionRaw
from app.pipeline.schemas import NormalizedDocument
from app.storage.base import ObjectStorageService

logger = logging.getLogger("app.extraction.service")


async def extract_criteria_for_tender_version(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    user: User,
    storage: ObjectStorageService,
    llm_client: Optional[BaseLLMClient] = None,
) -> ExtractionRun:
    """
    Execute AI criterion extraction against all processed documents for a tender version:
    1. Verify tender and tender_version association.
    2. Ensure usable processed documents exist.
    3. Initialize and persist ExtractionRun record.
    4. Fetch normalized artifacts, chunk context, and extract structured criteria via LLM adapter.
    5. Deduplicate, generate stable codes, and persist criteria and source references atomically.
    6. Maintain complete auditability and error state tracking.
    """
    settings = get_settings()
    if llm_client is None:
        llm_client = get_llm_client(settings)

    # 1. Validate tender and tender_version
    tender = db.execute(select(Tender).where(Tender.id == tender_id)).scalar_one_or_none()
    if not tender:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tender '{tender_id}' not found.",
        )

    version = db.execute(
        select(TenderVersion).where(
            TenderVersion.id == tender_version_id,
            TenderVersion.tender_id == tender_id,
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TenderVersion '{tender_version_id}' not found for Tender '{tender_id}'.",
        )

    # 2. Retrieve completed documents for this version
    docs = db.execute(
        select(Document).where(
            Document.tender_version_id == tender_version_id,
            Document.processing_status == ProcessingStatus.COMPLETED,
        )
    ).scalars().all()

    if not docs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No successfully processed documents available for this tender version. Please upload and process documents first.",
        )

    # 3. Create ExtractionRun record
    run_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)
    extraction_run = ExtractionRun(
        id=run_id,
        tender_version_id=tender_version_id,
        model_name=llm_client.model_name,
        model_version=settings.APP_VERSION,
        prompt_version=settings.EXTRACTION_PROMPT_VERSION,
        extractor_version=settings.EXTRACTOR_VERSION,
        status=ExtractionRunStatus.RUNNING,
        criteria_count=0,
        started_at=now,
        created_by=user.id,
    )
    db.add(extraction_run)
    db.commit()
    db.refresh(extraction_run)

    raw_criteria_accumulated: List[Tuple[uuid.UUID, ExtractedCriterionRaw]] = []

    try:
        # 4. Process each document's normalized artifact
        for doc in docs:
            # Find normalized JSON artifact key
            artifact = db.execute(
                select(ProcessingArtifact).where(
                    ProcessingArtifact.document_id == doc.id,
                    ProcessingArtifact.artifact_type == ArtifactType.NORMALIZED_CONTENT,
                )
            ).scalar_one_or_none()

            artifact_key = (
                artifact.storage_key
                if artifact
                else f"documents/tender/{tender_id}/version/{tender_version_id}/{doc.id}/artifacts/normalized_content.json"
            )

            # Download normalized document artifact from storage
            try:
                stream = storage.download(artifact_key)
                content_bytes = stream.read() if hasattr(stream, "read") else bytes(stream)
                doc_json = json.loads(content_bytes.decode("utf-8"))
                normalized_doc = NormalizedDocument.model_validate(doc_json)
            except Exception as read_err:
                logger.warning("Could not read normalized artifact for doc %s: %s", doc.id, str(read_err))
                continue

            # Chunk document content
            chunks = create_extraction_chunks(
                normalized_doc=normalized_doc,
                max_chunk_chars=settings.MAX_EXTRACTION_CHUNK_SIZE,
            )

            for chunk in chunks:
                user_prompt = build_user_prompt(chunk.formatted_text, doc.filename)
                raw_response = await llm_client.extract_structured(
                    system_prompt=CRITERION_EXTRACTION_PROMPT_V1,
                    user_prompt=user_prompt,
                    chunk=chunk,
                )

                for cand in raw_response.criteria:
                    raw_criteria_accumulated.append((doc.id, cand))

        if not raw_criteria_accumulated:
            logger.info("No criteria identified in tender documents for version %s", tender_version_id)

        # 5. Consolidate criteria
        all_candidates = [cand for _, cand in raw_criteria_accumulated]
        doc_map = {cand.source_clause: doc_id for doc_id, cand in raw_criteria_accumulated}
        consolidated = consolidate_candidate_criteria(all_candidates)

        # 6. Assign stable sequential codes per category and persist
        category_counters: Dict[CriterionCategory, int] = {cat: 1 for cat in CriterionCategory}

        # Check existing criterion count for this version to avoid collisions
        existing_criteria = db.execute(
            select(TenderCriterion).where(TenderCriterion.tender_version_id == tender_version_id)
        ).scalars().all()
        for ec in existing_criteria:
            if ec.criterion_code:
                parts = ec.criterion_code.split("-")
                if len(parts) == 2 and parts[1].isdigit():
                    num = int(parts[1])
                    if num >= category_counters.get(ec.category, 1):
                        category_counters[ec.category] = num + 1

        persisted_criteria_count = 0
        for cand in consolidated:
            cat = cand.category
            seq_num = category_counters[cat]
            category_counters[cat] += 1
            code = generate_criterion_code(cat, seq_num)
            doc_id = doc_map.get(cand.source_clause, docs[0].id)

            criterion = TenderCriterion(
                id=uuid.uuid4(),
                tender_version_id=tender_version_id,
                extraction_run_id=extraction_run.id,
                criterion_code=code,
                name=cand.name,
                description=cand.description,
                category=cand.category,
                requirement_type=cand.requirement_type,
                condition_text=cand.condition_text,
                operator=cand.operator,
                threshold_value=cand.threshold_value,
                threshold_text=cand.threshold_text,
                unit=cand.unit,
                currency=cand.currency,
                period=cand.period,
                mandatory=cand.mandatory,
                required_evidence=cand.required_evidence,
                source_clause=cand.source_clause,
                source_page=cand.source_page,
                source_section=cand.source_section,
                source_block_id=cand.source_block_id,
                source_table_reference=cand.source_table_reference,
                confidence=cand.confidence,
                extraction_status=cand.extraction_status,
                explanation=cand.explanation,
                model_name=llm_client.model_name,
                model_version=settings.APP_VERSION,
                prompt_version=settings.EXTRACTION_PROMPT_VERSION,
                # Phase 8 fields
                approval_status=ApprovalStatus.PENDING_REVIEW,
                is_corrected=False,
                original_name=cand.name,
                original_description=cand.description,
                original_category=cand.category,
                original_requirement_type=cand.requirement_type,
                original_operator=cand.operator,
                original_threshold_value=cand.threshold_value,
                original_threshold_text=cand.threshold_text,
                original_unit=cand.unit,
                original_currency=cand.currency,
                original_period=cand.period,
                original_mandatory=cand.mandatory,
                original_required_evidence=cand.required_evidence,
                original_source_clause=cand.source_clause,
            )
            db.add(criterion)
            db.flush()

            # Primary source reference
            primary_ref = CriterionSourceReference(
                id=uuid.uuid4(),
                criterion_id=criterion.id,
                document_id=doc_id,
                page_number=cand.source_page,
                section=cand.source_section,
                block_id=cand.source_block_id,
                table_reference=cand.source_table_reference,
                source_text=cand.source_clause,
            )
            db.add(primary_ref)

            # Additional sources if present
            for add_src in cand.additional_sources:
                add_ref = CriterionSourceReference(
                    id=uuid.uuid4(),
                    criterion_id=criterion.id,
                    document_id=doc_id,
                    page_number=add_src.page_number,
                    section=add_src.section,
                    block_id=add_src.block_id,
                    table_reference=add_src.table_reference,
                    bbox=add_src.bbox,
                    source_text=add_src.source_text,
                )
                db.add(add_ref)

            persisted_criteria_count += 1

        # 7. Update and finalize ExtractionRun
        finish_time = datetime.datetime.now(datetime.timezone.utc)
        extraction_run.status = ExtractionRunStatus.COMPLETED
        extraction_run.completed_at = finish_time
        extraction_run.criteria_count = persisted_criteria_count
        db.commit()
        db.refresh(extraction_run)

        logger.info(
            "Successfully completed AI extraction run %s for tender version %s (extracted %d criteria)",
            extraction_run.id,
            tender_version_id,
            persisted_criteria_count,
        )
        return extraction_run

    except Exception as exc:
        db.rollback()
        logger.error("Extraction run %s failed: %s", extraction_run.id, str(exc))
        try:
            # Record failure in database for auditability
            fail_time = datetime.datetime.now(datetime.timezone.utc)
            extraction_run.status = ExtractionRunStatus.FAILED
            extraction_run.completed_at = fail_time
            extraction_run.error_code = "EXTRACTION_FAILURE"
            extraction_run.error_message = str(exc)[:500]
            db.add(extraction_run)
            db.commit()
            db.refresh(extraction_run)
        except Exception as record_exc:
            logger.critical("Failed to record extraction run failure state: %s", str(record_exc))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI Criterion Extraction failed: {str(exc)}",
        )


def get_extraction_run_by_id(db: Session, run_id: uuid.UUID) -> ExtractionRun:
    """Retrieve extraction run record by UUID."""
    stmt = select(ExtractionRun).where(ExtractionRun.id == run_id)
    run = db.execute(stmt).scalar_one_or_none()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"ExtractionRun '{run_id}' not found.",
        )
    return run


def get_latest_extraction_run(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
) -> ExtractionRun:
    """Retrieve latest extraction run for a tender version."""
    db.expire_all()
    stmt = (
        select(ExtractionRun)
        .where(ExtractionRun.tender_version_id == tender_version_id)
        .order_by(
            ExtractionRun.started_at.desc(),
            ExtractionRun.created_at.desc(),
            ExtractionRun.id.desc(),
        )
    )
    run = db.execute(stmt).scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No extraction runs found for Tender Version '{tender_version_id}'.",
        )
    return run


def list_criteria_for_version(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    category: Optional[CriterionCategory] = None,
    requirement_type: Optional[RequirementType] = None,
    extraction_status: Optional[ExtractionStatus] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[TenderCriterion], int]:
    """List extracted candidate criteria for a specific tender version with filters."""
    # Validate tender version exists
    version = db.execute(
        select(TenderVersion).where(
            TenderVersion.id == tender_version_id,
            TenderVersion.tender_id == tender_id,
        )
    ).scalar_one_or_none()
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"TenderVersion '{tender_version_id}' not found for Tender '{tender_id}'.",
        )

    base_query = select(TenderCriterion).where(
        TenderCriterion.tender_version_id == tender_version_id
    )

    if category:
        base_query = base_query.where(TenderCriterion.category == category)
    if requirement_type:
        base_query = base_query.where(TenderCriterion.requirement_type == requirement_type)
    if extraction_status:
        base_query = base_query.where(TenderCriterion.extraction_status == extraction_status)

    total = db.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 0
    items = (
        db.execute(
            base_query.order_by(TenderCriterion.criterion_code.asc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return list(items), total


def get_criterion_by_id(
    db: Session,
    tender_id: uuid.UUID,
    tender_version_id: uuid.UUID,
    criterion_id: uuid.UUID,
) -> TenderCriterion:
    """Retrieve detailed criterion entity with source references."""
    stmt = select(TenderCriterion).where(
        TenderCriterion.id == criterion_id,
        TenderCriterion.tender_version_id == tender_version_id,
    )
    criterion = db.execute(stmt).scalar_one_or_none()
    if not criterion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Criterion '{criterion_id}' not found for Tender Version '{tender_version_id}'.",
        )
    return criterion
