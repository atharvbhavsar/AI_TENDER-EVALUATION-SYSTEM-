"""ComparativeEvaluationService orchestrating multi-bidder tender evaluation and deterministic ranking."""

import datetime
import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import select, and_, desc
from sqlalchemy.orm import Session
from app.audit.service import AuditService
from app.db.models.bid_submission import BidSubmission
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import EvaluationResult
from app.db.models.tender_evaluation_method import (
    EvaluationMethodType,
    RankingDirection,
    TenderEvaluationMethod,
)
from app.db.models.bidder_ranking import BidderRanking, RankingStatus
from app.db.models.tender_version import TenderVersion
from app.ranking.engine import (
    BidderEvaluationRecord,
    calculate_deterministic_ranking,
)
from app.ranking.schemas import (
    BidderRankingItem,
    ComparativeEvaluationRequest,
    ComparativeEvaluationResponse,
    TenderEvaluationMethodCreate,
    TenderEvaluationMethodResponse,
)

logger = logging.getLogger(__name__)


class ComparativeEvaluationService:
    """Service for managing tender evaluation methodologies and executing deterministic rankings."""

    @staticmethod
    def get_or_create_evaluation_method(
        db: Session,
        tender_id: uuid.UUID,
        tender_version_id: uuid.UUID,
    ) -> TenderEvaluationMethod:
        """Fetch the active TenderEvaluationMethod, or initialize the default L1 configuration."""
        stmt = (
            select(TenderEvaluationMethod)
            .where(TenderEvaluationMethod.tender_version_id == tender_version_id)
            .order_by(desc(TenderEvaluationMethod.created_at))
        )
        existing = db.execute(stmt).scalars().first()
        if existing:
            return existing

        # Default to L1 (Lowest Evaluated Price) as prescribed in CRPF tender documents
        default_method = TenderEvaluationMethod(
            id=uuid.uuid4(),
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            method_type=EvaluationMethodType.L1,
            description="L1 Lowest Evaluated Price methodology as defined in Tender Document Clause 12.4",
            financial_weight=None,
            technical_weight=None,
            minimum_technical_score=None,
            ranking_direction=RankingDirection.ASCENDING,
            currency="INR",
            tie_breaker_rule="HUMAN_REVIEW",
            version="v1.0",
        )
        db.add(default_method)
        db.flush()
        return default_method

    @staticmethod
    def set_evaluation_method(
        db: Session,
        tender_id: uuid.UUID,
        tender_version_id: uuid.UUID,
        payload: TenderEvaluationMethodCreate,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[str] = None,
    ) -> TenderEvaluationMethod:
        """Create or update the tender evaluation method configuration."""
        stmt = select(TenderEvaluationMethod).where(
            TenderEvaluationMethod.tender_version_id == tender_version_id
        )
        existing = db.execute(stmt).scalars().first()

        if existing:
            existing.method_type = payload.method_type
            existing.description = payload.description
            existing.financial_weight = payload.financial_weight
            existing.technical_weight = payload.technical_weight
            existing.minimum_technical_score = payload.minimum_technical_score
            existing.ranking_direction = payload.ranking_direction
            existing.currency = payload.currency
            existing.tie_breaker_rule = payload.tie_breaker_rule
            db.flush()
            method_obj = existing
        else:
            method_obj = TenderEvaluationMethod(
                id=uuid.uuid4(),
                tender_id=tender_id,
                tender_version_id=tender_version_id,
                method_type=payload.method_type,
                description=payload.description,
                financial_weight=payload.financial_weight,
                technical_weight=payload.technical_weight,
                minimum_technical_score=payload.minimum_technical_score,
                ranking_direction=payload.ranking_direction,
                currency=payload.currency,
                tie_breaker_rule=payload.tie_breaker_rule,
                version="v1.0",
            )
            db.add(method_obj)
            db.flush()

        AuditService.record(
            db,
            action="SET_TENDER_EVALUATION_METHOD",
            entity_type="TENDER_EVALUATION_METHOD",
            entity_id=str(method_obj.id),
            actor_id=actor_id,
            actor_role=actor_role,
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            new_state={
                "method_type": str(method_obj.method_type),
                "financial_weight": method_obj.financial_weight,
                "technical_weight": method_obj.technical_weight,
            },
        )
        db.commit()
        return method_obj

    @classmethod
    def run_comparative_evaluation(
        cls,
        db: Session,
        tender_id: uuid.UUID,
        tender_version_id: uuid.UUID,
        actor_id: Optional[uuid.UUID] = None,
        actor_role: Optional[str] = None,
        request: Optional[ComparativeEvaluationRequest] = None,
    ) -> ComparativeEvaluationResponse:
        """
        Execute deterministic comparative ranking across all submitted bidders.

        Enforces:
        1. Eligibility first: Bidders failing mandatory criteria are excluded.
        2. LLM independence: Ranks and scores are strictly calculated via deterministic Python.
        3. Audit trail: Generates immutable BidderRanking records tied to evaluation_run_id.
        """
        eval_method_obj = cls.get_or_create_evaluation_method(db, tender_id, tender_version_id)
        method_type = (
            request.evaluation_method
            if (request and request.evaluation_method)
            else eval_method_obj.method_type
        )
        fin_weight = (
            request.financial_weight
            if (request and request.financial_weight is not None)
            else eval_method_obj.financial_weight
        )
        tech_weight = (
            request.technical_weight
            if (request and request.technical_weight is not None)
            else eval_method_obj.technical_weight
        )
        tie_rule = (
            request.tie_breaker_rule
            if (request and request.tie_breaker_rule)
            else eval_method_obj.tie_breaker_rule
        )

        evaluation_run_id = uuid.uuid4()
        evaluation_date = datetime.datetime.now(datetime.timezone.utc)

        # 1. Fetch all submissions for this tender version
        sub_stmt = (
            select(BidSubmission)
            .where(BidSubmission.tender_version_id == tender_version_id)
            .order_by(BidSubmission.created_at.asc())
        )
        submissions = db.execute(sub_stmt).scalars().all()

        bidder_records: List[BidderEvaluationRecord] = []

        for sub in submissions:
            bidder = db.get(Bidder, sub.bidder_id)
            bidder_name = bidder.legal_name if bidder else f"Bidder {str(sub.bidder_id)[:8]}"

            # 2. Get latest BidderEvaluation for eligibility status
            eval_stmt = (
                select(BidderEvaluation)
                .where(
                    and_(
                        BidderEvaluation.bid_submission_id == sub.id,
                        BidderEvaluation.tender_version_id == tender_version_id,
                    )
                )
                .order_by(desc(BidderEvaluation.created_at))
            )
            bidder_eval = db.execute(eval_stmt).scalars().first()

            eligibility_status = (
                bidder_eval.result if bidder_eval else EvaluationResult.MANUAL_REVIEW
            )

            # 3. Extract financial & technical inputs
            sub_data = getattr(sub, "submission_data", None)
            if not isinstance(sub_data, dict):
                sub_data = {}

            eval_expl = (bidder_eval.explanation or {}) if bidder_eval else {}

            quoted_price = sub_data.get("quoted_price") or eval_expl.get("quoted_price")
            evaluated_price = (
                sub_data.get("evaluated_price")
                or eval_expl.get("evaluated_price")
                or quoted_price
            )
            technical_score = sub_data.get("technical_score") or eval_expl.get("technical_score")

            provenance = {
                "submission_id": str(sub.id),
                "bidder_id": str(sub.bidder_id),
                "financial_bid_source": sub_data.get("financial_bid_source") or eval_expl.get("financial_bid_source", "Envelope-II / Proforma FB-01"),
                "technical_score_source": sub_data.get("technical_score_source") or eval_expl.get("technical_score_source", "Technical Evaluation"),
            }

            bidder_records.append(
                BidderEvaluationRecord(
                    bidder_id=str(sub.bidder_id),
                    bidder_name=bidder_name,
                    bid_submission_id=str(sub.id),
                    eligibility_status=eligibility_status,
                    quoted_price=float(quoted_price) if quoted_price is not None else None,
                    evaluated_price=float(evaluated_price) if evaluated_price is not None else None,
                    technical_score=float(technical_score) if technical_score is not None else None,
                    provenance=provenance,
                )
            )

        # 4. Deterministic Ranking Engine calculation (Pure Math, No LLM)
        calc_result = calculate_deterministic_ranking(
            bidders=bidder_records,
            method_type=method_type,
            financial_weight=fin_weight,
            technical_weight=tech_weight,
            minimum_technical_score=eval_method_obj.minimum_technical_score,
            tie_breaker_rule=tie_rule,
        )

        # 5. Persist immutable BidderRanking records
        persisted_items: List[BidderRankingItem] = []
        for calc in calc_result.rankings:
            ranking_db = BidderRanking(
                id=uuid.uuid4(),
                tender_id=tender_id,
                tender_version_id=tender_version_id,
                evaluation_run_id=evaluation_run_id,
                bidder_id=uuid.UUID(calc.bidder_id),
                bid_submission_id=uuid.UUID(calc.bid_submission_id),
                evaluation_method=str(method_type.value if hasattr(method_type, "value") else method_type),
                eligibility_status=calc.eligibility_status,
                quoted_price=calc.quoted_price,
                evaluated_price=calc.evaluated_price,
                technical_score=calc.technical_score,
                financial_score=calc.financial_score,
                combined_score=calc.combined_score,
                rank=calc.rank,
                rank_label=calc.rank_label,
                ranking_status=calc.ranking_status,
                calculation_details=calc.calculation_details,
                provenance_metadata=calc.provenance_metadata,
            )
            db.add(ranking_db)
            persisted_items.append(
                BidderRankingItem(
                    id=ranking_db.id,
                    bidder_id=ranking_db.bidder_id,
                    bidder_name=calc.bidder_name,
                    bid_submission_id=ranking_db.bid_submission_id,
                    eligibility_status=ranking_db.eligibility_status,
                    quoted_price=ranking_db.quoted_price,
                    evaluated_price=ranking_db.evaluated_price,
                    technical_score=ranking_db.technical_score,
                    financial_score=ranking_db.financial_score,
                    combined_score=ranking_db.combined_score,
                    rank=ranking_db.rank,
                    rank_label=ranking_db.rank_label,
                    ranking_status=ranking_db.ranking_status,
                    calculation_details=ranking_db.calculation_details,
                    provenance_metadata=ranking_db.provenance_metadata,
                )
            )

        # 6. Audit Trail Event
        audit_entry = AuditService.record(
            db,
            action="MULTI_BIDDER_RANKING_COMPLETED",
            entity_type="TENDER_VERSION",
            entity_id=str(tender_version_id),
            actor_id=actor_id,
            actor_role=actor_role,
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            new_state={
                "evaluation_run_id": str(evaluation_run_id),
                "evaluation_method": str(method_type),
                "total_bidders": calc_result.total_bidders,
                "ranked_count": calc_result.ranked_count,
                "has_ties": calc_result.has_ties,
            },
        )
        db.commit()

        return ComparativeEvaluationResponse(
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            evaluation_run_id=evaluation_run_id,
            evaluation_method=method_type,
            method_description=eval_method_obj.description,
            evaluation_date=evaluation_date,
            total_bidders=calc_result.total_bidders,
            eligible_count=calc_result.eligible_count,
            not_eligible_count=calc_result.not_eligible_count,
            manual_review_count=calc_result.manual_review_count,
            ranked_count=calc_result.ranked_count,
            has_ties=calc_result.has_ties,
            rankings=persisted_items,
            audit_event_id=audit_entry.id if audit_entry else None,
        )

    @classmethod
    def get_rankings(
        cls,
        db: Session,
        tender_id: uuid.UUID,
        tender_version_id: uuid.UUID,
        evaluation_run_id: Optional[uuid.UUID] = None,
    ) -> ComparativeEvaluationResponse:
        """Fetch comparative rankings for a given tender version."""
        eval_method_obj = cls.get_or_create_evaluation_method(db, tender_id, tender_version_id)

        # Get latest evaluation_run_id if not specified
        if not evaluation_run_id:
            run_stmt = (
                select(BidderRanking.evaluation_run_id)
                .where(BidderRanking.tender_version_id == tender_version_id)
                .order_by(desc(BidderRanking.created_at))
                .limit(1)
            )
            evaluation_run_id = db.execute(run_stmt).scalar_one_or_none()

        if not evaluation_run_id:
            # No rankings generated yet
            return ComparativeEvaluationResponse(
                tender_id=tender_id,
                tender_version_id=tender_version_id,
                evaluation_run_id=uuid.uuid4(),
                evaluation_method=eval_method_obj.method_type,
                method_description=eval_method_obj.description,
                evaluation_date=datetime.datetime.now(datetime.timezone.utc),
                total_bidders=0,
                eligible_count=0,
                not_eligible_count=0,
                manual_review_count=0,
                ranked_count=0,
                has_ties=False,
                rankings=[],
            )

        stmt = (
            select(BidderRanking)
            .where(
                and_(
                    BidderRanking.tender_version_id == tender_version_id,
                    BidderRanking.evaluation_run_id == evaluation_run_id,
                )
            )
            .order_by(
                BidderRanking.rank.asc().nullslast(),
                BidderRanking.created_at.asc(),
            )
        )
        rows = db.execute(stmt).scalars().all()

        items: List[BidderRankingItem] = []
        has_ties = False
        eligible_count = 0
        not_eligible_count = 0
        manual_review_count = 0
        ranked_count = 0

        for r in rows:
            bidder = db.get(Bidder, r.bidder_id)
            bidder_name = bidder.legal_name if bidder else f"Bidder {str(r.bidder_id)[:8]}"

            if r.eligibility_status == EvaluationResult.ELIGIBLE:
                eligible_count += 1
            elif r.eligibility_status == EvaluationResult.NOT_ELIGIBLE:
                not_eligible_count += 1
            else:
                manual_review_count += 1

            if r.rank is not None:
                ranked_count += 1

            if r.ranking_status == RankingStatus.TIE_REQUIRES_HUMAN_REVIEW:
                has_ties = True

            items.append(
                BidderRankingItem(
                    id=r.id,
                    bidder_id=r.bidder_id,
                    bidder_name=bidder_name,
                    bid_submission_id=r.bid_submission_id,
                    eligibility_status=r.eligibility_status,
                    quoted_price=r.quoted_price,
                    evaluated_price=r.evaluated_price,
                    technical_score=r.technical_score,
                    financial_score=r.financial_score,
                    combined_score=r.combined_score,
                    rank=r.rank,
                    rank_label=r.rank_label,
                    ranking_status=r.ranking_status,
                    calculation_details=r.calculation_details,
                    provenance_metadata=r.provenance_metadata,
                )
            )

        return ComparativeEvaluationResponse(
            tender_id=tender_id,
            tender_version_id=tender_version_id,
            evaluation_run_id=evaluation_run_id,
            evaluation_method=eval_method_obj.method_type,
            method_description=eval_method_obj.description,
            evaluation_date=rows[0].created_at if rows else datetime.datetime.now(datetime.timezone.utc),
            total_bidders=len(rows),
            eligible_count=eligible_count,
            not_eligible_count=not_eligible_count,
            manual_review_count=manual_review_count,
            ranked_count=ranked_count,
            has_ties=has_ties,
            rankings=items,
        )

    @classmethod
    def get_bidder_ranking(
        cls,
        db: Session,
        tender_id: uuid.UUID,
        tender_version_id: uuid.UUID,
        bidder_id: uuid.UUID,
    ) -> Optional[BidderRankingItem]:
        """Fetch the latest ranking item for a specific bidder."""
        stmt = (
            select(BidderRanking)
            .where(
                and_(
                    BidderRanking.tender_version_id == tender_version_id,
                    BidderRanking.bidder_id == bidder_id,
                )
            )
            .order_by(desc(BidderRanking.created_at))
        )
        row = db.execute(stmt).scalars().first()
        if not row:
            return None

        bidder = db.get(Bidder, row.bidder_id)
        bidder_name = bidder.legal_name if bidder else f"Bidder {str(row.bidder_id)[:8]}"

        return BidderRankingItem(
            id=row.id,
            bidder_id=row.bidder_id,
            bidder_name=bidder_name,
            bid_submission_id=row.bid_submission_id,
            eligibility_status=row.eligibility_status,
            quoted_price=row.quoted_price,
            evaluated_price=row.evaluated_price,
            technical_score=row.technical_score,
            financial_score=row.financial_score,
            combined_score=row.combined_score,
            rank=row.rank,
            rank_label=row.rank_label,
            ranking_status=row.ranking_status,
            calculation_details=row.calculation_details,
            provenance_metadata=row.provenance_metadata,
        )
