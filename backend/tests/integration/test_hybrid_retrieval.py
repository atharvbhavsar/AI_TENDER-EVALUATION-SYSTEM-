"""Integration tests for hybrid retrieval (lexical + semantic) across bidder submissions."""

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
    TableData,
)
from app.storage.service import get_storage_service


@pytest.fixture
def hybrid_search_fixture(db_session, procurement_officer_user, procurement_officer_token):
    """Setup full hierarchy: Tender -> Version -> Approved Criterion -> Bidder -> Submission -> Indexed Document."""
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-HYB-{uuid.uuid4().hex[:6]}",
        title="High Altitude Surveillance Drones",
        status=TenderStatus.PUBLISHED,
        created_by=procurement_officer_user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        is_active=True,
        created_by=procurement_officer_user.id,
    )
    db_session.add(version)
    db_session.flush()

    # 1. Approved criteria
    crit_fin = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="FIN-001",
        name="Annual Financial Turnover",
        description="Average annual turnover must exceed ₹10 crore across the last 3 financial years",
        required_evidence=["Audited Balance Sheets & CA Certificate"],
        threshold_text=">= Rs 10 Crore",
        threshold_value=100000000.0,
        source_clause="Clause 3.2: Financial Eligibility",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=procurement_officer_user.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    crit_cert = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="CERT-001",
        name="Quality Management Certification",
        description="Must hold valid ISO 9001:2015 certification for aerospace equipment manufacturing",
        required_evidence=["Valid ISO 9001 Certificate"],
        source_clause="Clause 4.1: Quality Standards",
        category=CriterionCategory.CERTIFICATION,
        requirement_type=RequirementType.MANDATORY,
        model_name="mock-llm",
        model_version="v1.0",
        prompt_version="v1.0",
        approval_status=ApprovalStatus.APPROVED,
        approved_by=procurement_officer_user.id,
        approved_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add_all([crit_fin, crit_cert])
    db_session.flush()

    # 2. Bidder and Submission
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BIDDER-ALPHA",
        legal_name="Alpha Dynamics Private Limited",
        contact_email="bids@alphadynamics.com",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-ALPHA-001",
        status=SubmissionStatus.PROCESSING,
    )
    db_session.add(submission)
    db_session.flush()

    # 3. Bidder Document
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="Alpha_Technical_Proposal.pdf",
        storage_key=f"submissions/{submission.id}/docs/{uuid.uuid4()}.pdf",
        file_size=60000,
        content_type="application/pdf",
        file_extension=".pdf",
        sha256_hash="dummy_hash_alpha",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=procurement_officer_user.id,
    )
    db_session.add(doc)
    db_session.flush()

    # 4. Normalized Document with financial table and ISO certificate text
    norm_doc = NormalizedDocument(
        document_id=doc.id,
        document_type="PDF",
        processor_version="1.0.0",
        page_count=2,
        pages=[
            DocumentPage(
                page_number=1,
                blocks=[
                    DocumentBlock(
                        block_id="b1",
                        type=BlockType.HEADING,
                        text="Financial Statements and Turnover",
                    ),
                    DocumentBlock(
                        block_id="b2",
                        type=BlockType.TEXT,
                        text="Alpha Dynamics confirms audited annual turnover for the past 3 fiscal years.",
                    ),
                    DocumentBlock(
                        block_id="b3",
                        type=BlockType.TABLE,
                        table_data=TableData(
                            headers=["Fiscal Year", "Annual Turnover (INR Cr)", "Auditor"],
                            rows=[
                                ["2022-2023", "12.50", "KPMG India"],
                                ["2023-2024", "16.80", "KPMG India"],
                                ["2024-2025", "21.40", "KPMG India"],
                            ],
                        ),
                        bbox=[50.0, 150.0, 500.0, 300.0],
                    ),
                ],
            ),
            DocumentPage(
                page_number=2,
                blocks=[
                    DocumentBlock(
                        block_id="b4",
                        type=BlockType.HEADING,
                        text="Quality Certifications & Accreditations",
                    ),
                    DocumentBlock(
                        block_id="b5",
                        type=BlockType.TEXT,
                        text="We hold valid ISO 9001:2015 certification for design, manufacturing, and supply of defense UAV systems.",
                    ),
                ],
            ),
        ],
    )

    storage = get_storage_service()
    art_key = f"artifacts/{doc.id}/normalized.json"
    storage.upload(art_key, json.dumps(norm_doc.model_dump(mode="json")).encode("utf-8"), "application/json")

    artifact = ProcessingArtifact(
        id=uuid.uuid4(),
        document_id=doc.id,
        artifact_type=ArtifactType.NORMALIZED_CONTENT,
        storage_key=art_key,
        file_size=len(json.dumps(norm_doc.model_dump(mode="json"))),
        mime_type="application/json",
    )
    db_session.add(artifact)
    db_session.commit()

    return {
        "officer": procurement_officer_user,
        "tender": tender,
        "version": version,
        "criterion_fin": crit_fin,
        "criterion_cert": crit_cert,
        "bidder": bidder,
        "submission": submission,
        "document": doc,
        "token": procurement_officer_token,
    }


def test_search_by_approved_criterion(client: TestClient, hybrid_search_fixture):
    doc = hybrid_search_fixture["document"]
    submission = hybrid_search_fixture["submission"]
    crit_fin = hybrid_search_fixture["criterion_fin"]
    token = hybrid_search_fixture["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Index document first
    index_resp = client.post(f"/api/v1/documents/{doc.id}/index", headers=headers)
    assert index_resp.status_code == 200

    # 2. Search by financial criterion
    search_payload = {
        "criterion_id": str(crit_fin.id),
        "top_k": 5,
        "lexical_weight": 0.4,
        "semantic_weight": 0.6,
    }
    resp = client.post(
        f"/api/v1/submissions/{submission.id}/retrieval/search",
        json=search_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["submission_id"] == str(submission.id)
    assert data["criterion_id"] == str(crit_fin.id)
    assert data["returned_count"] > 0

    # The table or text discussing turnover should be top ranked
    top_result = data["results"][0]
    assert top_result["rank"] == 1
    assert "turnover" in top_result["content"].lower() or "financial" in top_result["content"].lower()
    assert top_result["document_name"] == "Alpha_Technical_Proposal.pdf"


def test_search_by_text_query(client: TestClient, hybrid_search_fixture):
    doc = hybrid_search_fixture["document"]
    submission = hybrid_search_fixture["submission"]
    token = hybrid_search_fixture["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Index document
    client.post(f"/api/v1/documents/{doc.id}/index", headers=headers)

    # Search for ISO 9001
    query_payload = {
        "query": "ISO 9001:2015 certification quality",
        "top_k": 3,
    }
    resp = client.post(
        f"/api/v1/submissions/{submission.id}/retrieval/query",
        json=query_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["returned_count"] > 0
    top_result = data["results"][0]
    assert "iso 9001" in top_result["content"].lower()
    assert top_result["page"] == 2
