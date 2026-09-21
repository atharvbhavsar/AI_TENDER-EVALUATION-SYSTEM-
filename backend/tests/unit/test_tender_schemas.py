"""Unit tests for Tender and TenderVersion Pydantic schemas."""

import datetime
import uuid
import pytest
from pydantic import ValidationError

from app.db.models.tender import TenderStatus
from app.tenders.schemas import (
    TenderCreate,
    TenderResponse,
    TenderUpdate,
    TenderVersionCreate,
    TenderVersionResponse,
)


def test_tender_create_schema_valid() -> None:
    """Verify valid TenderCreate instantiation."""
    data = TenderCreate(
        tender_number="CRPF/PROC/2026/001",
        title="Supply of Specialized Vehicles",
        description="Procurement of high-mobility vehicles",
        issuing_authority="Central Reserve Police Force",
    )
    assert data.tender_number == "CRPF/PROC/2026/001"
    assert data.title == "Supply of Specialized Vehicles"
    assert data.initial_version_label == "Initial Release"


def test_tender_create_schema_missing_required() -> None:
    """Verify missing required fields raise validation errors."""
    with pytest.raises(ValidationError):
        TenderCreate(tender_number="CRPF/001")  # missing title


def test_tender_update_schema() -> None:
    """Verify partial TenderUpdate fields."""
    update_data = TenderUpdate(
        title="Updated Title",
        status=TenderStatus.PUBLISHED,
    )
    assert update_data.title == "Updated Title"
    assert update_data.status == TenderStatus.PUBLISHED
    assert update_data.description is None


def test_tender_version_create_schema() -> None:
    """Verify TenderVersionCreate default and custom values."""
    version_data = TenderVersionCreate(
        version_label="Corrigendum 01",
        change_summary="Extension of submission deadline",
    )
    assert version_data.version_label == "Corrigendum 01"
    assert version_data.change_summary == "Extension of submission deadline"


def test_tender_response_serialization() -> None:
    """Verify TenderResponse serialization."""
    tender_id = uuid.uuid4()
    version_id = uuid.uuid4()
    user_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)

    active_v = TenderVersionResponse(
        id=version_id,
        tender_id=tender_id,
        version_number=1,
        version_label="Initial Release",
        effective_at=now,
        change_summary="Original Specification",
        is_active=True,
        created_by=user_id,
        created_at=now,
    )

    response = TenderResponse(
        id=tender_id,
        tender_number="CRPF/2026/001",
        title="Tender Title",
        description="Tender Description",
        issuing_authority="Central Reserve Police Force",
        status=TenderStatus.DRAFT,
        created_by=user_id,
        created_at=now,
        updated_at=now,
        active_version=active_v,
    )

    assert response.id == tender_id
    assert response.active_version is not None
    assert response.active_version.version_number == 1
