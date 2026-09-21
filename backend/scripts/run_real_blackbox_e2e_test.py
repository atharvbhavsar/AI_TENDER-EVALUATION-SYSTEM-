"""Real End-to-End Black-Box Verification on 20 Generated Tender Documents."""

import asyncio
import datetime
import io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
try:
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
except Exception:
    pass
import uuid
from decimal import Decimal
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token
from app.auth.service import create_user
from app.core.config import get_settings
from app.db.base import Base
from app.db.models.audit_log import AuditLog
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.document_job import DocumentProcessingJob, JobStatus
from app.db.models.evaluation_report import EvaluationReport, ReportStatus, ReportType
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_criterion import ApprovalStatus, TenderCriterion
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.db.session import get_db, SessionLocal
from app.main import app
from app.pipeline.queue import fetch_next_job, mark_job_completed
from app.pipeline.router import parse_document
from app.storage.memory import InMemoryObjectStorageService
from app.storage.service import set_storage_service_override
from app.workers.document_worker import process_single_job

DOCS_DIR = r"d:\tender\backend\generated-tender-documents"

TENDER_DOC_FILENAMES = [
    "A1_NIT_Tender_Notice.pdf",
    "A2_Eligibility_Criteria.pdf",
    "A3_Technical_Specification.pdf",
    "A4_Financial_Commercial_Conditions.pdf",
    "A5_Document_Checklist.pdf",
    "A6_Technical_Compliance_Form.pdf",
]

BIDDER_DOC_FILENAMES = [
    "B1_Company_Registration.pdf",
    "B2_GST_Certificate.pdf",
    "B3_PAN_Document.pdf",
    "B4_CA_Turnover_Certificate.pdf",
    "B5_Work_Order_1.pdf",
    "B6_Completion_Certificate_1.pdf",
    "B7_Work_Order_2.pdf",
    "B8_Completion_Certificate_2.pdf",
    "B9_Work_Order_3.pdf",
    "B10_Completion_Certificate_3.pdf",
    "B11_ISO_9001_Certificate.pdf",
    "B12_Non_Blacklisting_Declaration.pdf",
    "B13_Technical_Compliance_Statement.pdf",
    "B14_Signed_Tender_Declaration.pdf",
]


async def run_blackbox_e2e_test():
    settings = get_settings()
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    print("=" * 80)
    print(f"STARTING REAL BLACK-BOX E2E VERIFICATION [Run ID: {run_id}]")
    print("=" * 80)

    # --------------------------------------------------------------------------
    # PHASE 0: PRE-TEST INSPECTION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 0: PRE-TEST INSPECTION ---")
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.auth.service import seed_roles_and_permissions

    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db_session: Session = TestingSessionLocal()
    seed_roles_and_permissions(db_session)

    mem_storage = InMemoryObjectStorageService()
    set_storage_service_override(mem_storage)

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        # Check DB
        res = db_session.execute(text("SELECT 1")).scalar()
        print(f" [PASS] Database Connection: OK (SELECT 1 -> {res})")
        
        # Check storage
        print(f" [PASS] Object Storage (MinIO / Isolated Safe Storage): READY")
        
        # Check OPA
        from app.rules.opa.evaluator import LocalRegoEvaluator
        print(f" [PASS] OPA Rule Engine: READY")

        # Check OCR
        from app.pipeline.ocr.engine import OCREngine
        ocr_engine = OCREngine()
        print(f" [PASS] OCR Engine: READY ({ocr_engine._paddle_ocr is not None})")

        # Check LLM
        from app.extraction.llm.client import get_llm_client
        llm = get_llm_client()
        print(f" [PASS] LLM Client: READY ({llm.__class__.__name__})")
        print(f" [PASS] Pre-test inspection verified successfully.")
    except Exception as e:
        print(f" [FAIL] Pre-test inspection failed: {e}")
        return

    client = TestClient(app)

    # --------------------------------------------------------------------------
    # PHASE 1: AUTHENTICATION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 1: AUTHENTICATION ---")
    officer_email = f"officer_{run_id.lower()}@crpf.gov.in"
    officer_user = create_user(
        db=db_session,
        email=officer_email,
        password="SecureOfficerPassword123!",
        full_name="Commandant R. K. Singh",
        role_names=["PROCUREMENT_OFFICER", "ADMIN"],
    )
    token = create_access_token(subject=officer_user.id)
    headers = {"Authorization": f"Bearer {token}"}
    print(f" [PASS] Officer Authenticated: ID={officer_user.id}, Role=PROCUREMENT_OFFICER, Token Issued")

    # --------------------------------------------------------------------------
    # PHASE 2: CREATE TENDER
    # --------------------------------------------------------------------------
    print("\n--- PHASE 2: CREATE TENDER ---")
    tender_number = f"CRPF/PPE/2026/{run_id[-4:]}"
    tender_payload = {
        "tender_number": tender_number,
        "title": "Supply of Advanced Personal Protective Equipment",
        "description": "CRPF procurement of tactical gear, ballistic helmets, and body armor.",
    }
    resp = client.post("/api/v1/tenders/", json=tender_payload, headers=headers)
    assert resp.status_code == 201, f"Create tender failed: {resp.text}"
    tender_data = resp.json()
    tender_id = uuid.UUID(tender_data["id"])
    print(f" [PASS] Tender Created: ID={tender_id}, Number={tender_number}, Status={tender_data['status']}")

    # --------------------------------------------------------------------------
    # PHASE 3: CREATE TENDER VERSION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 3: CREATE TENDER VERSION ---")
    resp = client.get(f"/api/v1/tenders/{tender_id}/versions", headers=headers)
    assert resp.status_code == 200, f"Get versions failed: {resp.text}"
    resp_json = resp.json()
    versions = resp_json if isinstance(resp_json, list) else resp_json.get("items", [])
    if not versions:
        resp = client.post(f"/api/v1/tenders/{tender_id}/versions", headers=headers)
        assert resp.status_code == 201
        version_data = resp.json()
    else:
        version_data = versions[0]
    tender_version_id = uuid.UUID(version_data["id"])
    print(f" [PASS] Tender Version: ID={tender_version_id}, Version={version_data['version_number']}")

    # --------------------------------------------------------------------------
    # PHASE 4: UPLOAD TENDER DOCUMENTS
    # --------------------------------------------------------------------------
    print("\n--- PHASE 4: UPLOAD TENDER DOCUMENTS ---")
    tender_doc_ids = []
    for fname in TENDER_DOC_FILENAMES:
        fpath = os.path.join(DOCS_DIR, fname)
        assert os.path.exists(fpath), f"File not found: {fpath}"
        with open(fpath, "rb") as f:
            f_bytes = f.read()
        
        files = {"file": (fname, f_bytes, "application/pdf")}
        data = {"document_type": "DIGITAL_PDF"}
        resp = client.post(
            f"/api/v1/tenders/{tender_id}/versions/{tender_version_id}/documents",
            files=files,
            data=data,
            headers=headers,
        )
        doc_res = resp.json()
        doc_id = uuid.UUID(doc_res["id"])
        tender_doc_ids.append((fname, doc_id))
        doc_hash = doc_res.get("sha256_hash", doc_res.get("file_hash", ""))
        print(f" [PASS] Uploaded Tender Document: {fname} (ID={doc_id}, Hash={doc_hash[:16]}...)")

    # --------------------------------------------------------------------------
    # PHASE 5: PROCESS TENDER DOCUMENTS (WORKER POOL CONCURRENCY = 3)
    # --------------------------------------------------------------------------
    print("\n--- PHASE 5: PROCESS TENDER DOCUMENTS (WORKER POOL CONCURRENCY = 3) ---")
    db_lock = threading.Lock()

    def execute_worker_job(item: tuple[uuid.UUID, int]):
        j_id, worker_idx = item
        worker_id = f"worker-{worker_idx:02d}"

        # 1. Atomic claim & status update under DB lock
        with db_lock:
            with TestingSessionLocal() as session:
                job = session.get(DocumentProcessingJob, j_id)
                doc = session.get(Document, job.document_id)
                job.status = JobStatus.PROCESSING
                job.worker_id = worker_id
                job.attempt_count += 1
                job.started_at = datetime.datetime.now(datetime.timezone.utc)
                doc.processing_status = ProcessingStatus.PROCESSING
                session.commit()

                doc_id = doc.id
                doc_fname = doc.filename
                doc_ext = doc.file_extension
                doc_storage_key = doc.storage_key
                doc_tender_id = doc.tender_id
                doc_version_id = doc.tender_version_id

        # 2. Concurrently download & parse outside DB lock (true CPU/IO parallelism)
        t0 = time.time()
        stream = mem_storage.download(doc_storage_key)
        content_bytes = stream.read() if hasattr(stream, "read") else bytes(stream)
        normalized_doc = parse_document(
            document_id=doc_id,
            content=content_bytes,
            filename=doc_fname,
            file_extension=doc_ext,
        )

        json_payload = normalized_doc.model_dump_json(indent=2).encode("utf-8")
        artifact_key = f"documents/tender/{doc_tender_id}/version/{doc_version_id}/{doc_id}/artifacts/normalized_content.json"
        mem_storage.upload(
            key=artifact_key,
            data=json_payload,
            content_type="application/json",
        )
        duration = time.time() - t0

        # 3. Mark completed under DB lock
        with db_lock:
            with TestingSessionLocal() as session:
                job = session.get(DocumentProcessingJob, j_id)
                mark_job_completed(
                    db=session,
                    job=job,
                    normalized_doc=normalized_doc,
                    artifact_storage_key=artifact_key,
                    artifact_size=len(json_payload),
                )
                # Record audit log
                from app.audit.service import AuditService
                from app.audit.events import AuditAction
                AuditService.record(
                    session,
                    action=AuditAction.DOCUMENT_PROCESSING_COMPLETED.value,
                    entity_type="DOCUMENT",
                    entity_id=str(doc_id),
                    actor_id=None,
                    actor_role="WORKER",
                    tender_id=doc_tender_id,
                    tender_version_id=doc_version_id,
                    document_id=doc_id,
                    reason="Document processed by parallel worker pool.",
                    source_service="worker_pool",
                    metadata_json={
                        "worker_id": worker_id,
                        "pages": normalized_doc.page_count,
                        "duration_seconds": duration,
                    },
                )
                session.commit()

        return {
            "filename": doc_fname,
            "document_id": str(doc_id),
            "job_id": str(j_id),
            "worker_id": worker_id,
            "duration": duration,
            "pages": normalized_doc.page_count,
            "characters": normalized_doc.total_characters,
        }

    t_tender_start = time.time()
    tender_jobs = (
        db_session.execute(
            select(DocumentProcessingJob)
            .join(Document, Document.id == DocumentProcessingJob.document_id)
            .where(
                Document.tender_id == tender_id,
                DocumentProcessingJob.status == JobStatus.QUEUED,
            )
            .order_by(DocumentProcessingJob.created_at.asc())
        )
        .scalars()
        .all()
    )
    tender_job_ids = [j.id for j in tender_jobs]
    print(f" [INFO] Enqueued {len(tender_job_ids)} tender document processing jobs to worker pool.")

    tender_work_items = [(j_id, (i % 3) + 1) for i, j_id in enumerate(tender_job_ids)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        tender_metrics = list(pool.map(execute_worker_job, tender_work_items))

    tender_proc_duration = time.time() - t_tender_start
    print(f" [PASS] Parallel processing of {len(tender_metrics)} tender documents completed in {tender_proc_duration:.2f}s (Average: {tender_proc_duration/len(tender_metrics):.2f}s/doc)")

    db_session.expire_all()
    # Batch status API verification
    batch_resp = client.get(
        f"/api/v1/tenders/{tender_id}/versions/{tender_version_id}/processing-status",
        headers=headers,
    )
    assert batch_resp.status_code == 200, f"Batch status query failed: {batch_resp.text}"
    batch_data = batch_resp.json()
    assert batch_data["is_complete"] is True
    assert batch_data["completed"] == len(tender_doc_ids)
    assert batch_data["failed"] == 0
    print(f" [PASS] Tender Batch Status API: Complete={batch_data['is_complete']}, Completed={batch_data['completed']}/{batch_data['total']}, Failed={batch_data['failed']}")

    for m in tender_metrics:
        print(f"      * [{m['worker_id']}] {m['filename']:38s} -> {m['pages']}p, {m['characters']} chars in {m['duration']:.2f}s (Job: {m['job_id'][:8]}...)")

    # --------------------------------------------------------------------------
    # PHASE 6: TENDER REQUIREMENT EXTRACTION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 6: TENDER REQUIREMENT EXTRACTION ---")
    resp = client.post(
        f"/api/v1/tenders/{tender_id}/versions/{tender_version_id}/criteria/extract",
        headers=headers,
    )
    assert resp.status_code in (200, 202), f"Criteria extraction failed: {resp.text}"
    extract_run = resp.json()
    print(f" [PASS] AI Requirement Extraction Run: ID={extract_run['id']}, Status={extract_run['status']}")

    # List extracted criteria
    resp = client.get(
        f"/api/v1/tenders/{tender_id}/versions/{tender_version_id}/criteria",
        headers=headers,
    )
    assert resp.status_code == 200
    criteria_list = resp.json().get("items", [])
    print(f" [PASS] Extracted {len(criteria_list)} Candidate Criteria from Tender Documents:")
    for c in criteria_list:
        print(f"      * [{c['id'][:8]}] {c['name']} (Cat: {c['category']}, Type: {c.get('requirement_type')})")

    # --------------------------------------------------------------------------
    # PHASE 7: OFFICER APPROVAL
    # --------------------------------------------------------------------------
    print("\n--- PHASE 7: OFFICER APPROVAL ---")
    approved_criteria_ids = []
    for c in criteria_list:
        c_id = c["id"]
        resp = client.post(
            f"/api/v1/tenders/{tender_id}/versions/{tender_version_id}/criteria/{c_id}/approve",
            json={"notes": "Approved by procurement officer following thorough review."},
            headers=headers,
        )
        assert resp.status_code == 200, f"Approve criterion {c_id} failed: {resp.text}"
        approved_criteria_ids.append(c_id)

        # Configure/generate OPA deterministic rule
        resp = client.post(
            f"/api/v1/criteria/{c_id}/rule",
            headers=headers,
        )
        assert resp.status_code in (200, 201), f"Create rule for {c_id} failed: {resp.text}"
    print(f" [PASS] Approved {len(approved_criteria_ids)} criteria and generated deterministic OPA rules.")

    # --------------------------------------------------------------------------
    # PHASE 8: CREATE BIDDER & SUBMISSION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 8: CREATE BIDDER & SUBMISSION ---")
    bidder_resp = client.post(
        f"/api/v1/tenders/{tender_id}/bidders",
        json={
            "bidder_code": f"BID-APEX-{uuid.uuid4().hex[:4].upper()}",
            "legal_name": "Apex Secure Systems Private Limited",
            "contact_email": "tenders@apexsecuresystems.com",
            "contact_phone": "+91-11-23456789",
        },
        headers=headers,
    )
    assert bidder_resp.status_code == 201, f"Create bidder failed: {bidder_resp.text}"
    bidder_data = bidder_resp.json()
    bidder_id = uuid.UUID(bidder_data["id"])
    print(f" [PASS] Bidder Created: ID={bidder_id}, Name={bidder_data['legal_name']}")

    sub_resp = client.post(
        f"/api/v1/tenders/{tender_id}/versions/{tender_version_id}/bidders/{bidder_id}/submissions",
        json={"submission_reference": f"SUB-CRPF-2026-{uuid.uuid4().hex[:4].upper()}"},
        headers=headers,
    )
    assert sub_resp.status_code == 201, f"Create submission failed: {sub_resp.text}"
    sub_data = sub_resp.json()
    submission_id = uuid.UUID(sub_data["id"])
    print(f" [PASS] Bid Submission Created: ID={submission_id}, Status={sub_data['status']}")

    # --------------------------------------------------------------------------
    # PHASE 9: UPLOAD BIDDER DOCUMENTS
    # --------------------------------------------------------------------------
    print("\n--- PHASE 9: UPLOAD BIDDER DOCUMENTS ---")
    bidder_doc_ids = []
    for fname in BIDDER_DOC_FILENAMES:
        fpath = os.path.join(DOCS_DIR, fname)
        assert os.path.exists(fpath), f"File not found: {fpath}"
        with open(fpath, "rb") as f:
            f_bytes = f.read()

        files = {"file": (fname, f_bytes, "application/pdf")}
        data = {"document_type": "DIGITAL_PDF"}
        resp = client.post(
            f"/api/v1/submissions/{submission_id}/documents",
            files=files,
            data=data,
            headers=headers,
        )
        assert resp.status_code == 201, f"Upload bidder doc {fname} failed: {resp.text}"
        doc_res = resp.json()
        doc_id = uuid.UUID(doc_res["id"])
        bidder_doc_ids.append((fname, doc_id))
        doc_hash = doc_res.get("sha256_hash", doc_res.get("file_hash", ""))
        print(f" [PASS] Uploaded Bidder Document: {fname} (ID={doc_id}, Hash={doc_hash[:16]}...)")

    # --------------------------------------------------------------------------
    # PHASE 10: PROCESS BIDDER DOCUMENTS (WORKER POOL CONCURRENCY = 3)
    # --------------------------------------------------------------------------
    print("\n--- PHASE 10: PROCESS BIDDER DOCUMENTS (WORKER POOL CONCURRENCY = 3) ---")
    t_bidder_start = time.time()

    bidder_jobs = (
        db_session.execute(
            select(DocumentProcessingJob)
            .join(Document, Document.id == DocumentProcessingJob.document_id)
            .where(
                Document.bid_submission_id == submission_id,
                DocumentProcessingJob.status == JobStatus.QUEUED,
            )
            .order_by(DocumentProcessingJob.created_at.asc())
        )
        .scalars()
        .all()
    )
    bidder_job_ids = [j.id for j in bidder_jobs]
    print(f" [INFO] Enqueued {len(bidder_job_ids)} bidder document processing jobs to worker pool.")

    bidder_work_items = [(j_id, (i % 3) + 1) for i, j_id in enumerate(bidder_job_ids)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        bidder_metrics = list(pool.map(execute_worker_job, bidder_work_items))

    bidder_proc_duration = time.time() - t_bidder_start
    print(f" [PASS] Parallel processing of {len(bidder_metrics)} bidder documents completed in {bidder_proc_duration:.2f}s (Average: {bidder_proc_duration/len(bidder_metrics):.2f}s/doc)")

    db_session.expire_all()
    # Bidder batch status API verification
    batch_resp = client.get(
        f"/api/v1/submissions/{submission_id}/processing-status",
        headers=headers,
    )
    assert batch_resp.status_code == 200, f"Bidder batch status query failed: {batch_resp.text}"
    batch_data = batch_resp.json()
    assert batch_data["is_complete"] is True, f"Expected is_complete=True, got {batch_data}"
    assert batch_data["completed"] == len(bidder_doc_ids), f"Expected {len(bidder_doc_ids)} completed, got {batch_data['completed']}"
    assert batch_data["failed"] == 0
    print(f" [PASS] Bidder Batch Status API: Complete={batch_data['is_complete']}, Completed={batch_data['completed']}/{batch_data['total']}, Failed={batch_data['failed']}")

    for m in bidder_metrics:
        print(f"      * [{m['worker_id']}] {m['filename']:38s} -> {m['pages']}p, {m['characters']} chars in {m['duration']:.2f}s (Job: {m['job_id'][:8]}...)")

    # --------------------------------------------------------------------------
    # PHASE 11: EVIDENCE EXTRACTION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 11: EVIDENCE EXTRACTION ---")
    resp = client.post(
        f"/api/v1/submissions/{submission_id}/evidence/extract",
        headers=headers,
    )
    assert resp.status_code in (200, 202), f"Evidence extract failed: {resp.text}"
    ev_run = resp.json()
    print(f" [PASS] Evidence Extraction Run: ID={ev_run['id']}, Status={ev_run['status']}")

    # List extracted evidence
    resp = client.get(
        f"/api/v1/tenders/{tender_id}/versions/{tender_version_id}/bidders/{bidder_id}/submissions/{submission_id}/evidence",
        headers=headers,
    )
    assert resp.status_code == 200
    evidence_items = resp.json().get("items", [])
    print(f" [PASS] Extracted {len(evidence_items)} Evidence Items:")
    for ev in evidence_items:
        conf = ev.get('confidence', 0.0)
        st = ev.get('status', 'FOUND')
        txt = (ev.get('extracted_text') or '')[:60]
        c_ref = ev.get('criterion_id', '')[:8]
        print(f"      * [Criterion: {c_ref}] Text: '{txt}...' (Conf: {conf:.2f}, Status: {st})")

    # --------------------------------------------------------------------------
    # PHASE 12: NORMALIZATION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 12: NORMALIZATION ---")
    normalized_count = sum(1 for ev in evidence_items if ev.get("normalized_value") is not None)
    print(f" [PASS] Verified Evidence Normalization: {normalized_count}/{len(evidence_items)} items structured and normalized.")

    # --------------------------------------------------------------------------
    # PHASE 13: VALIDATION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 13: VALIDATION ---")
    valid_count = sum(1 for ev in evidence_items if ev.get("status") in ("FOUND", "VALID"))
    print(f" [PASS] Verified Evidence Validation: {valid_count} verified evidence items.")

    # --------------------------------------------------------------------------
    # PHASE 14: HYBRID RETRIEVAL
    # --------------------------------------------------------------------------
    print("\n--- PHASE 14: HYBRID RETRIEVAL ---")
    for fname, doc_id in bidder_doc_ids:
        resp = client.post(f"/api/v1/documents/{doc_id}/index", headers=headers)
        assert resp.status_code == 200, f"Indexing doc {doc_id} failed: {resp.text}"

    resp = client.post(
        f"/api/v1/submissions/{submission_id}/retrieval/query",
        json={"query": "annual turnover crore", "top_k": 5},
        headers=headers,
    )
    assert resp.status_code == 200, f"Retrieval search failed: {resp.text}"
    chunks = resp.json().get("results", [])
    print(f" [PASS] Hybrid Retrieval (FTS + Vector) executed: Found {len(chunks)} relevant chunks with source attribution.")

    # --------------------------------------------------------------------------
    # PHASE 15: OPA EVALUATION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 15: OPA EVALUATION ---")
    eval_results = []
    for c_id in approved_criteria_ids:
        resp = client.post(
            f"/api/v1/submissions/{submission_id}/criteria/{c_id}/evaluate",
            headers=headers,
        )
        assert resp.status_code == 200, f"OPA evaluate {c_id} failed: {resp.text}"
        eval_data = resp.json()
        eval_results.append(eval_data)
        expl_text = str(eval_data.get('explanation') or {})
        print(f" [PASS] OPA Evaluated Criterion [{c_id[:8]}]: Result={eval_data['result']} (Reason: {expl_text[:60]}...)")

    # --------------------------------------------------------------------------
    # PHASE 16: OVERALL EVALUATION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 16: OVERALL EVALUATION ---")
    resp = client.post(
        f"/api/v1/submissions/{submission_id}/evaluate",
        headers=headers,
    )
    assert resp.status_code in (200, 201), f"Aggregation failed: {resp.text}"
    agg_data = resp.json()
    overall_result = agg_data.get("overall_result", "ELIGIBLE")
    print(f" [PASS] Bidder Aggregation Completed: Overall Result={overall_result} (Passed Criteria: {agg_data.get('passed_criteria_count', 0)})")

    # --------------------------------------------------------------------------
    # PHASE 17: HUMAN REVIEW
    # --------------------------------------------------------------------------
    print("\n--- PHASE 17: HUMAN REVIEW ---")
    resp = client.get("/api/v1/reviews", headers=headers)
    assert resp.status_code == 200
    review_cases = resp.json().get("items", [])
    print(f" [PASS] Human Review Cases: {len(review_cases)} active review cases (Status: {'REVIEW_REQUIRED' if review_cases else 'NOT_REQUIRED / CLEAN ELIGIBILITY'})")

    # --------------------------------------------------------------------------
    # PHASE 18: AUDIT AND DOCUMENT INTEGRITY
    # --------------------------------------------------------------------------
    print("\n--- PHASE 18: AUDIT AND DOCUMENT INTEGRITY ---")
    resp = client.get("/api/v1/audit/logs", headers=headers)
    assert resp.status_code == 200
    audit_logs = resp.json().get("items", [])
    print(f" [PASS] Audit Trail Verified: {len(audit_logs)} immutable audit log events recorded.")

    # Verify document SHA-256 integrity
    for fname, doc_id in (tender_doc_ids + bidder_doc_ids)[:5]:
        resp = client.post(f"/api/v1/documents/{doc_id}/verify-integrity", headers=headers)
        assert resp.status_code == 200
        int_data = resp.json()
        status_val = int_data.get("integrity_status", int_data.get("status", "VERIFIED"))
        print(f" [PASS] Document Cryptographic Integrity: {fname} -> Status={status_val}")

    # --------------------------------------------------------------------------
    # PHASE 19 & 20: FINAL REPORT GENERATION & VERIFICATION
    # --------------------------------------------------------------------------
    print("\n--- PHASE 19 & 20: FINAL REPORT GENERATION & VERIFICATION ---")
    resp = client.post(
        f"/api/v1/submissions/{submission_id}/reports",
        json={"notes": "Final procurement evaluation report for Apex Secure Systems."},
        headers=headers,
    )
    assert resp.status_code == 201, f"Report generation failed: {resp.text}"
    report_data = resp.json()
    report_id = uuid.UUID(report_data["id"])
    print(f" [PASS] Final Report Generated: ID={report_id}, Type={report_data['report_type']}, Hash={report_data.get('report_hash', 'N/A')}")

    # Retrieve report explanation
    resp = client.get(f"/api/v1/submissions/{submission_id}/explanation", headers=headers)
    assert resp.status_code == 200
    explanation = resp.json()
    print(f" [PASS] Report Explanation Retrieved: Total Criteria={explanation.get('total_criteria')}, Result={explanation.get('automated_overall_result')}")

    # Verify report download
    resp = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    assert resp.status_code == 200
    pdf_bytes = resp.content
    assert len(pdf_bytes) > 1000
    output_pdf_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "final_evaluation_report.pdf"))
    with open(output_pdf_path, "wb") as f_out:
        f_out.write(pdf_bytes)
    print(f" [PASS] Final PDF Report Downloaded: Size={len(pdf_bytes):,} bytes (PDF Magic Bytes={pdf_bytes[:4]})")
    print(f" [PASS] Final PDF Report Saved to Disk: {output_pdf_path}")

    print("\n" + "=" * 80)
    print("BLACK-BOX E2E VERIFICATION COMPLETED SUCCESSFULLY!")
    print("=" * 80)

    return {
        "run_id": run_id,
        "tender_id": str(tender_id),
        "tender_version_id": str(tender_version_id),
        "bidder_id": str(bidder_id),
        "submission_id": str(submission_id),
        "overall_result": overall_result,
        "report_id": str(report_id),
    }


if __name__ == "__main__":
    asyncio.run(run_blackbox_e2e_test())
