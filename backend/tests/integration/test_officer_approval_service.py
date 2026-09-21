"""Integration tests for Officer Approval domain service and lifecycle."""

import pytest
import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.approval.schemas import (
    CriterionApprovalRequest,
    CriterionCorrectionRequest,
    CriterionRejectionRequest,
)
from app.approval.service import (
    approve_criterion,
    correct_criterion,
    get_approved_criteria,
    get_criterion_approval_history,
    reject_criterion,
)
from app.auth.service import create_user
from app.db.models.criterion_approval_history import ApprovalAction
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


@pytest.fixture
def test_officer(db_session: Session) -> User:
    return create_user(
        db=db_session,
        email="approval_officer@crpf.gov.in",
        password="SecureOfficerPassword123!",
        full_name="Approval Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )


@pytest.fixture
def candidate_criterion(db_session: Session, test_officer: User):
    tender = Tender(
        id=uuid.uuid4(),
        tender_number=f"CRPF-APP-{uuid.uuid4().hex[:6].upper()}",
        title="Tactical Body Armor Procurement",
        description="Level IV bullet resistant tactical armor tender.",
        status=TenderStatus.DRAFT,
        created_by=test_officer.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="Initial Release",
        is_active=True,
        created_by=test_officer.id,
    )
    db_session.add(version)
    db_session.flush()

    crit = TenderCriterion(
        id=uuid.uuid4(),
        tender_version_id=version.id,
        criterion_code="FIN-001",
        name="Annual Financial Turnover",
        description="Average annual turnover for last 3 financial years.",
        category=CriterionCategory.FINANCIAL,
        requirement_type=RequirementType.MANDATORY,
        operator=">=",
        threshold_value=50000000.0,
        threshold_text="₹5 Crore",
        unit="INR",
        currency="INR",
        period="preceding three financial years",
        mandatory=True,
        required_evidence=["Audited financial statements"],
        source_clause="The bidder shall have an average annual turnover of at least ₹5 Crore.",
        source_page=1,
        confidence=0.95,
        extraction_status=ExtractionStatus.EXTRACTED,
        model_name="mock-extractor-v1",
        model_version="1.0.0",
        prompt_version="v1",
        # Phase 8 fields
        approval_status=ApprovalStatus.PENDING_REVIEW,
        is_corrected=False,
        original_name="Annual Financial Turnover",
        original_description="Average annual turnover for last 3 financial years.",
        original_category=CriterionCategory.FINANCIAL,
        original_requirement_type=RequirementType.MANDATORY,
        original_operator=">=",
        original_threshold_value=50000000.0,
        original_threshold_text="₹5 Crore",
        original_unit="INR",
        original_currency="INR",
        original_period="preceding three financial years",
        original_mandatory=True,
        original_required_evidence=["Audited financial statements"],
        original_source_clause="The bidder shall have an average annual turnover of at least ₹5 Crore.",
    )
    db_session.add(crit)
    db_session.commit()
    db_session.refresh(crit)
    return tender, version, crit


def test_approve_candidate_criterion_lifecycle(
    db_session: Session,
    test_officer: User,
    candidate_criterion,
):
    """Test approving a candidate criterion transitions status and creates audit history."""
    tender, version, crit = candidate_criterion

    approved_crit = approve_criterion(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
        criterion_id=crit.id,
        current_user=test_officer,
        approval_data=CriterionApprovalRequest(reason="Verified against Ministry guidelines"),
    )

    assert approved_crit.approval_status == ApprovalStatus.APPROVED
    assert approved_crit.approved_by == test_officer.id
    assert approved_crit.approved_at is not None

    # Check history
    history = get_criterion_approval_history(db_session, tender.id, version.id, crit.id)
    assert len(history) == 1
    assert history[0].action == ApprovalAction.APPROVE
    assert history[0].officer_id == test_officer.id
    assert history[0].previous_status == "PENDING_REVIEW"
    assert history[0].new_status == "APPROVED"
    assert history[0].reason == "Verified against Ministry guidelines"

    # Verify query for evaluation engine
    approved_list = get_approved_criteria(db_session, version.id)
    assert len(approved_list) == 1
    assert approved_list[0].id == crit.id


def test_reject_candidate_criterion_lifecycle(
    db_session: Session,
    test_officer: User,
    candidate_criterion,
):
    """Test rejecting a criterion records mandatory reason and updates status."""
    tender, version, crit = candidate_criterion

    rejected_crit = reject_criterion(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
        criterion_id=crit.id,
        current_user=test_officer,
        rejection_data=CriterionRejectionRequest(reason="Redundant requirement covered by Technical Spec clause 4.2"),
    )

    assert rejected_crit.approval_status == ApprovalStatus.REJECTED
    assert rejected_crit.rejection_reason == "Redundant requirement covered by Technical Spec clause 4.2"
    assert rejected_crit.approved_by is None

    # Verify rejected criterion is EXCLUDED from approved evaluation query
    approved_list = get_approved_criteria(db_session, version.id)
    assert len(approved_list) == 0

    # Check audit history
    history = get_criterion_approval_history(db_session, tender.id, version.id, crit.id)
    assert len(history) == 1
    assert history[0].action == ApprovalAction.REJECT
    assert history[0].new_status == "REJECTED"


def test_correct_and_approve_criterion_lifecycle(
    db_session: Session,
    test_officer: User,
    candidate_criterion,
):
    """Test that correcting a criterion updates working fields, preserves AI snapshot, stays PENDING_REVIEW, then gets approved."""
    tender, version, crit = candidate_criterion

    # 1. Officer corrects threshold from 5 Crore to 6 Crore
    correction = CriterionCorrectionRequest(
        name="Updated Annual Turnover Requirement",
        threshold_value=60000000.0,
        threshold_text="₹6 Crore",
        reason="Amended threshold as per CRPF Standing Order No. 44",
    )

    corrected_crit = correct_criterion(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
        criterion_id=crit.id,
        correction=correction,
        current_user=test_officer,
    )

    # Verify working fields updated
    assert corrected_crit.name == "Updated Annual Turnover Requirement"
    assert corrected_crit.threshold_value == 60000000.0
    assert corrected_crit.threshold_text == "₹6 Crore"
    assert corrected_crit.is_corrected is True
    # Verify stays PENDING_REVIEW!
    assert corrected_crit.approval_status == ApprovalStatus.PENDING_REVIEW

    # Verify original AI extraction is IMMUTABLE and untouched!
    assert corrected_crit.original_name == "Annual Financial Turnover"
    assert corrected_crit.original_threshold_value == 50000000.0
    assert corrected_crit.original_threshold_text == "₹5 Crore"

    # 2. Officer explicitly approves corrected criterion
    final_approved = approve_criterion(
        db=db_session,
        tender_id=tender.id,
        tender_version_id=version.id,
        criterion_id=crit.id,
        current_user=test_officer,
        approval_data=CriterionApprovalRequest(reason="Approved with amended threshold"),
    )
    assert final_approved.approval_status == ApprovalStatus.APPROVED

    # Verify chronological audit history captures both CORRECT and APPROVE actions
    history = get_criterion_approval_history(db_session, tender.id, version.id, crit.id)
    assert len(history) == 2
    assert history[0].action == ApprovalAction.CORRECT
    assert history[0].changed_fields["threshold_value"]["old"] == 50000000.0
    assert history[0].changed_fields["threshold_value"]["new"] == 60000000.0
    assert history[1].action == ApprovalAction.APPROVE
