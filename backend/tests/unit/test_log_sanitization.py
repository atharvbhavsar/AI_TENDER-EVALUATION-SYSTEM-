"""Unit tests for SensitiveDataMaskingFilter in logging."""

import logging
from app.core.logging import SensitiveDataMaskingFilter, correlation_id_ctx


def test_sensitive_data_masking_filter_masks_passwords_and_tokens():
    """Verify password, token, and secret patterns are masked in log records."""
    log_filter = SensitiveDataMaskingFilter()
    correlation_id_ctx.set("test-req-999")

    # 1. Message with password
    record1 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="User login attempt with password=SuperSecretPassword123! from 127.0.0.1",
        args=(),
        exc_info=None,
    )
    assert log_filter.filter(record1) is True
    assert record1.correlation_id == "test-req-999"
    assert "SuperSecretPassword123!" not in record1.msg
    assert "***REDACTED***" in record1.msg

    # 2. Message with Bearer JWT token
    jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.doNotLeakThisSignature"
    record2 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=20,
        msg=f"Incoming authorization header Bearer {jwt_token}",
        args=(),
        exc_info=None,
    )
    assert log_filter.filter(record2) is True
    assert "doNotLeakThisSignature" not in record2.msg
    assert "***REDACTED***" in record2.msg

    # 3. Message with dict args containing secret keys
    record3 = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=30,
        msg="Database config: %(db_user)s %(jwt_secret_key)s",
        args={"db_user": "crpf", "jwt_secret_key": "supersecretkey"},
        exc_info=None,
    )
    assert log_filter.filter(record3) is True
    assert record3.args["jwt_secret_key"] == "***REDACTED***"
    assert record3.args["db_user"] == "crpf"
