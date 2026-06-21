"""Tenant / institution / campus — the organizational hierarchy."""
from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import (
    AuditMixin,
    GUID,
    PkMixin,
    SoftDeleteMixin,
    TimestampMixin,
)


class Tenant(PkMixin, TimestampMixin, AuditMixin, SoftDeleteMixin, Base):
    """Top-level customer (an institution group / SaaS tenant)."""

    __tablename__ = "tenant"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    plan: Mapped[str] = mapped_column(String(50), default="enterprise", nullable=False)
    settings_json: Mapped[dict | None] = mapped_column(type_=__import__("sqlalchemy").JSON, nullable=True)


class Institution(PkMixin, TimestampMixin, AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "institution"

    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("tenant.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(50), default="school", nullable=False)  # school/college/coaching
    board: Mapped[str | None] = mapped_column(String(50), nullable=True)  # CBSE/ICSE/IB/...
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class Campus(PkMixin, TimestampMixin, AuditMixin, SoftDeleteMixin, Base):
    __tablename__ = "campus"

    tenant_id: Mapped[uuid.UUID] = mapped_column(GUID(), index=True)
    institution_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("institution.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
