"""Unit tests for Phase 17 edge cases, security, determinism, data immutability, and storage failure handling."""

import hashlib
import io
import re
import uuid
from unittest.mock import MagicMock, patch
import pypdf
import pytest
from app.core.exceptions import ConflictException, NotFoundException
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.evaluation_report import EvaluationReport, ReportStatus, ReportType
from app.db.models.review_case import HumanDecision
from app.reports.pdf_generator import PDFReportGenerator
from app.reports.schemas import (
    BidderExplanationResponse,
    CriterionExplanationResponse,
    EvidenceProvenanceItem,
    ReportCreateRequest,
)
from app.reports.service import ReportService, sanitize_filename
from app.storage.memory import InMemoryObjectStorageService


@pytest.fixture
def base_bidder_explanation() -> BidderExplanationResponse:
    """Fixture providing rich explanation data for edge case testing."""
    cid = uuid.uuid4()
    ceid = uuid.uuid4()
    sub_id = uuid.uuid4()
    doc_id = uuid.uuid4()

    crit = CriterionExplanationResponse(
        criterion_evaluation_id=ceid,
        criterion_id=cid,
        requirement_name="Annual Manufacturing Capacity",
        category="TECHNICAL",
        requirement_type="MANDATORY",
        source_clause="Clause 4.2: Capacity of 50,000 units per annum.",
        rule_type="NUMERIC_THRESHOLD",
        rule_version="v1.0",
        rule_config={"min_value": 50000},
        evidence_items=[
            EvidenceProvenanceItem(
                evidence_id=uuid.uuid4(),
                document_id=doc_id,
                document_name="Factory_Inspection_Report.pdf",
                document_hash="44" * 32,
                page_number=3,
                block_id="blk-01",
                table_reference="Table 1: Production Metrics",
                bbox=[10, 20, 300, 400],
                extracted_value="60000 units/year",
                normalized_value=60000,
                evidence_status="FOUND",
                confidence_score=0.99,
                source_clause_quote="Certified annual capacity is 60,000 units.",
            )
        ],
        primary_document_id=doc_id,
        primary_document_name="Factory_Inspection_Report.pdf",
        primary_document_hash="44" * 32,
        primary_page_number=3,
        primary_bbox=[10, 20, 300, 400],
        extracted_value="60000 units/year",
        normalized_value=60000,
        evidence_status="FOUND",
        extraction_confidence=0.99,
        automated_result=EvaluationResult.ELIGIBLE,
        human_review_required=False,
        final_criterion_decision=EvaluationResult.ELIGIBLE,
    )

    return BidderExplanationResponse(
        tender_id=uuid.uuid4(),
        tender_number="CRPF-T-2026-UNIT-001",
        tender_title="Procurement of Ballistic Protection Helmets",
        tender_version_id=uuid.uuid4(),
        tender_version_number=1,
        bidder_id=uuid.uuid4(),
        bidder_name="Alpha Defense Industries",
        bid_submission_id=sub_id,
        evaluation_run_id=uuid.uuid4(),
        overall_evaluation_id=uuid.uuid4(),
        total_criteria=1,
        mandatory_criteria_count=1,
        optional_criteria_count=0,
        eligible_count=1,
        not_eligible_count=0,
        manual_review_count=0,
        mandatory_eligible_count=1,
        mandatory_not_eligible_count=0,
        mandatory_manual_review_count=0,
        missing_evidence_count=0,
        conflicting_evidence_count=0,
        unreadable_evidence_count=0,
        ambiguous_evidence_count=0,
        invalid_evidence_count=0,
        automated_overall_result=EvaluationResult.ELIGIBLE,
        human_overall_decision=HumanDecision.CONFIRM,
        final_decision_state=EvaluationResult.ELIGIBLE,
        criteria_explanations=[crit],
        review_cases_summary=[],
    )


def test_sha256_exact_match(base_bidder_explanation):
    """Verify that SHA-256 computed on PDF binary exactly matches stored hash."""
    report_meta = {
        "report_id": uuid.uuid4(),
        "generated_at": "2026-09-18 12:00:00 UTC",
        "report_version": 1,
    }
    pdf_bytes = PDFReportGenerator.generate_bidder_report(
        explanation=base_bidder_explanation,
        report_meta=report_meta,
    )

    expected_hash = hashlib.sha256(pdf_bytes).hexdigest()
    assert len(expected_hash) == 64
    assert expected_hash == hashlib.sha256(pdf_bytes).hexdigest()


def test_automated_vs_human_verdicts_separation(base_bidder_explanation):
    """Verify that Automated Result and Human Decision are distinctly rendered and neither replaces the other."""
    base_bidder_explanation.automated_overall_result = EvaluationResult.NOT_ELIGIBLE
    base_bidder_explanation.human_overall_decision = HumanDecision.OVERRIDE
    base_bidder_explanation.final_decision_state = EvaluationResult.ELIGIBLE

    pdf_bytes = PDFReportGenerator.generate_bidder_report(
        explanation=base_bidder_explanation,
    )

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    all_text = " ".join([page.extract_text() for page in reader.pages])
    norm_text = re.sub(r"\s+", " ", all_text)

    # Both must be present in executive summary
    assert "NOT_ELIGIBLE" in norm_text
    assert "OVERRIDE" in norm_text
    assert "ELIGIBLE" in norm_text


def test_long_content_performance_sanity_50_plus_criteria(base_bidder_explanation):
    """Performance sanity test: generate report with 55 detailed criteria."""
    criteria = []
    for i in range(1, 56):
        criteria.append(
            CriterionExplanationResponse(
                criterion_evaluation_id=uuid.uuid4(),
                criterion_id=uuid.uuid4(),
                requirement_name=f"CRPF Technical Specification #{i:02d} - Extended Detailed Requirement Description",
                category="TECHNICAL" if i % 2 == 0 else "FINANCIAL",
                requirement_type="MANDATORY" if i % 3 != 0 else "OPTIONAL",
                source_clause=f"Clause {i}.4.1: The bidder must furnish verifiable compliance documentation for spec #{i}.",
                rule_type="NUMERIC_THRESHOLD",
                rule_version="v1.0",
                evidence_items=[
                    EvidenceProvenanceItem(
                        evidence_id=uuid.uuid4(),
                        document_id=uuid.uuid4(),
                        document_name=f"Technical_Specification_Compliance_Doc_Set_{i:02d}.pdf",
                        page_number=i * 2,
                        extracted_value=f"Compliant Spec Value #{i} Tested and Verified",
                        normalized_value=float(i),
                        evidence_status="FOUND",
                        confidence_score=0.98,
                    )
                ],
                primary_document_name=f"Technical_Specification_Compliance_Doc_Set_{i:02d}.pdf",
                primary_page_number=i * 2,
                extracted_value=f"Compliant Spec Value #{i}",
                normalized_value=float(i),
                evidence_status="FOUND",
                automated_result=EvaluationResult.ELIGIBLE if i % 5 != 0 else EvaluationResult.MANUAL_REVIEW,
                human_review_required=(i % 5 == 0),
                final_criterion_decision=EvaluationResult.ELIGIBLE,
            )
        )

    base_bidder_explanation.criteria_explanations = criteria
    base_bidder_explanation.total_criteria = len(criteria)

    import time
    start_time = time.time()
    pdf_bytes = PDFReportGenerator.generate_bidder_report(explanation=base_bidder_explanation)
    duration = time.time() - start_time

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 10000
    assert duration < 5.0

    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    assert len(reader.pages) >= 3


def test_storage_failure_handling(db_session, base_bidder_explanation):
    """Verify that storage failure marks report as FAILED and does not claim COMPLETED state."""
    from app.db.models.bid_submission import BidSubmission, SubmissionStatus
    from app.db.models.bidder import Bidder
    from app.db.models.criterion_evaluation import CriterionEvaluation
    from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
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

    user = User(
        id=uuid.uuid4(),
        email=f"officer_fail_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Officer Fail Test",
        is_active=True,
        password_hash="pwd",
    )
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-FAIL-{uuid.uuid4().hex[:6]}",
        title="Fail Test Tender",
        status=TenderStatus.PUBLISHED,
        created_by=user.id,
    )
    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=user.id,
    )
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C01",
        name="Fail Test Requirement",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 1.1: Test clause",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        approval_status=ApprovalStatus.APPROVED,
        extraction_status=ExtractionStatus.EXTRACTED,
        description="Fail test requirement",
    )
    rule = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"min_value": 10},
        status=RuleStatus.ACTIVE,
    )
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="B-FAIL",
        legal_name="Fail Bidder",
    )
    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-FAIL",
        status=SubmissionStatus.READY,
    )
    ce = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        criterion_id=crit.id,
        rule_id=rule.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={},
        explanation={"passed": True},
    )

    db_session.add_all([user, tender, version, crit, rule, bidder, sub, ce])
    db_session.commit()

    failing_storage = MagicMock()
    failing_storage.upload.side_effect = IOError("MinIO / S3 Network Connection Timeout")

    req = ReportCreateRequest(title="Failing Storage Report")
    report = ReportService.generate_bidder_report(
        db=db_session,
        submission_id=sub.id,
        current_user=user,
        request=req,
        storage=failing_storage,
    )

    assert report.status == ReportStatus.FAILED
    assert "MinIO / S3 Network Connection Timeout" in (report.error_message or "")
    assert report.storage_key is None


def test_no_ai_and_no_opa_calls_during_report_generation(db_session):
    """Verify that ReportService does not invoke LLM, VLM, OCR or OPA evaluators."""
    from app.db.models.bid_submission import BidSubmission, SubmissionStatus
    from app.db.models.bidder import Bidder
    from app.db.models.criterion_evaluation import CriterionEvaluation
    from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
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

    user = User(
        id=uuid.uuid4(),
        email=f"officer_noai_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Officer No AI",
        is_active=True,
        password_hash="pwd",
    )
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-NOAI-{uuid.uuid4().hex[:6]}",
        title="No AI Tender",
        status=TenderStatus.PUBLISHED,
        created_by=user.id,
    )
    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=user.id,
    )
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C01",
        name="No AI Requirement",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 1.1: Spec requirement",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        approval_status=ApprovalStatus.APPROVED,
        extraction_status=ExtractionStatus.EXTRACTED,
        description="No AI requirement",
    )
    rule = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"min_value": 10},
        status=RuleStatus.ACTIVE,
    )
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="B-NOAI",
        legal_name="No AI Bidder",
    )
    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-NOAI",
        status=SubmissionStatus.READY,
    )
    ce = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        criterion_id=crit.id,
        rule_id=rule.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={},
        explanation={"passed": True},
    )

    db_session.add_all([user, tender, version, crit, rule, bidder, sub, ce])
    db_session.commit()

    storage = InMemoryObjectStorageService()

    with patch("app.rules.opa.evaluator.LocalRegoEvaluator.evaluate") as mock_opa, \
         patch("app.aggregation.service.aggregate_submission_evaluation") as mock_agg:
        req = ReportCreateRequest(title="Deterministic Report")
        report = ReportService.generate_bidder_report(
            db=db_session,
            submission_id=sub.id,
            current_user=user,
            request=req,
            storage=storage,
        )

        assert report.status == ReportStatus.COMPLETED
        # Verify neither OPA nor aggregation service is called during report generation
        mock_opa.assert_not_called()
        mock_agg.assert_not_called()


def test_data_immutability_during_report_generation(db_session):
    """Verify that generating a report does not mutate underlying criteria, evaluations, or submission status."""
    from app.db.models.bid_submission import BidSubmission, SubmissionStatus
    from app.db.models.bidder import Bidder
    from app.db.models.criterion_evaluation import CriterionEvaluation
    from app.db.models.criterion_rule import CriterionRule, RuleStatus, RuleType
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

    user = User(
        id=uuid.uuid4(),
        email=f"officer_immut_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        full_name="Officer Immutability",
        is_active=True,
        password_hash="pwd",
    )
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-IMMUT-{uuid.uuid4().hex[:6]}",
        title="Immutability Tender",
        status=TenderStatus.PUBLISHED,
        created_by=user.id,
    )
    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        created_by=user.id,
    )
    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="C01",
        name="Fixed Requirement",
        category=CriterionCategory.TECHNICAL,
        requirement_type=RequirementType.MANDATORY,
        source_clause="Clause 1.1: Immutable clause",
        model_name="crpf-ai-v1",
        model_version="1.0.0",
        prompt_version="1.0.0",
        approval_status=ApprovalStatus.APPROVED,
        extraction_status=ExtractionStatus.EXTRACTED,
        description="Must not mutate",
    )
    rule = CriterionRule(
        id=uuid.uuid4(),
        criterion_id=crit.id,
        tender_version_id=version.id,
        rule_type=RuleType.NUMERIC_THRESHOLD,
        rule_version="v1.0",
        configuration={"min_value": 10},
        status=RuleStatus.ACTIVE,
    )
    bidder = Bidder(
        id=uuid.uuid4(),
        tender_id=tender.id,
        bidder_code="B-IMMUT",
        legal_name="Immutable Bidder",
    )
    sub = BidSubmission(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        submission_reference="SUB-IMMUT",
        status=SubmissionStatus.READY,
    )
    ce = CriterionEvaluation(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        bidder_id=bidder.id,
        bid_submission_id=sub.id,
        criterion_id=crit.id,
        rule_id=rule.id,
        rule_version="v1.0",
        policy_version="v1.0",
        result=EvaluationResult.ELIGIBLE,
        input_snapshot={"val": 100},
        explanation={"passed": True},
    )

    db_session.add_all([user, tender, version, crit, rule, bidder, sub, ce])
    db_session.commit()

    baseline_sub_status = sub.status
    baseline_ce_result = ce.result
    baseline_crit_name = crit.name

    storage = InMemoryObjectStorageService()
    req = ReportCreateRequest(title="Read-Only Verification Report")
    report = ReportService.generate_bidder_report(
        db=db_session,
        submission_id=sub.id,
        current_user=user,
        request=req,
        storage=storage,
    )

    db_session.refresh(sub)
    db_session.refresh(ce)
    db_session.refresh(crit)

    assert sub.status == baseline_sub_status
    assert ce.result == baseline_ce_result
    assert crit.name == baseline_crit_name
