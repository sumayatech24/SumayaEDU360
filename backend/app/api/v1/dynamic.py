"""Mount typed CRUD routers for every entry in the domain registry.

Each spec yields a full tenant-scoped, audited, RBAC-guarded CRUD router at
``/api/v1/{slug}`` with schemas generated from the spec — real persistence, no
bespoke code per module.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.domain import DOMAIN_SPECS, build_schemas

router = APIRouter()

for spec in DOMAIN_SPECS:
    create_s, update_s, out_s = build_schemas(spec)
    sub = build_crud_router(
        model=spec.model,
        slug=spec.module_slug,
        tags=[spec.name],
        create_schema=create_s,
        update_schema=update_s,
        out_schema=out_s,
        search_fields=spec.search_fields,
    )
    router.include_router(sub, prefix=f"/{spec.slug}")
