"""Configurable masters (lookups) and settings — fully DB-driven."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_permission
from app.models.meta import MasterType, MasterValue, Setting

router = APIRouter(tags=["Masters & Settings"])

MASTER_PERM = "academic_configuration"


# --------------------------------------------------------------------------- schemas
class MasterTypeOut(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    module_slug: str | None = None
    description: str | None = None
    is_system: bool

    class Config:
        from_attributes = True


class MasterValueIn(BaseModel):
    code: str
    label: str
    sort_order: int = 100
    is_active: bool = True
    value_json: dict | None = None


class MasterValueOut(MasterValueIn):
    id: uuid.UUID
    master_type_id: uuid.UUID

    class Config:
        from_attributes = True


class MasterTypeIn(BaseModel):
    code: str
    name: str
    module_slug: str | None = None
    description: str | None = None


class SettingIn(BaseModel):
    key: str
    value_json: dict | None = None
    module_slug: str | None = None
    data_type: str = "string"
    description: str | None = None


class SettingOut(SettingIn):
    id: uuid.UUID

    class Config:
        from_attributes = True


# --------------------------------------------------------------------------- master types
@router.get("/master-types", response_model=list[MasterTypeOut])
async def list_master_types(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    rows = (
        await db.execute(
            select(MasterType).where(MasterType.tenant_id == user.tenant_id, MasterType.is_deleted.is_(False))
            .order_by(MasterType.name)
        )
    ).scalars().all()
    return rows


@router.post("/master-types", response_model=MasterTypeOut, status_code=201)
async def create_master_type(
    payload: MasterTypeIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(f"{MASTER_PERM}:create")),
):
    mt = MasterType(tenant_id=user.tenant_id, created_by=user.id, updated_by=user.id, **payload.model_dump())
    db.add(mt)
    await db.flush()
    await record_audit(db, action="create", entity="MasterType", entity_id=mt.id, actor=user)
    await db.refresh(mt)
    return mt


# --------------------------------------------------------------------------- master values
@router.get("/master-types/{code}/values", response_model=list[MasterValueOut])
async def list_values(code: str, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    mt = (
        await db.execute(select(MasterType).where(MasterType.tenant_id == user.tenant_id, MasterType.code == code))
    ).scalars().first()
    if not mt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Master type not found")
    rows = (
        await db.execute(
            select(MasterValue).where(MasterValue.master_type_id == mt.id, MasterValue.is_deleted.is_(False))
            .order_by(MasterValue.sort_order, MasterValue.label)
        )
    ).scalars().all()
    return rows


@router.post("/master-types/{code}/values", response_model=MasterValueOut, status_code=201)
async def add_value(
    code: str,
    payload: MasterValueIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(f"{MASTER_PERM}:create")),
):
    mt = (
        await db.execute(select(MasterType).where(MasterType.tenant_id == user.tenant_id, MasterType.code == code))
    ).scalars().first()
    if not mt:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Master type not found")
    mv = MasterValue(tenant_id=user.tenant_id, master_type_id=mt.id, created_by=user.id, updated_by=user.id,
                     **payload.model_dump())
    db.add(mv)
    await db.flush()
    await record_audit(db, action="create", entity="MasterValue", entity_id=mv.id, actor=user)
    await db.refresh(mv)
    return mv


@router.put("/master-values/{value_id}", response_model=MasterValueOut)
async def update_value(
    value_id: uuid.UUID,
    payload: MasterValueIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(f"{MASTER_PERM}:update")),
):
    mv = await db.get(MasterValue, value_id)
    if not mv or mv.tenant_id != user.tenant_id or mv.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Value not found")
    for k, v in payload.model_dump().items():
        setattr(mv, k, v)
    mv.updated_by = user.id
    await db.flush()
    await record_audit(db, action="update", entity="MasterValue", entity_id=mv.id, actor=user)
    await db.refresh(mv)
    return mv


@router.delete("/master-values/{value_id}")
async def delete_value(
    value_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission(f"{MASTER_PERM}:delete")),
):
    mv = await db.get(MasterValue, value_id)
    if not mv or mv.tenant_id != user.tenant_id or mv.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Value not found")
    mv.is_deleted = True
    await record_audit(db, action="delete", entity="MasterValue", entity_id=mv.id, actor=user)
    return {"detail": "deleted", "id": str(value_id)}


# --------------------------------------------------------------------------- settings
@router.get("/settings", response_model=list[SettingOut])
async def list_settings(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    rows = (
        await db.execute(select(Setting).where(Setting.tenant_id == user.tenant_id, Setting.is_deleted.is_(False)))
    ).scalars().all()
    return rows


@router.put("/settings/{key}", response_model=SettingOut)
async def upsert_setting(
    key: str,
    payload: SettingIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("security_compliance:update")),
):
    existing = (
        await db.execute(select(Setting).where(Setting.tenant_id == user.tenant_id, Setting.key == key))
    ).scalars().first()
    if existing:
        existing.value_json = payload.value_json
        existing.data_type = payload.data_type
        existing.description = payload.description
        existing.module_slug = payload.module_slug
        existing.updated_by = user.id
        await db.flush()
        await record_audit(db, action="update", entity="Setting", entity_id=existing.id, actor=user)
        await db.refresh(existing)
        return existing
    s = Setting(tenant_id=user.tenant_id, created_by=user.id, updated_by=user.id,
                **{**payload.model_dump(), "key": key})
    db.add(s)
    await db.flush()
    await record_audit(db, action="create", entity="Setting", entity_id=s.id, actor=user)
    await db.refresh(s)
    return s
