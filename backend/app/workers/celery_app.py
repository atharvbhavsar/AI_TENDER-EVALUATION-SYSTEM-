"""Celery application configuration and initialization for distributed document processing."""

import os
import sys
from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "tender_evaluation_workers",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

# Celery Configuration for robust, concurrent document processing
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Late ACKs ensure messages are redelivered if a worker terminates mid-task
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Worker prefetch 1 ensures fair work distribution across concurrent workers
    worker_prefetch_multiplier=1,
    task_default_queue="document_processing",
)

import logging
from celery.signals import worker_process_init

logger = logging.getLogger("app.workers.celery_app")


@worker_process_init.connect
def warm_up_ocr_models(**kwargs):
    """Pre-load OCR engine once per worker process at startup to avoid re-initializing weights per task."""
    try:
        from app.pipeline.ocr.engine import OCREngine
        OCREngine()
        logger.info("Worker process initialized and OCR models pre-warmed.")
    except Exception as exc:
        logger.warning("Worker OCR warm-up notice: %s", exc)


if __name__ == "__main__":
    celery_app.start()
