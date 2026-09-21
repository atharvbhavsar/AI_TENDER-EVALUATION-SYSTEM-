"""Integration tests for version control immutability and re-extraction safety."""

import pytest
import uuid
from sqlalchemy.orm import Session

from app.approval.schemas import CriterionApprovalRequest
from app.approval.service import approve_criterion, get_approved_criteria
from app.auth.service import create_user
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    ExtractionStatus,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.extraction.llm.mock import MockLLMClient
from app.extraction.service import extract_criteria_for_tender_version, list_criteria_for_version
from app.pipeline.schemas import BlockType, DocumentBlock, DocumentPage, NormalizedDocument
from app.storage.memory import InMemoryObjectStorageService


def test_approved_criteria_immutability_across_versions(db_session: Session):
    """Test that approving criteria in Version 1 preserves them immutably when Version 2 is created and modified."""
    officer = create_user(
        db=db_session,
        email="immutability_officer@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Immutability Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-IMMUT-{uuid.uuid4().hex[:6].upper()}",
        title="Tactical Radios",
        description="Encrypted VHF/UHF tactical radio equipment.",
        status=TenderStatus.DRAFT,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    # Version 1
    v1 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Release 1.0",
        is_active=True,
        created_by=officer.id,
    )
    db_session.add(v1)
    db_session.flush()

    c1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="FIN-001",
        name="Turnover Requirement V1",
        description="5 Crore turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        threshold_value=50000000.0,
        threshold_text="₹5 Crore",
        source_clause="Turnover >= 5 Crore",
        confidence=0.95,
        model_name="mock",
        model_version="1",
        prompt_version="1",
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )
    db_session.add(c1)
    db_session.commit()

    # Approve Version 1 criterion
    approve_criterion(db_session, tender.id, v1.id, c1.id, officer, CriterionApprovalRequest(reason="V1 Approved"))

    # Create Version 2 (Amendment)
    v2 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=2,
        version_label="Release 2.0 (Corrigendum)",
        is_active=True,
        created_by=officer.id,
    )
    v1.is_active = False
    db_session.add(v2)
    db_session.flush()

    c2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v2.id,
        criterion_code="FIN-001",
        name="Turnover Requirement V2 Amended",
        description="10 Crore turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        threshold_value=100000000.0,
        threshold_text="₹10 Crore",
        source_clause="Turnover >= 10 Crore",
        confidence=0.98,
        model_name="mock",
        model_version="1",
        prompt_version="1",
        approval_status=ApprovalStatus.PENDING_REVIEW,
    )
    db_session.add(c2)
    db_session.commit()

    # Query approved criteria for Version 1 vs Version 2
    v1_approved = get_approved_criteria(db_session, v1.id)
    v2_approved = get_approved_criteria(db_session, v2.id)

    assert len(v1_approved) == 1
    assert v1_approved[0].name == "Turnover Requirement V1"
    assert v1_approved[0].threshold_value == 50000000.0
    assert v1_approved[0].approval_status == ApprovalStatus.APPROVED

    # Version 2 has 0 approved criteria (still PENDING_REVIEW)
    assert len(v2_approved) == 0


@pytest.mark.asyncio
async def test_re_extraction_does_not_overwrite_approved_criteria(
    db_session: Session,
    memory_storage: InMemoryObjectStorageService,
):
    """Test that triggering re-extraction on a tender version does not overwrite already approved criteria."""
    officer = create_user(
        db=db_session,
        email="reextract_officer@crpf.gov.in",
        password="SecurePassword123!",
        full_name="Re-extraction Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-REEXT-{uuid.uuid4().hex[:6].upper()}",
        title="Helmets Procurement",
        description="Ballistic helmets.",
        status=TenderStatus.DRAFT,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=officer.id,
    )
    db_session.add(version)
    db_session.flush()

    document = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="helmet_specs.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=1024,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        storage_key=f"documents/tender/{tender.id}/version/{version.id}/doc.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(document)
    db_session.flush()

    norm_doc = NormalizedDocument(
        document_id=document.id,
        document_type="DIGITAL_PDF",
        processor_version="1.0.0",
        page_count=1,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="b1",
                        type=BlockType.TEXT,
                        text="The bidder shall have an average annual turnover of at least ₹5 Crore during preceding three financial years.",
                    )
                ],
            )
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

    # 1. First Extraction Run
    llm_client = MockLLMClient()
    await extract_criteria_for_tender_version(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
        user=officer,
        storage=memory_storage,
        llm_client=llm_client,
    )

    criteria1, _ = list_criteria_for_version(db_session, tender.id, version.id)
    assert len(criteria1) >= 1
    crit1 = criteria1[0]

    # 2. Officer approves criterion
    approve_criterion(db_session, tender.id, version.id, crit1.id, officer, CriterionApprovalRequest(reason="Approved Run 1"))

    # 3. Re-Extraction Run 2
    await extract_criteria_for_tender_version(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
        user=officer,
        storage=memory_storage,
        llm_client=llm_client,
    )

    # Verify approved criterion remains approved and was not silently deleted or overwritten
    db_session.refresh(crit1)
    assert crit1.approval_status == ApprovalStatus.APPROVED
    assert crit1.approved_by == officer.id

    approved_list = get_approved_criteria(db_session, version.id)
    assert len(approved_list) >= 1
    assert any(c.id == crit1.id for c in approved_list)
