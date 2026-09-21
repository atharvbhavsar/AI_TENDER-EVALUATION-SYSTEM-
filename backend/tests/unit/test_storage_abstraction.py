"""Unit tests for ObjectStorageService abstraction."""

import io
import pytest
from app.storage.service import InMemoryObjectStorageService


def test_in_memory_storage_lifecycle():
    storage = InMemoryObjectStorageService()
    key = "documents/test/sample.pdf"
    content = b"%PDF-1.4 mock content"

    # 1. Check initially does not exist
    assert storage.exists(key) is False

    # 2. Upload
    res_key = storage.upload(key=key, data=content, content_type="application/pdf")
    assert res_key == key
    assert storage.exists(key) is True

    # 3. Download
    stream = storage.download(key)
    downloaded = stream.read()
    assert downloaded == content

    # 4. Delete
    assert storage.delete(key) is True
    assert storage.exists(key) is False

    # 5. Download non-existent raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        storage.download(key)
