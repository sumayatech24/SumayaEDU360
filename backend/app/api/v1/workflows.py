"""Cross-module workflow lifecycle endpoints (state transitions & domain actions).

These are the verbs that make modules "complete": advancing an admission through its
pipeline, converting a lead to a student, issuing/returning a library book with fine
calculation, allocating/vacating a hostel room, and approving leave / running payroll.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import Grade, Section
from app.models.admissions import AdmissionLead
from app.models.hostel import HostelAllocation, HostelBed, HostelBlock, HostelRoom
from app.models.hr import LeaveRequest, Payroll
from app.models.library import BookIssue, LibraryBook
from app.models.people import Employee, Student

router = APIRouter(tags=["Workflows"])

# =============================================================== Admissions pipeline
ADMISSION_STAGES = [
    "inquiry", "counseling", "entrance_test", "document_collection", "approved", "enrolled", "rejected",
]


class StageIn(BaseModel):
    stage: str
    notes: str | None = None
    test_score: str | None = None


@router.post("/admissions/leads/{lead_id}/advance")
async def advance_lead(
    lead_id: uuid.UUID,
    payload: StageIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:update")),
):
    if payload.stage not in ADMISSION_STAGES:
        raise HTTPException(422, f"Invalid stage. Allowed: {', '.join(ADMISSION_STAGES)}")
    lead = await db.get(AdmissionLead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.is_deleted:
        raise HTTPException(404, "Lead not found")
    prev = lead.stage
    lead.stage = payload.stage
    if payload.notes:
        lead.notes = payload.notes
    if payload.test_score:
        lead.test_score = payload.test_score
    lead.updated_by = user.id
    await db.flush()
    await record_audit(db, action="advance", entity="AdmissionLead", entity_id=lead.id, actor=user,
                       changes={"from": prev, "to": payload.stage})
    return {"id": str(lead.id), "stage": lead.stage, "previous_stage": prev}


@router.post("/admissions/leads/{lead_id}/convert")
async def convert_lead(
    lead_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:create")),
):
    """Convert an approved admission lead into an enrolled Student record."""
    lead = await db.get(AdmissionLead, lead_id)
    if not lead or lead.tenant_id != user.tenant_id or lead.is_deleted:
        raise HTTPException(404, "Lead not found")
    if lead.converted_student_id:
        raise HTTPException(409, "Lead already converted")

    count = (
        await db.execute(select(func.count()).select_from(Student).where(Student.tenant_id == user.tenant_id))
    ).scalar_one()
    parts = lead.student_name.strip().split(" ", 1)
    student = Student(
        tenant_id=user.tenant_id,
        admission_no=f"ADM{date.today().year}{count + 1:04d}",
        first_name=parts[0],
        last_name=parts[1] if len(parts) > 1 else None,
        grade_id=lead.grade_applied_id,
        phone=lead.phone,
        email=lead.email,
        enrollment_status="enrolled",
        admission_date=date.today(),
        # Carry over the application details captured during admission.
        date_of_birth=lead.date_of_birth,
        gender=lead.gender,
        category=lead.category,
        religion=lead.religion,
        nationality=lead.nationality,
        address=lead.address,
        city=lead.city,
        state=lead.state,
        pincode=lead.pincode,
        previous_school=lead.previous_school,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(student)
    await db.flush()

    # Create guardian records from the application's parent details.
    from app.models.people import Guardian

    for relation, name, phone in [("father", lead.father_name, lead.father_phone),
                                  ("mother", lead.mother_name, lead.mother_phone)]:
        if name:
            db.add(Guardian(
                tenant_id=user.tenant_id, student_id=student.id, relation=relation,
                full_name=name, phone=phone, is_primary=(relation == "father"),
                created_by=user.id, updated_by=user.id,
            ))

    lead.converted_student_id = student.id
    lead.stage = "enrolled"
    lead.updated_by = user.id
    await record_audit(db, action="convert", entity="AdmissionLead", entity_id=lead.id, actor=user,
                       changes={"student_id": str(student.id)})
    return {"lead_id": str(lead.id), "student_id": str(student.id), "admission_no": student.admission_no}


# =============================================================== Library issue / return
class IssueIn(BaseModel):
    book_id: uuid.UUID
    student_id: uuid.UUID
    days: int = 14


FINE_PER_DAY = Decimal("2")


@router.post("/library/issues")
async def issue_book(
    payload: IssueIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:create")),
):
    book = await db.get(LibraryBook, payload.book_id)
    if not book or book.tenant_id != user.tenant_id or book.is_deleted:
        raise HTTPException(404, "Book not found")
    if book.available_copies < 1:
        raise HTTPException(409, "No copies available")
    student = await db.get(Student, payload.student_id)
    if not student or student.tenant_id != user.tenant_id:
        raise HTTPException(404, "Student not found")

    from datetime import timedelta

    issue = BookIssue(
        tenant_id=user.tenant_id, book_id=book.id, student_id=student.id,
        issue_date=date.today(), due_date=date.today() + timedelta(days=payload.days),
        issue_status="issued", created_by=user.id, updated_by=user.id,
    )
    book.available_copies -= 1
    db.add(issue)
    await db.flush()
    await record_audit(db, action="issue", entity="BookIssue", entity_id=issue.id, actor=user,
                       changes={"book_id": str(book.id), "student_id": str(student.id)})
    return {"id": str(issue.id), "due_date": issue.due_date.isoformat(), "book_available": book.available_copies}


@router.post("/library/issues/{issue_id}/return")
async def return_book(
    issue_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:update")),
):
    issue = await db.get(BookIssue, issue_id)
    if not issue or issue.tenant_id != user.tenant_id or issue.is_deleted:
        raise HTTPException(404, "Issue not found")
    if issue.issue_status == "returned":
        raise HTTPException(409, "Already returned")

    issue.return_date = date.today()
    overdue_days = max(0, (issue.return_date - issue.due_date).days)
    issue.fine_amount = FINE_PER_DAY * overdue_days
    issue.issue_status = "returned"
    issue.updated_by = user.id

    book = await db.get(LibraryBook, issue.book_id)
    if book:
        book.available_copies += 1
    await db.flush()
    await record_audit(db, action="return", entity="BookIssue", entity_id=issue.id, actor=user,
                       changes={"overdue_days": overdue_days, "fine": str(issue.fine_amount)})
    return {"id": str(issue.id), "overdue_days": overdue_days, "fine_amount": str(issue.fine_amount)}


@router.get("/library/issues")
async def list_issues(
    only_open: bool = False,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:read")),
):
    conds = [BookIssue.tenant_id == user.tenant_id, BookIssue.is_deleted.is_(False)]
    if only_open:
        conds.append(BookIssue.issue_status != "returned")
    rows = (await db.execute(select(BookIssue).where(*conds).order_by(BookIssue.created_at.desc()))).scalars().all()
    out = []
    for i in rows:
        book = await db.get(LibraryBook, i.book_id)
        student = await db.get(Student, i.student_id)
        out.append({
            "id": str(i.id), "book_id": str(i.book_id), "book": book.title if book else None,
            "student_id": str(i.student_id),
            "student": f"{student.first_name} {student.last_name or ''}".strip() if student else None,
            "issue_date": i.issue_date.isoformat(), "due_date": i.due_date.isoformat(),
            "return_date": i.return_date.isoformat() if i.return_date else None,
            "status": (
                "overdue" if i.issue_status == "issued" and i.due_date < date.today()
                else i.issue_status
            ),
            "fine_amount": str(i.fine_amount), "renew_count": i.renew_count,
        })
    return out


# =============================================================== Hostel allocation
class AllocateIn(BaseModel):
    student_id: uuid.UUID
    room_id: uuid.UUID
    bed_id: uuid.UUID | None = None


@router.post("/hostel/allocations")
async def allocate_room(
    payload: AllocateIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:create")),
):
    room = await db.get(HostelRoom, payload.room_id)
    if not room or room.tenant_id != user.tenant_id or room.is_deleted:
        raise HTTPException(404, "Room not found")
    student = await db.get(Student, payload.student_id)
    if not student or student.tenant_id != user.tenant_id or student.is_deleted:
        raise HTTPException(404, "Student not found")
    if not student.grade_id or not student.section_id:
        raise HTTPException(409, "Assign the student to a class and section before hostel allocation")
    existing = (await db.execute(select(HostelAllocation).where(
        HostelAllocation.tenant_id == user.tenant_id,
        HostelAllocation.student_id == student.id,
        HostelAllocation.allocation_status == "allocated",
        HostelAllocation.is_deleted.is_(False),
    ))).scalars().first()
    if existing:
        raise HTTPException(409, "Student already has an active hostel allocation")
    if room.occupied >= room.capacity:
        raise HTTPException(409, "Room is full")
    block = await db.get(HostelBlock, room.block_id)
    if block and student.gender:
        gender = student.gender.lower()
        if block.block_type == "boys" and gender not in ("male", "boy", "boys"):
            raise HTTPException(409, "Student gender does not match the boys hostel block")
        if block.block_type == "girls" and gender not in ("female", "girl", "girls"):
            raise HTTPException(409, "Student gender does not match the girls hostel block")
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
    bed = await db.get(HostelBed, payload.bed_id) if payload.bed_id else next(
        (b for b in beds if b.bed_status == "available"), None
    )
    if not bed or bed.room_id != room.id or bed.bed_status != "available":
        raise HTTPException(409, "No available bed in this room")
    alloc = HostelAllocation(
        tenant_id=user.tenant_id, student_id=payload.student_id, room_id=room.id,
        allocation_date=date.today(), allocation_status="allocated",
        created_by=user.id, updated_by=user.id,
    )
    room.occupied += 1
    db.add(alloc)
    await db.flush()
    bed.bed_status = "occupied"
    bed.current_allocation_id = alloc.id
    await record_audit(db, action="allocate", entity="HostelAllocation", entity_id=alloc.id, actor=user)
    return {
        "id": str(alloc.id), "bed_id": str(bed.id), "bed_no": bed.bed_no,
        "room_occupied": room.occupied, "room_capacity": room.capacity,
    }


@router.get("/hostel/allocations")
async def list_allocations(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:read")),
):
    rows = (
        await db.execute(select(HostelAllocation).where(
            HostelAllocation.tenant_id == user.tenant_id, HostelAllocation.is_deleted.is_(False))
            .order_by(HostelAllocation.created_at.desc()))
    ).scalars().all()
    out = []
    for a in rows:
        room = await db.get(HostelRoom, a.room_id)
        block = await db.get(HostelBlock, room.block_id) if room else None
        student = await db.get(Student, a.student_id)
        grade = await db.get(Grade, student.grade_id) if student and student.grade_id else None
        section = await db.get(Section, student.section_id) if student and student.section_id else None
        bed = (await db.execute(select(HostelBed).where(
            HostelBed.current_allocation_id == a.id, HostelBed.is_deleted.is_(False)
        ))).scalars().first()
        out.append({
            "id": str(a.id),
            "student_id": str(a.student_id),
            "student": f"{student.first_name} {student.last_name or ''}".strip() if student else None,
            "admission_no": student.admission_no if student else None,
            "grade": grade.name if grade else None,
            "section": section.name if section else None,
            "room": room.room_no if room else None,
            "room_id": str(room.id) if room else None,
            "block": block.name if block else None,
            "bed": bed.bed_no if bed else None,
            "allocation_date": a.allocation_date.isoformat() if a.allocation_date else None,
            "status": a.allocation_status,
        })
    return out


@router.post("/hostel/allocations/{alloc_id}/vacate")
async def vacate_room(
    alloc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("hostel:update")),
):
    alloc = await db.get(HostelAllocation, alloc_id)
    if not alloc or alloc.tenant_id != user.tenant_id or alloc.is_deleted:
        raise HTTPException(404, "Allocation not found")
    if alloc.allocation_status == "vacated":
        raise HTTPException(409, "Already vacated")
    alloc.allocation_status = "vacated"
    alloc.vacate_date = date.today()
    alloc.updated_by = user.id
    room = await db.get(HostelRoom, alloc.room_id)
    if room and room.occupied > 0:
        room.occupied -= 1
    bed = (await db.execute(select(HostelBed).where(
        HostelBed.current_allocation_id == alloc.id, HostelBed.is_deleted.is_(False)
    ))).scalars().first()
    if bed:
        bed.bed_status = "available"
        bed.current_allocation_id = None
    await db.flush()
    await record_audit(db, action="vacate", entity="HostelAllocation", entity_id=alloc.id, actor=user)
    return {"id": str(alloc.id), "status": "vacated"}


# =============================================================== HR leave / payroll
class LeaveIn(BaseModel):
    employee_id: uuid.UUID
    leave_type: str | None = None
    from_date: date
    to_date: date
    reason: str | None = None


@router.post("/hr/leave-requests")
async def apply_leave(
    payload: LeaveIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("employee_hrms:create")),
):
    if payload.to_date < payload.from_date:
        raise HTTPException(422, "to_date cannot precede from_date")
    days = (payload.to_date - payload.from_date).days + 1
    req = LeaveRequest(
        tenant_id=user.tenant_id, employee_id=payload.employee_id, leave_type=payload.leave_type,
        from_date=payload.from_date, to_date=payload.to_date, days=days, reason=payload.reason,
        request_status="applied", created_by=user.id, updated_by=user.id,
    )
    db.add(req)
    await db.flush()
    await record_audit(db, action="apply_leave", entity="LeaveRequest", entity_id=req.id, actor=user)
    return {"id": str(req.id), "days": days, "status": req.request_status}


class LeaveDecision(BaseModel):
    decision: str  # approved / rejected


@router.post("/hr/leave-requests/{req_id}/decide")
async def decide_leave(
    req_id: uuid.UUID,
    payload: LeaveDecision,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("employee_hrms:approve")),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be approved or rejected")
    req = await db.get(LeaveRequest, req_id)
    if not req or req.tenant_id != user.tenant_id or req.is_deleted:
        raise HTTPException(404, "Leave request not found")
    req.request_status = payload.decision
    req.approver_id = user.id
    req.decided_at = date.today()
    req.updated_by = user.id
    await db.flush()
    await record_audit(db, action=payload.decision, entity="LeaveRequest", entity_id=req.id, actor=user)
    return {"id": str(req.id), "status": req.request_status}


class PayrollIn(BaseModel):
    employee_id: uuid.UUID
    month: int
    year: int
    allowances: Decimal = Decimal(0)
    deductions: Decimal = Decimal(0)


@router.post("/hr/payroll/generate")
async def generate_payroll(
    payload: PayrollIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("employee_hrms:create")),
):
    emp = await db.get(Employee, payload.employee_id)
    if not emp or emp.tenant_id != user.tenant_id or emp.is_deleted:
        raise HTTPException(404, "Employee not found")
    existing = (
        await db.execute(select(Payroll).where(
            Payroll.tenant_id == user.tenant_id, Payroll.employee_id == emp.id,
            Payroll.month == payload.month, Payroll.year == payload.year, Payroll.is_deleted.is_(False)))
    ).scalars().first()
    if existing:
        raise HTTPException(409, "Payroll already generated for this period")
    basic = emp.salary or Decimal(0)
    net = basic + payload.allowances - payload.deductions
    pr = Payroll(
        tenant_id=user.tenant_id, employee_id=emp.id, month=payload.month, year=payload.year,
        basic=basic, allowances=payload.allowances, deductions=payload.deductions, net_pay=net,
        payroll_status="finalized", created_by=user.id, updated_by=user.id,
    )
    db.add(pr)
    await db.flush()
    await record_audit(db, action="generate_payroll", entity="Payroll", entity_id=pr.id, actor=user,
                       changes={"period": f"{payload.month}/{payload.year}", "net": str(net)})
    return {"id": str(pr.id), "net_pay": str(net), "status": pr.payroll_status}


@router.get("/hr/payroll")
async def list_payroll(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("employee_hrms:read")),
):
    rows = (
        await db.execute(select(Payroll).where(Payroll.tenant_id == user.tenant_id, Payroll.is_deleted.is_(False))
                         .order_by(Payroll.year.desc(), Payroll.month.desc()))
    ).scalars().all()
    out = []
    for p in rows:
        emp = await db.get(Employee, p.employee_id)
        out.append({
            "id": str(p.id), "employee": f"{emp.first_name} {emp.last_name or ''}".strip() if emp else None,
            "month": p.month, "year": p.year, "basic": str(p.basic), "net_pay": str(p.net_pay),
            "status": p.payroll_status,
        })
    return out
