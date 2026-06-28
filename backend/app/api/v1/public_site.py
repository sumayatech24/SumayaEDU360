"""Public institution website (no auth) — driven by CMS pages, banners and branding.

Multi-tenant: content is resolved by the tenant's public ``code`` in the URL, e.g.
``/api/v1/public/site/SUMAYA``. Only published pages / active banners are exposed.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.branding import _branding_for
from app.core.database import get_db
from app.models.operations import Banner, CmsPage
from app.models.tenant import Institution, Tenant

router = APIRouter(prefix="/public/site", tags=["Public Site"])


async def _tenant_by_code(db: AsyncSession, code: str) -> Tenant:
    tenant = (
        await db.execute(select(Tenant).where(
            func.lower(Tenant.code) == code.lower(), Tenant.is_deleted.is_(False)))
    ).scalars().first()
    if not tenant:
        raise HTTPException(404, "Institution not found")
    return tenant


def _excerpt(body: str | None, n: int = 180) -> str:
    if not body:
        return ""
    return body[:n] + ("…" if len(body) > n else "")


@router.get("/{tenant_code}")
async def public_site(tenant_code: str, db: AsyncSession = Depends(get_db)):
    tenant = await _tenant_by_code(db, tenant_code)
    tid = tenant.id
    branding = await _branding_for(db, tid)
    institution = (
        await db.execute(select(Institution).where(Institution.tenant_id == tid, Institution.is_deleted.is_(False)))
    ).scalars().first()

    banners = (
        await db.execute(select(Banner).where(
            Banner.tenant_id == tid, Banner.is_active.is_(True), Banner.is_deleted.is_(False))
            .order_by(Banner.sort_order))
    ).scalars().all()

    pages = (
        await db.execute(select(CmsPage).where(
            CmsPage.tenant_id == tid, CmsPage.is_published.is_(True), CmsPage.page_type == "page",
            CmsPage.is_deleted.is_(False)).order_by(CmsPage.title))
    ).scalars().all()

    news = (
        await db.execute(select(CmsPage).where(
            CmsPage.tenant_id == tid, CmsPage.is_published.is_(True),
            CmsPage.page_type.in_(["news", "event", "blog"]), CmsPage.is_deleted.is_(False))
            .order_by(CmsPage.publish_date.desc()).limit(6))
    ).scalars().all()

    return {
        "tenant_code": tenant.code,
        "branding": branding,
        "institution": None if not institution else {
            "name": institution.name, "type": institution.type, "board": institution.board,
            "address": institution.address,
        },
        "banners": [
            {"title": b.title, "image_url": b.image_url, "link_url": b.link_url} for b in banners
        ],
        "pages": [{"title": p.title, "slug": p.slug} for p in pages],
        "news": [
            {"title": n.title, "slug": n.slug, "type": n.page_type,
             "date": n.publish_date.isoformat() if n.publish_date else None, "excerpt": _excerpt(n.body)}
            for n in news
        ],
    }


@router.get("/{tenant_code}/page/{slug}")
async def public_page(tenant_code: str, slug: str, db: AsyncSession = Depends(get_db)):
    tenant = await _tenant_by_code(db, tenant_code)
    page = (
        await db.execute(select(CmsPage).where(
            CmsPage.tenant_id == tenant.id, CmsPage.slug == slug, CmsPage.is_published.is_(True),
            CmsPage.is_deleted.is_(False)))
    ).scalars().first()
    if not page:
        raise HTTPException(404, "Page not found")
    return {
        "title": page.title, "body": page.body, "type": page.page_type,
        "date": page.publish_date.isoformat() if page.publish_date else None,
        "branding": await _branding_for(db, tenant.id),
    }
