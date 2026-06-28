"""Curriculum planning — admin oversight of quarterly class/subject plans.

Teachers author and submit plans from their portal and a reviewer (HOD) approves
them there. This router gives administrators a tenant-wide view of every plan and
the ability to approve/reject submitted ones, independent of the assigned reviewer.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import Grade, Section, Subject
from app.models.academics_ops import CurriculumPlan
from app.models.people import Employee

router = APIRouter(prefix="/curriculum", tags=["Curriculum"])


class PlanReviewIn(BaseModel):
    decision: str  # approved / rejected
    review_note: str | None = None


async def _maps(db: AsyncSession, tid: uuid.UUID) -> dict:
    async def collect(model, label):
        rows = (await db.execute(select(model).where(
            model.tenant_id == tid, model.is_deleted.is_(False)
        ))).scalars().all()
        return {r.id: label(r) for r in rows}

    return {
        "grades": await collect(Grade, lambda g: g.name),
        "sections": await collect(Section, lambda s: s.name),
        "subjects": await collect(Subject, lambda s: s.name),
        "employees": await collect(Employee, lambda e: f"{e.first_name} {e.last_name or ''}".strip()),
    }


def _plan_dict(p: CurriculumPlan, maps: dict) -> dict:
    return {
        "id": str(p.id),
        "title": p.title,
        "term": p.term,
        "grade": maps["grades"].get(p.grade_id, "—"),
        "section": maps["sections"].get(p.section_id, "—"),
        "subject": maps["subjects"].get(p.subject_id, "General"),
        "teacher": maps["employees"].get(p.teacher_id, "—"),
        "reviewer": maps["employees"].get(p.reviewer_id, None),
        "objectives": p.objectives,
        "resources": p.resources,
        "topics": p.topics or [],
        "completion_percent": p.completion_percent,
        "status": p.plan_status,
        "review_note": p.review_note,
        "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
        "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
    }


@router.get("/plans")
async def list_plans(
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("curriculum_lesson_planning:read")),
):
    conds = [CurriculumPlan.tenant_id == user.tenant_id, CurriculumPlan.is_deleted.is_(False)]
    if status:
        conds.append(CurriculumPlan.plan_status == status)
    rows = (await db.execute(select(CurriculumPlan).where(*conds)
                             .order_by(CurriculumPlan.created_at.desc()))).scalars().all()
    maps = await _maps(db, user.tenant_id)
    return [_plan_dict(p, maps) for p in rows]


@router.post("/plans/{plan_id}/review")
async def review_plan(
    plan_id: uuid.UUID,
    payload: PlanReviewIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("curriculum_lesson_planning:approve")),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be approved or rejected")
    plan = await db.get(CurriculumPlan, plan_id)
    if not plan or plan.tenant_id != user.tenant_id or plan.is_deleted:
        raise HTTPException(404, "Plan not found")
    if plan.plan_status != "submitted":
        raise HTTPException(409, "Only submitted plans can be reviewed")
    plan.plan_status = payload.decision
    plan.review_note = payload.review_note
    plan.reviewed_at = datetime.now(timezone.utc)
    plan.updated_by = user.id
    await db.flush()
    await record_audit(db, action=payload.decision, entity="CurriculumPlan", entity_id=plan.id, actor=user)
    return {"id": str(plan.id), "status": plan.plan_status}
