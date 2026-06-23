"""Dashboards & reports — aggregated, role-aware metrics (all from the DB)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.attendance import Attendance
from app.models.fees import Invoice, Payment
from app.models.finance import Expense
from app.models.hr import LeaveRequest
from app.models.library import BookIssue
from app.models.meta import AuditLog, Module
from app.models.operations import Activity, InventoryItem
from app.models.people import Employee, Student


async def _count(db: AsyncSession, model, tenant_id) -> int:
    return (
        await db.execute(
            select(func.count()).select_from(model).where(model.tenant_id == tenant_id, model.is_deleted.is_(False))
        )
    ).scalar_one()


router = APIRouter(prefix="/reports", tags=["Reports & Dashboards"])


@router.get("/dashboard")
async def dashboard(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    tid = user.tenant_id
    students = await _count(db, Student, tid)
    employees = await _count(db, Employee, tid)
    modules = await _count(db, Module, tid)

    total_billed = (
        await db.execute(select(func.coalesce(func.sum(Invoice.net_amount), 0)).where(
            Invoice.tenant_id == tid, Invoice.is_deleted.is_(False)))
    ).scalar_one()
    total_collected = (
        await db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.tenant_id == tid, Payment.is_deleted.is_(False)))
    ).scalar_one()

    today_present = (
        await db.execute(select(func.count()).select_from(Attendance).where(
            Attendance.tenant_id == tid, Attendance.att_date == date.today(),
            Attendance.state == "present", Attendance.is_deleted.is_(False)))
    ).scalar_one()

    # Operational signals across the newer modules.
    books_out = (
        await db.execute(select(func.count()).select_from(BookIssue).where(
            BookIssue.tenant_id == tid, BookIssue.issue_status != "returned", BookIssue.is_deleted.is_(False)))
    ).scalar_one()
    pending_leave = (
        await db.execute(select(func.count()).select_from(LeaveRequest).where(
            LeaveRequest.tenant_id == tid, LeaveRequest.request_status == "applied",
            LeaveRequest.is_deleted.is_(False)))
    ).scalar_one()
    pending_expenses = (
        await db.execute(select(func.count()).select_from(Expense).where(
            Expense.tenant_id == tid, Expense.approval_status == "pending", Expense.is_deleted.is_(False)))
    ).scalar_one()
    low_stock = (
        await db.execute(select(func.count()).select_from(InventoryItem).where(
            InventoryItem.tenant_id == tid, InventoryItem.is_deleted.is_(False),
            InventoryItem.quantity_on_hand <= InventoryItem.reorder_level))
    ).scalar_one()
    activities = await _count(db, Activity, tid)

    return {
        "cards": [
            {"key": "students", "label": "Students", "value": students, "icon": "users"},
            {"key": "employees", "label": "Employees", "value": employees, "icon": "briefcase"},
            {"key": "modules", "label": "Active Modules", "value": modules, "icon": "grid"},
            {"key": "present_today", "label": "Present Today", "value": today_present, "icon": "check"},
            {"key": "books_out", "label": "Books Issued", "value": books_out, "icon": "book"},
            {"key": "pending_leave", "label": "Pending Leave", "value": pending_leave, "icon": "edit"},
            {"key": "pending_expenses", "label": "Expenses to Approve", "value": pending_expenses, "icon": "credit-card"},
            {"key": "low_stock", "label": "Low-Stock Items", "value": low_stock, "icon": "table"},
            {"key": "activities", "label": "Activities", "value": activities, "icon": "trending-up"},
        ],
        "finance": {
            "total_billed": str(total_billed or Decimal(0)),
            "total_collected": str(total_collected or Decimal(0)),
            "outstanding": str((total_billed or Decimal(0)) - (total_collected or Decimal(0))),
        },
    }


@router.get("/students-by-grade")
async def students_by_grade(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    rows = (
        await db.execute(
            select(Student.grade_id, func.count()).where(
                Student.tenant_id == user.tenant_id, Student.is_deleted.is_(False))
            .group_by(Student.grade_id)
        )
    ).all()
    return [{"grade_id": str(g) if g else None, "count": c} for g, c in rows]


@router.get("/fees-collection")
async def fees_collection(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    rows = (
        await db.execute(
            select(Invoice.payment_status, func.count(), func.coalesce(func.sum(Invoice.net_amount), 0))
            .where(Invoice.tenant_id == user.tenant_id, Invoice.is_deleted.is_(False))
            .group_by(Invoice.payment_status)
        )
    ).all()
    return [{"status": s, "count": c, "amount": str(a)} for s, c, a in rows]


@router.get("/audit-log")
async def audit_log(
    limit: int = 100, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    rows = (
        await db.execute(
            select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
            .order_by(AuditLog.created_at.desc()).limit(limit)
        )
    ).scalars().all()
    return [
        {
            "id": str(r.id), "action": r.action, "entity": r.entity, "entity_id": r.entity_id,
            "actor_email": r.actor_email, "method": r.method, "path": r.path,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
