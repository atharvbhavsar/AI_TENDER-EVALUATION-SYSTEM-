"""Integration tests for Phase 14 Reporting and Explainability APIs."""

import hashlib
import io
import uuid
import pypdf
import pytest
from fastapi.testclient import TestClient
from app.auth.jwt import create_access_token
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
def report_fixture(db_session):
    """Setup complete test fixture for Phase 14 reporting workflows."""
    mem_storage = InMemoryObjectStorageService()
    set_storage_service_override(mem_storage)

    officer_role = db_session.query(Role).filter_by(name="PROCUREMENT_OFFICER").first()

    officer = User(
        id=uuid.uuid4(),
        email=f"officer_rep_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Procurement Officer Report",
        is_active=True,
        password_hash="dummy_hash",
    )
    if officer_role:
        officer.roles.append(officer_role)
    db_session.add(officer)

    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-REP-{uuid.uuid4().hex[:6]}",
        title="Procurement of Night Vision Devices",
        status=TenderStatus.PUBLISHED,
        created_by=officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=officer.id,
    )
    db_session.add(version)
    db_session.flush()

    crit1 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C01",
        name="Turnover Requirement",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 4.1: Turnover requirement",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extraction_status=ExtractionStatus.EXTRACTED,
        approval_status=ApprovalStatus.APPROVED,
        description="Minimum turnover 15 Crore in INR",
    )
    crit2 = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C02",
        name="OEM Authorization Certificate",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 5.2: OEM authorization letter",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        extraction_status=ExtractionStatus.EXTRACTED,
        approval_status=ApprovalStatus.APPROVED,
        description="Valid OEM authorization letter",
    )
    db_session.add_all([crit1, crit2])
    db_session.flush()

    rule1 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit1.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"min_value": 15.0, "currency": "INR"},
        status=RuleStatus.ACTIVE,
    )
    rule2 = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit2.id,
        tender_version_id=version.id,
        rule_type=RuleType.CERTIFICATE_EXISTENCE,
        rule_version="v1.0",
        configuration={"cert_type": "OEM_AUTH"},
        status=RuleStatus.ACTIVE,
    )
    db_session.add_all([rule1, rule2])
    db_session.flush()

    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code=f"OPT-{uuid.uuid4().hex[:4]}",
        legal_name="NightOptics India Pvt Ltd",
        contact_email="contact@nightoptics.in",
    )
    db_session.add(bidder)
    db_session.flush()

    submission = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-OPT-001",
        status=SubmissionStatus.READY,
    )
    db_session.add(submission)
    db_session.flush()



    doc = Document(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bid_submission_id=submission.id,
        filename="Financial_Audit_2023.pdf",
        content_type="application/pdf",
        file_extension=".pdf",
        file_size=5000,
        sha256_hash="11" * 32,
        storage_key=f"docs/{submission.id}/audit.pdf",
        document_type=DocumentType.DIGITAL_PDF,
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=officer.id,
    )
    db_session.add(doc)
    db_session.flush()

    run_id = uuid.uuid4()
    ev1 = Evidence(
        id=uuid.uuid4(),
        document_id=doc.id,
        criterion_id=crit1.id,
        bid_submission_id=submission.id,
        extraction_run_id=run_id,
        extractor_version="1.0.0",
        status=EvidenceStatus.FOUND,
        source_page=1,
        extracted_value=18.5,
        normalized_value="18.5",
        confidence=0.99,
        extracted_text="Annual turnover is 18.5 Cr in FY23",
        raw_extracted_data={"extracted_value": 18.5, "normalized_value": 18.5},
    )
    ev2 = Evidence(
        id=uuid.uuid4(),
        document_id=doc.id,
        criterion_id=crit2.id,
        bid_submission_id=submission.id,
        extraction_run_id=run_id,
        extractor_version="1.0.0",
        status=EvidenceStatus.UNREADABLE,
        source_page=5,
        confidence=0.4,
        extracted_text="Blurry scan of certificate",
        raw_extracted_data={"status": "UNREADABLE"},
    )
    db_session.add_all([ev1, ev2])
    db_session.flush()

    ce1 = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=crit1.id,
        rule_id=rule1.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"extracted": 18.5, "min": 15.0},
        evidence_ids=[str(ev1.id)],
        explanation={"extracted": 18.5, "min": 15.0, "passed": True},
    )
    ce2 = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=crit2.id,
        rule_id=rule2.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.MANUAL_REVIEW,
        input_snapshot={"status": "UNREADABLE"},
        evidence_ids=[str(ev2.id)],
        explanation={"reason": "Unreadable scan requires manual inspection"},
    )
    db_session.add_all([ce1, ce2])
    db_session.flush()

    be = BidderEvaluation(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
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

    rc = ReviewCase(
        id=uuid.uuid4(),
        tender_id=tender.id,
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=submission.id,
        criterion_id=crit2.id,
        criterion_evaluation_id=ce2.id,
        status=ReviewStatus.RESOLVED,
        priority=ReviewPriority.HIGH,
        issue_type=ReviewIssueType.UNREADABLE_EVIDENCE,
        title="OEM Letter Clarification",
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
        reason="Verified original stamped letter from manufacturer.",
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
        "version": version,
        "bidder": bidder,
        "submission": submission,
        "ce1": ce1,
        "ce2": ce2,
        "storage": mem_storage,
    }

    set_storage_service_override(None)


def test_explainability_endpoints(client: TestClient, report_fixture):
    """Test criterion-level and bidder-level explanation endpoints."""
    headers = report_fixture["headers"]
    ce1 = report_fixture["ce1"]
    submission = report_fixture["submission"]

    # 1. Criterion explanation
    res1 = client.get(f"/api/v1/criterion-evaluations/{ce1.id}/explanation", headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["requirement_name"] == "Turnover Requirement"
    assert data1["automated_result"] == "ELIGIBLE"
    assert data1["final_criterion_decision"] == "ELIGIBLE"
    assert data1["primary_document_name"] == "Financial_Audit_2023.pdf"

    # 2. Bidder explanation
    res2 = client.get(f"/api/v1/submissions/{submission.id}/explanation", headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["bidder_name"] == "NightOptics India Pvt Ltd"
    assert data2["automated_overall_result"] == "MANUAL_REVIEW"
    assert data2["human_overall_decision"] == "OVERRIDE"
    assert data2["final_decision_state"] == "ELIGIBLE"
    assert len(data2["criteria_explanations"]) == 2


def test_bidder_report_generation_and_download_flow(client: TestClient, report_fixture):
    """Test full flow: generate bidder report, get metadata, download PDF, verify versioning."""
    headers = report_fixture["headers"]
    submission = report_fixture["submission"]
    tender = report_fixture["tender"]
    version = report_fixture["version"]

    # 1. Generate Report v1
    res1 = client.post(
        f"/api/v1/submissions/{submission.id}/reports",
        json={"title": "Official Tender Evaluation Report", "include_audit_summary": True},
        headers=headers,
    )
    assert res1.status_code == 201
    rep1 = res1.json()
    assert rep1["status"] == "COMPLETED"
    assert rep1["report_version"] == 1
    assert rep1["file_hash"] is not None
    assert rep1["storage_key"] is not None
    report_id = rep1["id"]

    # 2. Get Metadata
    res_meta = client.get(f"/api/v1/reports/{report_id}", headers=headers)
    assert res_meta.status_code == 200
    assert res_meta.json()["id"] == report_id

    # 3. Download PDF
    res_dl = client.get(f"/api/v1/reports/{report_id}/download", headers=headers)
    assert res_dl.status_code == 200
    assert res_dl.headers["content-type"] == "application/pdf"
    assert res_dl.headers["x-report-sha256"] == rep1["file_hash"]
    pdf_bytes = res_dl.content
    assert pdf_bytes.startswith(b"%PDF-")
    assert hashlib.sha256(pdf_bytes).hexdigest() == rep1["file_hash"]

    # Read PDF text
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    full_text = "".join([p.extract_text() for p in reader.pages])
    assert "NightOptics India Pvt Ltd" in full_text
    assert "CRPF" in full_text

    # 4. Generate Report v2 (regenerate creates next version, does NOT overwrite v1)
    res2 = client.post(
        f"/api/v1/submissions/{submission.id}/reports",
        json={"title": "Official Tender Evaluation Report Revised"},
        headers=headers,
    )
    assert res2.status_code == 201
    rep2 = res2.json()
    assert rep2["report_version"] == 2
    assert rep2["id"] != rep1["id"]

    # 5. Consolidated Tender Report
    res_cons = client.post(
        f"/api/v1/tenders/{tender.id}/versions/{version.id}/reports",
        json={"title": "Consolidated Tender Report v1"},
        headers=headers,
    )
    assert res_cons.status_code == 201
    cons_rep = res_cons.json()
    assert cons_rep["report_type"] == "CONSOLIDATED_TENDER_REPORT"
    assert cons_rep["status"] == "COMPLETED"

    # 6. List Tender Version Reports
    res_list = client.get(f"/api/v1/tenders/{tender.id}/versions/{version.id}/reports", headers=headers)
    assert res_list.status_code == 200
    list_data = res_list.json()
    assert list_data["total"] >= 3  # 2 bidder reports + 1 consolidated report
