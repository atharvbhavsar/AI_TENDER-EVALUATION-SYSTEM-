"""Provenance and lineage reconstruction service for Phase 16."""

import logging
import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.schemas import (
    CriterionProvenanceDetail,
    DecisionProvenanceDetail,
    DocumentProvenanceDetail,
    EvidenceProvenanceDetail,
    SubmissionProvenanceResponse,
)
from app.db.models.audit_log import AuditLog
from app.db.models.bid_submission import BidSubmission
from app.db.models.bidder_evaluation import BidderEvaluation
from app.db.models.criterion_evaluation import CriterionEvaluation
from app.db.models.criterion_rule import CriterionRule
from app.db.models.document import Document
from app.db.models.evidence import Evidence
from app.db.models.review_case import OfficerDecision, ReviewCase
from app.db.models.tender_criterion import RequirementType, TenderCriterion

logger = logging.getLogger("app.audit.provenance")


class ProvenanceService:
    """Service to reconstruct complete audit lineages and document provenances."""

    @staticmethod
    def reconstruct_submission_provenance(
        db: Session,
        submission_id: uuid.UUID,
    ) -> SubmissionProvenanceResponse:
        """
        Reconstruct the full deterministic provenance and evaluation lineage
        for a specific bid submission from tender criteria down to officer decisions.
        """
        stmt = (
            select(BidSubmission)
            .where(BidSubmission.id == submission_id)
        )
        submission = db.execute(stmt).scalar_one_or_none()
        if not submission:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"BidSubmission '{submission_id}' not found.",
            )

        # 1. Fetch Tender & Version
        version = submission.tender_version
        tender = version.tender
        bidder = submission.bidder

        # 2. Fetch all Documents associated with this submission
        doc_stmt = select(Document).where(
            (Document.bid_submission_id == submission_id)
            | (Document.tender_version_id == version.id)
        )
        documents = db.execute(doc_stmt).scalars().all()
        doc_map = {doc.id: doc for doc in documents}

        doc_details = [
            DocumentProvenanceDetail(
                document_id=doc.id,
                filename=doc.filename,
                content_type=doc.content_type,
                file_size=doc.file_size,
                sha256_hash=doc.sha256_hash,
                storage_key=doc.storage_key,
                processing_status=doc.processing_status.value if hasattr(doc.processing_status, "value") else str(doc.processing_status),
                uploaded_by=doc.uploaded_by,
                uploaded_at=doc.created_at,
            )
            for doc in documents
        ]

        # 3. Fetch all criteria for this tender version
        criteria_stmt = (
            select(TenderCriterion)
            .where(TenderCriterion.tender_version_id == submission.tender_version_id)
            .order_by(TenderCriterion.created_at.asc())
        )
        criteria = db.execute(criteria_stmt).scalars().all()

        # 4. Fetch all evidence items for this submission
        evidence_stmt = select(Evidence).where(Evidence.bid_submission_id == submission_id)
        evidence_items = db.execute(evidence_stmt).scalars().all()

        # Group evidence by criterion_id
        evidence_by_crit: dict[uuid.UUID, List[Evidence]] = {}
        for ev in evidence_items:
            evidence_by_crit.setdefault(ev.criterion_id, []).append(ev)

        # 5. Fetch criterion evaluations for this submission
        eval_stmt = select(CriterionEvaluation).where(
            CriterionEvaluation.bid_submission_id == submission_id
        )
        evaluations = db.execute(eval_stmt).scalars().all()
        eval_by_crit = {e.criterion_id: e for e in evaluations}

        # 6. Fetch rules for criteria
        rules_stmt = select(CriterionRule).where(
            CriterionRule.criterion_id.in_([c.id for c in criteria])
        )
        rules = db.execute(rules_stmt).scalars().all() if criteria else []
        rule_by_crit = {r.criterion_id: r for r in rules}

        criteria_details: List[CriterionProvenanceDetail] = []
        for crit in criteria:
            rule = rule_by_crit.get(crit.id)
            crit_eval = eval_by_crit.get(crit.id)
            crit_evs = evidence_by_crit.get(crit.id, [])

            ev_details: List[EvidenceProvenanceDetail] = []
            for ev in crit_evs:
                ev_doc = doc_map.get(ev.document_id) if ev.document_id else None
                ev_details.append(
                    EvidenceProvenanceDetail(
                        evidence_id=ev.id,
                        criterion_id=ev.criterion_id,
                        document_id=ev.document_id,
                        document_filename=ev_doc.filename if ev_doc else None,
                        document_sha256=ev_doc.sha256_hash if ev_doc else None,
                        extracted_text=ev.extracted_text,
                        extracted_value=ev.extracted_value,
                        normalized_value=ev.normalized_value,
                        unit=ev.unit,
                        currency=ev.currency,
                        source_page=ev.source_page,
                        source_block_id=ev.source_block_id,
                        source_table_reference=ev.source_table_reference,
                        bbox=ev.bbox,
                        status=ev.status.value if hasattr(ev.status, "value") else str(ev.status),
                        confidence=ev.confidence,
                        extractor_version=ev.extractor_version,
                        created_at=ev.created_at,
                    )
                )

            is_mandatory = bool(crit.mandatory or (crit.requirement_type == RequirementType.MANDATORY))

            criteria_details.append(
                CriterionProvenanceDetail(
                    criterion_id=crit.id,
                    code=crit.criterion_code,
                    title=crit.name,
                    criterion_type=crit.category.value if hasattr(crit.category, "value") else str(crit.category),
                    is_mandatory=is_mandatory,
                    source_page=crit.source_page,
                    source_section=crit.source_section,
                    source_clause=crit.source_clause,
                    source_block_id=crit.source_block_id,
                    rule_version=rule.rule_version if rule else None,
                    policy_version=rule.rego_policy_reference if rule else None,
                    operator=crit.operator,
                    threshold_value=crit.threshold_value,
                    threshold_unit=crit.unit,
                    threshold_currency=crit.currency,
                    evaluation_result=crit_eval.result.value if crit_eval and hasattr(crit_eval.result, "value") else (str(crit_eval.result) if crit_eval else None),
                    evidence_items=ev_details,
                )
            )

        # 7. Fetch Human Decisions
        decisions_stmt = (
            select(OfficerDecision)
            .join(ReviewCase, OfficerDecision.review_case_id == ReviewCase.id)
            .where(ReviewCase.bid_submission_id == submission_id)
            .order_by(OfficerDecision.created_at.asc())
        )
        decisions = db.execute(decisions_stmt).scalars().all()

        decision_details = [
            DecisionProvenanceDetail(
                review_case_id=dec.review_case_id,
                decision=dec.decision.value if hasattr(dec.decision, "value") else str(dec.decision),
                system_result=dec.system_result.value if hasattr(dec.system_result, "value") else str(dec.system_result),
                final_verdict=dec.final_verdict.value if dec.final_verdict and hasattr(dec.final_verdict, "value") else (str(dec.final_verdict) if dec.final_verdict else None),
                reason=dec.reason,
                officer_id=dec.officer_id,
                officer_name=dec.officer.full_name if dec.officer else None,
                created_at=dec.created_at,
            )
            for dec in decisions
        ]

        # 8. Fetch overall evaluation if exists
        overall_eval_stmt = select(BidderEvaluation).where(
            BidderEvaluation.bid_submission_id == submission_id
        ).order_by(BidderEvaluation.created_at.desc())
        overall_eval = db.execute(overall_eval_stmt).scalars().first()

        # 9. Count audit events
        audit_count_stmt = select(func.count(AuditLog.id)).where(
            AuditLog.bid_submission_id == submission_id
        )
        audit_count = db.scalar(audit_count_stmt) or 0

        return SubmissionProvenanceResponse(
            submission_id=submission.id,
            submission_number=submission.submission_reference,
            tender_id=tender.id,
            tender_title=tender.title,
            tender_version_id=version.id,
            tender_version_number=version.version_number,
            bidder_id=bidder.id,
            bidder_name=bidder.legal_name,
            submission_status=submission.status.value if hasattr(submission.status, "value") else str(submission.status),
            submitted_at=submission.created_at,
            overall_evaluation_result=overall_eval.result.value if overall_eval and hasattr(overall_eval.result, "value") else (str(overall_eval.result) if overall_eval else None),
            documents=doc_details,
            criteria=criteria_details,
            human_decisions=decision_details,
            audit_events_count=audit_count,
        )

    @staticmethod
    def reconstruct_criterion_provenance(
        db: Session,
        criterion_id: uuid.UUID,
    ) -> CriterionProvenanceDetail:
        """Reconstruct the definition and rule provenance for a single criterion."""
        stmt = select(TenderCriterion).where(TenderCriterion.id == criterion_id)
        crit = db.execute(stmt).scalar_one_or_none()
        if not crit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TenderCriterion '{criterion_id}' not found.",
            )

        rule_stmt = select(CriterionRule).where(CriterionRule.criterion_id == criterion_id)
        rule = db.execute(rule_stmt).scalar_one_or_none()
        is_mandatory = bool(crit.mandatory or (crit.requirement_type == RequirementType.MANDATORY))

        return CriterionProvenanceDetail(
            criterion_id=crit.id,
            code=crit.criterion_code,
            title=crit.name,
            criterion_type=crit.category.value if hasattr(crit.category, "value") else str(crit.category),
            is_mandatory=is_mandatory,
            source_page=crit.source_page,
            source_section=crit.source_section,
            source_clause=crit.source_clause,
            source_block_id=crit.source_block_id,
            rule_version=rule.rule_version if rule else None,
            policy_version=rule.rego_policy_reference if rule else None,
            operator=crit.operator,
            threshold_value=crit.threshold_value,
            threshold_unit=crit.unit,
            threshold_currency=crit.currency,
            evaluation_result=None,
            evidence_items=[],
        )
