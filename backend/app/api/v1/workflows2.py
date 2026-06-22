"""Lifecycle endpoints for finance, inventory, homework and communication."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academics_ops import Homework, HomeworkSubmission
from app.models.finance import Expense
from app.models.operations import Activity, ActivityRegistration, Announcement, InventoryItem, StockMovement

router = APIRouter(tags=["Workflows · Ops"])


# ----------------------------------------------------------------- Finance: expense approval
class Decision(BaseModel):
    decision: str  # approved / rejected / paid


@router.post("/finance/expenses/{expense_id}/decide")
async def decide_expense(
    expense_id: uuid.UUID,
    payload: Decision,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("finance_accounting:approve")),
):
    if payload.decision not in ("approved", "rejected", "paid"):
        raise HTTPException(422, "decision must be approved/rejected/paid")
    exp = await db.get(Expense, expense_id)
    if not exp or exp.tenant_id != user.tenant_id or exp.is_deleted:
        raise HTTPException(404, "Expense not found")
    exp.approval_status = payload.decision
    exp.approver_id = user.id
    exp.updated_by = user.id
    await db.flush()
    await record_audit(db, action=payload.decision, entity="Expense", entity_id=exp.id, actor=user)
    return {"id": str(exp.id), "status": exp.approval_status}


# ----------------------------------------------------------------- Inventory: stock movement
class StockIn(BaseModel):
    item_id: uuid.UUID
    movement_type: str  # in / out
    quantity: int
    reference: str | None = None


@router.post("/inventory/stock-movements")
async def record_stock_movement(
    payload: StockIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("finance_accounting:create")),
):
    if payload.movement_type not in ("in", "out"):
        raise HTTPException(422, "movement_type must be in/out")
    if payload.quantity <= 0:
        raise HTTPException(422, "quantity must be positive")
    item = await db.get(InventoryItem, payload.item_id)
    if not item or item.tenant_id != user.tenant_id or item.is_deleted:
        raise HTTPException(404, "Item not found")
    if payload.movement_type == "out" and item.quantity_on_hand < payload.quantity:
        raise HTTPException(409, "Insufficient stock")

    mv = StockMovement(
        tenant_id=user.tenant_id, item_id=item.id, movement_type=payload.movement_type,
        quantity=payload.quantity, reference=payload.reference, movement_date=date.today(),
        created_by=user.id, updated_by=user.id,
    )
    item.quantity_on_hand += payload.quantity if payload.movement_type == "in" else -payload.quantity
    db.add(mv)
    await db.flush()
    await record_audit(db, action=f"stock_{payload.movement_type}", entity="StockMovement",
                       entity_id=mv.id, actor=user, changes={"qty": payload.quantity})
    return {"id": str(mv.id), "on_hand": item.quantity_on_hand}


# ----------------------------------------------------------------- Homework grading
class GradeIn(BaseModel):
    marks_awarded: float
    remarks: str | None = None


@router.post("/homework/submissions/{submission_id}/grade")
async def grade_submission(
    submission_id: uuid.UUID,
    payload: GradeIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("homework_assignments:update")),
):
    sub = await db.get(HomeworkSubmission, submission_id)
    if not sub or sub.tenant_id != user.tenant_id or sub.is_deleted:
        raise HTTPException(404, "Submission not found")
    sub.marks_awarded = payload.marks_awarded
    sub.remarks = payload.remarks
    sub.submission_status = "graded"
    sub.updated_by = user.id
    await db.flush()
    await record_audit(db, action="grade", entity="HomeworkSubmission", entity_id=sub.id, actor=user)
    return {"id": str(sub.id), "marks_awarded": str(sub.marks_awarded), "status": sub.submission_status}


# ----------------------------------------------------------------- Activities registration (capacity-aware)
class RegisterIn(BaseModel):
    activity_id: uuid.UUID
    student_id: uuid.UUID


@router.post("/activities/register")
async def register_activity(
    payload: RegisterIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("activities_events:create")),
):
    activity = await db.get(Activity, payload.activity_id)
    if not activity or activity.tenant_id != user.tenant_id or activity.is_deleted:
        raise HTTPException(404, "Activity not found")
    count = len((
        await db.execute(select(ActivityRegistration).where(
            ActivityRegistration.tenant_id == user.tenant_id,
            ActivityRegistration.activity_id == activity.id,
            ActivityRegistration.registration_status == "registered",
            ActivityRegistration.is_deleted.is_(False)))
    ).scalars().all())
    if activity.capacity and count >= activity.capacity:
        raise HTTPException(409, "Activity is full")
    reg = ActivityRegistration(
        tenant_id=user.tenant_id, activity_id=activity.id, student_id=payload.student_id,
        registration_date=date.today(), registration_status="registered",
        created_by=user.id, updated_by=user.id,
    )
    db.add(reg)
    await db.flush()
    await record_audit(db, action="register", entity="ActivityRegistration", entity_id=reg.id, actor=user)
    return {"id": str(reg.id), "registered": count + 1, "capacity": activity.capacity}


# ----------------------------------------------------------------- Communication: publish
@router.post("/announcements/{ann_id}/publish")
async def publish_announcement(
    ann_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("ptm_communication:update")),
):
    ann = await db.get(Announcement, ann_id)
    if not ann or ann.tenant_id != user.tenant_id or ann.is_deleted:
        raise HTTPException(404, "Announcement not found")
    ann.announcement_status = "published"
    ann.publish_date = date.today()
    ann.updated_by = user.id
    await db.flush()
    await record_audit(db, action="publish", entity="Announcement", entity_id=ann.id, actor=user)
    return {"id": str(ann.id), "status": ann.announcement_status}
