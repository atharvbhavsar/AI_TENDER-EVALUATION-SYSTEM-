"""Object storage dependency and factory provider."""

from functools import lru_cache
from app.core.config import get_settings
from app.storage.base import ObjectStorageService
from app.storage.memory import InMemoryObjectStorageService
from app.storage.s3 import S3ObjectStorageService

_storage_service_override: ObjectStorageService | None = None


@lru_cache()
def _build_default_storage_service() -> ObjectStorageService:
    """Build default S3ObjectStorageService configured from environment settings."""
    settings = get_settings()
    service = S3ObjectStorageService(
        endpoint_url=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY,
        bucket_name=settings.S3_BUCKET,
        region_name=settings.S3_REGION,
        use_ssl=settings.S3_USE_SSL,
    )
    return service


def get_storage_service() -> ObjectStorageService:
    """Dependency provider returning current active ObjectStorageService instance."""
    if _storage_service_override is not None:
        return _storage_service_override
    return _build_default_storage_service()


def set_storage_service_override(service: ObjectStorageService | None) -> None:
    """Set an override storage service instance (used for testing / mocks)."""
    global _storage_service_override
    _storage_service_override = service
