"""Health, liveness, and readiness probes."""

import httpx
from fastapi import APIRouter, Response, status

from app.core.config import get_settings
from app.db.session import check_db_connectivity
from app.schemas.health import HealthResponse, LivenessResponse, ReadinessResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Liveness Probe",
    description="Returns HTTP 200 indicating the application process is running and able to handle requests.",
)
async def get_liveness() -> LivenessResponse:
    """Fast liveness check."""
    return LivenessResponse(status="alive")


def check_redis_connectivity() -> bool:
    """Check whether Redis broker is reachable."""
    settings = get_settings()
    try:
        import redis
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2.0)
        return bool(client.ping())
    except Exception:
        return False


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Dependency Readiness Probe",
    description="Checks critical backend dependencies (PostgreSQL, Object Storage, OPA, Redis). Returns 503 if not ready.",
)
async def get_readiness(response: Response) -> ReadinessResponse:
    """Verify backend database, object storage, OPA, and Redis readiness."""
    settings = get_settings()
    components = {}
    is_ready = True

    # 1. Database Check
    db_ok = check_db_connectivity()
    components["database"] = {"status": "connected" if db_ok else "unreachable"}
    if not db_ok:
        is_ready = False

    # 2. Storage Check
    try:
        from app.storage.service import get_storage_service
        storage = get_storage_service()
        # In-memory storage is always ready, MinIO/S3 checks bucket
        storage.ensure_bucket_exists()
        components["storage"] = {"status": "ready"}
    except Exception as exc:
        components["storage"] = {"status": "unreachable", "error": str(exc)}
        # In non-production tests or mock storage, avoid failing if storage is disabled
        if settings.ENVIRONMENT == "production":
            is_ready = False

    # 3. OPA Check (if enabled)
    if settings.OPA_ENABLED and settings.OPA_URL:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{settings.OPA_URL}/health")
                if res.status_code == 200:
                    components["opa"] = {"status": "ready"}
                else:
                    components["opa"] = {"status": "degraded", "code": res.status_code}
        except Exception:
            components["opa"] = {"status": "unreachable"}
            # OPA degraded does not hard-fail development/test runs

    # 4. Redis Queue Check
    redis_ok = check_redis_connectivity()
    components["redis"] = {"status": "ready" if redis_ok else "unreachable"}
    if settings.ENVIRONMENT == "production" and not redis_ok:
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", components=components)

    return ReadinessResponse(status="ready", components=components)


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="General Health Check",
    description="Backward-compatible health status endpoint checking database and Redis.",
)
async def get_health() -> HealthResponse:
    """Return health status of application, database, and redis."""
    db_ok = check_db_connectivity()
    redis_ok = check_redis_connectivity()
    all_healthy = db_ok and redis_ok
    return HealthResponse(
        status="healthy" if all_healthy else "degraded",
        database="healthy" if db_ok else "unhealthy",
        redis="healthy" if redis_ok else "unhealthy",
    )

