"""Student transfer, withdrawal, transfer-certificate and re-enrollment lifecycle."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import AcademicYear, Grade, Section
from app.models.fees import Invoice
from app.models.hostel import HostelAllocation, HostelBed, HostelRoom
from app.models.library import BookIssue
from app.models.operations import AssetAssignment
from app.models.people import Student
from app.models.student_records import StudentLifecycleRequest
from app.models.transport import StudentTransportAssignment

router = APIRouter(prefix="/student-lifecycle", tags=["Student lifecycle"])


class RequestIn(BaseModel):
    student_id: uuid.UUID
    request_type: str
    effective_date: date
    reason: str = Field(min_length=3, max_length=2000)
    destination_school: str | None = Field(default=None, max_length=255)
    target_grade_id: uuid.UUID | None = None
    target_section_id: uuid.UUID | None = None


class DecisionIn(BaseModel):
    remarks: str | None = Field(default=None, max_length=2000)
    override_clearance: bool = False


async def _case(db: AsyncSession, tid: uuid.UUID, case_id: uuid.UUID) -> StudentLifecycleRequest:
    row = await db.get(StudentLifecycleRequest, case_id)
    if not row or row.tenant_id != tid or row.is_deleted:
        raise HTTPException(404, "Student lifecycle request not found")
    return row


async def _clearance(db: AsyncSession, tid: uuid.UUID, student_id: uuid.UUID) -> dict:
    invoices = (await db.execute(select(Invoice).where(
        Invoice.tenant_id == tid, Invoice.student_id == student_id, Invoice.is_deleted.is_(False)
    ))).scalars().all()
    fee_balance = sum(
        (invoice.net_amount or Decimal(0)) - (invoice.paid_amount or Decimal(0))
        for invoice in invoices
    )
    books = (await db.execute(select(func.count()).select_from(BookIssue).where(
        BookIssue.tenant_id == tid, BookIssue.student_id == student_id,
        BookIssue.issue_status == "issued", BookIssue.is_deleted.is_(False),
    ))).scalar_one()
    assets = (await db.execute(select(func.count()).select_from(AssetAssignment).where(
        AssetAssignment.tenant_id == tid, AssetAssignment.student_id == student_id,
        AssetAssignment.assignment_status == "issued", AssetAssignment.is_deleted.is_(False),
    ))).scalar_one()
    hostel = (await db.execute(select(func.count()).select_from(HostelAllocation).where(
        HostelAllocation.tenant_id == tid, HostelAllocation.student_id == student_id,
        HostelAllocation.allocation_status == "allocated", HostelAllocation.is_deleted.is_(False),
    ))).scalar_one()
    blockers = []
    if fee_balance > 0:
        blockers.append(f"Outstanding fee balance: {fee_balance}")
    if books:
        blockers.append(f"{books} library book(s) not returned")
    if assets:
        blockers.append(f"{assets} school asset(s) not returned")
    if hostel:
        blockers.append("Active hostel allocation")
    return {
        "fee_balance": str(fee_balance),
        "library_books": books,
        "assets": assets,
        "hostel_allocations": hostel,
        "clear": not blockers,
        "blockers": blockers,
        "checked_on": datetime.utcnow().isoformat(),
    }


async def _out(db: AsyncSession, row: StudentLifecycleRequest) -> dict:
    student = await db.get(Student, row.student_id)
    grade = await db.get(Grade, row.target_grade_id) if row.target_grade_id else None
    section = await db.get(Section, row.target_section_id) if row.target_section_id else None
    return {
        "id": str(row.id), "student_id": str(row.student_id),
        "student": f"{student.first_name} {student.last_name or ''}".strip() if student else "—",
        "admission_no": student.admission_no if student else None,
        "request_no": row.request_no, "request_type": row.request_type,
        "status": row.request_status, "effective_date": row.effective_date.isoformat(),
        "reason": row.reason, "destination_school": row.destination_school,
        "target_grade": grade.name if grade else None,
        "target_section": section.name if section else None,
        "clearance": row.clearance_snapshot, "approval_remarks": row.approval_remarks,
        "certificate_no": row.certificate_no,
        "certificate": row.certificate_snapshot,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.get("")
async def list_requests(
    student_id: uuid.UUID | None = None,
    request_status: str | None = Query(default=None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:read")),
):
    conditions = [
        StudentLifecycleRequest.tenant_id == user.tenant_id,
        StudentLifecycleRequest.is_deleted.is_(False),
    ]
    if student_id:
        conditions.append(StudentLifecycleRequest.student_id == student_id)
    if request_status:
        conditions.append(StudentLifecycleRequest.request_status == request_status)
    rows = (await db.execute(select(StudentLifecycleRequest).where(*conditions).order_by(
        StudentLifecycleRequest.created_at.desc()
    ))).scalars().all()
    return [await _out(db, row) for row in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: RequestIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:update")),
):
    if payload.request_type not in ("transfer", "withdrawal", "reenrollment"):
        raise HTTPException(422, "Type must be transfer, withdrawal or reenrollment")
    student = await db.get(Student, payload.student_id)
    if not student or student.tenant_id != user.tenant_id or student.is_deleted:
        raise HTTPException(404, "Student not found")
    if payload.request_type == "reenrollment":
        if student.enrollment_status not in ("transferred", "dropped", "graduated"):
            raise HTTPException(409, "Only an inactive student can be re-enrolled")
        if not payload.target_grade_id or not payload.target_section_id:
            raise HTTPException(422, "Target class and section are required for re-enrollment")
    elif student.enrollment_status not in ("enrolled", "promoted"):
        raise HTTPException(409, "Only an active student can be transferred or withdrawn")
    open_case = (await db.execute(select(StudentLifecycleRequest).where(
        StudentLifecycleRequest.tenant_id == user.tenant_id,
        StudentLifecycleRequest.student_id == student.id,
        StudentLifecycleRequest.request_status.in_(("draft", "submitted", "approved")),
        StudentLifecycleRequest.is_deleted.is_(False),
    ))).scalars().first()
    if open_case:
        raise HTTPException(409, f"Open lifecycle request {open_case.request_no} already exists")
    count = (await db.execute(select(func.count()).select_from(StudentLifecycleRequest).where(
        StudentLifecycleRequest.tenant_id == user.tenant_id
    ))).scalar_one()
    row = StudentLifecycleRequest(
        tenant_id=user.tenant_id, student_id=student.id,
        request_no=f"SLR-{date.today().year}-{count + 1:05d}",
        request_type=payload.request_type, effective_date=payload.effective_date,
        reason=payload.reason.strip(), destination_school=payload.destination_school,
        target_grade_id=payload.target_grade_id, target_section_id=payload.target_section_id,
        created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(db, action="create", entity="StudentLifecycleRequest", entity_id=row.id, actor=user)
    return await _out(db, row)


@router.post("/{case_id}/submit")
async def submit_request(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:update")),
):
    row = await _case(db, user.tenant_id, case_id)
    if row.request_status != "draft":
        raise HTTPException(409, "Only a draft request can be submitted")
    row.clearance_snapshot = await _clearance(db, user.tenant_id, row.student_id)
    row.request_status = "submitted"
    row.updated_by = user.id
    await record_audit(db, action="submit", entity="StudentLifecycleRequest", entity_id=row.id, actor=user,
                       changes={"clearance": row.clearance_snapshot})
    return await _out(db, row)


@router.post("/{case_id}/approve")
async def approve_request(
    case_id: uuid.UUID,
    payload: DecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:approve")),
):
    row = await _case(db, user.tenant_id, case_id)
    if row.request_status != "submitted":
        raise HTTPException(409, "Only a submitted request can be approved")
    clearance = await _clearance(db, user.tenant_id, row.student_id)
    if not clearance["clear"] and not payload.override_clearance:
        raise HTTPException(409, {"message": "Clearance is incomplete", "blockers": clearance["blockers"]})
    row.clearance_snapshot = clearance
    row.override_clearance = payload.override_clearance
    row.approval_remarks = payload.remarks
    row.approved_by = user.id
    row.approved_on = date.today()
    row.request_status = "approved"
    row.updated_by = user.id
    await record_audit(db, action="approve", entity="StudentLifecycleRequest", entity_id=row.id, actor=user,
                       changes={"override_clearance": payload.override_clearance, "remarks": payload.remarks})
    return await _out(db, row)


@router.post("/{case_id}/reject")
async def reject_request(
    case_id: uuid.UUID,
    payload: DecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:approve")),
):
    row = await _case(db, user.tenant_id, case_id)
    if row.request_status not in ("submitted", "approved"):
        raise HTTPException(409, "Only a submitted or approved request can be rejected")
    row.request_status, row.approval_remarks, row.updated_by = "rejected", payload.remarks, user.id
    await record_audit(db, action="reject", entity="StudentLifecycleRequest", entity_id=row.id, actor=user)
    return await _out(db, row)


@router.post("/{case_id}/cancel")
async def cancel_request(
    case_id: uuid.UUID,
    payload: DecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:update")),
):
    row = await _case(db, user.tenant_id, case_id)
    if row.request_status not in ("draft", "submitted"):
        raise HTTPException(409, "Only a draft or submitted request can be cancelled")
    row.request_status, row.approval_remarks, row.updated_by = "cancelled", payload.remarks, user.id
    await record_audit(db, action="cancel", entity="StudentLifecycleRequest", entity_id=row.id, actor=user)
    return await _out(db, row)


@router.post("/{case_id}/complete")
async def complete_request(
    case_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:approve")),
):
    row = await _case(db, user.tenant_id, case_id)
    if row.request_status != "approved":
        raise HTTPException(409, "Only an approved request can be completed")
    student = await db.get(Student, row.student_id)
    if not student or student.tenant_id != user.tenant_id:
        raise HTTPException(404, "Student not found")
    old_grade, old_section = student.grade_id, student.section_id
    if row.request_type == "reenrollment":
        grade, section = await db.get(Grade, row.target_grade_id), await db.get(Section, row.target_section_id)
        if not grade or not section or grade.tenant_id != user.tenant_id or section.tenant_id != user.tenant_id:
            raise HTTPException(409, "Target class or section is unavailable")
        if section.grade_id != grade.id:
            raise HTTPException(409, "Target section does not belong to target class")
        student.grade_id, student.section_id, student.enrollment_status = grade.id, section.id, "enrolled"
    else:
        student.enrollment_status = "transferred" if row.request_type == "transfer" else "dropped"
        student.grade_id, student.section_id = None, None
        active_hostel = (await db.execute(select(HostelAllocation).where(
            HostelAllocation.tenant_id == user.tenant_id,
            HostelAllocation.student_id == student.id,
            HostelAllocation.allocation_status == "allocated",
            HostelAllocation.is_deleted.is_(False),
        ))).scalars().all()
        for allocation in active_hostel:
            allocation.allocation_status, allocation.vacate_date = "vacated", row.effective_date
            room = await db.get(HostelRoom, allocation.room_id)
            if room and room.occupied:
                room.occupied -= 1
            bed = (await db.execute(select(HostelBed).where(
                HostelBed.current_allocation_id == allocation.id,
                HostelBed.is_deleted.is_(False),
            ))).scalars().first()
            if bed:
                bed.bed_status, bed.current_allocation_id = "available", None
        transports = (await db.execute(select(StudentTransportAssignment).where(
            StudentTransportAssignment.tenant_id == user.tenant_id,
            StudentTransportAssignment.student_id == student.id,
            StudentTransportAssignment.assignment_status == "active",
            StudentTransportAssignment.is_deleted.is_(False),
        ))).scalars().all()
        for assignment in transports:
            assignment.assignment_status = "inactive"

    year = await db.get(AcademicYear, student.academic_year_id) if student.academic_year_id else None
    grade = await db.get(Grade, old_grade) if old_grade else None
    section = await db.get(Section, old_section) if old_section else None
    if row.request_type in ("transfer", "withdrawal"):
        count = (await db.execute(select(func.count()).select_from(StudentLifecycleRequest).where(
            StudentLifecycleRequest.tenant_id == user.tenant_id,
            StudentLifecycleRequest.certificate_no.is_not(None),
        ))).scalar_one()
        row.certificate_no = f"TC-{date.today().year}-{count + 1:05d}"
        row.certificate_snapshot = {
            "certificate_no": row.certificate_no, "issued_on": date.today().isoformat(),
            "student_name": f"{student.first_name} {student.last_name or ''}".strip(),
            "admission_no": student.admission_no,
            "date_of_birth": student.date_of_birth.isoformat() if student.date_of_birth else None,
            "academic_year": year.name if year else None,
            "last_class": grade.name if grade else None,
            "last_section": section.name if section else None,
            "effective_date": row.effective_date.isoformat(),
            "reason": row.reason, "destination_school": row.destination_school,
            "conduct": "Good", "dues_cleared": bool(row.clearance_snapshot and row.clearance_snapshot.get("clear")),
        }
    row.request_status, row.completed_on, row.updated_by = "completed", date.today(), user.id
    await record_audit(db, action="complete", entity="StudentLifecycleRequest", entity_id=row.id, actor=user,
                       changes={"student_status": student.enrollment_status, "certificate_no": row.certificate_no})
    return await _out(db, row)
