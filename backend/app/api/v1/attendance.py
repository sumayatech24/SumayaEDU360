"""Attendance — bulk marking and summaries."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.attendance import Attendance

router = APIRouter(prefix="/attendance", tags=["Attendance"])


class AttendanceEntry(BaseModel):
    student_id: uuid.UUID
    state: str = "present"  # present/absent/late/leave
    remarks: str | None = None


class BulkAttendanceIn(BaseModel):
    section_id: uuid.UUID | None = None
    att_date: date
    method: str = "manual"
    entries: list[AttendanceEntry]


@router.post("/bulk")
async def mark_bulk(
    payload: BulkAttendanceIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("attendance:create")),
):
    """Upsert attendance for a list of students on a date (idempotent per student/date)."""
    written = 0
    for entry in payload.entries:
        existing = (
            await db.execute(
                select(Attendance).where(
                    Attendance.tenant_id == user.tenant_id,
                    Attendance.student_id == entry.student_id,
                    Attendance.att_date == payload.att_date,
                )
            )
        ).scalars().first()
        if existing:
            existing.state = entry.state
            existing.remarks = entry.remarks
            existing.method = payload.method
            existing.marked_by = user.id
            existing.updated_by = user.id
        else:
            db.add(Attendance(
                tenant_id=user.tenant_id, student_id=entry.student_id, section_id=payload.section_id,
                att_date=payload.att_date, state=entry.state, method=payload.method,
                remarks=entry.remarks, marked_by=user.id, created_by=user.id, updated_by=user.id,
            ))
        written += 1
    await db.flush()
    await record_audit(db, action="bulk_mark", entity="Attendance", actor=user,
                       changes={"date": payload.att_date.isoformat(), "count": written})
    return {"detail": "attendance recorded", "count": written, "date": payload.att_date.isoformat()}


@router.get("/summary")
async def summary(
    att_date: date = Query(..., description="date to summarise"),
    section_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("attendance:read")),
):
    conditions = [Attendance.tenant_id == user.tenant_id, Attendance.att_date == att_date,
                  Attendance.is_deleted.is_(False)]
    if section_id:
        conditions.append(Attendance.section_id == section_id)
    rows = (
        await db.execute(select(Attendance.state, func.count()).where(and_(*conditions)).group_by(Attendance.state))
    ).all()
    by_state = {state: count for state, count in rows}
    return {"date": att_date.isoformat(), "by_state": by_state, "total": sum(by_state.values())}
