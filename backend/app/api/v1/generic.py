"""Generic entity-record API.

Any ``EntityDef`` that is not promoted to a typed table is stored as JSON in
``entity_record`` and exposed here. This is what makes all 30 modules — and any
future master/transaction added at runtime — immediately operable, validated
against their ``FieldDef`` metadata, with RBAC + audit.
"""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.pagination import Page
from app.models.meta import EntityDef, FieldDef, Module

router = APIRouter(prefix="/records", tags=["Generic Records"])


class RecordIn(BaseModel):
    data: dict[str, Any]
    academic_year_id: uuid.UUID | None = None


class RecordOut(BaseModel):
    id: uuid.UUID
    entity_slug: str
    academic_year_id: uuid.UUID | None = None
    data: dict[str, Any]
    status: str | None = None

    class Config:
        from_attributes = True


async def _resolve_entity(db: AsyncSession, user: CurrentUser, slug: str) -> tuple[EntityDef, str]:
    entity = (
        await db.execute(select(EntityDef).where(EntityDef.tenant_id == user.tenant_id, EntityDef.slug == slug))
    ).scalars().first()
    if not entity:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Entity '{slug}' not defined")
    if entity.is_typed:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Entity '{slug}' is a typed entity; use its dedicated endpoint")
    module = await db.get(Module, entity.module_id)
    return entity, (module.slug if module else "administration_workflow")


def _check(user: CurrentUser, module_slug: str, action: str) -> None:
    if user.is_superadmin or "*" in user.permissions:
        return
    if f"{module_slug}:{action}" in user.permissions or f"{module_slug}:*" in user.permissions:
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, f"Missing permission: {module_slug}:{action}")


async def _validate(db: AsyncSession, entity: EntityDef, data: dict[str, Any]) -> None:
    fields = (
        await db.execute(select(FieldDef).where(FieldDef.entity_id == entity.id, FieldDef.is_deleted.is_(False)))
    ).scalars().all()
    missing = [f.label for f in fields if f.is_required and not data.get(f.name)]
    if missing:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"Missing required fields: {', '.join(missing)}")


@router.get("/{slug}", response_model=Page[RecordOut])
async def list_records(
    slug: str,
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    from app.models.meta import EntityRecord

    entity, module_slug = await _resolve_entity(db, user, slug)
    _check(user, module_slug, "read")
    conditions = [
        EntityRecord.tenant_id == user.tenant_id,
        EntityRecord.entity_slug == slug,
        EntityRecord.is_deleted.is_(False),
    ]
    base = select(EntityRecord).where(*conditions)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        await db.execute(base.order_by(EntityRecord.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()
    items = [RecordOut.model_validate(r) for r in rows]
    if q:
        ql = q.lower()
        items = [r for r in items if ql in str(r.data).lower()]
    return Page.build(items, total, page, page_size)


@router.post("/{slug}", response_model=RecordOut, status_code=201)
async def create_record(
    slug: str,
    payload: RecordIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    from app.models.meta import EntityRecord

    entity, module_slug = await _resolve_entity(db, user, slug)
    _check(user, module_slug, "create")
    await _validate(db, entity, payload.data)
    rec = EntityRecord(
        tenant_id=user.tenant_id, entity_slug=slug, data=payload.data,
        academic_year_id=payload.academic_year_id, created_by=user.id, updated_by=user.id,
    )
    db.add(rec)
    await db.flush()
    await record_audit(db, action="create", entity=f"record:{slug}", entity_id=rec.id, actor=user,
                       changes=payload.data, method="POST", path=str(request.url.path))
    await db.refresh(rec)
    return rec


@router.put("/{slug}/{record_id}", response_model=RecordOut)
async def update_record(
    slug: str,
    record_id: uuid.UUID,
    payload: RecordIn,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    from app.models.meta import EntityRecord

    entity, module_slug = await _resolve_entity(db, user, slug)
    _check(user, module_slug, "update")
    rec = await db.get(EntityRecord, record_id)
    if not rec or rec.tenant_id != user.tenant_id or rec.is_deleted or rec.entity_slug != slug:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    await _validate(db, entity, payload.data)
    rec.data = payload.data
    if payload.academic_year_id is not None:
        rec.academic_year_id = payload.academic_year_id
    rec.updated_by = user.id
    await db.flush()
    await record_audit(db, action="update", entity=f"record:{slug}", entity_id=rec.id, actor=user,
                       changes=payload.data, method="PUT", path=str(request.url.path))
    await db.refresh(rec)
    return rec


@router.delete("/{slug}/{record_id}")
async def delete_record(
    slug: str,
    record_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    from app.models.meta import EntityRecord

    _, module_slug = await _resolve_entity(db, user, slug)
    _check(user, module_slug, "delete")
    rec = await db.get(EntityRecord, record_id)
    if not rec or rec.tenant_id != user.tenant_id or rec.is_deleted or rec.entity_slug != slug:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")
    rec.is_deleted = True
    await record_audit(db, action="delete", entity=f"record:{slug}", entity_id=rec.id, actor=user,
                       method="DELETE", path=str(request.url.path))
    return {"detail": "deleted", "id": str(record_id)}
