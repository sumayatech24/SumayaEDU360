"""Metadata endpoints — modules, navigation, entity definitions.

The React client reads these to build the sidebar and dynamic master screens, so
the application surface is entirely database-driven.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.meta import EntityDef, FieldDef, MenuItem, Module, ModuleCapability

router = APIRouter(tags=["Metadata"])


class ModuleOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    slug: str
    description: str | None = None
    icon: str
    priority: str | None = None
    release_bucket: str | None = None
    sort_order: int
    is_enabled: bool

    class Config:
        from_attributes = True


class CapabilityOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    persona: str | None = None
    priority: str | None = None

    class Config:
        from_attributes = True


class MenuOut(BaseModel):
    id: uuid.UUID
    label: str
    icon: str
    path: str
    module_slug: str | None = None
    permission_code: str | None = None
    sort_order: int

    class Config:
        from_attributes = True


class FieldOut(BaseModel):
    name: str
    label: str
    data_type: str
    is_required: bool
    is_unique: bool
    is_list_visible: bool
    options_master: str | None = None
    reference_entity: str | None = None
    default_value: str | None = None
    sort_order: int
    help_text: str | None = None

    class Config:
        from_attributes = True


class EntityDefOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    kind: str
    purpose: str | None = None
    is_typed: bool
    typed_table: str | None = None
    icon: str
    fields: list[FieldOut] = []

    class Config:
        from_attributes = True


@router.get("/modules", response_model=list[ModuleOut])
async def list_modules(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    rows = (
        await db.execute(
            select(Module)
            .where(Module.tenant_id == user.tenant_id, Module.is_deleted.is_(False))
            .order_by(Module.sort_order, Module.name)
        )
    ).scalars().all()
    return rows


@router.get("/modules/{slug}/capabilities", response_model=list[CapabilityOut])
async def module_capabilities(
    slug: str, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    module = (
        await db.execute(select(Module).where(Module.tenant_id == user.tenant_id, Module.slug == slug))
    ).scalars().first()
    if not module:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Module not found")
    rows = (
        await db.execute(
            select(ModuleCapability)
            .where(ModuleCapability.module_id == module.id, ModuleCapability.is_deleted.is_(False))
            .order_by(ModuleCapability.name)
        )
    ).scalars().all()
    return rows


@router.get("/navigation", response_model=list[MenuOut])
async def navigation(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Return menu items the current user is permitted to see."""
    rows = (
        await db.execute(
            select(MenuItem)
            .where(MenuItem.tenant_id == user.tenant_id, MenuItem.is_enabled.is_(True),
                   MenuItem.is_deleted.is_(False))
            .order_by(MenuItem.sort_order)
        )
    ).scalars().all()
    visible = []
    for m in rows:
        if not m.permission_code or user.is_superadmin or "*" in user.permissions:
            visible.append(m)
            continue
        module = m.permission_code.split(":", 1)[0]
        if m.permission_code in user.permissions or f"{module}:*" in user.permissions:
            visible.append(m)
    return visible


@router.get("/entities", response_model=list[EntityDefOut])
async def list_entities(
    kind: str | None = Query(None, description="filter by master|transaction"),
    module_slug: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    conditions = [EntityDef.tenant_id == user.tenant_id, EntityDef.is_deleted.is_(False)]
    if kind:
        conditions.append(EntityDef.kind == kind)
    rows = (await db.execute(select(EntityDef).where(*conditions).order_by(EntityDef.name))).scalars().all()

    if module_slug:
        modules = {
            m.id: m.slug
            for m in (await db.execute(select(Module).where(Module.tenant_id == user.tenant_id))).scalars().all()
        }
        rows = [r for r in rows if modules.get(r.module_id) == module_slug]

    out: list[EntityDefOut] = []
    for r in rows:
        fields = (
            await db.execute(
                select(FieldDef).where(FieldDef.entity_id == r.id, FieldDef.is_deleted.is_(False))
                .order_by(FieldDef.sort_order)
            )
        ).scalars().all()
        dto = EntityDefOut.model_validate(r)
        dto.fields = [FieldOut.model_validate(f) for f in fields]
        out.append(dto)
    return out


@router.get("/entities/{slug}", response_model=EntityDefOut)
async def get_entity(slug: str, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    r = (
        await db.execute(select(EntityDef).where(EntityDef.tenant_id == user.tenant_id, EntityDef.slug == slug))
    ).scalars().first()
    if not r:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entity not found")
    fields = (
        await db.execute(
            select(FieldDef).where(FieldDef.entity_id == r.id, FieldDef.is_deleted.is_(False))
            .order_by(FieldDef.sort_order)
        )
    ).scalars().all()
    dto = EntityDefOut.model_validate(r)
    dto.fields = [FieldOut.model_validate(f) for f in fields]
    return dto
