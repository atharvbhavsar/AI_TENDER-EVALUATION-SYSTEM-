"""Unit tests for HealthResponse Pydantic schema."""

from app.schemas.health import HealthResponse


def test_health_response_default() -> None:
    """Verify default initialization of HealthResponse."""
    model = HealthResponse()
    assert model.status == "healthy"
    assert model.database == "healthy"
    assert model.model_dump() == {"status": "healthy", "database": "healthy"}


def test_health_response_custom() -> None:
    """Verify custom initialization of HealthResponse."""
    model = HealthResponse(status="degraded", database="unhealthy")
    assert model.status == "degraded"
    assert model.database == "unhealthy"
    assert model.model_dump() == {"status": "degraded", "database": "unhealthy"}
