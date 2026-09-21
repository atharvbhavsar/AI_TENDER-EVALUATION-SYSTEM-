"""Unit tests for Phase 10 retrieval Pydantic schemas."""

import uuid
import pytest
from pydantic import ValidationError
from app.retrieval.schemas import (
    CriterionSearchRequest,
    HybridSearchResultItem,
    IndexDocumentResponse,
    TextSearchRequest,
)


def test_criterion_search_request_valid():
    req = CriterionSearchRequest(
        criterion_id=uuid.uuid4(),
        top_k=15,
        lexical_weight=0.3,
        semantic_weight=0.7,
    )
    assert req.top_k == 15
    assert req.lexical_weight == 0.3
    assert req.semantic_weight == 0.7


def test_criterion_search_request_top_k_bounds():
    # Negative top_k
    with pytest.raises(ValidationError):
        CriterionSearchRequest(criterion_id=uuid.uuid4(), top_k=0)

    # Exceeding MAX_TOP_K (50)
    with pytest.raises(ValidationError):
        CriterionSearchRequest(criterion_id=uuid.uuid4(), top_k=51)


def test_text_search_request_validation():
    # Empty query string
    with pytest.raises(ValidationError):
        TextSearchRequest(query="")

    # Valid query string
    req = TextSearchRequest(query="ISO 9001 quality certificate")
    assert req.query == "ISO 9001 quality certificate"
    assert req.top_k == 10
