"""Attendance — bulk marking and summaries for students and staff.

One polymorphic endpoint set keyed by ``person_type`` (student | employee).
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.attendance import Attendance

router = APIRouter(prefix="/attendance", tags=["Attendance"])

PERSON_TYPES = {"student", "employee"}


class AttendanceEntry(BaseModel):
    person_id: uuid.UUID
    state: str = "present"  # present/absent/late/leave/holiday/half_day/on_duty
    remarks: str | None = None


class BulkAttendanceIn(BaseModel):
    person_type: str = "student"  # student | employee
    section_id: uuid.UUID | None = None
    att_date: date
    method: str = "manual"
    entries: list[AttendanceEntry]


def _check_person_type(person_type: str) -> None:
    if person_type not in PERSON_TYPES:
        raise HTTPException(422, "person_type must be 'student' or 'employee'")


@router.post("/bulk")
async def mark_bulk(
    payload: BulkAttendanceIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("attendance:create")),
):
    """Upsert attendance for a list of people on a date (idempotent per person/date)."""
    _check_person_type(payload.person_type)
    written = 0
    for entry in payload.entries:
        existing = (
            await db.execute(
                select(Attendance).where(
                    Attendance.tenant_id == user.tenant_id,
                    Attendance.person_type == payload.person_type,
                    Attendance.person_id == entry.person_id,
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
                tenant_id=user.tenant_id, person_type=payload.person_type, person_id=entry.person_id,
                student_id=entry.person_id if payload.person_type == "student" else None,
                section_id=payload.section_id if payload.person_type == "student" else None,
                att_date=payload.att_date, state=entry.state, method=payload.method,
                remarks=entry.remarks, marked_by=user.id, created_by=user.id, updated_by=user.id,
            ))
        written += 1
    await db.flush()
    await record_audit(db, action="bulk_mark", entity="Attendance", actor=user,
                       changes={"person_type": payload.person_type,
                                "date": payload.att_date.isoformat(), "count": written})
    return {"detail": "attendance recorded", "count": written,
            "person_type": payload.person_type, "date": payload.att_date.isoformat()}


@router.get("/day")
async def day(
    att_date: date = Query(...),
    person_type: str = Query("student"),
    section_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("attendance:read")),
):
    """Existing marks for a date, keyed by person_id — used to prefill the grid."""
    _check_person_type(person_type)
    conditions = [Attendance.tenant_id == user.tenant_id, Attendance.att_date == att_date,
                  Attendance.person_type == person_type, Attendance.is_deleted.is_(False)]
    if section_id and person_type == "student":
        conditions.append(Attendance.section_id == section_id)
    rows = (await db.execute(select(Attendance).where(and_(*conditions)))).scalars().all()
    return {
        "person_type": person_type,
        "date": att_date.isoformat(),
        "marks": {
            str(r.person_id): {"state": r.state, "method": r.method, "remarks": r.remarks}
            for r in rows
        },
    }


@router.get("/summary")
async def summary(
    att_date: date = Query(..., description="date to summarise"),
    person_type: str = Query("student"),
    section_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("attendance:read")),
):
    _check_person_type(person_type)
    conditions = [Attendance.tenant_id == user.tenant_id, Attendance.att_date == att_date,
                  Attendance.person_type == person_type, Attendance.is_deleted.is_(False)]
    if section_id and person_type == "student":
        conditions.append(Attendance.section_id == section_id)
    rows = (
        await db.execute(select(Attendance.state, func.count()).where(and_(*conditions)).group_by(Attendance.state))
    ).all()
    by_state = {state: count for state, count in rows}
    return {"date": att_date.isoformat(), "person_type": person_type,
            "by_state": by_state, "total": sum(by_state.values())}
