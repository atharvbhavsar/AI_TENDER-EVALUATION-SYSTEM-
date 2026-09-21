"""Custom database column types supporting PostgreSQL and SQLite compatibility."""

import json
from typing import Any, List, Optional
from sqlalchemy import JSON, Text, TypeDecorator
from sqlalchemy.dialects import postgresql


class VectorType(TypeDecorator):
    """
    Platform-independent vector column type.
    Uses pgvector Vector in PostgreSQL and JSON-serialized array in SQLite/other engines.
    """

    impl = Text
    cache_ok = True

    def __init__(self, dim: int = 1024, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.dim = dim

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector
                return dialect.type_descriptor(Vector(self.dim))
            except ImportError:
                return dialect.type_descriptor(postgresql.ARRAY(postgresql.DOUBLE_PRECISION))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Optional[List[float]], dialect: Any) -> Any:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        if isinstance(value, list):
            return value
        return list(value)

    def process_result_value(self, value: Any, dialect: Any) -> Optional[List[float]]:
        if value is None:
            return None
        if isinstance(value, list):
            return [float(x) for x in value]
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return [float(x) for x in parsed]
            except Exception:
                pass
        return value


class TSVectorType(TypeDecorator):
    """
    Platform-independent tsvector column type.
    Uses postgresql.TSVECTOR in PostgreSQL and Text in SQLite/other engines.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(postgresql.TSVECTOR())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        return value

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        return value
