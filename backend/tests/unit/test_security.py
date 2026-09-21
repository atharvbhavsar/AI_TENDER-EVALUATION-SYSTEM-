"""Unit tests for password hashing and security functions."""

from app.auth.security import (
    hash_password,
    normalize_email,
    validate_password_policy,
    verify_password,
)


def test_password_hashing_and_verification() -> None:
    """Verify that Argon2id hashes passwords and correctly verifies valid passwords."""
    raw_password = "SuperSecretPassword123!"
    pwd_hash = hash_password(raw_password)

    # Hash should not equal plaintext
    assert pwd_hash != raw_password
    assert pwd_hash.startswith("$argon2id$")

    # Correct password verifies
    assert verify_password(raw_password, pwd_hash) is True

    # Incorrect password fails
    assert verify_password("WrongPassword123!", pwd_hash) is False

    # Password hash cannot be used as plaintext password
    assert verify_password(pwd_hash, pwd_hash) is False


def test_password_policy_validation() -> None:
    """Verify password policy checks."""
    assert validate_password_policy("12345678") is True
    assert validate_password_policy("short") is False
    assert validate_password_policy("") is False


def test_email_normalization() -> None:
    """Verify email normalization to lowercase and stripped spaces."""
    assert normalize_email("  User@Example.COM  ") == "user@example.com"
    assert normalize_email("OFFICER@CRPF.GOV.IN") == "officer@crpf.gov.in"
