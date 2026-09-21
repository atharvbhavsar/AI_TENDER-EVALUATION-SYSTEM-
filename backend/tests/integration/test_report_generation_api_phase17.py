"""Comprehensive Integration Tests for Phase 17 - Report Generation API & Workflow."""

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
def phase17_test_data(db_session):
    """Setup complete database fixture with evaluated submission and review cases."""
    mem_storage = InMemoryObjectStorageService()
    set_storage_service_override(mem_storage)

    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"procurement_officer_p17_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Officer Phase 17",
        is_active=True,
        password_hash="hashed_pw",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)
    db_session.flush()

    # Tender T1
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-ARM-2026-{uuid.uuid4().hex[:4]}",
        title="Procurement of Ballistic Protection Equipment",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    # Tender Version 1
    v1 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    # Tender Version 2 (for isolation testing)
    v2 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=2,
        created_by=officer.id,
    )
    db_session.add_all([v1, v2])
    db_session.flush()

    # Criterion 1: Financial
    crit1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="FIN-01",
        name="Average Annual Turnover",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 4.1: Minimum turnover of 20 Cr INR",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extraction_status=ExtractionStatus.EXTRACTED,
        approval_status=ApprovalStatus.APPROVED,
        description="Minimum turnover 20 Crore INR",
    )
    # Criterion 2: Technical
    crit2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        criterion_code="TECH-01",
        name="OEM Manufacturer Authorization",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 5.1: Direct manufacturer OEM authorization",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extraction_status=ExtractionStatus.EXTRACTED,
        approval_status=ApprovalStatus.APPROVED,
        description="OEM authorization certificate required",
    )
    db_session.add_all([crit1, crit2])
    db_session.flush()

    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit1.id,
        tender_version_id=v1.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"min_value": 20.0, "currency": "INR"},
        status=RuleStatus.ACTIVE,
    )
    rule2 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit2.id,
        tender_version_id=v1.id,
        rule_type=RuleType.CERTIFICATE_EXISTENCE,
        rule_version="v1.0",
        configuration={"cert_type": "OEM_AUTH"},
        status=RuleStatus.ACTIVE,
    )
    db_session.add_all([rule1, rule2])
    db_session.flush()

    # Bidder A
    bidder_a = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="BID-01",
        legal_name="Zenith Armaments Pvt Ltd",
        contact_email="contact@zenitharmor.in",
    )
    db_session.add(bidder_a)
    db_session.flush()

    # Submission on Version 1
    sub_a = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        submission_reference="SUB-ZEN-001",
        status=SubmissionStatus.READY,
    )
    db_session.add(sub_a)
    db_session.flush()

    # Document
    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bid_submission_id=sub_a.id,
        filename="Audited_Financials_2025.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=12000,
        sha256_hash="55" * 32,
        storage_key=f"docs/{sub_a.id}/fin.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()

    # Evidence
    run_id = uuid.uuid4()
    ev1 = Evidence(
        id=uuid.uuid4(),
        document_id=doc.id,
        criterion_id=crit1.id,
        bid_submission_id=sub_a.id,
        extraction_run_id=run_id,
        extractor_version="1.0.0",
        status=EvidenceStatus.FOUND,
        source_page=2,
        extracted_value=24.5,
        normalized_value="24.5",
        confidence=0.98,
        extracted_text="Audited turnover is 24.5 Crore",
        raw_extracted_data={"extracted_value": 24.5, "normalized_value": 24.5},
    )
    ev2 = Evidence(
        id=uuid.uuid4(),
        document_id=doc.id,
        criterion_id=crit2.id,
        bid_submission_id=sub_a.id,
        extraction_run_id=run_id,
        extractor_version="1.0.0",
        status=EvidenceStatus.UNREADABLE,
        source_page=8,
        confidence=0.5,
        extracted_text="Unclear scan of OEM authorization certificate",
        raw_extracted_data={"status": "UNREADABLE"},
    )
    db_session.add_all([ev1, ev2])
    db_session.flush()

    # Criterion Evaluations
    ce1 = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        bid_submission_id=sub_a.id,
        criterion_id=crit1.id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"extracted": 24.5, "min": 20.0},
        evidence_ids=[str(ev1.id)],
        explanation={"passed": True, "value": 24.5},
    )
    ce2 = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        bid_submission_id=sub_a.id,
        criterion_id=crit2.id,
        rule_id=rule2.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.MANUAL_REVIEW,
        input_snapshot={"status": "UNREADABLE"},
        evidence_ids=[str(ev2.id)],
        explanation={"reason": "Unreadable evidence requires officer inspection"},
    )
    db_session.add_all([ce1, ce2])
    db_session.flush()

    # Bidder Overall Evaluation
    be = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        bid_submission_id=sub_a.id,
        result=EvaluationResult.MANUAL_REVIEW,
        criterion_count=2,
        eligible_count=1,
        not_eligible_count=0,
        manual_review_count=1,
        mandatory_criterion_count=2,
        mandatory_eligible_count=1,
        mandatory_not_eligible_count=0,
        mandatory_manual_review_count=1,
    )
    db_session.add(be)
    db_session.flush()

    # Review Case & Officer Decision
    rc = ReviewCase(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=v1.id,
        bidder_id=bidder_a.id,
        bid_submission_id=sub_a.id,
        criterion_id=crit2.id,
        criterion_evaluation_id=ce2.id,
        status=ReviewStatus.RESOLVED,
        priority=ReviewPriority.HIGH,
        issue_type=ReviewIssueType.UNREADABLE_EVIDENCE,
        title="OEM Certificate Verification",
    )
    db_session.add(rc)
    db_session.flush()

    dec = OfficerDecision(
        id=uuid.uuid4(),
        review_case_id=rc.id,
        criterion_id=crit2.id,
        criterion_evaluation_id=ce2.id,
        decision=HumanDecision.OVERRIDE,
        system_result=EvaluationResult.MANUAL_REVIEW,
        final_verdict=EvaluationResult.ELIGIBLE,
        reason="Physical stamped OEM certificate inspected and validated.",
        officer_id=officer.id,
    )
    db_session.add(dec)
    db_session.commit()

    token = create_access_token(officer.id)
    headers = {"Authorization": f"Bearer {token}"}

    yield {
        "officer": officer,
        "headers": headers,
        "tender": tender,
        "v1": v1,
        "v2": v2,
        "bidder_a": bidder_a,
        "sub_a": sub_a,
        "ce1": ce1,
        "ce2": ce2,
        "storage": mem_storage,
    }

    set_storage_service_override(None)


def test_full_bidder_report_lifecycle_and_historical_versioning(client: TestClient, phase17_test_data, db_session):
    """Test full Phase 17 bidder report lifecycle: generate v1 -> metadata -> download -> regenerate v2 -> list."""
    headers = phase17_test_data["headers"]
    sub_a = phase17_test_data["sub_a"]
    tender = phase17_test_data["tender"]
    v1 = phase17_test_data["v1"]

    # 1. Generate Report v1
    res1 = client.post(
        f"/api/v1/submissions/{sub_a.id}/reports",
        json={"title": "Official Tender Evaluation Report v1", "include_audit_summary": True},
        headers=headers,
    )
    assert res1.status_code == 201
    rep1 = res1.json()
    assert rep1["status"] == "COMPLETED"
    assert rep1["report_version"] == 1
    assert rep1["file_hash"] is not None
    assert len(rep1["file_hash"]) == 64
    assert rep1["storage_key"] is not None
    report_id_v1 = rep1["id"]

    # 2. Fetch Report Metadata
    res_meta = client.get(f"/api/v1/reports/{report_id_v1}", headers=headers)
    assert res_meta.status_code == 200
    meta_data = res_meta.json()
    assert meta_data["id"] == report_id_v1
    assert meta_data["report_type"] == "BIDDER_EVALUATION_REPORT"
    assert meta_data["report_version"] == 1

    # 3. Download PDF Stream & Check SHA-256 Header
    res_dl = client.get(f"/api/v1/reports/{report_id_v1}/download", headers=headers)
    assert res_dl.status_code == 200
    assert res_dl.headers["content-type"] == "application/pdf"
    assert res_dl.headers["x-report-sha256"] == rep1["file_hash"]
    pdf_content = res_dl.content
    assert pdf_content.startswith(b"%PDF-")
    assert hashlib.sha256(pdf_content).hexdigest() == rep1["file_hash"]

    # 4. Regenerate Report to create Version 2 (Historical preservation)
    res2 = client.post(
        f"/api/v1/submissions/{sub_a.id}/reports",
        json={"title": "Official Tender Evaluation Report v2 (Regenerated)"},
        headers=headers,
    )
    assert res2.status_code == 201
    rep2 = res2.json()
    assert rep2["status"] == "COMPLETED"
    assert rep2["report_version"] == 2
    assert rep2["id"] != report_id_v1

    # 5. Verify v1 is still accessible and unchanged
    res_v1_check = client.get(f"/api/v1/reports/{report_id_v1}", headers=headers)
    assert res_v1_check.status_code == 200
    assert res_v1_check.json()["report_version"] == 1

    # 6. List Submission Reports
    res_sub_list = client.get(f"/api/v1/submissions/{sub_a.id}/reports", headers=headers)
    assert res_sub_list.status_code == 200
    sub_list_data = res_sub_list.json()
    assert sub_list_data["total"] == 2
    versions = [r["report_version"] for r in sub_list_data["items"]]
    assert 1 in versions
    assert 2 in versions

    # 7. Generate Consolidated Tender Report
    res_cons = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{v1.id}/reports",
        json={"title": "Consolidated Tender Report for Version 1"},
        headers=headers,
    )
    assert res_cons.status_code == 201
    cons_rep = res_cons.json()
    assert cons_rep["report_type"] == "CONSOLIDATED_TENDER_REPORT"
    assert cons_rep["status"] == "COMPLETED"

    # 8. List Reports at Tender Version Level
    res_tv_list = client.get(f"/api/v1/tenders/{tender.id}/versions/{v1.id}/reports", headers=headers)
    assert res_tv_list.status_code == 200
    assert res_tv_list.json()["total"] == 3  # 2 bidder + 1 consolidated

    # 9. List All Reports via Global Reports Endpoint with Filter
    res_all = client.get(f"/api/v1/reports?tender_id={tender.id}", headers=headers)
    assert res_all.status_code == 200
    assert res_all.json()["total"] == 3

    # 10. Verify Audit Trail Events Recorded
    audit_entries = db_session.query(AuditLog).filter(
        AuditLog.entity_type == "REPORT",
        AuditLog.tender_id == tender.id,
    ).all()
    actions = [a.action for a in audit_entries]
    assert "REPORT_GENERATED" in actions
    assert "REPORT_DOWNLOADED" in actions
