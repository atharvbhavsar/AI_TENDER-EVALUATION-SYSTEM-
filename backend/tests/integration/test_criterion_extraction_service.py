"""Integration tests for AI Criterion Extraction domain service."""

import json
import pytest
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.service import create_user
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.extraction_run import ExtractionRun, ExtractionRunStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import (
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.extraction.llm.mock import MockLLMClient
from app.extraction.service import (
    extract_criteria_for_tender_version,
    get_criterion_by_id,
    get_latest_extraction_run,
    list_criteria_for_version,
)
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument
from app.storage.memory import InMemoryObjectStorageService


@pytest.fixture
def mock_procurement_user(db_session: Session) -> User:
    """Create a test procurement officer user."""
    return create_user(
        db=db_session,
        email="extraction_officer@crpf.gov.in",
        password="SecureOfficerPassword123!",
        full_name="Extraction Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )


@pytest.fixture
def tender_with_processed_document(
    db_session: Session,
    mock_procurement_user: User,
    memory_storage: InMemoryObjectStorageService,
):
    """Set up a tender, active version, completed document, and normalized content artifact in storage."""
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-EXTRACT-{uuid.uuid4().hex[:6].upper()}",
        title="Procurement of Tactical Surveillance UAVs",
        description="High-altitude surveillance drone procurement tender.",
        status=TenderStatus.DRAFT,
        created_by=mock_procurement_user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=mock_procurement_user.id,
    )
    db_session.add(version)
    db_session.flush()

    document = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="tactical_uav_specs.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key=f"documents/tender/{tender.id}/version/{version.id}/doc.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=mock_procurement_user.id,
    )
    db_session.add(document)
    db_session.flush()

    # Create normalized artifact in storage
    norm_doc = NormalizedDocument(
        document_id=document.id,
        document_type="DIGITAL_PDF",
        processor_version="1.0.0",
        page_count=2,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="b1",
                        type=BlockType.HEADING,
                        text="Section 3: Eligibility and Qualification Criteria",
                    ),
                    DocumentBlock(
                        block_id="b2",
                        type=BlockType.TEXT,
                        text="The bidder shall have an average annual turnover of at least ₹5 Crore during the preceding three financial years. Audited balance sheets must be submitted.",
                    ),
                    DocumentBlock(
                        block_id="b3",
                        type=BlockType.TEXT,
                        text="The bidder must be registered under GST and possess valid GSTIN certificate.",
                    ),
                ],
            ),
            DocumentPage(
                page_number=2,
                blocks=[
                    DocumentBlock(
                        block_id="b4",
                        type=BlockType.TEXT,
                        text="Bidder must have completed 3 similar projects during the last 5 years. Completion certificates required.",
                    ),
                    DocumentBlock(
                        block_id="b5",
                        type=BlockType.TEXT,
                        text="The bidder shall possess a valid ISO 9001:2015 Quality Management System certificate.",
                    ),
                ],
            ),
        ],
    )

    artifact_key = f"documents/tender/{tender.id}/version/{version.id}/{document.id}/artifacts/normalized_content.json"
    json_bytes = norm_doc.model_dump_json(indent=2).encode("utf-8")
    memory_storage.upload(artifact_key, json_bytes, content_type="application/json")

    artifact = ProcessingArtifact(
        id=uuid.uuid4(),
        document_id=document.id,
        artifact_type=ArtifactType.NORMALIZED_CONTENT,
        storage_key=artifact_key,
        file_size=len(json_bytes),
        mime_type="application/json",
    )
    db_session.add(artifact)
    db_session.commit()

    return tender, version, document, norm_doc


@pytest.mark.asyncio
async def test_extract_criteria_service_lifecycle(
    db_session: Session,
    mock_procurement_user: User,
    memory_storage: InMemoryObjectStorageService,
    tender_with_processed_document,
):
    """Test full extraction service run, code generation, and database persistence."""
    tender, version, document, _ = tender_with_processed_document
    llm_client = MockLLMClient()

    run = await extract_criteria_for_tender_version(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
        user=mock_procurement_user,
        storage=memory_storage,
        llm_client=llm_client,
    )

    assert run.status == ExtractionRunStatus.COMPLETED
    assert run.criteria_count >= 4
    assert run.completed_at is not None

    # Verify criteria in database
    criteria, total = list_criteria_for_version(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
    )
    assert total >= 4

    # Verify stable sequential code generation (e.g. FIN-001, TECH-001, COMP-001, CERT-001)
    codes = {c.criterion_code for c in criteria}
    assert any(c.startswith("FIN-") for c in codes)
    assert any(c.startswith("TECH-") for c in codes)
    assert any(c.startswith("COMP-") for c in codes)
    assert any(c.startswith("CERT-") for c in codes)

    # Verify source references
    fin_crit = next(c for c in criteria if c.category == CriterionCategory.FINANCIAL)
    assert len(fin_crit.source_references) >= 1
    assert fin_crit.source_references[0].document_id == document.id
    assert fin_crit.source_references[0].page_number == 1
    assert "₹5 Crore" in fin_crit.source_references[0].source_text


@pytest.mark.asyncio
async def test_extraction_version_isolation(
    db_session: Session,
    mock_procurement_user: User,
    memory_storage: InMemoryObjectStorageService,
    tender_with_processed_document,
):
    """Test that criteria extracted for Version 1 are strictly isolated from Version 2."""
    tender, version1, document, _ = tender_with_processed_document
    llm_client = MockLLMClient()

    # Extract for Version 1
    await extract_criteria_for_tender_version(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version1.id,
        user=mock_procurement_user,
        storage=memory_storage,
        llm_client=llm_client,
    )

    v1_criteria, v1_total = list_criteria_for_version(db_session, tender.id, version1.id)
    assert v1_total >= 4

    # Create Version 2
    version2 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=2,
        version_label="Amendment 1",
        is_active=True,
        created_by=mock_procurement_user.id,
    )
    version1.is_active = False
    db_session.add(version2)
    db_session.commit()

    # Verify Version 2 currently has 0 criteria
    v2_criteria, v2_total = list_criteria_for_version(db_session, tender.id, version2.id)
    assert v2_total == 0

    # Ensure Version 1 criteria remain unchanged
    v1_check, v1_check_total = list_criteria_for_version(db_session, tender.id, version1.id)
    assert v1_check_total == v1_total


@pytest.mark.asyncio
async def test_extraction_failure_rollback_and_status_tracking(
    db_session: Session,
    mock_procurement_user: User,
    memory_storage: InMemoryObjectStorageService,
    tender_with_processed_document,
):
    """Test that LLM failure safely records FAILED ExtractionRun without dangling criteria."""
    tender, version, _, _ = tender_with_processed_document
    failing_client = MockLLMClient(should_fail=True)

    with pytest.raises(Exception):
        await extract_criteria_for_tender_version(
            db=db_session,
            tender_id=tender.id,
            tender_version_id=version.id,
            user=mock_procurement_user,
            storage=memory_storage,
            llm_client=failing_client,
        )

    # Check extraction run record status
    run = get_latest_extraction_run(db_session, tender.id, version.id)
    assert run.status == ExtractionRunStatus.FAILED
    assert run.error_code == "EXTRACTION_FAILURE"

    # Verify no dangling criteria were saved
    criteria, total = list_criteria_for_version(db_session, tender.id, version.id)
    assert total == 0
