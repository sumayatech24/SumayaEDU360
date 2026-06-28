"""Tenant branding — logo, institution name and theme colour.

Public (no auth) so the login screen can render branding, and updatable by admins.
Multi-tenant ready: branding is stored per tenant in the Setting table; for now the
default (first) tenant is resolved. Subdomain/host resolution can hook in here later.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.meta import Setting
from app.models.tenant import Institution, Tenant

router = APIRouter(tags=["Branding"])

BRANDING_KEYS = ("branding.institution_name", "branding.logo_url", "branding.tagline",
                 "branding.primary_color", "branding.address", "branding.phone",
                 "branding.email", "branding.website")
DEFAULTS = {
    "branding.institution_name": "SumayaEDU360",
    "branding.logo_url": "",
    "branding.tagline": "AI EduOS",
    "branding.primary_color": "#2563eb",
    "branding.address": "",
    "branding.phone": "",
    "branding.email": "",
    "branding.website": "",
}


async def _branding_for(db: AsyncSession, tenant_id) -> dict:
    rows = (
        await db.execute(select(Setting).where(
            Setting.tenant_id == tenant_id, Setting.key.in_(BRANDING_KEYS), Setting.is_deleted.is_(False)))
    ).scalars().all()
    out = dict(DEFAULTS)
    for s in rows:
        val = (s.value_json or {}).get("value") if isinstance(s.value_json, dict) else s.value_json
        if val not in (None, ""):
            out[s.key] = val
    # Fall back to the registered institution's address when none is set in branding.
    if not out["branding.address"]:
        inst = (await db.execute(select(Institution).where(
            Institution.tenant_id == tenant_id, Institution.is_deleted.is_(False)).limit(1))).scalars().first()
        if inst and inst.address:
            out["branding.address"] = inst.address
    return {
        "institution_name": out["branding.institution_name"],
        "logo_url": out["branding.logo_url"],
        "tagline": out["branding.tagline"],
        "primary_color": out["branding.primary_color"],
        "address": out["branding.address"],
        "phone": out["branding.phone"],
        "email": out["branding.email"],
        "website": out["branding.website"],
    }


@router.get("/branding")
async def public_branding(db: AsyncSession = Depends(get_db)):
    """Branding for the default tenant (used by the login screen, pre-auth)."""
    tenant = (await db.execute(select(Tenant).where(Tenant.is_deleted.is_(False)).limit(1))).scalars().first()
    if not tenant:
        return {"institution_name": DEFAULTS["branding.institution_name"],
                "logo_url": "", "tagline": DEFAULTS["branding.tagline"],
                "primary_color": DEFAULTS["branding.primary_color"],
                "address": "", "phone": "", "email": "", "website": ""}
    return await _branding_for(db, tenant.id)


@router.get("/branding/me")
async def my_branding(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    return await _branding_for(db, user.tenant_id)
