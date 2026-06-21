"""Users, roles, permissions and RBAC join tables."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import BaseEntity, GUID, PkMixin, TimestampMixin


class User(BaseEntity, Base):
    __tablename__ = "app_user"
    __table_args__ = (UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Optional linkage to a person record (student/employee)
    person_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    person_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)

    roles: Mapped[list["Role"]] = relationship(
        secondary="user_role", back_populates="users", lazy="selectin"
    )


class Role(BaseEntity, Base):
    __tablename__ = "role"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_role_tenant_code"),)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    users: Mapped[list[User]] = relationship(
        secondary="user_role", back_populates="roles", lazy="selectin"
    )
    permissions: Mapped[list["Permission"]] = relationship(
        secondary="role_permission", back_populates="roles", lazy="selectin"
    )


class Permission(PkMixin, TimestampMixin, Base):
    """A permission is ``<module_slug>:<action>`` (e.g. ``fees:create``)."""

    __tablename__ = "permission"
    __table_args__ = (UniqueConstraint("code", name="uq_permission_code"),)

    code: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    roles: Mapped[list[Role]] = relationship(
        secondary="role_permission", back_populates="permissions", lazy="selectin"
    )


class UserRole(PkMixin, Base):
    __tablename__ = "user_role"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("app_user.id", ondelete="CASCADE"))
    role_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("role.id", ondelete="CASCADE"))


class RolePermission(PkMixin, Base):
    __tablename__ = "role_permission"
    __table_args__ = (UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),)

    role_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("role.id", ondelete="CASCADE"))
    permission_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("permission.id", ondelete="CASCADE")
    )
