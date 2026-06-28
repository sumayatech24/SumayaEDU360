"""Hostel operations: beds, class rosters, transfers, attendance, visitors and incidents."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import Grade, Section
from app.models.hostel import (
    HostelAllocation, HostelAttendance, HostelBed, HostelBlock, HostelIncident,
    HostelRoom, HostelVisitor,
)
from app.models.people import Student

router = APIRouter(prefix="/hostel", tags=["Hostel"])


async def _active_allocation(db: AsyncSession, tid: uuid.UUID, student_id: uuid.UUID):
    return (await db.execute(select(HostelAllocation).where(
        HostelAllocation.tenant_id == tid, HostelAllocation.student_id == student_id,
        HostelAllocation.allocation_status == "allocated", HostelAllocation.is_deleted.is_(False),
    ))).scalars().first()


async def _ensure_beds(db: AsyncSession, user: CurrentUser, room: HostelRoom):
    beds = (await db.execute(select(HostelBed).where(
        HostelBed.tenant_id == user.tenant_id, HostelBed.room_id == room.id,
        HostelBed.is_deleted.is_(False),
    ).order_by(HostelBed.bed_no))).scalars().all()
    for number in range(len(beds) + 1, room.capacity + 1):
        bed = HostelBed(
            tenant_id=user.tenant_id, room_id=room.id, bed_no=str(number),
            created_by=user.id, updated_by=user.id,
        )
        db.add(bed)
        beds.append(bed)
    await db.flush()
    return beds


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:read")),
):
    blocks = (await db.execute(select(HostelBlock).where(
        HostelBlock.tenant_id == user.tenant_id, HostelBlock.is_deleted.is_(False)
    ))).scalars().all()
    rooms = (await db.execute(select(HostelRoom).where(
        HostelRoom.tenant_id == user.tenant_id, HostelRoom.is_deleted.is_(False)
    ))).scalars().all()
    active = (await db.execute(select(HostelAllocation).where(
        HostelAllocation.tenant_id == user.tenant_id,
        HostelAllocation.allocation_status == "allocated",
        HostelAllocation.is_deleted.is_(False),
    ))).scalars().all()
    today_attendance = (await db.execute(select(HostelAttendance).where(
        HostelAttendance.tenant_id == user.tenant_id,
        HostelAttendance.attendance_date == date.today(),
        HostelAttendance.is_deleted.is_(False),
    ))).scalars().all()
    return {
        "blocks": len(blocks), "rooms": len(rooms),
        "capacity": sum(r.capacity for r in rooms), "occupied": len(active),
        "available": max(0, sum(r.capacity for r in rooms) - len(active)),
        "today_present": sum(a.attendance_status == "present" for a in today_attendance),
        "today_leave": sum(a.attendance_status == "leave" for a in today_attendance),
        "today_absent": sum(a.attendance_status == "absent" for a in today_attendance),
    }


@router.get("/eligible-students")
async def eligible_students(
    grade_id: uuid.UUID = Query(...),
    section_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:read")),
):
    conditions = [
        Student.tenant_id == user.tenant_id, Student.grade_id == grade_id,
        Student.enrollment_status == "enrolled", Student.is_deleted.is_(False),
        Student.section_id.is_not(None),
    ]
    if section_id:
        conditions.append(Student.section_id == section_id)
    students = (await db.execute(select(Student).where(*conditions).order_by(
        Student.roll_no, Student.admission_no
    ))).scalars().all()
    allocated = {
        row[0] for row in (await db.execute(select(HostelAllocation.student_id).where(
            HostelAllocation.tenant_id == user.tenant_id,
            HostelAllocation.allocation_status == "allocated",
            HostelAllocation.is_deleted.is_(False),
        ))).all()
    }
    grades = {g.id: g.name for g in (await db.execute(select(Grade).where(
        Grade.tenant_id == user.tenant_id))).scalars().all()}
    sections = {s.id: s.name for s in (await db.execute(select(Section).where(
        Section.tenant_id == user.tenant_id))).scalars().all()}
    return [{
        "id": str(s.id), "admission_no": s.admission_no, "roll_no": s.roll_no,
        "name": f"{s.first_name} {s.last_name or ''}".strip(),
        "grade": grades.get(s.grade_id), "section": sections.get(s.section_id),
        "gender": s.gender, "already_allocated": s.id in allocated,
    } for s in students]


@router.get("/beds")
async def beds(
    room_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:read")),
):
    rooms = (await db.execute(select(HostelRoom).where(
        HostelRoom.tenant_id == user.tenant_id, HostelRoom.is_deleted.is_(False),
        *( [HostelRoom.id == room_id] if room_id else [] ),
    ))).scalars().all()
    result = []
    for room in rooms:
        block = await db.get(HostelBlock, room.block_id)
        for bed in await _ensure_beds(db, user, room):
            result.append({
                "id": str(bed.id), "room_id": str(room.id), "room": room.room_no,
                "block": block.name if block else None, "bed_no": bed.bed_no,
                "status": bed.bed_status,
            })
    return result


class TransferIn(BaseModel):
    room_id: uuid.UUID
    bed_id: uuid.UUID | None = None


@router.post("/allocations/{allocation_id}/transfer")
async def transfer(
    allocation_id: uuid.UUID,
    payload: TransferIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:update")),
):
    old = await db.get(HostelAllocation, allocation_id)
    room = await db.get(HostelRoom, payload.room_id)
    if not old or old.tenant_id != user.tenant_id or old.allocation_status != "allocated":
        raise HTTPException(404, "Active allocation not found")
    if not room or room.tenant_id != user.tenant_id or room.is_deleted:
        raise HTTPException(404, "Destination room not found")
    if room.occupied >= room.capacity:
        raise HTTPException(409, "Destination room is full")
    beds = await _ensure_beds(db, user, room)
    bed = await db.get(HostelBed, payload.bed_id) if payload.bed_id else next(
        (b for b in beds if b.bed_status == "available"), None
    )
    if not bed or bed.room_id != room.id or bed.bed_status != "available":
        raise HTTPException(409, "No available bed in destination room")
    old_room = await db.get(HostelRoom, old.room_id)
    old_bed = (await db.execute(select(HostelBed).where(
        HostelBed.current_allocation_id == old.id, HostelBed.is_deleted.is_(False)
    ))).scalars().first()
    if old_bed:
        old_bed.bed_status, old_bed.current_allocation_id = "available", None
    old.allocation_status, old.vacate_date = "transferred", date.today()
    if old_room and old_room.occupied:
        old_room.occupied -= 1
    new = HostelAllocation(
        tenant_id=user.tenant_id, student_id=old.student_id, room_id=room.id,
        allocation_date=date.today(), allocation_status="allocated",
        created_by=user.id, updated_by=user.id,
    )
    db.add(new)
    await db.flush()
    bed.bed_status, bed.current_allocation_id = "occupied", new.id
    room.occupied += 1
    await record_audit(db, action="transfer", entity="HostelAllocation", entity_id=new.id, actor=user)
    return {"id": str(new.id), "status": "allocated"}


class AttendanceIn(BaseModel):
    attendance_date: date = date.today()
    student_id: uuid.UUID
    attendance_status: str
    remarks: str | None = None


@router.get("/attendance")
async def list_attendance(
    attendance_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:read")),
):
    rows = (await db.execute(select(HostelAttendance).where(
        HostelAttendance.tenant_id == user.tenant_id,
        HostelAttendance.is_deleted.is_(False),
        *( [HostelAttendance.attendance_date == attendance_date] if attendance_date else [] ),
    ).order_by(HostelAttendance.attendance_date.desc()))).scalars().all()
    return [await _attendance_out(db, row) for row in rows]


async def _attendance_out(db, row):
    student = await db.get(Student, row.student_id)
    return {
        "id": str(row.id), "student_id": str(row.student_id),
        "student": f"{student.first_name} {student.last_name or ''}".strip() if student else "—",
        "date": row.attendance_date.isoformat(), "status": row.attendance_status,
        "remarks": row.remarks,
    }


@router.post("/attendance", status_code=status.HTTP_201_CREATED)
async def mark_attendance(
    payload: AttendanceIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:update")),
):
    if payload.attendance_status not in ("present", "leave", "absent"):
        raise HTTPException(422, "Status must be present, leave or absent")
    if not await _active_allocation(db, user.tenant_id, payload.student_id):
        raise HTTPException(409, "Student has no active hostel allocation")
    row = (await db.execute(select(HostelAttendance).where(
        HostelAttendance.tenant_id == user.tenant_id,
        HostelAttendance.student_id == payload.student_id,
        HostelAttendance.attendance_date == payload.attendance_date,
    ))).scalars().first()
    if not row:
        row = HostelAttendance(
            tenant_id=user.tenant_id, student_id=payload.student_id,
            attendance_date=payload.attendance_date, created_by=user.id, updated_by=user.id,
        )
        db.add(row)
    row.attendance_status, row.remarks, row.updated_by = payload.attendance_status, payload.remarks, user.id
    await db.flush()
    return await _attendance_out(db, row)


class VisitorIn(BaseModel):
    student_id: uuid.UUID
    visitor_name: str
    relation: str | None = None
    phone: str | None = None
    purpose: str | None = None


@router.get("/visitors")
async def visitors(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:read")),
):
    rows = (await db.execute(select(HostelVisitor).where(
        HostelVisitor.tenant_id == user.tenant_id, HostelVisitor.is_deleted.is_(False)
    ).order_by(HostelVisitor.check_in_at.desc()))).scalars().all()
    out = []
    for row in rows:
        student = await db.get(Student, row.student_id)
        out.append({
            "id": str(row.id), "student": f"{student.first_name} {student.last_name or ''}".strip(),
            "visitor_name": row.visitor_name, "relation": row.relation, "phone": row.phone,
            "purpose": row.purpose, "check_in_at": row.check_in_at.isoformat(),
            "check_out_at": row.check_out_at.isoformat() if row.check_out_at else None,
            "status": row.visitor_status,
        })
    return out


@router.post("/visitors", status_code=status.HTTP_201_CREATED)
async def check_in(
    payload: VisitorIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:create")),
):
    if not await _active_allocation(db, user.tenant_id, payload.student_id):
        raise HTTPException(409, "Student has no active hostel allocation")
    row = HostelVisitor(
        tenant_id=user.tenant_id, **payload.model_dump(), check_in_at=datetime.now(timezone.utc),
        created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    return {"id": str(row.id), "status": row.visitor_status}


@router.post("/visitors/{visitor_id}/checkout")
async def check_out(
    visitor_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:update")),
):
    row = await db.get(HostelVisitor, visitor_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "Visitor record not found")
    if row.visitor_status == "checked_out":
        raise HTTPException(409, "Visitor already checked out")
    row.visitor_status, row.check_out_at, row.updated_by = "checked_out", datetime.now(timezone.utc), user.id
    await db.flush()
    return {"id": str(row.id), "status": row.visitor_status}


class IncidentIn(BaseModel):
    student_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    incident_date: date = date.today()
    incident_type: str
    severity: str = "low"
    description: str
    action_taken: str | None = None


@router.get("/incidents")
async def incidents(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:read")),
):
    rows = (await db.execute(select(HostelIncident).where(
        HostelIncident.tenant_id == user.tenant_id, HostelIncident.is_deleted.is_(False)
    ).order_by(HostelIncident.incident_date.desc()))).scalars().all()
    return [{
        "id": str(r.id), "student_id": str(r.student_id) if r.student_id else None,
        "room_id": str(r.room_id) if r.room_id else None, "date": r.incident_date.isoformat(),
        "type": r.incident_type, "severity": r.severity, "description": r.description,
        "action_taken": r.action_taken, "status": r.incident_status,
    } for r in rows]


@router.post("/incidents", status_code=status.HTTP_201_CREATED)
async def create_incident(
    payload: IncidentIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:create")),
):
    row = HostelIncident(
        tenant_id=user.tenant_id, **payload.model_dump(), created_by=user.id, updated_by=user.id
    )
    db.add(row)
    await db.flush()
    return {"id": str(row.id), "status": row.incident_status}


class IncidentDecisionIn(BaseModel):
    status: str
    action_taken: str | None = None


@router.post("/incidents/{incident_id}/resolve")
async def resolve_incident(
    incident_id: uuid.UUID,
    payload: IncidentDecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:update")),
):
    row = await db.get(HostelIncident, incident_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "Incident not found")
    if payload.status not in ("investigating", "resolved", "closed"):
        raise HTTPException(422, "Invalid incident status")
    row.incident_status, row.action_taken, row.updated_by = payload.status, payload.action_taken, user.id
    await db.flush()
    return {"id": str(row.id), "status": row.incident_status}
