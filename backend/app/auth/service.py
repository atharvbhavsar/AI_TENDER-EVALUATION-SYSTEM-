"""Authentication and authorization services."""

import datetime
import logging
import uuid
from typing import Dict, List, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password, normalize_email, verify_password
from app.db.models.permission import Permission
from app.db.models.role import Role
from app.db.models.user import User

logger = logging.getLogger("app.auth.service")

# Standard initial permissions defined for the procurement platform
INITIAL_PERMISSIONS: Dict[str, str] = {
    "USER_READ": "View user accounts and profiles",
    "USER_MANAGE": "Create, update, and manage user accounts and role assignments",
    "TENDER_READ": "View tender details, criteria, and versions",
    "TENDER_CREATE": "Create new tender records and drafts",
    "TENDER_UPDATE": "Edit tender specifications and upload amendments",
    "TENDER_APPROVE": "Officer approval for extracted tender criteria and rules",
    "BIDDER_READ": "View bidder submissions and company profiles",
    "BIDDER_MANAGE": "Register and manage bidder entities",
    "DOCUMENT_READ": "View and access uploaded procurement documents",
    "DOCUMENT_UPLOAD": "Upload tender and bidder documents for processing",
    "EVIDENCE_READ": "View extracted evidence records and source citations",
    "EVALUATION_READ": "View deterministic rule evaluation results and logs",
    "REVIEW_CREATE": "Create human review notes and recommendations",
    "REVIEW_APPROVE": "Final officer sign-off and review approval",
    "REPORT_READ": "Access and generate consolidated evaluation reports",
}

# Initial role mappings
ROLE_PERMISSIONS_MAPPING: Dict[str, List[str]] = {
    "ADMIN": list(INITIAL_PERMISSIONS.keys()),
    "PROCUREMENT_OFFICER": [
        "USER_READ",
        "TENDER_READ",
        "TENDER_CREATE",
        "TENDER_UPDATE",
        "TENDER_APPROVE",
        "BIDDER_READ",
        "DOCUMENT_READ",
        "DOCUMENT_UPLOAD",
        "EVIDENCE_READ",
        "EVALUATION_READ",
        "REVIEW_CREATE",
        "REVIEW_APPROVE",
        "REPORT_READ",
    ],
    "REVIEWER": [
        "TENDER_READ",
        "BIDDER_READ",
        "DOCUMENT_READ",
        "EVIDENCE_READ",
        "EVALUATION_READ",
        "REVIEW_CREATE",
        "REPORT_READ",
    ],
    "BIDDER": [
        "TENDER_READ",
        "DOCUMENT_READ",
        "BIDDER_READ",
    ],
}


def seed_roles_and_permissions(db: Session) -> Dict[str, int]:
    """Idempotently seed predefined roles, permissions, and their associations."""
    permissions_created = 0
    roles_created = 0

    # 1. Seed Permissions
    permission_objs: Dict[str, Permission] = {}
    for name, desc in INITIAL_PERMISSIONS.items():
        stmt = select(Permission).where(Permission.name == name)
        perm = db.execute(stmt).scalar_one_or_none()
        if not perm:
            perm = Permission(name=name, description=desc)
            db.add(perm)
            permissions_created += 1
        permission_objs[name] = perm

    db.flush()

    # 2. Seed Roles and Associate Permissions
    for role_name, perm_names in ROLE_PERMISSIONS_MAPPING.items():
        stmt = select(Role).where(Role.name == role_name)
        role = db.execute(stmt).scalar_one_or_none()
        if not role:
            role = Role(name=role_name, description=f"{role_name.replace('_', ' ').title()} Role")
            db.add(role)
            roles_created += 1

        # Associate required permissions
        current_perms = {p.name for p in role.permissions}
        for p_name in perm_names:
            if p_name not in current_perms and p_name in permission_objs:
                role.permissions.append(permission_objs[p_name])

    db.commit()
    logger.info(
        "Seeded RBAC: %d new permissions, %d new roles initialized",
        permissions_created,
        roles_created,
    )
    return {"permissions_created": permissions_created, "roles_created": roles_created}


def get_user_by_email(db: Session, email: str) -> User | None:
    """Retrieve a user by normalized email address."""
    normalized = normalize_email(email)
    stmt = select(User).where(User.email == normalized)
    return db.execute(stmt).scalar_one_or_none()


def get_user_by_id(db: Session, user_id: uuid.UUID) -> User | None:
    """Retrieve a user by unique UUID."""
    stmt = select(User).where(User.id == user_id)
    return db.execute(stmt).scalar_one_or_none()


def create_user(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    role_names: Sequence[str] | None = None,
    company_name: str | None = None,
    phone: str | None = None,
    is_active: bool = True,
) -> User:
    """Create a new user account with hashed password and role associations."""
    normalized = normalize_email(email)
    pwd_hash = hash_password(password)

    user = User(
        email=normalized,
        password_hash=pwd_hash,
        full_name=full_name.strip(),
        company_name=company_name.strip() if company_name else None,
        phone=phone.strip() if phone else None,
        is_active=is_active,
    )

    if role_names:
        stmt = select(Role).where(Role.name.in_(role_names))
        roles = db.execute(stmt).scalars().all()
        user.roles.extend(roles)

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception:
        db.rollback()
        raise


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    """Validate credentials and return user if active."""
    user = get_user_by_email(db, email)
    if not user:
        return None

    if not verify_password(password, user.password_hash):
        return None

    if not user.is_active:
        return None

    # Update last login timestamp
    try:
        user.last_login_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
    except Exception as exc:
        logger.warning("Failed to update last_login_at for user %s: %s", user.id, str(exc))
        db.rollback()

    return user
