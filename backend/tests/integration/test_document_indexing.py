"""Integration tests for Phase 10 Document Chunking & Indexing lifecycle."""

import datetime
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth.jwt import create_access_token
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.processing_artifact import ArtifactType, ProcessingArtifact
from app.db.models.retrieval_chunk import RetrievalChunk
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.pipeline.schemas import (
    BlockType,
    DocumentBlock,
    DocumentPage,
    NormalizedDocument,
    TableData,
)
from app.storage.service import get_storage_service


@pytest.fixture
def indexing_fixture(db_session, procurement_officer_user, procurement_officer_token):
    """Setup tender, officer, and a completed document with normalized content in storage."""
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-IDX-{uuid.uuid4().hex[:6]}",
        title="Tactical Security System",
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

    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        filename="Technical_Bid_Alpha.pdf",
        storage_key=f"tenders/{tender.id}/docs/{uuid.uuid4()}.pdf",
        file_size=50000,
        content_type="application/pdf",
        file_extension=".pdf",
        sha256_hash="dummy_sha256",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=procurement_officer_user.id,
    )
    db_session.add(doc)
    db_session.flush()

    # Upload normalized document artifact
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
                        text="1. Corporate Overview",
                        bbox=[50.0, 50.0, 400.0, 80.0],
                    ),
                    DocumentBlock(
                        block_id="b2",
                        type=BlockType.TEXT,
                        text="Alpha Security Systems has 10 years of defense contracting experience.",
                        bbox=[50.0, 90.0, 500.0, 140.0],
                    ),
                    DocumentBlock(
                        block_id="b3",
                        type=BlockType.TABLE,
                        table_data=TableData(
                            headers=["Year", "Turnover (Cr)", "Net Worth (Cr)"],
                            rows=[
                                ["2022-23", "14.5", "8.0"],
                                ["2023-24", "18.2", "11.5"],
                                ["2024-25", "22.0", "15.0"],
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
                        text="2. Certifications",
                    ),
                    DocumentBlock(
                        block_id="b5",
                        type=BlockType.TEXT,
                        text="The company maintains valid ISO 9001:2015 and ISO 27001 certifications.",
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
        "document": doc,
        "token": procurement_officer_token,
    }


def test_index_document_lifecycle_and_idempotency(client: TestClient, indexing_fixture, db_session):
    doc = indexing_fixture["document"]
    token = indexing_fixture["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Index document
    resp = client.post(f"/api/v1/documents/{doc.id}/index", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["document_id"] == str(doc.id)
    assert data["status"] == "COMPLETED"
    assert data["chunks_indexed"] == 5
    assert data["embedding_model"] == "BAAI/bge-m3"

    # Verify chunks in DB
    chunks = db_session.query(RetrievalChunk).filter_by(document_id=doc.id).all()
    assert len(chunks) == 5
    for c in chunks:
        assert c.embedding is not None
        assert len(c.embedding) == 1024
        assert len(c.content_hash) == 64

    # 2. Re-index document (Idempotency check)
    resp2 = client.post(f"/api/v1/documents/{doc.id}/index", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["chunks_indexed"] == 5

    # Verify no duplicate chunks were created
    chunks_after = db_session.query(RetrievalChunk).filter_by(document_id=doc.id).all()
    assert len(chunks_after) == 5


def test_list_document_chunks(client: TestClient, indexing_fixture):
    doc = indexing_fixture["document"]
    token = indexing_fixture["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Index first
    client.post(f"/api/v1/documents/{doc.id}/index", headers=headers)

    # Fetch chunks
    resp = client.get(f"/api/v1/documents/{doc.id}/chunks", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_chunks"] == 5
    assert len(data["chunks"]) == 5

    # Verify table chunk preserves table reference
    table_chunks = [c for c in data["chunks"] if c["content_type"] == "TABLE"]
    assert len(table_chunks) == 1
    assert table_chunks[0]["table_reference"] == "b3"
    assert "| Year | Turnover (Cr) | Net Worth (Cr) |" in table_chunks[0]["content"]


def test_index_uncompleted_document_rejected(client: TestClient, indexing_fixture, db_session):
    doc = indexing_fixture["document"]
    token = indexing_fixture["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Set document to PROCESSING
    doc.processing_status = ProcessingStatus.PROCESSING
    db_session.commit()

    resp = client.post(f"/api/v1/documents/{doc.id}/index", headers=headers)
    assert resp.status_code == 400
    assert "Document must be COMPLETED" in resp.json()["detail"]
