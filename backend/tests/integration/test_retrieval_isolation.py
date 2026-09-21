"""Integration tests verifying strict version, bidder, and tender isolation in retrieval."""

import datetime
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import (
    ApprovalStatus,
    CriterionCategory,
    RequirementType,
    TenderCriterion,
)
from app.db.models.tender_version import TenderVersion
from app.pipeline.schemas import (
    BlockType,
    DocumentBlock,
    DocumentPage,
    NormalizedDocument,
)
from app.storage.service import get_storage_service


@pytest.fixture
def multi_bidder_isolation_fixture(db_session, procurement_officer_user, procurement_officer_token):
    """Setup Tender with 2 Bidders, each having their own submission and documents."""
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-ISO-{uuid.uuid4().hex[:6]}",
        title="Tactical Body Armor Procurement",
        status=TenderStatus.PUBLISHED,
        created_by=procurement_officer_user.id,
    )
    db_session.add(tender)
    db_session.flush()

    # Version 1
    version_1 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        is_active=True,
        created_by=procurement_officer_user.id,
    )
    # Version 2
    version_2 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=2,
        is_active=False,
        created_by=procurement_officer_user.id,
    )
    db_session.add_all([version_1, version_2])
    db_session.flush()

    # Approved criterion for Version 1
    crit_v1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version_1.id,
        criterion_code="ARMOR-001",
        name="Ballistic Protection Certificate",
        description="Must provide NIJ Level IV certification",
        source_clause="Clause 4.1: Ballistic Protection",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=procurement_officer_user.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(crit_v1)
    db_session.flush()

    # Bidder A on Version 1
    bidder_a = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BIDDER-ALPHA",
        legal_name="Alpha Defense Corp",
    )
    # Bidder B on Version 1
    bidder_b = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BIDDER-BRAVO",
        legal_name="Bravo Armory Ltd",
    )
    db_session.add_all([bidder_a, bidder_b])
    db_session.flush()

    sub_a = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version_1.id,
        bidder_id=bidder_a.id,
        submission_reference="SUB-ALPHA",
        status=SubmissionStatus.PROCESSING,
    )
    sub_b = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version_1.id,
        bidder_id=bidder_b.id,
        submission_reference="SUB-BRAVO",
        status=SubmissionStatus.PROCESSING,
    )
    db_session.add_all([sub_a, sub_b])
    db_session.flush()

    # Doc A for Bidder A
    doc_a = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version_1.id,
        bid_submission_id=sub_a.id,
        filename="Alpha_Certificates.pdf",
        storage_key=f"submissions/{sub_a.id}/docs/{uuid.uuid4()}.pdf",
        file_size=40000,
        content_type="application/pdf",
        file_extension=".pdf",
        sha256_hash="hash_a",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=procurement_officer_user.id,
    )
    # Doc B for Bidder B
    doc_b = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version_1.id,
        bid_submission_id=sub_b.id,
        filename="Bravo_Secret_Certificates.pdf",
        storage_key=f"submissions/{sub_b.id}/docs/{uuid.uuid4()}.pdf",
        file_size=40000,
        content_type="application/pdf",
        file_extension=".pdf",
        sha256_hash="hash_b",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=procurement_officer_user.id,
    )
    db_session.add_all([doc_a, doc_b])
    db_session.flush()

    storage = get_storage_service()

    # Artifact A
    norm_a = NormalizedDocument(
        document_id=doc_a.id,
        document_type="PDF",
        processor_version="1.0.0",
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="a1",
                        type=BlockType.TEXT,
                        text="Alpha Defense Corp NIJ Level IV Ballistic Certificate Number AL-9988.",
                    )
                ],
            )
        ],
    )
    art_a_key = f"artifacts/{doc_a.id}/normalized.json"
    storage.upload(art_a_key, json.dumps(norm_a.model_dump(mode="json")).encode("utf-8"), "application/json")
    db_session.add(
        ProcessingArtifact(
            id=uuid.uuid4(),
            document_id=doc_a.id,
            artifact_type=ArtifactType.NORMALIZED_CONTENT,
            storage_key=art_a_key,
            file_size=100,
            mime_type="application/json",
        )
    )

    # Artifact B
    norm_b = NormalizedDocument(
        document_id=doc_b.id,
        document_type="PDF",
        processor_version="1.0.0",
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="b1",
                        type=BlockType.TEXT,
                        text="Bravo Armory Proprietary Armor Formula and NIJ Certificate BR-4411.",
                    )
                ],
            )
        ],
    )
    art_b_key = f"artifacts/{doc_b.id}/normalized.json"
    storage.upload(art_b_key, json.dumps(norm_b.model_dump(mode="json")).encode("utf-8"), "application/json")
    db_session.add(
        ProcessingArtifact(
            id=uuid.uuid4(),
            document_id=doc_b.id,
            artifact_type=ArtifactType.NORMALIZED_CONTENT,
            storage_key=art_b_key,
            file_size=100,
            mime_type="application/json",
        )
    )

    db_session.commit()

    return {
        "tender": tender,
        "version_1": version_1,
        "version_2": version_2,
        "criterion_v1": crit_v1,
        "sub_a": sub_a,
        "sub_b": sub_b,
        "doc_a": doc_a,
        "doc_b": doc_b,
        "token": procurement_officer_token,
    }


def test_bidder_isolation_cross_bidder_leakage_prevented(client: TestClient, multi_bidder_isolation_fixture):
    doc_a = multi_bidder_isolation_fixture["doc_a"]
    doc_b = multi_bidder_isolation_fixture["doc_b"]
    sub_a = multi_bidder_isolation_fixture["sub_a"]
    sub_b = multi_bidder_isolation_fixture["sub_b"]
    crit_v1 = multi_bidder_isolation_fixture["criterion_v1"]
    token = multi_bidder_isolation_fixture["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Index both documents
    client.post(f"/api/v1/documents/{doc_a.id}/index", headers=headers)
    client.post(f"/api/v1/documents/{doc_b.id}/index", headers=headers)

    # 1. Search Bidder A's submission
    resp_a = client.post(
        f"/api/v1/submissions/{sub_a.id}/retrieval/search",
        json={"criterion_id": str(crit_v1.id), "top_k": 10},
        headers=headers,
    )
    assert resp_a.status_code == 200
    results_a = resp_a.json()["results"]
    assert len(results_a) > 0
    # Every returned chunk MUST belong to Document A, never Document B
    for r in results_a:
        assert r["document_id"] == str(doc_a.id)
        assert "Bravo" not in r["content"]
        assert "BR-4411" not in r["content"]

    # 2. Search Bidder B's submission
    resp_b = client.post(
        f"/api/v1/submissions/{sub_b.id}/retrieval/search",
        json={"criterion_id": str(crit_v1.id), "top_k": 10},
        headers=headers,
    )
    assert resp_b.status_code == 200
    results_b = resp_b.json()["results"]
    assert len(results_b) > 0
    for r in results_b:
        assert r["document_id"] == str(doc_b.id)
        assert "Alpha" not in r["content"]
        assert "AL-9988" not in r["content"]
