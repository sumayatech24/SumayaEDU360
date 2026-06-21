"""Reusable column mixins shared by every domain model.

Every business table carries:
  * a surrogate ``id``
  * a ``tenant_id`` for multi-tenant isolation
  * ``status`` for lifecycle (active/inactive/archived)
  * immutable audit columns (created/updated by + at)
  * soft-delete (``is_deleted`` / ``deleted_at``)
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    """Platform-independent UUID type (PostgreSQL native, CHAR(36) elsewhere)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class PkMixin:
    id: Mapped[uuid.UUID] = mapped_column(GUID(), primary_key=True, default=_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AuditMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class SoftDeleteMixin:
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenantMixin:
    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)


class BaseEntity(PkMixin, TenantMixin, TimestampMixin, AuditMixin, SoftDeleteMixin):
    """Convenience base combining every mixin for tenant-scoped business tables."""
