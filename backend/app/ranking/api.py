"""FastAPI REST routes for Multi-Bidder Tender Evaluation and Deterministic Ranking."""

import logging
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_active_user, require_permissions
from app.db.models.user import User
from app.db.session import get_db
from app.ranking.schemas import (
    BidderRankingItem,
    ComparativeEvaluationRequest,
    ComparativeEvaluationResponse,
    TenderEvaluationMethodCreate,
    TenderEvaluationMethodResponse,
)
from app.ranking.service import ComparativeEvaluationService

logger = logging.getLogger("app.ranking.api")

router = APIRouter(tags=["Multi-Bidder Evaluation & Deterministic Ranking"])


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/evaluation-method",
    response_model=TenderEvaluationMethodResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active tender evaluation methodology",
)
def get_evaluation_method_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_READ")),
):
    """Retrieve the prescribed evaluation and ranking method for a tender version."""
    method_obj = ComparativeEvaluationService.get_or_create_evaluation_method(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
    )
    return method_obj


@router.post(
    "/tenders/{tender_id}/versions/{version_id}/evaluation-method",
    response_model=TenderEvaluationMethodResponse,
    status_code=status.HTTP_200_OK,
    summary="Configure tender evaluation methodology",
)
def set_evaluation_method_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: TenderEvaluationMethodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("TENDER_UPDATE")),
):
    """Configure or update the deterministic evaluation method (L1, QCBS, weights)."""
    return ComparativeEvaluationService.set_evaluation_method(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        payload=payload,
        actor_id=current_user.id,
        actor_role="PROCUREMENT_OFFICER",
    )


@router.post(
    "/tenders/{tender_id}/versions/{version_id}/comparative-evaluation",
    response_model=ComparativeEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute deterministic comparative evaluation across all bidders",
)
def run_comparative_evaluation_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: Optional[ComparativeEvaluationRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """
    Execute deterministic comparative ranking across all submitted bidders.

    CRITICAL RULES:
    1. Mandatory eligibility strictly precedes ranking: Ineligible bidders are excluded.
    2. Ranks are computed 100% deterministically by the backend. Client cannot inject ranks.
    3. LLMs are NOT permitted to pick winners or rank bidders.
    """
    return ComparativeEvaluationService.run_comparative_evaluation(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        actor_id=current_user.id,
        actor_role="PROCUREMENT_OFFICER",
        request=payload,
    )


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/rankings",
    response_model=ComparativeEvaluationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest comparative ranking results",
)
def get_rankings_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    run_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """Fetch comparative ranking results for a tender version."""
    return ComparativeEvaluationService.get_rankings(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        evaluation_run_id=run_id,
    )


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/rankings/{bidder_id}",
    response_model=BidderRankingItem,
    status_code=status.HTTP_200_OK,
    summary="Get ranking standing for an individual bidder",
)
def get_bidder_ranking_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    bidder_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """Fetch the comparative ranking standing and calculation details for a specific bidder."""
    item = ComparativeEvaluationService.get_bidder_ranking(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        bidder_id=bidder_id,
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ranking for bidder {bidder_id} in tender version {version_id} not found.",
        )
    return item


@router.get(
    "/tenders/{tender_id}/versions/{version_id}/comparative-report/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download official comparative ranking PDF report",
)
def download_comparative_report_pdf_endpoint(
    tender_id: uuid.UUID,
    version_id: uuid.UUID,
    run_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permissions("EVALUATION_READ")),
):
    """Generate and stream the official CRPF comparative evaluation PDF report."""
    from fastapi.responses import Response
    from app.reports.comparative_pdf_generator import generate_comparative_ranking_pdf

    ranking_data = ComparativeEvaluationService.get_rankings(
        db=db,
        tender_id=tender_id,
        tender_version_id=version_id,
        evaluation_run_id=run_id,
    )

    pdf_bytes = generate_comparative_ranking_pdf(ranking_data=ranking_data)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="comparative_ranking_{version_id}.pdf"',
            "Content-Type": "application/pdf",
        },
    )

