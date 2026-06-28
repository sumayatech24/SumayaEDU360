"""Aggregate the v1 API surface."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    attendance,
    admissions,
    auth,
    branding,
    curriculum,
    documents,
    dynamic,
    entities,
    exams,
    fees,
    generic,
    hostel,
    library,
    masters,
    meta,
    portal,
    promotion,
    public_site,
    reporting,
    reports,
    users,
    workflows,
    workflows2,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admissions.router)
api_router.include_router(branding.router)
api_router.include_router(documents.router)
api_router.include_router(public_site.router)
api_router.include_router(portal.router)
api_router.include_router(curriculum.router)      # quarterly plan oversight + approval
api_router.include_router(meta.router)
api_router.include_router(masters.router)
api_router.include_router(users.router)
api_router.include_router(entities.router)        # typed CRUD (students, fees, exams, ...)
api_router.include_router(dynamic.router)         # typed CRUD from the domain registry
api_router.include_router(generic.router)         # metadata-driven records for all modules
api_router.include_router(hostel.router)          # residence lifecycle and safeguarding
api_router.include_router(library.router)         # catalog analytics, acquisitions and receiving
api_router.include_router(fees.router)            # payments / ledger
api_router.include_router(attendance.router)
api_router.include_router(exams.router)           # marks / report card
api_router.include_router(promotion.router)
api_router.include_router(workflows.router)       # lifecycle: admissions, library, hostel, hr
api_router.include_router(workflows2.router)      # lifecycle: finance, inventory, homework, activities
api_router.include_router(reports.router)
api_router.include_router(reporting.router)       # report catalog + generic runner
