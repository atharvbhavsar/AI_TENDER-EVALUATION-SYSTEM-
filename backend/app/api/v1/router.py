"""API v1 router aggregator."""

from fastapi import APIRouter
from app.aggregation.api import router as aggregation_router
from app.approval.api import router as approval_router
from app.audit.api import router as audit_router
from app.auth.router import router as auth_router
from app.bidders.router import router as bidders_router
from app.documents.router import router as documents_router
from app.evidence.api import router as evidence_router
from app.extraction.api import router as extraction_router
from app.health.router import router as health_router
from app.pipeline.api import router as pipeline_router
from app.ranking.api import router as ranking_router
from app.reports.api import router as reports_router
from app.retrieval.api import router as retrieval_router
from app.reviews.api import router as reviews_router
from app.rules.api import router as rules_router
from app.tenders.router import router as tenders_router

v1_router = APIRouter()

# Include feature routers
v1_router.include_router(health_router)
v1_router.include_router(auth_router)
v1_router.include_router(bidders_router)
v1_router.include_router(tenders_router)
v1_router.include_router(documents_router)
v1_router.include_router(pipeline_router)
v1_router.include_router(extraction_router)
v1_router.include_router(approval_router)
v1_router.include_router(evidence_router)
v1_router.include_router(retrieval_router)
v1_router.include_router(rules_router)
v1_router.include_router(aggregation_router)
v1_router.include_router(reviews_router)
v1_router.include_router(ranking_router)
v1_router.include_router(audit_router)
v1_router.include_router(reports_router)

