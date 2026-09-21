"""Object storage service abstraction interface."""

from abc import ABC, abstractmethod
from typing import BinaryIO


class ObjectStorageService(ABC):
    """Abstract base class for object storage operations."""

    @abstractmethod
    def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload an object to storage and return its storage key."""
        raise NotImplementedError

    @abstractmethod
    def download(self, key: str) -> BinaryIO:
        """Download an object stream from storage by key."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete an object from storage by key. Return True if successful or key does not exist."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Check whether an object exists in storage by key."""
        raise NotImplementedError

    @abstractmethod
    def ensure_bucket_exists(self) -> None:
        """Idempotently ensure that the target bucket exists in storage."""
        raise NotImplementedError
