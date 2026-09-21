"""Integration tests for User, Role, and Permission models and constraints."""

import uuid
import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.service import create_user
from app.db.models.permission import Permission
from app.db.models.role import Role
from app.db.models.user import User


def test_user_creation_and_relationships(db_session: Session) -> None:
    """Verify user persistence, password hashing, and role associations."""
    user = create_user(
        db=db_session,
        email="test_model@crpf.gov.in",
        password="MySecretPassword123!",
        full_name="Test Officer",
        role_names=["PROCUREMENT_OFFICER"],
    )
    assert user.id is not None
    assert user.email == "test_model@crpf.gov.in"
    assert user.password_hash != "MySecretPassword123!"
    assert len(user.roles) == 1
    assert user.roles[0].name == "PROCUREMENT_OFFICER"
    assert "TENDER_READ" in user.permissions


def test_unique_email_constraint(db_session: Session) -> None:
    """Verify that creating two users with the same email raises IntegrityError."""
    create_user(
        db=db_session,
        email="duplicate@crpf.gov.in",
        password="Password123!",
        full_name="User One",
    )

    with pytest.raises(IntegrityError):
        create_user(
            db=db_session,
            email="duplicate@crpf.gov.in",
            password="Password456!",
            full_name="User Two",
        )


def test_unique_role_name_constraint(db_session: Session) -> None:
    """Verify unique role name constraint."""
    role1 = Role(name="CUSTOM_ROLE", description="Custom")
    role2 = Role(name="CUSTOM_ROLE", description="Duplicate")
    db_session.add(role1)
    db_session.commit()

    db_session.add(role2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_permission_name_constraint(db_session: Session) -> None:
    """Verify unique permission name constraint."""
    perm1 = Permission(name="CUSTOM_PERM", description="Custom Perm 1")
    perm2 = Permission(name="CUSTOM_PERM", description="Custom Perm 2")
    db_session.add(perm1)
    db_session.commit()

    db_session.add(perm2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
