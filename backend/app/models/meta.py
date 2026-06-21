"""Metadata engine — makes the whole ERP configurable from the database.

These tables describe the *application itself*: which modules exist, what masters
and entities they contain, what fields each entity has, what menu items to render,
and free-form settings. The generic CRUD API and the React client read this metadata
so new modules/masters can be added without code changes.
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID, PkMixin, TimestampMixin


class Module(BaseEntity, Base):
    """A functional module (Admissions, Fees, Library, ...) from the catalog."""

    __tablename__ = "module"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_module_tenant_slug"),)

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(String(64), default="cube", nullable=False)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    release_bucket: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ModuleCapability(BaseEntity, Base):
    """A capability/feature within a module (drives feature-level screens & APIs)."""

    __tablename__ = "module_capability"

    module_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("module.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    persona: Mapped[str | None] = mapped_column(String(100), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EntityDef(BaseEntity, Base):
    """Definition of a data entity (master or transaction) within a module."""

    __tablename__ = "entity_def"
    __table_args__ = (UniqueConstraint("tenant_id", "slug", name="uq_entity_tenant_slug"),)

    module_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("module.id"), index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="master", nullable=False)  # master/transaction
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    # When true the entity is backed by a typed table; otherwise stored in entity_record.
    is_typed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    typed_table: Mapped[str | None] = mapped_column(String(100), nullable=True)
    icon: Mapped[str] = mapped_column(String(64), default="table", nullable=False)


class FieldDef(BaseEntity, Base):
    """A field belonging to an EntityDef — drives dynamic forms & tables."""

    __tablename__ = "field_def"

    entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("entity_def.id"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)  # machine name
    label: Mapped[str] = mapped_column(String(150), nullable=False)
    data_type: Mapped[str] = mapped_column(String(32), default="string", nullable=False)
    # string/text/number/decimal/bool/date/datetime/select/reference/email/phone/json
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_list_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    options_master: Mapped[str | None] = mapped_column(String(150), nullable=True)  # MasterType code
    reference_entity: Mapped[str | None] = mapped_column(String(150), nullable=True)  # EntityDef slug
    default_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    help_text: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MasterType(BaseEntity, Base):
    """A configurable lookup/master list (e.g. Gender, Blood Group, Fee Frequency)."""

    __tablename__ = "master_type"
    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_mastertype_tenant_code"),)

    code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    module_slug: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class MasterValue(BaseEntity, Base):
    """A value belonging to a MasterType."""

    __tablename__ = "master_value"

    master_type_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("master_type.id"), index=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Setting(BaseEntity, Base):
    """Free-form key/value configuration, scoped to tenant (and optional module)."""

    __tablename__ = "setting"
    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_setting_tenant_key"),)

    key: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    value_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    module_slug: Mapped[str | None] = mapped_column(String(150), nullable=True)
    data_type: Mapped[str] = mapped_column(String(32), default="string", nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)


class MenuItem(BaseEntity, Base):
    """DB-driven navigation. The client renders the sidebar from these rows."""

    __tablename__ = "menu_item"

    label: Mapped[str] = mapped_column(String(150), nullable=False)
    icon: Mapped[str] = mapped_column(String(64), default="cube", nullable=False)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    module_slug: Mapped[str | None] = mapped_column(String(150), nullable=True)
    permission_code: Mapped[str | None] = mapped_column(String(150), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class EntityRecord(BaseEntity, Base):
    """Generic JSON-backed record store for non-typed (metadata-driven) entities.

    This is what lets all 30 modules be operable from day one: any EntityDef that
    is not yet promoted to a typed table stores its rows here as JSON.
    """

    __tablename__ = "entity_record"

    entity_slug: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)


class AuditLog(PkMixin, TimestampMixin, Base):
    """Immutable audit trail. Never updated or deleted."""

    __tablename__ = "audit_log"

    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False)  # create/update/delete/login/...
    entity: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    changes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Notification(BaseEntity, Base):
    __tablename__ = "notification"

    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(20), default="in_app", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class Document(BaseEntity, Base):
    __tablename__ = "document"

    owner_type: Mapped[str] = mapped_column(String(50), nullable=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
