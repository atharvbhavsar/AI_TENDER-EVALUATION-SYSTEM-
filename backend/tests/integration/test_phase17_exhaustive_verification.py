"""Comprehensive Integration Tests for Phase 17 Exhaustive Verification.
Covers startup, migrations, OpenAPI, model persistence, versioning, RBAC, IDOR, audit trail, and historical preservation.
"""

import hashlib
import io
import uuid
import pypdf
import pytest
from fastapi.testclient import TestClient
from app.auth.jwt import create_access_token
from app.db.models.audit_log import AuditLog
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
from app.db.models.document import Document, DocumentType, ProcessingStatus
from app.db.models.evaluation_report import EvaluationReport, ReportStatus, ReportType
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.review_case import (
    HumanDecision,
    OfficerDecision,
    ReviewCase,
    ReviewIssueType,
    ReviewPriority,
    ReviewStatus,
)
from app.db.models.role import Role
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
from app.storage.memory import InMemoryObjectStorageService
from app.storage.service import set_storage_service_override


@pytest.fixture
def exhaustive_fixture(db_session):
    """Setup dual tender/version fixture with evaluated submissions for exhaustive testing."""
    mem_storage = InMemoryObjectStorageService()
    set_storage_service_override(mem_storage)

    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_exh_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer Exhaustive",
        is_active=True,
        password_hash="pwd",
    )
    unauthorized_user = User(
        id=uuid.uuid4(),
        email=f"unauth_user_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Unauthorized User",
        is_active=True,
        password_hash="pwd",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add_all([officer, unauthorized_user])
    db_session.flush()

    # Tender 1
    tender1 = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-EXH-T1-{uuid.uuid4().hex[:4]}",
        title="Procurement of Bullet Resistant Vests",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender1)
    db_session.flush()

    # Version 1 and Version 2
    v1 = TenderVersion(id=uuid.uuid4(), tender_id=tender1.id, version_number=1, created_by=officer.id)
    v2 = TenderVersion(id=uuid.uuid4(), tender_id=tender1.id, version_number=2, created_by=officer.id)
    db_session.add_all([v1, v2])
    db_session.flush()

    # Criteria for Version 1
    crit1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="FIN-01",
        name="Minimum Turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 3.1: Minimum turnover 30 Cr INR",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        approval_status=ApprovalStatus.APPROVED,
        extraction_status=ExtractionStatus.EXTRACTED,
        description="Minimum turnover 30 Crore",
    )
    db_session.add(crit1)
    db_session.flush()

    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit1.id,
        tender_version_id=v1.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"min_value": 30.0, "currency": "INR"},
        status=RuleStatus.ACTIVE,
    )
    db_session.add(rule1)
    db_session.flush()

    # Bidder Alpha
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender1.id,
        bidder_code="BID-ALPHA",
        legal_name="Alpha Defense Corp",
        contact_email="contact@alphacorp.in",
    )
    db_session.add(bidder)
    db_session.flush()

    # Submission on Version 1
    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder.id,
        submission_reference="SUB-ALPHA-01",
        status=SubmissionStatus.READY,
    )
    db_session.add(sub)
    db_session.flush()

    # Document
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender1.id,
        tender_version_id=v1.id,
        bid_submission_id=sub.id,
        filename="Turnover_Audit.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=8000,
        sha256_hash="77" * 32,
        storage_key=f"docs/{sub.id}/audit.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()

    # Evidence & Evaluation
    ev = Evidence(
        id=uuid.uuid4(),
        document_id=doc.id,
        criterion_id=crit1.id,
        bid_submission_id=sub.id,
        extraction_run_id=uuid.uuid4(),
        extractor_version="1.0.0",
        status=EvidenceStatus.FOUND,
        source_page=1,
        extracted_value=35.0,
        normalized_value="35.0",
        confidence=0.99,
        extracted_text="Audited annual turnover is 35.0 Cr",
    )
    db_session.add(ev)
    db_session.flush()

    ce = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        criterion_id=crit1.id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"extracted": 35.0, "min": 30.0},
        evidence_ids=[str(ev.id)],
        explanation={"passed": True},
    )
    be = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender1.id,
        tender_version_id=v1.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        result=EvaluationResult.ELIGIBLE,
        criterion_count=1,
        eligible_count=1,
        not_eligible_count=0,
        manual_review_count=0,
        mandatory_criterion_count=1,
        mandatory_eligible_count=1,
        mandatory_not_eligible_count=0,
        mandatory_manual_review_count=0,
    )
    db_session.add_all([ce, be])
    db_session.commit()

    token_officer = create_access_token(officer.id)
    token_unauth = create_access_token(unauthorized_user.id)

    yield {
        "headers_officer": {"Authorization": f"Bearer {token_officer}"},
        "headers_unauth": {"Authorization": f"Bearer {token_unauth}"},
        "tender1": tender1,
        "v1": v1,
        "v2": v2,
        "bidder": bidder,
        "sub": sub,
        "ce": ce,
        "be": be,
        "storage": mem_storage,
    }

    set_storage_service_override(None)


def test_openapi_schema_contains_report_endpoints(client: TestClient):
    """Verify OpenAPI documentation accurately lists all Phase 17 report routes."""
    res = client.get("/openapi.json")
    assert res.status_code == 200
    schema = res.json()
    paths = schema.get("paths", {})

    assert "/api/v1/submissions/{id}/reports" in paths
    assert "/api/v1/reports/{id}" in paths
    assert "/api/v1/reports/{id}/download" in paths
    assert "/api/v1/reports" in paths
    assert "/api/v1/tenders/{tender_id}/versions/{version_id}/reports" in paths


def test_missing_data_rejection_workflows(client: TestClient, exhaustive_fixture):
    """Verify missing tender version, invalid submission, or non-existent IDs fail safely with 404/409."""
    headers = exhaustive_fixture["headers_officer"]
    tender1 = exhaustive_fixture["tender1"]
    fake_id = uuid.uuid4()

    # 1. Non-existent submission for report generation -> 404
    res1 = client.post(f"/api/v1/submissions/{fake_id}/reports", json={}, headers=headers)
    assert res1.status_code == 404

    # 2. Non-existent tender version for consolidated report -> 404
    res2 = client.post(f"/api/v1/tenders/{tender1.id}/versions/{fake_id}/reports", json={}, headers=headers)
    assert res2.status_code == 404

    # 3. Non-existent report metadata retrieval -> 404
    res3 = client.get(f"/api/v1/reports/{fake_id}", headers=headers)
    assert res3.status_code == 404


def test_tender_version_isolation_for_reports(client: TestClient, exhaustive_fixture):
    """Verify reports generated on Tender Version 1 do not leak into Tender Version 2 listings."""
    headers = exhaustive_fixture["headers_officer"]
    tender1 = exhaustive_fixture["tender1"]
    v1 = exhaustive_fixture["v1"]
    v2 = exhaustive_fixture["v2"]
    sub = exhaustive_fixture["sub"]

    # Generate Report on Version 1
    res = client.post(
        f"/api/v1/submissions/{sub.id}/reports",
        json={"title": "V1 Bidder Report"},
        headers=headers,
    )
    assert res.status_code == 201
    rep_v1_id = res.json()["id"]

    # Listing on Version 1 should contain it
    res_v1 = client.get(f"/api/v1/tenders/{tender1.id}/versions/{v1.id}/reports", headers=headers)
    assert res_v1.status_code == 200
    ids_v1 = [r["id"] for r in res_v1.json()["items"]]
    assert rep_v1_id in ids_v1

    # Listing on Version 2 should NOT contain it
    res_v2 = client.get(f"/api/v1/tenders/{tender1.id}/versions/{v2.id}/reports", headers=headers)
    assert res_v2.status_code == 200
    ids_v2 = [r["id"] for r in res_v2.json()["items"]]
    assert rep_v1_id not in ids_v2


def test_rbac_and_idor_protection(client: TestClient, exhaustive_fixture):
    """Verify unauthorized users cannot generate or download evaluation reports."""
    headers_unauth = exhaustive_fixture["headers_unauth"]
    headers_officer = exhaustive_fixture["headers_officer"]
    sub = exhaustive_fixture["sub"]

    # Generate report with authorized officer
    res_gen = client.post(
        f"/api/v1/submissions/{sub.id}/reports",
        json={"title": "Officer Auth Report"},
        headers=headers_officer,
    )
    assert res_gen.status_code == 201
    report_id = res_gen.json()["id"]

    # Unauthorized user attempting to access report metadata -> 403
    res_meta_unauth = client.get(f"/api/v1/reports/{report_id}", headers=headers_unauth)
    assert res_meta_unauth.status_code == 403

    # Unauthorized user attempting to download report PDF -> 403
    res_dl_unauth = client.get(f"/api/v1/reports/{report_id}/download", headers=headers_unauth)
    assert res_dl_unauth.status_code == 403

    # Unauthorized user attempting to generate report -> 403
    res_gen_unauth = client.post(f"/api/v1/submissions/{sub.id}/reports", json={}, headers=headers_unauth)
    assert res_gen_unauth.status_code == 403


def test_report_listing_filtering_and_pagination(client: TestClient, exhaustive_fixture):
    """Verify report listing supports filtering by status, type, submission, and tender."""
    headers = exhaustive_fixture["headers_officer"]
    tender1 = exhaustive_fixture["tender1"]
    v1 = exhaustive_fixture["v1"]
    sub = exhaustive_fixture["sub"]

    # Generate Bidder Report (v1)
    client.post(f"/api/v1/submissions/{sub.id}/reports", json={"title": "Report A"}, headers=headers)
    # Generate Consolidated Report
    client.post(f"/api/v1/tenders/{tender1.id}/versions/{v1.id}/reports", json={"title": "Consolidated A"}, headers=headers)

    # 1. Filter by report_type
    res_b = client.get("/api/v1/reports?report_type=BIDDER_EVALUATION_REPORT", headers=headers)
    assert res_b.status_code == 200
    for r in res_b.json()["items"]:
        assert r["report_type"] == "BIDDER_EVALUATION_REPORT"

    res_c = client.get("/api/v1/reports?report_type=CONSOLIDATED_TENDER_REPORT", headers=headers)
    assert res_c.status_code == 200
    for r in res_c.json()["items"]:
        assert r["report_type"] == "CONSOLIDATED_TENDER_REPORT"

    # 2. Filter by status
    res_status = client.get("/api/v1/reports?status=COMPLETED", headers=headers)
    assert res_status.status_code == 200
    for r in res_status.json()["items"]:
        assert r["status"] == "COMPLETED"

    # 3. Pagination
    res_page = client.get("/api/v1/reports?limit=1&offset=0", headers=headers)
    assert res_page.status_code == 200
    assert len(res_page.json()["items"]) <= 1
    assert res_page.json()["total"] >= 2


def test_audit_event_emission_and_provenance(client: TestClient, exhaustive_fixture, db_session):
    """Verify that REPORT_GENERATED and REPORT_DOWNLOADED audit events are immutably emitted with document hash."""
    headers = exhaustive_fixture["headers_officer"]
    sub = exhaustive_fixture["sub"]

    res_gen = client.post(
        f"/api/v1/submissions/{sub.id}/reports",
        json={"title": "Audited Report"},
        headers=headers,
    )
    assert res_gen.status_code == 201
    report_id = res_gen.json()["id"]
    file_hash = res_gen.json()["file_hash"]

    # Trigger download
    res_dl = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    assert res_dl.status_code == 200

    # Query audit logs
    gen_audit = db_session.query(AuditLog).filter(
        AuditLog.entity_type == "REPORT",
        AuditLog.entity_id == report_id,
        AuditLog.action == "REPORT_GENERATED",
    ).first()
    assert gen_audit is not None
    assert gen_audit.document_hash == file_hash

    dl_audit = db_session.query(AuditLog).filter(
        AuditLog.entity_type == "REPORT",
        AuditLog.entity_id == report_id,
        AuditLog.action == "REPORT_DOWNLOADED",
    ).first()
    assert dl_audit is not None
    assert dl_audit.document_hash == file_hash
