"""User model for authentication and authorization."""

import datetime
import uuid
from typing import TYPE_CHECKING, List, Set
from sqlalchemy import Boolean, DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.role import Role


class User(Base):
    """User account entity."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin",
    )

    @property
    def permissions(self) -> Set[str]:
        """Aggregate all distinct permission names granted by assigned roles."""
        perms: Set[str] = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.name)
        return perms

    def has_permission(self, permission_name: str) -> bool:
        """Check if user has a specific permission."""
        return permission_name in self.permissions

    def has_any_permission(self, *permission_names: str) -> bool:
        """Check if user has at least one of the specified permissions."""
        user_perms = self.permissions
        return any(perm in user_perms for perm in permission_names)

    def has_all_permissions(self, *permission_names: str) -> bool:
        """Check if user has all specified permissions."""
        user_perms = self.permissions
        return all(perm in user_perms for perm in permission_names)

    def __repr__(self) -> str:
        return f"<User(email='{self.email}', is_active={self.is_active})>"
