"""Generic, tenant-scoped CRUD router factory.

Produces list/get/create/update/delete endpoints for a typed SQLAlchemy model with:
  * automatic tenant isolation (filtered by the caller's tenant)
  * soft-delete (DELETE flips ``is_deleted``)
  * RBAC guards derived from a module slug (``<slug>:read|create|update|delete``)
  * immutable audit-log entries on every mutation
  * keyword search across string columns and simple equality filters

NOTE: this module must NOT use ``from __future__ import annotations`` — the request
body parameter is annotated with a closure variable (the create/update schema), and
PEP 563 stringised annotations would hide that class from FastAPI, causing it to treat
the body as query params. Keeping real (evaluated) annotations is required here.
"""
import uuid
from typing import Any, Type

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import String, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import Base, get_db
from app.core.deps import CurrentUser, require_permission
from app.core.pagination import Page


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


def build_crud_router(
    *,
    model: Type[Base],
    slug: str,
    tags: list[str],
    create_schema: Type[BaseModel],
    update_schema: Type[BaseModel],
    out_schema: Type[BaseModel],
    search_fields: list[str] | None = None,
    default_order: str = "created_at",
) -> APIRouter:
    router = APIRouter(tags=tags)
    entity_name = model.__name__

    async def _get_owned(db: AsyncSession, tenant_id: uuid.UUID, obj_id: uuid.UUID):
        obj = await db.get(model, obj_id)
        if obj is None or getattr(obj, "is_deleted", False) or obj.tenant_id != tenant_id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"{entity_name} not found")
        return obj

    @router.get("", response_model=Page[out_schema])
    async def list_items(
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(25, ge=1, le=200),
        q: str | None = Query(None, description="keyword search"),
        db: AsyncSession = Depends(get_db),
        user: CurrentUser = Depends(require_permission(f"{slug}:read")),
    ):
        conditions = [model.tenant_id == user.tenant_id]
        if hasattr(model, "is_deleted"):
            conditions.append(model.is_deleted.is_(False))

        # Simple equality filters from query params (?grade_id=...&status=active)
        reserved = {"page", "page_size", "q"}
        for key, value in request.query_params.items():
            if key in reserved or not hasattr(model, key):
                continue
            conditions.append(getattr(model, key) == value)

        if q and search_fields:
            like = f"%{q}%"
            conditions.append(or_(*[getattr(model, f).ilike(like) for f in search_fields if hasattr(model, f)]))

        base = select(model).where(*conditions)
        total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
        order_col = getattr(model, default_order, None)
        # Always tie-break on the primary key so pagination is deterministic even
        # when many rows share the same created_at (common right after seeding).
        id_col = getattr(model, "id", None)
        if order_col is not None:
            base = base.order_by(order_col.desc(), *( [id_col.desc()] if id_col is not None else [] ))
        elif id_col is not None:
            base = base.order_by(id_col.desc())
        rows = (await db.execute(base.offset((page - 1) * page_size).limit(page_size))).scalars().all()
        items = [out_schema.model_validate(r) for r in rows]
        return Page.build(items, total, page, page_size)

    @router.get("/{obj_id}", response_model=out_schema)
    async def get_item(
        obj_id: uuid.UUID,
        db: AsyncSession = Depends(get_db),
        user: CurrentUser = Depends(require_permission(f"{slug}:read")),
    ):
        return out_schema.model_validate(await _get_owned(db, user.tenant_id, obj_id))

    @router.post("", response_model=out_schema, status_code=status.HTTP_201_CREATED)
    async def create_item(
        payload: create_schema,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: CurrentUser = Depends(require_permission(f"{slug}:create")),
    ):
        data: dict[str, Any] = payload.model_dump(exclude_unset=True)
        obj = model(**data)
        obj.tenant_id = user.tenant_id
        if hasattr(obj, "created_by"):
            obj.created_by = user.id
            obj.updated_by = user.id
        db.add(obj)
        await db.flush()
        await record_audit(db, action="create", entity=entity_name, entity_id=obj.id, actor=user,
                           changes=data, method="POST", path=str(request.url.path), ip_address=_client_ip(request))
        await db.refresh(obj)
        return out_schema.model_validate(obj)

    @router.put("/{obj_id}", response_model=out_schema)
    async def update_item(
        obj_id: uuid.UUID,
        payload: update_schema,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: CurrentUser = Depends(require_permission(f"{slug}:update")),
    ):
        obj = await _get_owned(db, user.tenant_id, obj_id)
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(obj, key, value)
        if hasattr(obj, "updated_by"):
            obj.updated_by = user.id
        await db.flush()
        await record_audit(db, action="update", entity=entity_name, entity_id=obj.id, actor=user,
                           changes=data, method="PUT", path=str(request.url.path), ip_address=_client_ip(request))
        await db.refresh(obj)
        return out_schema.model_validate(obj)

    @router.delete("/{obj_id}", status_code=status.HTTP_200_OK)
    async def delete_item(
        obj_id: uuid.UUID,
        request: Request,
        db: AsyncSession = Depends(get_db),
        user: CurrentUser = Depends(require_permission(f"{slug}:delete")),
    ):
        obj = await _get_owned(db, user.tenant_id, obj_id)
        if hasattr(obj, "is_deleted"):
            from datetime import datetime, timezone

            obj.is_deleted = True
            obj.deleted_at = datetime.now(timezone.utc)
        else:
            await db.delete(obj)
        await record_audit(db, action="delete", entity=entity_name, entity_id=obj_id, actor=user,
                           method="DELETE", path=str(request.url.path), ip_address=_client_ip(request))
        return {"detail": f"{entity_name} deleted", "id": str(obj_id)}

    return router
