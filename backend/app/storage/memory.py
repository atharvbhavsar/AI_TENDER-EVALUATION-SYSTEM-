"""In-memory object storage service implementation for testing and development."""

import io
from typing import BinaryIO, Dict
from app.storage.base import ObjectStorageService


class InMemoryObjectStorageService(ObjectStorageService):
    """In-memory object storage implementation."""

    def __init__(self) -> None:
        self._objects: Dict[str, bytes] = {}

    def upload(
        self,
        key: str,
        data: BinaryIO | bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        if isinstance(data, bytes):
            self._objects[key] = data
        else:
            self._objects[key] = data.read()
        return key

    def download(self, key: str) -> BinaryIO:
        if key not in self._objects:
            raise FileNotFoundError(f"Object '{key}' not found in storage")
        return io.BytesIO(self._objects[key])

    def delete(self, key: str) -> bool:
        self._objects.pop(key, None)
        return True

    def exists(self, key: str) -> bool:
        return key in self._objects

    def ensure_bucket_exists(self) -> None:
        pass
