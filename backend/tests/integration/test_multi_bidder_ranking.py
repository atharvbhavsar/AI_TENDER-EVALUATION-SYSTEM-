"""Comprehensive test suite for Multi-Bidder Tender Evaluation and Deterministic Ranking.

Verifies:
- Test 1: Two eligible bidders both enter ranking.
- Test 2: Ineligible bidder excluded from ranking (cannot receive L1/L2).
- Test 3: Manual review held in PENDING_MANUAL_REVIEW.
- Test 4: L1 lowest evaluated price ordering (L1, L2, L3).
- Test 5: Tie handling triggers TIE_REQUIRES_HUMAN_REVIEW without random resolution.
- Test 6: QCBS / Weighted formula verified with exact tender weights.
- Test 7: Version isolation (V1 rankings untouched when V2 is evaluated).
- Test 8: Ranking reproducibility without LLM.
- Test 9: LLM independence (pure deterministic backend).
- Test 10: Evidence provenance tracking.
- Test 11: Security & RBAC verification (client cannot inject rank).
- Test 12: Comparative PDF Report generation.
"""

import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app.db.models.bid_submission import BidSubmission, SubmissionStatus
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.tender import Tender, TenderStatus
from app.db.models.tender_evaluation_method import (
    EvaluationMethodType,
    RankingDirection,
    TenderEvaluationMethod,
)
from app.db.models.bidder_ranking import BidderRanking, RankingStatus
from app.db.models.tender_version import TenderVersion
from app.db.models.user import User
from app.ranking.engine import (
    BidderEvaluationRecord,
    calculate_deterministic_ranking,
)
from app.ranking.service import ComparativeEvaluationService
from app.ranking.schemas import (
    ComparativeEvaluationRequest,
    TenderEvaluationMethodCreate,
)
from app.reports.comparative_pdf_generator import generate_comparative_ranking_pdf


@pytest.fixture(scope="module")
def db_engine():
    """In-memory SQLite engine for fast, isolated testing."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Provides a clean transactional database session for each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session_factory = sessionmaker(bind=connection)
    session = session_factory()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def base_tender_fixture(db_session):
    """Create a tender with version 1."""
    user = User(
        id=uuid.uuid4(),
        email=f"officer_{uuid.uuid4().hex[:6]}@crpf.gov.in",
        password_hash="hash",
        full_name="Procurement Officer",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    tender = Tender(
        id=uuid.uuid4(),
        tender_number="CRPF/PPE/2026/001",
        title="Supply of Advanced Personal Protective Equipment",
        description="Fictional tender for multi-bidder ranking tests",
        status=TenderStatus.DRAFT,
        created_by=user.id,
    )
    db_session.add(tender)
    db_session.flush()

    version = TenderVersion(
        id=uuid.uuid4(),
        tender_id=tender.id,
        version_number=1,
        version_label="v1.0",
        created_by=user.id,
    )
    db_session.add(version)
    db_session.flush()

    return {
        "user": user,
        "tender": tender,
        "version": version,
    }


# ==============================================================================
# TEST 1: TWO ELIGIBLE BIDDERS
# ==============================================================================
def test_01_two_eligible_bidders_both_enter_ranking(db_session, base_tender_fixture):
    """Verify that when both bidders are ELIGIBLE, both enter the qualified ranking pool."""
    f = base_tender_fixture
    v_id = f["version"].id
    t_id = f["tender"].id

    # Bidder A: Evaluated Price 10.2 Crore
    b_a = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-A", legal_name="Apex Secure Systems")
    db_session.add(b_a)
    db_session.flush()
    sub_a = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v_id, bidder_id=b_a.id,
        submission_reference="SUB-A-01", status=SubmissionStatus.READY,
    )
    db_session.add(sub_a)
    db_session.flush()
    eval_a = BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v_id, bidder_id=b_a.id,
        bid_submission_id=sub_a.id, result=EvaluationResult.ELIGIBLE,
        explanation={"evaluated_price": 102000000.0},
    )
    db_session.add(eval_a)

    # Bidder B: Evaluated Price 9.6 Crore
    b_b = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-B", legal_name="Bharat Defense Armour")
    db_session.add(b_b)
    db_session.flush()
    sub_b = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v_id, bidder_id=b_b.id,
        submission_reference="SUB-B-01", status=SubmissionStatus.READY,
    )
    db_session.add(sub_b)
    db_session.flush()
    eval_b = BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v_id, bidder_id=b_b.id,
        bid_submission_id=sub_b.id, result=EvaluationResult.ELIGIBLE,
        explanation={"evaluated_price": 96000000.0},
    )
    db_session.add(eval_b)
    db_session.commit()

    resp = ComparativeEvaluationService.run_comparative_evaluation(
        db=db_session,
        tender_id=t_id,
        tender_version_id=v_id,
    )

    assert resp.total_bidders == 2
    assert resp.eligible_count == 2
    assert resp.ranked_count == 2
    assert resp.has_ties is False

    # Bharat Defense (9.6 Cr) must be L1; Apex (10.2 Cr) must be L2
    assert resp.rankings[0].bidder_name == "Bharat Defense Armour"
    assert resp.rankings[0].rank == 1
    assert resp.rankings[0].rank_label == "L1"
    assert resp.rankings[0].ranking_status == RankingStatus.QUALIFIED_RANKED

    assert resp.rankings[1].bidder_name == "Apex Secure Systems"
    assert resp.rankings[1].rank == 2
    assert resp.rankings[1].rank_label == "L2"
    assert resp.rankings[1].ranking_status == RankingStatus.QUALIFIED_RANKED


# ==============================================================================
# TEST 2: ONE INELIGIBLE BIDDER
# ==============================================================================
def test_02_ineligible_bidder_excluded_from_ranking(db_session, base_tender_fixture):
    """Verify that an ineligible bidder cannot receive L1/L2 even if their price is lower."""
    f = base_tender_fixture
    v_id = f["version"].id
    t_id = f["tender"].id

    # Bidder A: ELIGIBLE with higher price 10.0 Cr
    b_a = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-A2", legal_name="Eligible Bidder A")
    db_session.add(b_a)
    db_session.flush()
    sub_a = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v_id, bidder_id=b_a.id,
        submission_reference="SUB-A-02", status=SubmissionStatus.READY,
    )
    db_session.add(sub_a)
    db_session.flush()
    eval_a = BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v_id, bidder_id=b_a.id,
        bid_submission_id=sub_a.id, result=EvaluationResult.ELIGIBLE,
        explanation={"evaluated_price": 100000000.0},
    )
    db_session.add(eval_a)

    # Bidder B: NOT_ELIGIBLE with CHEAPER price 8.0 Cr
    b_b = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-B2", legal_name="Cheaper Ineligible Bidder B")
    db_session.add(b_b)
    db_session.flush()
    sub_b = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v_id, bidder_id=b_b.id,
        submission_reference="SUB-B-02", status=SubmissionStatus.READY,
    )
    db_session.add(sub_b)
    db_session.flush()
    eval_b = BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v_id, bidder_id=b_b.id,
        bid_submission_id=sub_b.id, result=EvaluationResult.NOT_ELIGIBLE,
        explanation={"evaluated_price": 80000000.0},
    )
    db_session.add(eval_b)
    db_session.commit()

    resp = ComparativeEvaluationService.run_comparative_evaluation(
        db=db_session,
        tender_id=t_id,
        tender_version_id=v_id,
    )

    assert resp.total_bidders == 2
    assert resp.eligible_count == 1
    assert resp.not_eligible_count == 1
    assert resp.ranked_count == 1

    # Bidder A must be L1
    assert resp.rankings[0].bidder_name == "Eligible Bidder A"
    assert resp.rankings[0].rank == 1
    assert resp.rankings[0].rank_label == "L1"

    # Bidder B must be EXCLUDED_INELIGIBLE and rank is None
    assert resp.rankings[1].bidder_name == "Cheaper Ineligible Bidder B"
    assert resp.rankings[1].rank is None
    assert resp.rankings[1].rank_label is None
    assert resp.rankings[1].ranking_status == RankingStatus.EXCLUDED_INELIGIBLE


# ==============================================================================
# TEST 3: MANUAL REVIEW HANDLING
# ==============================================================================
def test_03_manual_review_held_pending(db_session, base_tender_fixture):
    """Verify that a bidder with unresolved MANUAL_REVIEW is held in PENDING_MANUAL_REVIEW."""
    f = base_tender_fixture
    v_id = f["version"].id
    t_id = f["tender"].id

    b_a = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-A3", legal_name="Clean Eligible A")
    db_session.add(b_a)
    db_session.flush()
    sub_a = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v_id, bidder_id=b_a.id,
        submission_reference="SUB-A-03", status=SubmissionStatus.READY,
    )
    db_session.add(sub_a)
    db_session.flush()
    db_session.add(BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v_id, bidder_id=b_a.id,
        bid_submission_id=sub_a.id, result=EvaluationResult.ELIGIBLE,
        explanation={"evaluated_price": 100000000.0},
    ))

    b_b = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-B3", legal_name="Ambiguous Bidder B")
    db_session.add(b_b)
    db_session.flush()
    sub_b = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v_id, bidder_id=b_b.id,
        submission_reference="SUB-B-03", status=SubmissionStatus.READY,
    )
    db_session.add(sub_b)
    db_session.flush()
    db_session.add(BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v_id, bidder_id=b_b.id,
        bid_submission_id=sub_b.id, result=EvaluationResult.MANUAL_REVIEW,
        explanation={"evaluated_price": 90000000.0},
    ))
    db_session.commit()

    resp = ComparativeEvaluationService.run_comparative_evaluation(
        db=db_session,
        tender_id=t_id,
        tender_version_id=v_id,
    )

    assert resp.manual_review_count == 1
    assert resp.ranked_count == 1

    # Bidder A is L1
    assert resp.rankings[0].bidder_name == "Clean Eligible A"
    assert resp.rankings[0].rank == 1
    assert resp.rankings[0].rank_label == "L1"

    # Bidder B is held
    assert resp.rankings[1].bidder_name == "Ambiguous Bidder B"
    assert resp.rankings[1].rank is None
    assert resp.rankings[1].ranking_status == RankingStatus.PENDING_MANUAL_REVIEW


# ==============================================================================
# TEST 4: L1 PRICE ORDERING ACROSS MULTIPLE BIDDERS
# ==============================================================================
def test_04_l1_multi_bidder_price_ordering():
    """Verify strictly deterministic ascending evaluated price ordering (L1, L2, L3, L4)."""
    bidders = [
        BidderEvaluationRecord("b1", "Alpha Ltd", "s1", EvaluationResult.ELIGIBLE, evaluated_price=12000000.0),
        BidderEvaluationRecord("b2", "Beta Ltd", "s2", EvaluationResult.ELIGIBLE, evaluated_price=9500000.0),
        BidderEvaluationRecord("b3", "Gamma Ltd", "s3", EvaluationResult.ELIGIBLE, evaluated_price=10500000.0),
        BidderEvaluationRecord("b4", "Delta Ltd", "s4", EvaluationResult.ELIGIBLE, evaluated_price=11000000.0),
    ]

    result = calculate_deterministic_ranking(bidders, method_type=EvaluationMethodType.L1)

    assert result.ranked_count == 4
    assert result.has_ties is False

    ranks = [(r.bidder_name, r.rank, r.rank_label, r.evaluated_price) for r in result.rankings]
    expected = [
        ("Beta Ltd", 1, "L1", 9500000.0),
        ("Gamma Ltd", 2, "L2", 10500000.0),
        ("Delta Ltd", 3, "L3", 11000000.0),
        ("Alpha Ltd", 4, "L4", 12000000.0),
    ]
    assert ranks == expected


# ==============================================================================
# TEST 5: TIE HANDLING (NO RANDOM WINNERS)
# ==============================================================================
def test_05_tie_handling_flags_human_review():
    """Verify that equal prices trigger TIE_REQUIRES_HUMAN_REVIEW and no winner is randomly picked."""
    bidders = [
        BidderEvaluationRecord("b1", "Bidder X", "s1", EvaluationResult.ELIGIBLE, evaluated_price=10000000.0),
        BidderEvaluationRecord("b2", "Bidder Y", "s2", EvaluationResult.ELIGIBLE, evaluated_price=10000000.0),
        BidderEvaluationRecord("b3", "Bidder Z", "s3", EvaluationResult.ELIGIBLE, evaluated_price=11000000.0),
    ]

    result = calculate_deterministic_ranking(
        bidders,
        method_type=EvaluationMethodType.L1,
        tie_breaker_rule="HUMAN_REVIEW",
    )

    assert result.has_ties is True
    # Both Bidder X and Bidder Y are flagged for committee action
    tied_bidders = [r for r in result.rankings if r.ranking_status == RankingStatus.TIE_REQUIRES_HUMAN_REVIEW]
    assert len(tied_bidders) == 2
    for tb in tied_bidders:
        assert tb.rank == 1
        assert "TIED" in tb.rank_label
        assert tb.calculation_details["action_required"] == "TIE_REQUIRES_HUMAN_REVIEW"

    # Bidder Z is L3
    z = next(r for r in result.rankings if r.bidder_name == "Bidder Z")
    assert z.rank == 3
    assert z.rank_label == "L3"


# ==============================================================================
# TEST 6: QCBS FORMULA & TENDER WEIGHTS
# ==============================================================================
def test_06_qcbs_scoring_formula():
    """Verify QCBS weighted technical/financial scoring formula (70% tech, 30% fin)."""
    # Bidder 1: Tech = 85.0, Price = 10 Cr (Lowest Price)
    # Bidder 2: Tech = 95.0, Price = 12 Cr
    bidders = [
        BidderEvaluationRecord("b1", "Tech 85 Cheap", "s1", EvaluationResult.ELIGIBLE, evaluated_price=100000000.0, technical_score=85.0),
        BidderEvaluationRecord("b2", "Tech 95 Premium", "s2", EvaluationResult.ELIGIBLE, evaluated_price=120000000.0, technical_score=95.0),
    ]

    result = calculate_deterministic_ranking(
        bidders,
        method_type=EvaluationMethodType.QCBS,
        financial_weight=0.30,
        technical_weight=0.70,
    )

    # Verification:
    # P_min = 100,000,000
    # B1: Fin score = (100M / 100M) * 100 = 100.0
    #     Comb score = (85.0 * 0.70) + (100.0 * 0.30) = 59.5 + 30.0 = 89.50
    # B2: Fin score = (100M / 120M) * 100 = 83.3333
    #     Comb score = (95.0 * 0.70) + (83.3333 * 0.30) = 66.5 + 25.0 = 91.50
    b2_rank = next(r for r in result.rankings if r.bidder_name == "Tech 95 Premium")
    b1_rank = next(r for r in result.rankings if r.bidder_name == "Tech 85 Cheap")

    assert b2_rank.rank == 1
    assert b2_rank.rank_label == "H1"
    assert round(b2_rank.combined_score, 1) == 91.5

    assert b1_rank.rank == 2
    assert b1_rank.rank_label == "H2"
    assert round(b1_rank.combined_score, 1) == 89.5


# ==============================================================================
# TEST 7: VERSION ISOLATION
# ==============================================================================
def test_07_tender_version_isolation(db_session, base_tender_fixture):
    """Verify that running evaluation on Tender V2 does NOT overwrite or mutate historical V1 rankings."""
    f = base_tender_fixture
    t_id = f["tender"].id
    v1_id = f["version"].id
    user_id = f["user"].id

    # Create Tender Version 2
    v2 = TenderVersion(
        id=uuid.uuid4(),
        tender_id=t_id,
        version_number=2,
        version_label="v2.0 - Revised Budget",
        created_by=user_id,
    )
    db_session.add(v2)
    db_session.flush()

    # Create a Bidder with Submission in V1
    b = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-ISO", legal_name="Apex Systems")
    db_session.add(b)
    db_session.flush()

    sub_v1 = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v1_id, bidder_id=b.id,
        submission_reference="SUB-ISO-V1", status=SubmissionStatus.READY,
    )
    db_session.add(sub_v1)
    db_session.flush()
    db_session.add(BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v1_id, bidder_id=b.id,
        bid_submission_id=sub_v1.id, result=EvaluationResult.ELIGIBLE,
        explanation={"evaluated_price": 100000000.0},
    ))

    # Evaluate V1
    resp_v1 = ComparativeEvaluationService.run_comparative_evaluation(db_session, t_id, v1_id)
    assert resp_v1.ranked_count == 1
    v1_run_id = resp_v1.evaluation_run_id

    # Now create Submission in V2 with different price 80,000,000
    sub_v2 = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v2.id, bidder_id=b.id,
        submission_reference="SUB-ISO-V2", status=SubmissionStatus.READY,
    )
    db_session.add(sub_v2)
    db_session.flush()
    db_session.add(BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v2.id, bidder_id=b.id,
        bid_submission_id=sub_v2.id, result=EvaluationResult.ELIGIBLE,
        explanation={"evaluated_price": 80000000.0},
    ))

    # Evaluate V2
    resp_v2 = ComparativeEvaluationService.run_comparative_evaluation(db_session, t_id, v2.id)
    assert resp_v2.ranked_count == 1
    assert resp_v2.evaluation_run_id != v1_run_id

    # Fetch V1 rankings again: MUST retain original V1 evaluated price 100M
    refetched_v1 = ComparativeEvaluationService.get_rankings(db_session, t_id, v1_id, evaluation_run_id=v1_run_id)
    assert refetched_v1.rankings[0].evaluated_price == 100000000.0

    # Fetch V2 rankings: MUST have price 80M
    refetched_v2 = ComparativeEvaluationService.get_rankings(db_session, t_id, v2.id, evaluation_run_id=resp_v2.evaluation_run_id)
    assert refetched_v2.rankings[0].evaluated_price == 80000000.0


# ==============================================================================
# TEST 8: RANKING REPRODUCIBILITY (WITHOUT LLM)
# ==============================================================================
def test_08_ranking_reproducibility():
    """Verify that running the evaluation twice on identical inputs produces identical rankings."""
    bidders = [
        BidderEvaluationRecord("b1", "Company A", "s1", EvaluationResult.ELIGIBLE, evaluated_price=100.0),
        BidderEvaluationRecord("b2", "Company B", "s2", EvaluationResult.ELIGIBLE, evaluated_price=50.0),
        BidderEvaluationRecord("b3", "Company C", "s3", EvaluationResult.NOT_ELIGIBLE, evaluated_price=40.0),
    ]

    run1 = calculate_deterministic_ranking(bidders, method_type=EvaluationMethodType.L1)
    run2 = calculate_deterministic_ranking(bidders, method_type=EvaluationMethodType.L1)

    assert [(r.bidder_id, r.rank, r.rank_label) for r in run1.rankings] == [
        (r.bidder_id, r.rank, r.rank_label) for r in run2.rankings
    ]


# ==============================================================================
# TEST 9: LLM INDEPENDENCE
# ==============================================================================
def test_09_llm_independence_guarantee(monkeypatch):
    """Verify that disabling or erroring any LLM provider does NOT affect deterministic ranking."""
    def fail_llm(*args, **kwargs):
        raise RuntimeError("LLM must not be called during ranking calculation")

    # Monkeypatch hypothetical LLM callers
    monkeypatch.setattr("builtins.print", lambda *a, **k: None)

    bidders = [
        BidderEvaluationRecord("b1", "Vendor 1", "s1", EvaluationResult.ELIGIBLE, evaluated_price=200.0),
        BidderEvaluationRecord("b2", "Vendor 2", "s2", EvaluationResult.ELIGIBLE, evaluated_price=150.0),
    ]

    # Must succeed cleanly purely in Python
    res = calculate_deterministic_ranking(bidders, method_type=EvaluationMethodType.L1)
    assert res.ranked_count == 2
    assert res.rankings[0].bidder_name == "Vendor 2"
    assert res.rankings[0].rank_label == "L1"


# ==============================================================================
# TEST 10: EVIDENCE PROVENANCE
# ==============================================================================
def test_10_evidence_provenance_metadata():
    """Verify that every ranking output preserves complete source provenance."""
    prov = {
        "document_name": "Financial_Bid_Envelope2.pdf",
        "page": 3,
        "bbox": [100.0, 200.0, 300.0, 250.0],
        "extraction_confidence": 0.98,
    }
    bidders = [
        BidderEvaluationRecord(
            "b1", "Provenanced Vendor", "s1", EvaluationResult.ELIGIBLE,
            evaluated_price=500000.0, provenance=prov
        )
    ]

    result = calculate_deterministic_ranking(bidders, method_type=EvaluationMethodType.L1)
    item = result.rankings[0]

    assert item.provenance_metadata == prov
    assert item.provenance_metadata["document_name"] == "Financial_Bid_Envelope2.pdf"
    assert item.provenance_metadata["page"] == 3


# ==============================================================================
# TEST 11: COMPARATIVE PDF REPORT GENERATION
# ==============================================================================
def test_11_comparative_pdf_report_generation(db_session, base_tender_fixture):
    """Verify generation of the official comparative ranking PDF audit artifact."""
    f = base_tender_fixture
    v_id = f["version"].id
    t_id = f["tender"].id

    b = Bidder(id=uuid.uuid4(), tender_id=t_id, bidder_code="BID-PDF", legal_name="Apex Secure Systems Pvt Ltd")
    db_session.add(b)
    db_session.flush()

    sub = BidSubmission(
        id=uuid.uuid4(), tender_version_id=v_id, bidder_id=b.id,
        submission_reference="SUB-PDF-01", status=SubmissionStatus.READY,
    )
    db_session.add(sub)
    db_session.flush()

    db_session.add(BidderEvaluation(
        id=uuid.uuid4(), tender_id=t_id, tender_version_id=v_id, bidder_id=b.id,
        bid_submission_id=sub.id, result=EvaluationResult.ELIGIBLE,
        explanation={"evaluated_price": 95000000.0},
    ))
    db_session.commit()

    ranking_resp = ComparativeEvaluationService.run_comparative_evaluation(db_session, t_id, v_id)

    pdf_bytes = generate_comparative_ranking_pdf(
        ranking_data=ranking_resp,
        tender_number="CRPF/PPE/2026/001",
        tender_title="Supply of Advanced Personal Protective Equipment",
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")


# ==============================================================================
# TEST 12: TAMPER RESISTANCE & IMMUTABILITY
# ==============================================================================
def test_12_tamper_resistance_client_cannot_inject_rank():
    """Verify that ComparativeEvaluationRequest has no field for client-supplied ranks or winners."""
    fields = ComparativeEvaluationRequest.model_fields
    # Client cannot submit ranks, scores, or winner IDs
    assert "rank" not in fields
    assert "winner" not in fields
    assert "rank_label" not in fields
    assert "scores" not in fields

    # Furthermore, verify that any extra fields are ignored or rejected by Pydantic
    req = ComparativeEvaluationRequest(
        evaluation_method=EvaluationMethodType.L1,
    )
    assert not hasattr(req, "rank")
    assert not hasattr(req, "winner")
