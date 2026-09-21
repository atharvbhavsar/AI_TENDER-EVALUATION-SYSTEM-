"""Pure deterministic mathematical ranking engine for multi-bidder tender evaluations.

CRITICAL ARCHITECTURAL CONSTRAINTS:
1. No LLMs are involved in ranking or score calculations. Ranking is 100% deterministic,
   auditable, and reproducible without external APIs.
2. Eligibility strictly precedes ranking: Ineligible bidders and unresolved manual-review
   bidders are NEVER ranked as winners or assigned L1/L2 ranks.
3. Ties are never resolved randomly. If no tender-defined tie breaker exists, the system
   flags TIE_REQUIRES_HUMAN_REVIEW.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.tender_evaluation_method import EvaluationMethodType, RankingDirection
from app.db.models.bidder_ranking import RankingStatus


@dataclass
class BidderEvaluationRecord:
    """Standardized input representation of an evaluated bidder for comparative ranking."""

    bidder_id: str
    bidder_name: str
    bid_submission_id: str
    eligibility_status: EvaluationResult
    quoted_price: Optional[float] = None
    evaluated_price: Optional[float] = None
    technical_score: Optional[float] = None
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CalculatedBidderRanking:
    """Deterministic output for a bidder's calculated standing."""

    bidder_id: str
    bidder_name: str
    bid_submission_id: str
    eligibility_status: EvaluationResult
    quoted_price: Optional[float]
    evaluated_price: Optional[float]
    technical_score: Optional[float]
    financial_score: Optional[float]
    combined_score: Optional[float]
    rank: Optional[int]
    rank_label: Optional[str]
    ranking_status: RankingStatus
    calculation_details: Dict[str, Any]
    provenance_metadata: Dict[str, Any]


@dataclass
class ComparativeRankingResult:
    """Complete comparative evaluation outcome."""

    method_type: EvaluationMethodType
    total_bidders: int
    eligible_count: int
    not_eligible_count: int
    manual_review_count: int
    ranked_count: int
    has_ties: bool
    rankings: List[CalculatedBidderRanking]


def calculate_deterministic_ranking(
    bidders: List[BidderEvaluationRecord],
    method_type: EvaluationMethodType = EvaluationMethodType.L1,
    financial_weight: Optional[float] = None,
    technical_weight: Optional[float] = None,
    minimum_technical_score: Optional[float] = None,
    tie_breaker_rule: Optional[str] = "HUMAN_REVIEW",
) -> ComparativeRankingResult:
    """
    Execute deterministic comparative ranking across multiple bidders.

    Steps:
    1. Segregate bidders by mandatory eligibility status.
    2. Exclude NOT_ELIGIBLE bidders (status: EXCLUDED_INELIGIBLE, rank: None).
    3. Hold MANUAL_REVIEW bidders (status: PENDING_MANUAL_REVIEW, rank: None).
    4. Pass ELIGIBLE bidders into the Qualified / Responsive Pool.
    5. Apply the tender's prescribed evaluation methodology (L1, QCBS, Technical Score).
    6. Check and handle ties deterministically.
    """
    total_bidders = len(bidders)
    eligible_count = sum(1 for b in bidders if b.eligibility_status == EvaluationResult.ELIGIBLE)
    not_eligible_count = sum(1 for b in bidders if b.eligibility_status == EvaluationResult.NOT_ELIGIBLE)
    manual_review_count = sum(1 for b in bidders if b.eligibility_status == EvaluationResult.MANUAL_REVIEW)

    rankings: List[CalculatedBidderRanking] = []
    qualified_pool: List[BidderEvaluationRecord] = []

    # Stage 1: Eligibility Gatekeeper
    for b in bidders:
        if b.eligibility_status == EvaluationResult.NOT_ELIGIBLE:
            rankings.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=b.technical_score,
                    financial_score=None,
                    combined_score=None,
                    rank=None,
                    rank_label=None,
                    ranking_status=RankingStatus.EXCLUDED_INELIGIBLE,
                    calculation_details={
                        "reason": "Disqualified at mandatory eligibility stage",
                        "eligible": False,
                    },
                    provenance_metadata=b.provenance,
                )
            )
        elif b.eligibility_status == EvaluationResult.MANUAL_REVIEW:
            rankings.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=b.technical_score,
                    financial_score=None,
                    combined_score=None,
                    rank=None,
                    rank_label=None,
                    ranking_status=RankingStatus.PENDING_MANUAL_REVIEW,
                    calculation_details={
                        "reason": "Held pending resolution of manual review criteria",
                        "eligible": False,
                        "pending_review": True,
                    },
                    provenance_metadata=b.provenance,
                )
            )
        else:
            qualified_pool.append(b)

    has_ties = False

    # Stage 2: Method-Specific Deterministic Ranking
    if method_type == EvaluationMethodType.L1:
        ranked_pool, ties_detected = _rank_l1(qualified_pool, tie_breaker_rule=tie_breaker_rule)
        rankings.extend(ranked_pool)
        has_ties = ties_detected

    elif method_type in (
        EvaluationMethodType.QCBS,
        EvaluationMethodType.WEIGHTED_TECHNICAL_FINANCIAL,
    ):
        ranked_pool, ties_detected = _rank_qcbs(
            qualified_pool,
            financial_weight=financial_weight or 0.30,
            technical_weight=technical_weight or 0.70,
            minimum_technical_score=minimum_technical_score,
            tie_breaker_rule=tie_breaker_rule,
        )
        rankings.extend(ranked_pool)
        has_ties = ties_detected

    elif method_type == EvaluationMethodType.TECHNICAL_SCORE:
        ranked_pool, ties_detected = _rank_technical_score(
            qualified_pool,
            minimum_technical_score=minimum_technical_score,
            tie_breaker_rule=tie_breaker_rule,
        )
        rankings.extend(ranked_pool)
        has_ties = ties_detected

    else:
        # Default / TENDER_DEFINED fallback to L1
        ranked_pool, ties_detected = _rank_l1(qualified_pool, tie_breaker_rule=tie_breaker_rule)
        rankings.extend(ranked_pool)
        has_ties = ties_detected

    # Sort final list: Ranked first by rank asc, then unranked by name
    rankings.sort(
        key=lambda r: (
            0 if r.rank is not None else 1,
            r.rank if r.rank is not None else 999999,
            r.bidder_name,
        )
    )

    ranked_count = sum(1 for r in rankings if r.rank is not None)

    return ComparativeRankingResult(
        method_type=method_type,
        total_bidders=total_bidders,
        eligible_count=eligible_count,
        not_eligible_count=not_eligible_count,
        manual_review_count=manual_review_count,
        ranked_count=ranked_count,
        has_ties=has_ties,
        rankings=rankings,
    )


def _rank_l1(
    pool: List[BidderEvaluationRecord],
    tie_breaker_rule: Optional[str] = "HUMAN_REVIEW",
) -> Tuple[List[CalculatedBidderRanking], bool]:
    """
    Execute deterministic L1 (Lowest Evaluated Responsive Price) ranking.

    Sorts by evaluated_price ascending:
    Lowest evaluated price = L1 (Rank 1)
    Second lowest = L2 (Rank 2)
    Third lowest = L3 (Rank 3)
    """
    valid_bidders: List[BidderEvaluationRecord] = []
    missing_price_bidders: List[CalculatedBidderRanking] = []

    for b in pool:
        if b.evaluated_price is None or b.evaluated_price <= 0:
            missing_price_bidders.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=b.technical_score,
                    financial_score=None,
                    combined_score=None,
                    rank=None,
                    rank_label=None,
                    ranking_status=RankingStatus.MISSING_FINANCIAL_BID,
                    calculation_details={"reason": "Missing evaluated price in submission"},
                    provenance_metadata=b.provenance,
                )
            )
        else:
            valid_bidders.append(b)

    # Sort valid bidders by evaluated_price ascending
    valid_bidders.sort(key=lambda x: x.evaluated_price)

    # Check for ties
    price_counts: Dict[float, int] = {}
    for b in valid_bidders:
        p = round(b.evaluated_price, 2)
        price_counts[p] = price_counts.get(p, 0) + 1

    has_ties = any(cnt > 1 for cnt in price_counts.values())

    results: List[CalculatedBidderRanking] = []
    current_rank = 1

    i = 0
    while i < len(valid_bidders):
        b = valid_bidders[i]
        p = round(b.evaluated_price, 2)
        count = price_counts[p]

        if count > 1 and tie_breaker_rule == "HUMAN_REVIEW":
            # Unresolved tie: Hold all tied bidders for human review
            for j in range(i, i + count):
                tied_b = valid_bidders[j]
                results.append(
                    CalculatedBidderRanking(
                        bidder_id=tied_b.bidder_id,
                        bidder_name=tied_b.bidder_name,
                        bid_submission_id=tied_b.bid_submission_id,
                        eligibility_status=tied_b.eligibility_status,
                        quoted_price=tied_b.quoted_price,
                        evaluated_price=tied_b.evaluated_price,
                        technical_score=tied_b.technical_score,
                        financial_score=None,
                        combined_score=None,
                        rank=current_rank,
                        rank_label=f"L{current_rank} (TIED)",
                        ranking_status=RankingStatus.TIE_REQUIRES_HUMAN_REVIEW,
                        calculation_details={
                            "method": "L1",
                            "evaluated_price": tied_b.evaluated_price,
                            "tie_detected": True,
                            "tied_with_count": count,
                            "action_required": "TIE_REQUIRES_HUMAN_REVIEW",
                        },
                        provenance_metadata=tied_b.provenance,
                    )
                )
            current_rank += count
            i += count
        else:
            label = f"L{current_rank}"
            results.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=b.technical_score,
                    financial_score=None,
                    combined_score=None,
                    rank=current_rank,
                    rank_label=label,
                    ranking_status=RankingStatus.QUALIFIED_RANKED,
                    calculation_details={
                        "method": "L1",
                        "evaluated_price": b.evaluated_price,
                        "rank": current_rank,
                        "label": label,
                    },
                    provenance_metadata=b.provenance,
                )
            )
            current_rank += 1
            i += 1

    results.extend(missing_price_bidders)
    return results, has_ties


def _rank_qcbs(
    pool: List[BidderEvaluationRecord],
    financial_weight: float,
    technical_weight: float,
    minimum_technical_score: Optional[float] = None,
    tie_breaker_rule: Optional[str] = "HUMAN_REVIEW",
) -> Tuple[List[CalculatedBidderRanking], bool]:
    """
    Execute deterministic Quality and Cost Based Selection (QCBS).

    Formulas:
    1. Financial Score: S_fin = (P_min / P_bidder) * 100
    2. Combined Score: S_combined = (S_tech * W_tech) + (S_fin * W_fin)
    3. Rank descending by S_combined.
    """
    valid_bidders: List[BidderEvaluationRecord] = []
    disqualified_bidders: List[CalculatedBidderRanking] = []

    for b in pool:
        # Check minimum technical score
        if minimum_technical_score is not None and (
            b.technical_score is None or b.technical_score < minimum_technical_score
        ):
            disqualified_bidders.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=b.technical_score,
                    financial_score=None,
                    combined_score=None,
                    rank=None,
                    rank_label=None,
                    ranking_status=RankingStatus.DISQUALIFIED_TECHNICAL,
                    calculation_details={
                        "reason": f"Technical score {b.technical_score} below minimum threshold {minimum_technical_score}",
                        "minimum_technical_score": minimum_technical_score,
                    },
                    provenance_metadata=b.provenance,
                )
            )
        elif b.evaluated_price is None or b.evaluated_price <= 0:
            disqualified_bidders.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=b.technical_score,
                    financial_score=None,
                    combined_score=None,
                    rank=None,
                    rank_label=None,
                    ranking_status=RankingStatus.MISSING_FINANCIAL_BID,
                    calculation_details={"reason": "Missing evaluated price for financial scoring"},
                    provenance_metadata=b.provenance,
                )
            )
        else:
            valid_bidders.append(b)

    if not valid_bidders:
        return disqualified_bidders, False

    # Find lowest evaluated price P_min
    p_min = min(b.evaluated_price for b in valid_bidders)

    scored_items: List[Dict[str, Any]] = []
    for b in valid_bidders:
        tech_score = b.technical_score if b.technical_score is not None else 0.0
        fin_score = (p_min / b.evaluated_price) * 100.0
        comb_score = round((tech_score * technical_weight) + (fin_score * financial_weight), 4)

        scored_items.append({
            "bidder": b,
            "tech_score": tech_score,
            "fin_score": round(fin_score, 4),
            "comb_score": comb_score,
        })

    # Sort descending by combined score
    scored_items.sort(key=lambda x: x["comb_score"], reverse=True)

    score_counts: Dict[float, int] = {}
    for item in scored_items:
        s = item["comb_score"]
        score_counts[s] = score_counts.get(s, 0) + 1

    has_ties = any(cnt > 1 for cnt in score_counts.values())

    results: List[CalculatedBidderRanking] = []
    current_rank = 1

    i = 0
    while i < len(scored_items):
        item = scored_items[i]
        b = item["bidder"]
        s = item["comb_score"]
        count = score_counts[s]

        if count > 1 and tie_breaker_rule == "HUMAN_REVIEW":
            for j in range(i, i + count):
                tied_item = scored_items[j]
                tb = tied_item["bidder"]
                results.append(
                    CalculatedBidderRanking(
                        bidder_id=tb.bidder_id,
                        bidder_name=tb.bidder_name,
                        bid_submission_id=tb.bid_submission_id,
                        eligibility_status=tb.eligibility_status,
                        quoted_price=tb.quoted_price,
                        evaluated_price=tb.evaluated_price,
                        technical_score=tied_item["tech_score"],
                        financial_score=tied_item["fin_score"],
                        combined_score=tied_item["comb_score"],
                        rank=current_rank,
                        rank_label=f"H{current_rank} (TIED)",
                        ranking_status=RankingStatus.TIE_REQUIRES_HUMAN_REVIEW,
                        calculation_details={
                            "method": "QCBS",
                            "p_min": p_min,
                            "evaluated_price": tb.evaluated_price,
                            "technical_score": tied_item["tech_score"],
                            "financial_score": tied_item["fin_score"],
                            "technical_weight": technical_weight,
                            "financial_weight": financial_weight,
                            "formula": "S_comb = (S_tech * W_tech) + (S_fin * W_fin)",
                            "tie_detected": True,
                        },
                        provenance_metadata=tb.provenance,
                    )
                )
            current_rank += count
            i += count
        else:
            label = f"H{current_rank}"
            results.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=item["tech_score"],
                    financial_score=item["fin_score"],
                    combined_score=item["comb_score"],
                    rank=current_rank,
                    rank_label=label,
                    ranking_status=RankingStatus.QUALIFIED_RANKED,
                    calculation_details={
                        "method": "QCBS",
                        "p_min": p_min,
                        "evaluated_price": b.evaluated_price,
                        "technical_score": item["tech_score"],
                        "financial_score": item["fin_score"],
                        "technical_weight": technical_weight,
                        "financial_weight": financial_weight,
                        "formula": "S_comb = (S_tech * W_tech) + (S_fin * W_fin)",
                    },
                    provenance_metadata=b.provenance,
                )
            )
            current_rank += 1
            i += 1

    results.extend(disqualified_bidders)
    return results, has_ties


def _rank_technical_score(
    pool: List[BidderEvaluationRecord],
    minimum_technical_score: Optional[float] = None,
    tie_breaker_rule: Optional[str] = "HUMAN_REVIEW",
) -> Tuple[List[CalculatedBidderRanking], bool]:
    """Execute deterministic ranking by technical score descending."""
    valid_bidders: List[BidderEvaluationRecord] = []
    disqualified_bidders: List[CalculatedBidderRanking] = []

    for b in pool:
        if minimum_technical_score is not None and (
            b.technical_score is None or b.technical_score < minimum_technical_score
        ):
            disqualified_bidders.append(
                CalculatedBidderRanking(
                    bidder_id=b.bidder_id,
                    bidder_name=b.bidder_name,
                    bid_submission_id=b.bid_submission_id,
                    eligibility_status=b.eligibility_status,
                    quoted_price=b.quoted_price,
                    evaluated_price=b.evaluated_price,
                    technical_score=b.technical_score,
                    financial_score=None,
                    combined_score=None,
                    rank=None,
                    rank_label=None,
                    ranking_status=RankingStatus.DISQUALIFIED_TECHNICAL,
                    calculation_details={"reason": f"Below minimum threshold {minimum_technical_score}"},
                    provenance_metadata=b.provenance,
                )
            )
        else:
            valid_bidders.append(b)

    valid_bidders.sort(key=lambda x: x.technical_score or 0.0, reverse=True)

    results: List[CalculatedBidderRanking] = []
    for idx, b in enumerate(valid_bidders, 1):
        label = f"T{idx}"
        results.append(
            CalculatedBidderRanking(
                bidder_id=b.bidder_id,
                bidder_name=b.bidder_name,
                bid_submission_id=b.bid_submission_id,
                eligibility_status=b.eligibility_status,
                quoted_price=b.quoted_price,
                evaluated_price=b.evaluated_price,
                technical_score=b.technical_score,
                financial_score=None,
                combined_score=b.technical_score,
                rank=idx,
                rank_label=label,
                ranking_status=RankingStatus.QUALIFIED_RANKED,
                calculation_details={"method": "TECHNICAL_SCORE", "score": b.technical_score},
                provenance_metadata=b.provenance,
            )
        )

    results.extend(disqualified_bidders)
    return results, False
