"""Deterministic Explainability and Lineage Service for Phase 14."""

import logging
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import Select, select
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.db.models.bid_submission import BidSubmission
from app.db.models.bidder import Bidder
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation, EvaluationResult
from app.db.models.criterion_rule import CriterionRule
from app.db.models.document import Document
from app.db.models.evidence import Evidence, EvidenceStatus
from app.db.models.review_case import HumanDecision, OfficerDecision, ReviewCase
from app.db.models.tender import Tender
from app.db.models.tender_criterion import TenderCriterion
from app.db.models.tender_version import TenderVersion
from app.reports.schemas import (
    BidderExplanationResponse,
    CriterionExplanationResponse,
    EvidenceProvenanceItem,
)

logger = logging.getLogger(__name__)


class ExplanationService:
    """Provides deterministic, factual criterion and bidder-level explanations based strictly on stored DB provenance."""

    @staticmethod
    def get_criterion_explanation(
        db: Session,
        criterion_evaluation_id: uuid.UUID,
    ) -> CriterionExplanationResponse:
        """
        Build a comprehensive, deterministic explanation for an individual criterion evaluation,
        answering all 20 provenance and decision points.
        """
        ce = db.get(CriterionEvaluation, criterion_evaluation_id)
        if not ce:
            raise NotFoundException(f"Criterion evaluation '{criterion_evaluation_id}' not found")

        criterion = db.get(TenderCriterion, ce.criterion_id)
        if not criterion:
            raise NotFoundException(f"Associated criterion '{ce.criterion_id}' not found")

        rule = db.get(CriterionRule, ce.rule_id) if ce.rule_id else None

        # Gather all evidence items for this submission and criterion
        ev_query: Select = select(Evidence).where(
            Evidence.bid_submission_id == ce.bid_submission_id,
            Evidence.criterion_id == ce.criterion_id,
        )
        evidence_records = list(db.scalars(ev_query).all())

        # If primary evidence_ids was specifically set on CE and not in list, fetch it
        primary_ev_id = None
        if getattr(ce, "evidence_ids", None) and len(ce.evidence_ids) > 0:
            try:
                primary_ev_id = uuid.UUID(str(ce.evidence_ids[0]))
            except Exception:
                pass
        
        primary_ev = db.get(Evidence, primary_ev_id) if primary_ev_id else (evidence_records[0] if evidence_records else None)
        if primary_ev and primary_ev not in evidence_records:
            evidence_records.insert(0, primary_ev)

        # Build evidence provenance items
        evidence_items: List[EvidenceProvenanceItem] = []
        for ev in evidence_records:
            doc = db.get(Document, ev.document_id) if ev.document_id else None
            evidence_items.append(
                EvidenceProvenanceItem(
                    evidence_id=ev.id,
                    document_id=ev.document_id,
                    document_name=getattr(doc, "filename", getattr(doc, "name", None)) if doc else None,
                    document_hash=getattr(doc, "sha256_hash", getattr(doc, "file_hash", None)) if doc else None,
                    page_number=ev.source_page,
                    block_id=getattr(ev, "source_block_id", None) or (str(ev.raw_extracted_data.get("block_id")) if ev.raw_extracted_data and isinstance(ev.raw_extracted_data, dict) else None),
                    table_reference=getattr(ev, "source_table_reference", None) or (str(ev.raw_extracted_data.get("table_reference")) if ev.raw_extracted_data and isinstance(ev.raw_extracted_data, dict) else None),
                    bbox=ev.bbox,
                    extracted_value=ev.extracted_value or (ev.raw_extracted_data.get("extracted_value") if ev.raw_extracted_data and isinstance(ev.raw_extracted_data, dict) else None),
                    normalized_value=ev.normalized_value or (ev.raw_extracted_data.get("normalized_value") if ev.raw_extracted_data and isinstance(ev.raw_extracted_data, dict) else None),
                    evidence_status=ev.status.value if hasattr(ev.status, "value") else str(ev.status),
                    confidence_score=getattr(ev, "confidence", getattr(ev, "confidence_score", 1.0)),
                    source_clause_quote=getattr(ev, "extracted_text", getattr(ev, "source_text", None)),
                )
            )

        # Primary evidence metadata
        primary_doc = db.get(Document, primary_ev.document_id) if primary_ev and primary_ev.document_id else None

        # Check for Human Review Cases & Officer Decisions
        rc_query: Select = select(ReviewCase).where(
            ReviewCase.bid_submission_id == ce.bid_submission_id,
            (ReviewCase.criterion_evaluation_id == ce.id) | (ReviewCase.criterion_id == ce.criterion_id),
        )
        review_case = db.scalars(rc_query).first()

        human_review_required = ce.result == EvaluationResult.MANUAL_REVIEW or (review_case is not None)
        human_decision: Optional[HumanDecision] = None
        is_overridden = False
        override_reason: Optional[str] = None
        officer_id: Optional[uuid.UUID] = None
        final_criterion_decision = ce.result

        if review_case and review_case.decisions:
            latest_decision: OfficerDecision = review_case.decisions[0]
            human_decision = latest_decision.decision
            officer_id = latest_decision.officer_id
            if latest_decision.decision == HumanDecision.OVERRIDE:
                is_overridden = True
                override_reason = latest_decision.reason
                final_criterion_decision = latest_decision.final_verdict or ce.result
            elif latest_decision.decision == HumanDecision.CONFIRM:
                final_criterion_decision = latest_decision.final_verdict or ce.result

        # Source clause text from source references
        source_clause = criterion.description
        if criterion.source_references:
            ref = criterion.source_references[0]
            source_clause = getattr(ref, "source_text", getattr(ref, "source_text_snippet", None)) or criterion.description

        return CriterionExplanationResponse(
            criterion_evaluation_id=ce.id,
            criterion_id=criterion.id,
            requirement_name=getattr(criterion, "name", getattr(criterion, "title", "Requirement")),
            category=criterion.category.value if hasattr(criterion.category, "value") else str(criterion.category),

            requirement_type=criterion.requirement_type.value if hasattr(criterion.requirement_type, "value") else str(criterion.requirement_type),
            source_clause=source_clause,
            rule_id=rule.id if rule else None,
            rule_type=rule.rule_type.value if (rule and hasattr(rule.rule_type, "value")) else (str(rule.rule_type) if rule else None),
            rule_version=getattr(rule, "rule_version", getattr(rule, "version", "v1.0")) if rule else None,
            rule_config=getattr(rule, "configuration", getattr(rule, "rule_config", {})) if rule else {},

            evidence_items=evidence_items,
            primary_document_id=primary_doc.id if primary_doc else None,
            primary_document_name=getattr(primary_doc, "filename", getattr(primary_doc, "name", None)) if primary_doc else None,
            primary_document_hash=getattr(primary_doc, "sha256_hash", getattr(primary_doc, "file_hash", None)) if primary_doc else None,
            primary_page_number=primary_ev.source_page if primary_ev else None,

            primary_bbox=primary_ev.bbox if primary_ev else None,
            extracted_value=primary_ev.extracted_value if primary_ev else None,
            normalized_value=primary_ev.normalized_value if primary_ev else None,
            evidence_status=primary_ev.status.value if (primary_ev and hasattr(primary_ev.status, "value")) else (str(primary_ev.status) if primary_ev else "MISSING"),
            extraction_confidence=getattr(primary_ev, "confidence", getattr(primary_ev, "confidence_score", None)) if primary_ev else None,
            rule_evaluation_details=getattr(ce, "explanation", getattr(ce, "evaluation_details", {})) or {},
            automated_result=ce.result,
            human_review_required=human_review_required,
            review_case_id=review_case.id if review_case else None,
            human_decision=human_decision,
            is_overridden=is_overridden,
            override_reason=override_reason,
            officer_id=officer_id,
            final_criterion_decision=final_criterion_decision,
        )

    @staticmethod
    def get_bidder_explanation(
        db: Session,
        submission_id: uuid.UUID,
    ) -> BidderExplanationResponse:
        """
        Build consolidated bidder-level explanation comparing automated overall results
        with human officer decisions, structured criterion breakdowns, and evidence health metrics.
        """
        submission = db.get(BidSubmission, submission_id)
        if not submission:
            raise NotFoundException(f"Bid submission '{submission_id}' not found")

        bidder = db.get(Bidder, submission.bidder_id)
        if not bidder:
            raise NotFoundException(f"Associated bidder '{submission.bidder_id}' not found")

        tender_version = db.get(TenderVersion, submission.tender_version_id)
        if not tender_version:
            raise NotFoundException(f"Associated tender version '{submission.tender_version_id}' not found")

        tender = db.get(Tender, tender_version.tender_id)
        if not tender:
            raise NotFoundException(f"Associated tender '{tender_version.tender_id}' not found")

        # Fetch latest BidderEvaluation
        be_query: Select = (
            select(BidderEvaluation)
            .where(BidderEvaluation.bid_submission_id == submission_id)
            .order_by(BidderEvaluation.created_at.desc())
        )
        overall_eval = db.scalars(be_query).first()

        # Fetch all criterion evaluations for this submission
        ce_query: Select = select(CriterionEvaluation).where(
            CriterionEvaluation.bid_submission_id == submission_id
        )
        ce_records = list(db.scalars(ce_query).all())

        # Build individual explanations
        criteria_explanations: List[CriterionExplanationResponse] = []
        for ce in ce_records:
            criteria_explanations.append(ExplanationService.get_criterion_explanation(db, ce.id))

        # Fetch evidence items to calculate health metrics
        ev_query: Select = select(Evidence).where(Evidence.bid_submission_id == submission_id)
        all_evidence = list(db.scalars(ev_query).all())

        missing_count = sum(1 for e in all_evidence if e.status == EvidenceStatus.MISSING)
        conflicting_count = sum(1 for e in all_evidence if e.status == EvidenceStatus.CONFLICTING)
        unreadable_count = sum(1 for e in all_evidence if e.status == EvidenceStatus.UNREADABLE)
        ambiguous_count = sum(1 for e in all_evidence if e.status == EvidenceStatus.AMBIGUOUS)
        invalid_count = sum(1 for e in all_evidence if e.status == EvidenceStatus.INVALID)

        # Fetch review cases for this submission
        rc_query: Select = select(ReviewCase).where(ReviewCase.bid_submission_id == submission_id)
        review_cases = list(db.scalars(rc_query).all())
        review_summaries = []
        for rc in review_cases:
            review_summaries.append({
                "id": str(rc.id),
                "title": rc.title,
                "status": rc.status.value,
                "priority": rc.priority.value,
                "issue_type": rc.issue_type.value,
                "decision_count": len(rc.decisions),
                "latest_decision": rc.decisions[0].decision.value if rc.decisions else None,
            })

        # Calculate counts
        total_criteria = len(criteria_explanations)
        mandatory_criteria_count = sum(1 for c in criteria_explanations if c.requirement_type == "MANDATORY")
        optional_criteria_count = total_criteria - mandatory_criteria_count

        eligible_count = sum(1 for c in criteria_explanations if c.automated_result == EvaluationResult.ELIGIBLE)
        not_eligible_count = sum(1 for c in criteria_explanations if c.automated_result == EvaluationResult.NOT_ELIGIBLE)
        manual_review_count = sum(1 for c in criteria_explanations if c.automated_result == EvaluationResult.MANUAL_REVIEW)

        mandatory_eligible_count = sum(
            1 for c in criteria_explanations if c.requirement_type == "MANDATORY" and c.automated_result == EvaluationResult.ELIGIBLE
        )
        mandatory_not_eligible_count = sum(
            1 for c in criteria_explanations if c.requirement_type == "MANDATORY" and c.automated_result == EvaluationResult.NOT_ELIGIBLE
        )
        mandatory_manual_review_count = sum(
            1 for c in criteria_explanations if c.requirement_type == "MANDATORY" and c.automated_result == EvaluationResult.MANUAL_REVIEW
        )

        automated_overall_result = overall_eval.result if overall_eval else (
            EvaluationResult.NOT_ELIGIBLE if mandatory_not_eligible_count > 0 else (
                EvaluationResult.MANUAL_REVIEW if (mandatory_manual_review_count > 0 or manual_review_count > 0) else EvaluationResult.ELIGIBLE
            )
        )

        # Check overall human decision
        human_overall_decision: Optional[HumanDecision] = None
        has_override = any(c.is_overridden for c in criteria_explanations)
        all_confirmed = all(c.human_decision == HumanDecision.CONFIRM for c in criteria_explanations if c.human_review_required)

        if has_override:
            human_overall_decision = HumanDecision.OVERRIDE
        elif all_confirmed and any(c.human_decision == HumanDecision.CONFIRM for c in criteria_explanations):
            human_overall_decision = HumanDecision.CONFIRM

        # Determine final decision state (derived from final criterion decisions)
        final_mandatory_failures = sum(
            1 for c in criteria_explanations if c.requirement_type == "MANDATORY" and c.final_criterion_decision == EvaluationResult.NOT_ELIGIBLE
        )
        final_manual_reviews = sum(
            1 for c in criteria_explanations if c.final_criterion_decision == EvaluationResult.MANUAL_REVIEW
        )

        final_decision_state = (
            EvaluationResult.NOT_ELIGIBLE if final_mandatory_failures > 0 else (
                EvaluationResult.MANUAL_REVIEW if final_manual_reviews > 0 else EvaluationResult.ELIGIBLE
            )
        )

        return BidderExplanationResponse(
            tender_id=tender.id,
            tender_number=tender.tender_number,
            tender_title=tender.title,
            tender_version_id=tender_version.id,
            tender_version_number=tender_version.version_number,
            bidder_id=bidder.id,
            bidder_name=getattr(bidder, "legal_name", getattr(bidder, "name", str(bidder.id))),
            bid_submission_id=submission.id,

            evaluation_run_id=overall_eval.evaluation_run_id if overall_eval else None,
            overall_evaluation_id=overall_eval.id if overall_eval else None,
            total_criteria=total_criteria,
            mandatory_criteria_count=mandatory_criteria_count,
            optional_criteria_count=optional_criteria_count,
            eligible_count=eligible_count,
            not_eligible_count=not_eligible_count,
            manual_review_count=manual_review_count,
            mandatory_eligible_count=mandatory_eligible_count,
            mandatory_not_eligible_count=mandatory_not_eligible_count,
            mandatory_manual_review_count=mandatory_manual_review_count,
            missing_evidence_count=missing_count,
            conflicting_evidence_count=conflicting_count,
            unreadable_evidence_count=unreadable_count,
            ambiguous_evidence_count=ambiguous_count,
            invalid_evidence_count=invalid_count,
            automated_overall_result=automated_overall_result,
            human_overall_decision=human_overall_decision,
            final_decision_state=final_decision_state,
            criteria_explanations=criteria_explanations,
            review_cases_summary=review_summaries,
        )
