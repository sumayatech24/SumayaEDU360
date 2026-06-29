"""Per-persona portals.

Resolves which portal a signed-in user belongs to (student / parent / teacher / admin)
and serves self-scoped dashboard data that does NOT require module-level RBAC — a student
or parent can always see their own child's data, a teacher their teaching summary.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.reporting import student_360
from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.academic import AcademicYear, Grade, Section, Subject
from app.models.academics_ops import CurriculumPlan, Homework, HomeworkSubmission, TimetablePeriod
from app.models.attendance import Attendance
from app.models.auth import User
from app.models.content import LearningResource, PtmMeeting
from app.models.engagement import Complaint
from app.models.exams import Exam, ExamSubject, Marks, MarksBatch
from app.models.operations import (
    Activity, ActivityRegistration, Announcement, Facility, FacilityBooking,
)
from app.models.people import Employee, Student, TeacherAssignment, TeacherProfile

router = APIRouter(prefix="/portal", tags=["Portals"])


class HomeworkSubmitIn(BaseModel):
    content: str


class GradeIn(BaseModel):
    marks_awarded: float
    remarks: str | None = None


class AttEntry(BaseModel):
    student_id: uuid.UUID
    state: str = "present"


class BulkAttIn(BaseModel):
    att_date: date
    entries: list[AttEntry]


class HomeworkCreateIn(BaseModel):
    title: str
    subject_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    assigned_date: date | None = None
    due_date: date | None = None
    description: str | None = None
    max_marks: float = 10


class TopicIn(BaseModel):
    name: str
    weeks: str | None = None
    hours: float | None = None
    status: str = "pending"  # pending / in_progress / done


class PlanIn(BaseModel):
    title: str
    term: str = "Quarter 1"
    academic_year_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    subject_id: uuid.UUID | None = None
    objectives: str | None = None
    resources: str | None = None
    topics: list[TopicIn] = []


class PlanSubmitIn(BaseModel):
    reviewer_id: uuid.UUID | None = None


class PlanReviewIn(BaseModel):
    decision: str  # approved / rejected
    review_note: str | None = None


class TeacherMarkEntryIn(BaseModel):
    student_id: uuid.UUID
    marks_obtained: Decimal | None = None
    is_absent: bool = False
    remarks: str | None = None


class TeacherMarkSheetIn(BaseModel):
    assignment_id: uuid.UUID
    exam_id: uuid.UUID
    entries: list[TeacherMarkEntryIn]


class MarksReviewIn(BaseModel):
    decision: str
    review_note: str | None = None


class ResultRuleIn(BaseModel):
    pass_marks: Decimal


def portal_for(roles: list[str], is_super: bool) -> str:
    if is_super:
        return "admin"
    if "student" in roles:
        return "student"
    if "parent" in roles:
        return "parent"
    if "teacher" in roles:
        return "teacher"
    if "principal" in roles or "vice_principal" in roles:
        return "principal"
    return "admin"  # accountant, librarian, ... use the admin shell (RBAC-filtered)


async def _announcements(db: AsyncSession, tid: uuid.UUID, audience: str | None = None) -> list[dict]:
    conds = [Announcement.tenant_id == tid, Announcement.is_deleted.is_(False),
             Announcement.announcement_status == "published"]
    rows = (
        await db.execute(select(Announcement).where(*conds).order_by(Announcement.created_at.desc()).limit(10))
    ).scalars().all()
    out = []
    for a in rows:
        if audience and a.audience not in ("all", audience):
            continue
        out.append({"title": a.title, "body": a.body, "audience": a.audience,
                    "date": a.publish_date.isoformat() if a.publish_date else None})
    return out


async def _linked_student_id(db: AsyncSession, user: CurrentUser) -> uuid.UUID:
    db_user = await db.get(User, user.id)
    if not db_user or not db_user.person_id or db_user.person_type != "student":
        raise HTTPException(404, "No student linked to this account")
    return db_user.person_id


async def _linked_employee_id(db: AsyncSession, user: CurrentUser) -> uuid.UUID:
    db_user = await db.get(User, user.id)
    if not db_user or not db_user.person_id or db_user.person_type != "employee":
        raise HTTPException(404, "No employee linked to this account")
    return db_user.person_id


async def _name_maps(db: AsyncSession, tid: uuid.UUID):
    async def collect(model, label):
        rows = (await db.execute(select(model).where(
            model.tenant_id == tid, model.is_deleted.is_(False)
        ))).scalars().all()
        return {r.id: label(r) for r in rows}

    return {
        "grades": await collect(Grade, lambda g: g.name),
        "sections": await collect(Section, lambda s: s.name),
        "subjects": await collect(Subject, lambda s: s.name),
    }


@router.get("/context")
async def context(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    db_user = await db.get(User, user.id)
    portal = portal_for(user.roles, user.is_superadmin)
    return {
        "portal": portal,
        "name": user.full_name,
        "email": user.email,
        "roles": user.roles,
        "is_superadmin": user.is_superadmin,
        "person_type": db_user.person_type,
        "person_id": str(db_user.person_id) if db_user.person_id else None,
    }


@router.get("/announcements")
async def my_announcements(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    portal = portal_for(user.roles, user.is_superadmin)
    audience = {"student": "students", "parent": "parents", "teacher": "teachers"}.get(portal)
    return await _announcements(db, user.tenant_id, audience)


@router.get("/student/dashboard")
async def student_dashboard(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Self-scoped 360 for a student or a parent (their linked child).

    Fee visibility differs by persona: a student only sees whether fees are pending
    (not the full ledger); a parent sees the full ledger, payments and can download
    receipts. Remarks flagged not-visible-to-parent are hidden from parents.
    """
    student_id = await _linked_student_id(db, user)
    is_parent = "parent" in user.roles
    data = await student_360(str(student_id), db, user)
    data["announcements"] = await _announcements(db, user.tenant_id,
                                                  "parents" if is_parent else "students")
    data["persona"] = "parent" if is_parent else "student"

    if not is_parent:
        # Student: only a pending-due signal, no amounts/ledger.
        balance = float(data["fees"]["balance"])
        data["fees"] = {"pending": balance > 0, "balance": data["fees"]["balance"]}
        data["invoices"] = []
        data["payments"] = []
    else:
        data["fees"]["pending"] = float(data["fees"]["balance"]) > 0
        data["remarks"] = [r for r in data["remarks"] if r.get("visible_to_parent", True)]

    return data


@router.get("/student/homework")
async def student_homework(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    student_id = await _linked_student_id(db, user)
    student = await db.get(Student, student_id)
    if not student or student.tenant_id != user.tenant_id or student.is_deleted:
        raise HTTPException(404, "Student not found")

    maps = await _name_maps(db, user.tenant_id)
    conditions = [
        Homework.tenant_id == user.tenant_id,
        Homework.is_deleted.is_(False),
        Homework.homework_status == "assigned",
    ]
    if student.grade_id:
        conditions.append((Homework.grade_id == student.grade_id) | (Homework.grade_id.is_(None)))
    homeworks = (await db.execute(
        select(Homework).where(*conditions).order_by(Homework.due_date.asc(), Homework.created_at.desc())
    )).scalars().all()

    submissions = (await db.execute(select(HomeworkSubmission).where(
        HomeworkSubmission.tenant_id == user.tenant_id,
        HomeworkSubmission.student_id == student_id,
        HomeworkSubmission.is_deleted.is_(False),
    ))).scalars().all()
    by_homework = {s.homework_id: s for s in submissions}

    return [
        {
            "id": str(hw.id),
            "title": hw.title,
            "description": hw.description,
            "subject": maps["subjects"].get(hw.subject_id, "General"),
            "grade": maps["grades"].get(hw.grade_id, "All grades"),
            "section": maps["sections"].get(hw.section_id, "All sections"),
            "assigned_date": hw.assigned_date.isoformat() if hw.assigned_date else None,
            "due_date": hw.due_date.isoformat() if hw.due_date else None,
            "max_marks": str(hw.max_marks),
            "submission": (
                {
                    "id": str(by_homework[hw.id].id),
                    "status": by_homework[hw.id].submission_status,
                    "submitted_date": by_homework[hw.id].submitted_date.isoformat()
                    if by_homework[hw.id].submitted_date else None,
                    "marks_awarded": str(by_homework[hw.id].marks_awarded)
                    if by_homework[hw.id].marks_awarded is not None else None,
                    "remarks": by_homework[hw.id].remarks,
                    "content": by_homework[hw.id].content,
                }
                if hw.id in by_homework else None
            ),
        }
        for hw in homeworks
    ]


@router.post("/student/homework/{homework_id}/submit")
async def submit_homework(
    homework_id: uuid.UUID,
    payload: HomeworkSubmitIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    student_id = await _linked_student_id(db, user)
    hw = await db.get(Homework, homework_id)
    if not hw or hw.tenant_id != user.tenant_id or hw.is_deleted or hw.homework_status != "assigned":
        raise HTTPException(404, "Homework not found")
    sub = (await db.execute(select(HomeworkSubmission).where(
        HomeworkSubmission.tenant_id == user.tenant_id,
        HomeworkSubmission.homework_id == hw.id,
        HomeworkSubmission.student_id == student_id,
        HomeworkSubmission.is_deleted.is_(False),
    ))).scalars().first()
    if sub and sub.submission_status == "graded":
        raise HTTPException(409, "Graded homework cannot be changed")
    if sub:
        sub.content = payload.content
        sub.submitted_date = date.today()
        sub.submission_status = "submitted"
        sub.updated_by = user.id
    else:
        sub = HomeworkSubmission(
            tenant_id=user.tenant_id, homework_id=hw.id, student_id=student_id,
            submitted_date=date.today(), content=payload.content,
            submission_status="submitted", created_by=user.id, updated_by=user.id,
        )
        db.add(sub)
    await db.flush()
    await record_audit(db, action="submit", entity="HomeworkSubmission", entity_id=sub.id, actor=user)
    return {"id": str(sub.id), "status": sub.submission_status}


@router.get("/student/timetable")
async def student_timetable(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    student_id = await _linked_student_id(db, user)
    student = await db.get(Student, student_id)
    if not student or student.tenant_id != user.tenant_id or student.is_deleted:
        raise HTTPException(404, "Student not found")
    maps = await _name_maps(db, user.tenant_id)
    rows = (await db.execute(select(TimetablePeriod).where(
        TimetablePeriod.tenant_id == user.tenant_id,
        TimetablePeriod.is_deleted.is_(False),
        (TimetablePeriod.grade_id == student.grade_id) | (TimetablePeriod.grade_id.is_(None)),
        (TimetablePeriod.section_id == student.section_id) | (TimetablePeriod.section_id.is_(None)),
    ).order_by(TimetablePeriod.day_of_week, TimetablePeriod.period_no))).scalars().all()
    return [
        {
            "id": str(p.id),
            "day": p.day_of_week,
            "period_no": p.period_no,
            "subject": maps["subjects"].get(p.subject_id, "Activity"),
            "room": p.room,
            "start_time": p.start_time.strftime("%H:%M") if p.start_time else None,
            "end_time": p.end_time.strftime("%H:%M") if p.end_time else None,
        }
        for p in rows
    ]


@router.get("/student/activities")
async def student_activities(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    student_id = await _linked_student_id(db, user)
    activities = (await db.execute(select(Activity).where(
        Activity.tenant_id == user.tenant_id,
        Activity.is_deleted.is_(False),
    ).order_by(Activity.start_date.asc(), Activity.name))).scalars().all()
    regs = (await db.execute(select(ActivityRegistration).where(
        ActivityRegistration.tenant_id == user.tenant_id,
        ActivityRegistration.student_id == student_id,
        ActivityRegistration.is_deleted.is_(False),
    ))).scalars().all()
    registered = {r.activity_id: r for r in regs if r.registration_status == "registered"}
    counts = dict((await db.execute(select(
        ActivityRegistration.activity_id, func.count()
    ).where(
        ActivityRegistration.tenant_id == user.tenant_id,
        ActivityRegistration.registration_status == "registered",
        ActivityRegistration.is_deleted.is_(False),
    ).group_by(ActivityRegistration.activity_id))).all())
    emp_names = await _employee_names(db, user.tenant_id)
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "code": a.code,
            "activity_type": a.activity_type,
            "coordinator": a.coordinator,
            "in_charge": emp_names.get(a.in_charge_id) if a.in_charge_id else a.coordinator,
            "venue": a.venue,
            "schedule": a.schedule,
            "start_date": a.start_date.isoformat() if a.start_date else None,
            "fee": str(a.fee),
            "capacity": a.capacity,
            "registered_count": counts.get(a.id, 0),
            "registered": a.id in registered,
            "payment_status": registered[a.id].payment_status if a.id in registered else None,
        }
        for a in activities
    ]


@router.post("/student/activities/{activity_id}/register")
async def self_register_activity(
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    student_id = await _linked_student_id(db, user)
    activity = await db.get(Activity, activity_id)
    if not activity or activity.tenant_id != user.tenant_id or activity.is_deleted:
        raise HTTPException(404, "Activity not found")
    existing = (await db.execute(select(ActivityRegistration).where(
        ActivityRegistration.tenant_id == user.tenant_id,
        ActivityRegistration.activity_id == activity.id,
        ActivityRegistration.student_id == student_id,
        ActivityRegistration.is_deleted.is_(False),
    ))).scalars().first()
    if existing and existing.registration_status == "registered":
        return {"id": str(existing.id), "status": existing.registration_status}
    count = (await db.execute(select(func.count()).select_from(ActivityRegistration).where(
        ActivityRegistration.tenant_id == user.tenant_id,
        ActivityRegistration.activity_id == activity.id,
        ActivityRegistration.registration_status == "registered",
        ActivityRegistration.is_deleted.is_(False),
    ))).scalar_one()
    if activity.capacity and count >= activity.capacity:
        raise HTTPException(409, "Activity is full")
    pay_status = "unpaid" if activity.fee and activity.fee > 0 else "waived"
    if existing:
        existing.registration_status = "registered"
        existing.registration_date = date.today()
        existing.amount = activity.fee
        if existing.payment_status not in ("paid", "waived"):
            existing.payment_status = pay_status
        existing.updated_by = user.id
        reg = existing
    else:
        reg = ActivityRegistration(
            tenant_id=user.tenant_id, activity_id=activity.id, student_id=student_id,
            registration_date=date.today(), registration_status="registered",
            amount=activity.fee, payment_status=pay_status,
            created_by=user.id, updated_by=user.id,
        )
        db.add(reg)
    await db.flush()
    await record_audit(db, action="self_register", entity="ActivityRegistration", entity_id=reg.id, actor=user)
    return {"id": str(reg.id), "status": reg.registration_status, "payment_status": reg.payment_status}


@router.post("/student/activities/{activity_id}/pay")
async def pay_activity(
    activity_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Record an activity fee payment (demo gateway — marks the registration paid)."""
    student_id = await _linked_student_id(db, user)
    reg = (await db.execute(select(ActivityRegistration).where(
        ActivityRegistration.tenant_id == user.tenant_id,
        ActivityRegistration.activity_id == activity_id,
        ActivityRegistration.student_id == student_id,
        ActivityRegistration.is_deleted.is_(False),
    ))).scalars().first()
    if not reg or reg.registration_status != "registered":
        raise HTTPException(404, "Register for the activity before paying")
    if reg.payment_status == "paid":
        return {"id": str(reg.id), "payment_status": "paid"}
    reg.payment_status = "paid"
    reg.paid_at = date.today()
    reg.updated_by = user.id
    await db.flush()
    await record_audit(db, action="activity_payment", entity="ActivityRegistration", entity_id=reg.id, actor=user)
    return {"id": str(reg.id), "payment_status": reg.payment_status}


# ----------------------------------------------------------------- Facilities (browse / book / pay)
@router.get("/student/facilities")
async def student_facilities(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    student_id = await _linked_student_id(db, user)
    facilities = (await db.execute(select(Facility).where(
        Facility.tenant_id == user.tenant_id, Facility.is_deleted.is_(False)
    ).order_by(Facility.name))).scalars().all()
    bookings = (await db.execute(select(FacilityBooking).where(
        FacilityBooking.tenant_id == user.tenant_id,
        FacilityBooking.student_id == student_id,
        FacilityBooking.is_deleted.is_(False),
    ).order_by(FacilityBooking.created_at.desc()))).scalars().all()
    emp_names = await _employee_names(db, user.tenant_id)
    fac_names = {f.id: f.name for f in facilities}
    return {
        "facilities": [
            {
                "id": str(f.id), "name": f.name, "code": f.code, "facility_type": f.facility_type,
                "in_charge": emp_names.get(f.in_charge_id) if f.in_charge_id else None,
                "location": f.location, "capacity": f.capacity, "usage_fee": str(f.usage_fee),
                "status": f.facility_status, "description": f.description,
            }
            for f in facilities
        ],
        "bookings": [
            {
                "id": str(b.id), "facility": fac_names.get(b.facility_id, "—"),
                "booking_date": b.booking_date.isoformat() if b.booking_date else None,
                "slot": b.slot, "purpose": b.purpose, "amount": str(b.amount),
                "payment_status": b.payment_status, "status": b.booking_status,
            }
            for b in bookings
        ],
    }


class FacilityBookIn(BaseModel):
    booking_date: date | None = None
    slot: str | None = None
    purpose: str | None = None


@router.post("/student/facilities/{facility_id}/book")
async def book_facility(
    facility_id: uuid.UUID,
    payload: FacilityBookIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    student_id = await _linked_student_id(db, user)
    facility = await db.get(Facility, facility_id)
    if not facility or facility.tenant_id != user.tenant_id or facility.is_deleted:
        raise HTTPException(404, "Facility not found")
    if facility.facility_status != "available":
        raise HTTPException(409, "Facility is not available for booking")
    booking = FacilityBooking(
        tenant_id=user.tenant_id, facility_id=facility.id, student_id=student_id,
        requested_by=user.id, requested_by_name=user.full_name,
        booking_date=payload.booking_date, slot=payload.slot, purpose=payload.purpose,
        amount=facility.usage_fee,
        payment_status="unpaid" if facility.usage_fee and facility.usage_fee > 0 else "waived",
        booking_status="requested", created_by=user.id, updated_by=user.id,
    )
    db.add(booking)
    await db.flush()
    await record_audit(db, action="facility_book", entity="FacilityBooking", entity_id=booking.id, actor=user)
    return {"id": str(booking.id), "status": booking.booking_status, "payment_status": booking.payment_status}


@router.post("/student/facility-bookings/{booking_id}/pay")
async def pay_facility_booking(
    booking_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    student_id = await _linked_student_id(db, user)
    booking = await db.get(FacilityBooking, booking_id)
    if not booking or booking.tenant_id != user.tenant_id or booking.student_id != student_id or booking.is_deleted:
        raise HTTPException(404, "Booking not found")
    if booking.payment_status == "paid":
        return {"id": str(booking.id), "payment_status": "paid"}
    booking.payment_status = "paid"
    booking.updated_by = user.id
    await db.flush()
    await record_audit(db, action="facility_payment", entity="FacilityBooking", entity_id=booking.id, actor=user)
    return {"id": str(booking.id), "payment_status": booking.payment_status}


# ----------------------------------------------------------------- Learning materials
def _resource_dict(r: LearningResource, maps: dict) -> dict:
    return {
        "id": str(r.id), "title": r.title, "resource_type": r.resource_type,
        "audience": r.audience, "subject": maps["subjects"].get(r.subject_id) if r.subject_id else None,
        "grade": maps["grades"].get(r.grade_id) if r.grade_id else "All classes",
        "url": r.url, "description": r.description,
        "shared_on": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/student/learning-materials")
async def student_learning_materials(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Auto-scoped: general material for everyone + student material for the
    learner's own class (grade). Teacher-only material is never shown."""
    student_id = await _linked_student_id(db, user)
    student = await db.get(Student, student_id)
    tid = user.tenant_id
    rows = (await db.execute(select(LearningResource).where(
        LearningResource.tenant_id == tid, LearningResource.is_deleted.is_(False),
        LearningResource.audience.in_(("general", "students")),
        (LearningResource.grade_id.is_(None)) | (LearningResource.grade_id == student.grade_id),
    ).order_by(LearningResource.created_at.desc()))).scalars().all()
    maps = await _name_maps(db, tid)
    return [_resource_dict(r, maps) for r in rows]


@router.get("/teacher/learning-materials")
async def teacher_learning_materials(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Staff-facing: general material + teacher-only material across all classes."""
    tid = user.tenant_id
    rows = (await db.execute(select(LearningResource).where(
        LearningResource.tenant_id == tid, LearningResource.is_deleted.is_(False),
        LearningResource.audience.in_(("general", "teachers")),
    ).order_by(LearningResource.created_at.desc()))).scalars().all()
    maps = await _name_maps(db, tid)
    return [_resource_dict(r, maps) for r in rows]


# ----------------------------------------------------------------- Facility in-charge approvals
class BookingDecisionIn(BaseModel):
    decision: str  # approved / rejected / completed


@router.get("/teacher/facility-bookings")
async def teacher_facility_bookings(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Booking requests for facilities this staff member is in-charge of."""
    emp_id = await _linked_employee_id(db, user)
    tid = user.tenant_id
    my_facilities = {f.id: f.name for f in (await db.execute(select(Facility).where(
        Facility.tenant_id == tid, Facility.in_charge_id == emp_id, Facility.is_deleted.is_(False)
    ))).scalars().all()}
    if not my_facilities:
        return []
    bookings = (await db.execute(select(FacilityBooking).where(
        FacilityBooking.tenant_id == tid, FacilityBooking.facility_id.in_(my_facilities.keys()),
        FacilityBooking.is_deleted.is_(False),
    ).order_by(FacilityBooking.created_at.desc()))).scalars().all()
    students = await _student_names_map(db, tid)
    return [
        {
            "id": str(b.id), "facility": my_facilities.get(b.facility_id, "—"),
            "requested_by": b.requested_by_name or students.get(b.student_id, "—"),
            "booking_date": b.booking_date.isoformat() if b.booking_date else None,
            "slot": b.slot, "purpose": b.purpose, "amount": str(b.amount),
            "payment_status": b.payment_status, "status": b.booking_status,
        }
        for b in bookings
    ]


@router.post("/teacher/facility-bookings/{booking_id}/decision")
async def teacher_decide_facility_booking(
    booking_id: uuid.UUID, payload: BookingDecisionIn,
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user),
):
    if payload.decision not in ("approved", "rejected", "completed"):
        raise HTTPException(422, "decision must be approved, rejected or completed")
    emp_id = await _linked_employee_id(db, user)
    booking = await db.get(FacilityBooking, booking_id)
    if not booking or booking.tenant_id != user.tenant_id or booking.is_deleted:
        raise HTTPException(404, "Booking not found")
    facility = await db.get(Facility, booking.facility_id)
    if not facility or facility.in_charge_id != emp_id:
        raise HTTPException(403, "You are not the in-charge of this facility")
    booking.booking_status = payload.decision
    booking.updated_by = user.id
    await db.flush()
    await record_audit(db, action=f"booking_{payload.decision}", entity="FacilityBooking",
                       entity_id=booking.id, actor=user)
    return {"id": str(booking.id), "status": booking.booking_status}


@router.get("/teacher/dashboard")
async def teacher_dashboard(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tid = user.tenant_id
    db_user = await db.get(User, user.id)
    teacher = None
    profile = None
    assignments = []
    my_open_complaints = 0
    my_meetings = 0
    if db_user.person_id:
        emp = await db.get(Employee, db_user.person_id)
        if emp:
            my_open_complaints = (await db.execute(select(func.count()).select_from(Complaint).where(
                Complaint.tenant_id == tid, Complaint.assigned_to_id == emp.id,
                Complaint.complaint_status.in_(("open", "assigned", "in_progress", "reopened")),
                Complaint.is_deleted.is_(False)))).scalar_one()
            my_meetings = (await db.execute(select(func.count()).select_from(PtmMeeting).where(
                PtmMeeting.tenant_id == tid, PtmMeeting.teacher_id == emp.id,
                PtmMeeting.meeting_status == "scheduled", PtmMeeting.is_deleted.is_(False)))).scalar_one()
            teacher = {"name": f"{emp.first_name} {emp.last_name or ''}".strip(),
                       "designation": emp.designation, "department": emp.department,
                       "email": emp.email, "phone": emp.phone}
            prof = (await db.execute(select(TeacherProfile).where(
                TeacherProfile.tenant_id == tid,
                TeacherProfile.employee_id == emp.id,
                TeacherProfile.is_deleted.is_(False),
            ))).scalars().first()
            if prof:
                profile = {
                    "expertise": prof.expertise,
                    "certifications": prof.certifications,
                    "subjects_can_teach": prof.subjects_can_teach,
                    "qualification": prof.qualification,
                }
            maps = await _name_maps(db, tid)
            rows = (await db.execute(select(TeacherAssignment).where(
                TeacherAssignment.tenant_id == tid,
                TeacherAssignment.employee_id == emp.id,
                TeacherAssignment.assignment_status == "active",
                TeacherAssignment.is_deleted.is_(False),
            ))).scalars().all()
            assignments = [
                {
                    "id": str(a.id),
                    "grade": maps["grades"].get(a.grade_id, "All"),
                    "section": maps["sections"].get(a.section_id, "All"),
                    "subject": maps["subjects"].get(a.subject_id, "General"),
                }
                for a in rows
            ]

    students = (
        await db.execute(select(func.count()).select_from(Student).where(
            Student.tenant_id == tid, Student.is_deleted.is_(False)))
    ).scalar_one()
    marked_today = (
        await db.execute(select(func.count()).select_from(Attendance).where(
            Attendance.tenant_id == tid, Attendance.att_date == date.today(),
            Attendance.is_deleted.is_(False)))
    ).scalar_one()
    homework_open = (
        await db.execute(select(func.count()).select_from(Homework).where(
            Homework.tenant_id == tid, Homework.homework_status == "assigned",
            Homework.is_deleted.is_(False)))
    ).scalar_one()
    to_grade = (
        await db.execute(select(func.count()).select_from(HomeworkSubmission).where(
            HomeworkSubmission.tenant_id == tid, HomeworkSubmission.submission_status != "graded",
            HomeworkSubmission.is_deleted.is_(False)))
    ).scalar_one()

    return {
        "teacher": teacher,
        "profile": profile,
        "assignments": assignments,
        "cards": [
            {"key": "students", "label": "Students", "value": students, "icon": "users"},
            {"key": "marked_today", "label": "Attendance Marked Today", "value": marked_today, "icon": "check-square"},
            {"key": "homework_open", "label": "Open Homework", "value": homework_open, "icon": "edit"},
            {"key": "to_grade", "label": "Submissions to Grade", "value": to_grade, "icon": "book"},
            {"key": "my_complaints", "label": "Open Complaints", "value": my_open_complaints, "icon": "shield"},
            {"key": "my_meetings", "label": "Upcoming Meetings", "value": my_meetings, "icon": "calendar"},
        ],
        "announcements": await _announcements(db, tid, "teachers"),
    }


@router.get("/teacher/students")
async def teacher_students(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Assigned class roster for the teacher portal (read-only)."""
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    maps = await _name_maps(db, tid)
    assignments = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == tid,
        TeacherAssignment.employee_id == emp_id,
        TeacherAssignment.assignment_status == "active",
        TeacherAssignment.is_deleted.is_(False),
    ))).scalars().all()
    conditions = [Student.tenant_id == tid, Student.is_deleted.is_(False)]
    if assignments:
        grade_ids = {a.grade_id for a in assignments if a.grade_id}
        section_ids = {a.section_id for a in assignments if a.section_id}
        if grade_ids:
            conditions.append(Student.grade_id.in_(grade_ids))
        if section_ids:
            conditions.append(Student.section_id.in_(section_ids))
    rows = (await db.execute(select(Student).where(*conditions).order_by(Student.admission_no))).scalars().all()
    return [
        {
            "id": str(s.id), "admission_no": s.admission_no,
            "name": f"{s.first_name} {s.last_name or ''}".strip(),
            "grade": maps["grades"].get(s.grade_id, "—"), "section": maps["sections"].get(s.section_id, "—"),
            "status": s.enrollment_status, "phone": s.phone, "email": s.email,
            "address": s.address, "government_id_type": s.government_id_type,
            "government_id_masked": ("*" * max(len(s.government_id_number or "") - 4, 0) + (s.government_id_number or "")[-4:])
            if s.government_id_number else None,
        }
        for s in rows
    ]


@router.get("/teacher/submissions")
async def teacher_submissions(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Homework submissions awaiting grading."""
    tid = user.tenant_id
    students = {
        s.id: f"{s.first_name} {s.last_name or ''}".strip()
        for s in (await db.execute(select(Student).where(Student.tenant_id == tid))).scalars().all()
    }
    homeworks = {
        h.id: h.title
        for h in (await db.execute(select(Homework).where(Homework.tenant_id == tid))).scalars().all()
    }
    rows = (
        await db.execute(select(HomeworkSubmission).where(
            HomeworkSubmission.tenant_id == tid, HomeworkSubmission.is_deleted.is_(False))
            .order_by(HomeworkSubmission.created_at.desc()))
    ).scalars().all()
    return [
        {
            "id": str(s.id), "homework": homeworks.get(s.homework_id, "—"),
            "student": students.get(s.student_id, "—"), "status": s.submission_status,
            "submitted_date": s.submitted_date.isoformat() if s.submitted_date else None,
            "marks_awarded": str(s.marks_awarded) if s.marks_awarded is not None else None,
            "content": s.content,
        }
        for s in rows
    ]


@router.get("/teacher/schedule")
async def teacher_schedule(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    maps = await _name_maps(db, tid)
    assignments = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == tid,
        TeacherAssignment.employee_id == emp_id,
        TeacherAssignment.assignment_status == "active",
        TeacherAssignment.is_deleted.is_(False),
    ))).scalars().all()
    grade_ids = {a.grade_id for a in assignments if a.grade_id}
    section_ids = {a.section_id for a in assignments if a.section_id}
    subject_ids = {a.subject_id for a in assignments if a.subject_id}
    tt_conditions = [TimetablePeriod.tenant_id == tid, TimetablePeriod.is_deleted.is_(False)]
    if grade_ids:
        tt_conditions.append(TimetablePeriod.grade_id.in_(grade_ids))
    if section_ids:
        tt_conditions.append(TimetablePeriod.section_id.in_(section_ids))
    if subject_ids:
        tt_conditions.append(TimetablePeriod.subject_id.in_(subject_ids))
    periods = (await db.execute(select(TimetablePeriod).where(*tt_conditions)
                                .order_by(TimetablePeriod.day_of_week, TimetablePeriod.period_no))).scalars().all()
    exam_conditions = [ExamSubject.tenant_id == tid, ExamSubject.is_deleted.is_(False)]
    if grade_ids:
        exam_conditions.append(ExamSubject.grade_id.in_(grade_ids))
    if section_ids:
        exam_conditions.append(ExamSubject.section_id.in_(section_ids))
    if subject_ids:
        exam_conditions.append(ExamSubject.subject_id.in_(subject_ids))
    exam_rows = (await db.execute(select(ExamSubject).where(*exam_conditions)
                                  .order_by(ExamSubject.exam_date))).scalars().all()
    exam_names = {
        e.id: e.name
        for e in (await db.execute(select(Exam).where(Exam.tenant_id == tid))).scalars().all()
    }
    return {
        "classes": [
            {
                "id": str(p.id), "day": p.day_of_week, "period_no": p.period_no,
                "subject": maps["subjects"].get(p.subject_id, "General"),
                "grade": maps["grades"].get(p.grade_id, "All"),
                "section": maps["sections"].get(p.section_id, "All"),
                "room": p.room,
                "start_time": p.start_time.strftime("%H:%M") if p.start_time else None,
                "end_time": p.end_time.strftime("%H:%M") if p.end_time else None,
            }
            for p in periods
        ],
        "exams": [
            {
                "id": str(e.id), "exam": exam_names.get(e.exam_id, "Exam"),
                "subject": maps["subjects"].get(e.subject_id, "General"),
                "grade": maps["grades"].get(e.grade_id, "All"),
                "section": maps["sections"].get(e.section_id, "All"),
                "date": e.exam_date.isoformat() if e.exam_date else None,
                "room": e.room, "status": e.schedule_status,
            }
            for e in exam_rows
        ],
    }


@router.get("/teacher/marks-review")
async def teacher_marks_review(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    maps = await _name_maps(db, tid)
    exam_names = {
        e.id: e.name
        for e in (await db.execute(select(Exam).where(Exam.tenant_id == tid))).scalars().all()
    }
    rows = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == tid,
        MarksBatch.reviewer_id == emp_id,
        MarksBatch.is_deleted.is_(False),
    ).order_by(MarksBatch.updated_at.desc()))).scalars().all()
    return [
        {
            "id": str(b.id), "exam": exam_names.get(b.exam_id, "Exam"),
            "subject": maps["subjects"].get(b.subject_id, "General"),
            "grade": maps["grades"].get(b.grade_id, "All"),
            "section": maps["sections"].get(b.section_id, "All"),
            "status": b.batch_status, "review_note": b.review_note,
        }
        for b in rows
    ]


def _mark_grade(marks: Decimal, maximum: Decimal, absent: bool) -> str:
    if absent:
        return "AB"
    pct = float(marks / maximum * 100) if maximum else 0
    if pct >= 90:
        return "A+"
    if pct >= 80:
        return "A"
    if pct >= 70:
        return "B+"
    if pct >= 60:
        return "B"
    if pct >= 50:
        return "C"
    if pct >= 40:
        return "D"
    return "E"


async def _teacher_assignment(
    db: AsyncSession, user: CurrentUser, assignment_id: uuid.UUID
) -> tuple[uuid.UUID, TeacherAssignment]:
    employee_id = await _linked_employee_id(db, user)
    assignment = await db.get(TeacherAssignment, assignment_id)
    today = date.today()
    if (
        not assignment
        or assignment.tenant_id != user.tenant_id
        or assignment.employee_id != employee_id
        or assignment.assignment_status != "active"
        or assignment.is_deleted
        or (assignment.effective_from and assignment.effective_from > today)
        or (assignment.effective_to and assignment.effective_to < today)
    ):
        raise HTTPException(403, "This class/subject is not assigned to the signed-in teacher")
    if not assignment.grade_id or not assignment.section_id or not assignment.subject_id:
        raise HTTPException(409, "Teacher assignment must include class, section and subject")
    return employee_id, assignment


async def _assignment_exam(
    db: AsyncSession, user: CurrentUser, assignment: TeacherAssignment, exam_id: uuid.UUID
) -> tuple[Exam, Decimal]:
    exam = await db.get(Exam, exam_id)
    if (
        not exam
        or exam.tenant_id != user.tenant_id
        or exam.is_deleted
        or (exam.grade_id and exam.grade_id != assignment.grade_id)
    ):
        raise HTTPException(404, "Exam is not available for this assigned class")
    paper = (await db.execute(select(ExamSubject).where(
        ExamSubject.tenant_id == user.tenant_id,
        ExamSubject.exam_id == exam.id,
        ExamSubject.subject_id == assignment.subject_id,
        ExamSubject.grade_id == assignment.grade_id,
        ExamSubject.section_id == assignment.section_id,
        ExamSubject.is_deleted.is_(False),
    ))).scalars().first()
    return exam, Decimal(paper.max_marks if paper else exam.max_marks)


async def _assignment_roster(
    db: AsyncSession, user: CurrentUser, assignment: TeacherAssignment
) -> list[Student]:
    return (await db.execute(select(Student).where(
        Student.tenant_id == user.tenant_id,
        Student.grade_id == assignment.grade_id,
        Student.section_id == assignment.section_id,
        Student.is_deleted.is_(False),
    ).order_by(Student.roll_no, Student.admission_no))).scalars().all()


async def _marks_batch(
    db: AsyncSession,
    user: CurrentUser,
    employee_id: uuid.UUID,
    assignment: TeacherAssignment,
    exam_id: uuid.UUID,
    create: bool = False,
) -> MarksBatch | None:
    batch = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == user.tenant_id,
        MarksBatch.exam_id == exam_id,
        MarksBatch.subject_id == assignment.subject_id,
        MarksBatch.grade_id == assignment.grade_id,
        MarksBatch.section_id == assignment.section_id,
        MarksBatch.is_deleted.is_(False),
    ))).scalars().first()
    if not batch and create:
        batch = MarksBatch(
            tenant_id=user.tenant_id,
            exam_id=exam_id,
            subject_id=assignment.subject_id,
            grade_id=assignment.grade_id,
            section_id=assignment.section_id,
            teacher_id=employee_id,
            reviewer_id=assignment.reporting_manager_id,
            batch_status="draft",
            created_by=user.id,
            updated_by=user.id,
        )
        db.add(batch)
        await db.flush()
    return batch


@router.get("/teacher/marks-entry-options")
async def teacher_marks_entry_options(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    employee_id = await _linked_employee_id(db, user)
    today = date.today()
    assignments = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == user.tenant_id,
        TeacherAssignment.employee_id == employee_id,
        TeacherAssignment.assignment_status == "active",
        TeacherAssignment.is_deleted.is_(False),
    ))).scalars().all()
    assignments = [
        a for a in assignments
        if (not a.effective_from or a.effective_from <= today)
        and (not a.effective_to or a.effective_to >= today)
        and a.grade_id and a.section_id and a.subject_id
    ]
    maps = await _name_maps(db, user.tenant_id)
    exams = (await db.execute(select(Exam).where(
        Exam.tenant_id == user.tenant_id,
        Exam.is_deleted.is_(False),
    ).order_by(Exam.start_date.desc(), Exam.name))).scalars().all()
    employees = {
        e.id: f"{e.first_name} {e.last_name or ''}".strip()
        for e in (await db.execute(select(Employee).where(
            Employee.tenant_id == user.tenant_id,
            Employee.is_deleted.is_(False),
        ))).scalars().all()
    }
    return {
        "assignments": [
            {
                "id": str(a.id),
                "grade_id": str(a.grade_id),
                "section_id": str(a.section_id),
                "subject_id": str(a.subject_id),
                "grade": maps["grades"].get(a.grade_id, "Class"),
                "section": maps["sections"].get(a.section_id, "Section"),
                "subject": maps["subjects"].get(a.subject_id, "Subject"),
                "reviewer": employees.get(a.reporting_manager_id),
                "exams": [
                    {"id": str(e.id), "name": e.name, "code": e.code}
                    for e in exams if not e.grade_id or e.grade_id == a.grade_id
                ],
            }
            for a in assignments
        ]
    }


@router.get("/teacher/result-rules")
async def teacher_result_rules(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    employee_id = await _linked_employee_id(db, user)
    assignments = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == user.tenant_id,
        TeacherAssignment.reporting_manager_id == employee_id,
        TeacherAssignment.assignment_status == "active",
        TeacherAssignment.is_deleted.is_(False),
    ))).scalars().all()
    scopes = {(a.grade_id, a.section_id, a.subject_id) for a in assignments}
    maps = await _name_maps(db, user.tenant_id)
    exams = {
        exam.id: exam
        for exam in (await db.execute(select(Exam).where(
            Exam.tenant_id == user.tenant_id,
            Exam.is_deleted.is_(False),
        ))).scalars().all()
    }
    papers = (await db.execute(select(ExamSubject).where(
        ExamSubject.tenant_id == user.tenant_id,
        ExamSubject.is_deleted.is_(False),
    ))).scalars().all()
    return [
        {
            "id": str(paper.id),
            "exam": exams[paper.exam_id].name if paper.exam_id in exams else "Exam",
            "is_final_exam": exams[paper.exam_id].is_final_exam if paper.exam_id in exams else False,
            "subject": maps["subjects"].get(paper.subject_id, "Subject"),
            "grade": maps["grades"].get(paper.grade_id, "Class"),
            "section": maps["sections"].get(paper.section_id, "Section"),
            "max_marks": str(paper.max_marks),
            "pass_marks": str(paper.pass_marks),
            "pass_percentage": round(float(paper.pass_marks) / float(paper.max_marks) * 100, 2)
            if paper.max_marks else 0,
        }
        for paper in papers
        if (paper.grade_id, paper.section_id, paper.subject_id) in scopes
    ]


@router.put("/teacher/result-rules/{paper_id}")
async def teacher_update_result_rule(
    paper_id: uuid.UUID,
    payload: ResultRuleIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    employee_id = await _linked_employee_id(db, user)
    paper = await db.get(ExamSubject, paper_id)
    if not paper or paper.tenant_id != user.tenant_id or paper.is_deleted:
        raise HTTPException(404, "Examination subject not found")
    assignment = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == user.tenant_id,
        TeacherAssignment.reporting_manager_id == employee_id,
        TeacherAssignment.grade_id == paper.grade_id,
        TeacherAssignment.section_id == paper.section_id,
        TeacherAssignment.subject_id == paper.subject_id,
        TeacherAssignment.assignment_status == "active",
        TeacherAssignment.is_deleted.is_(False),
    ))).scalars().first()
    if not assignment:
        raise HTTPException(403, "Only the mapped HOD can configure this subject pass mark")
    if payload.pass_marks <= 0 or payload.pass_marks >= paper.max_marks:
        raise HTTPException(422, f"Pass marks must be greater than 0 and below {paper.max_marks}")
    published = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == user.tenant_id,
        MarksBatch.exam_id == paper.exam_id,
        MarksBatch.subject_id == paper.subject_id,
        MarksBatch.grade_id == paper.grade_id,
        MarksBatch.section_id == paper.section_id,
        MarksBatch.batch_status == "published",
        MarksBatch.is_deleted.is_(False),
    ))).scalars().first()
    if published:
        raise HTTPException(409, "Pass marks cannot change after results are published")
    paper.pass_marks = payload.pass_marks
    paper.updated_by = user.id
    await db.flush()
    await record_audit(
        db,
        action="update_pass_marks",
        entity="ExamSubject",
        entity_id=paper.id,
        actor=user,
        changes={"pass_marks": str(payload.pass_marks), "max_marks": str(paper.max_marks)},
    )
    return {"id": str(paper.id), "pass_marks": str(paper.pass_marks)}


@router.get("/teacher/marks-sheet")
async def teacher_marks_sheet(
    assignment_id: uuid.UUID,
    exam_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    employee_id, assignment = await _teacher_assignment(db, user, assignment_id)
    exam, maximum = await _assignment_exam(db, user, assignment, exam_id)
    students = await _assignment_roster(db, user, assignment)
    marks = (await db.execute(select(Marks).where(
        Marks.tenant_id == user.tenant_id,
        Marks.exam_id == exam_id,
        Marks.subject_id == assignment.subject_id,
        Marks.student_id.in_([s.id for s in students]) if students else Marks.student_id.is_(None),
        Marks.is_deleted.is_(False),
    ))).scalars().all()
    by_student = {m.student_id: m for m in marks}
    batch = await _marks_batch(db, user, employee_id, assignment, exam_id)
    return {
        "exam": {"id": str(exam.id), "name": exam.name, "code": exam.code},
        "assignment": {
            "id": str(assignment.id),
            "grade_id": str(assignment.grade_id),
            "section_id": str(assignment.section_id),
            "subject_id": str(assignment.subject_id),
        },
        "max_marks": str(maximum),
        "batch": None if not batch else {
            "id": str(batch.id),
            "status": batch.batch_status,
            "review_note": batch.review_note,
        },
        "rows": [
            {
                "student_id": str(s.id),
                "admission_no": s.admission_no,
                "roll_no": s.roll_no,
                "student_name": f"{s.first_name} {s.last_name or ''}".strip(),
                "marks_obtained": (
                    str(by_student[s.id].marks_obtained) if s.id in by_student and not by_student[s.id].is_absent else ""
                ),
                "is_absent": by_student[s.id].is_absent if s.id in by_student else False,
                "remarks": by_student[s.id].remarks if s.id in by_student else "",
                "grade": by_student[s.id].grade_letter if s.id in by_student else None,
            }
            for s in students
        ],
    }


async def _save_teacher_marks(
    db: AsyncSession, user: CurrentUser, payload: TeacherMarkSheetIn, submit: bool
) -> tuple[MarksBatch, int]:
    employee_id, assignment = await _teacher_assignment(db, user, payload.assignment_id)
    _, maximum = await _assignment_exam(db, user, assignment, payload.exam_id)
    students = await _assignment_roster(db, user, assignment)
    roster_ids = {s.id for s in students}
    entries = {e.student_id: e for e in payload.entries}
    if set(entries) - roster_ids:
        raise HTTPException(422, "Marks contain a student outside the assigned class")
    if submit and set(entries) != roster_ids:
        raise HTTPException(422, "Every student must have marks or be marked absent before submission")
    batch = await _marks_batch(db, user, employee_id, assignment, payload.exam_id, create=True)
    assert batch is not None
    if batch.batch_status in ("approved", "published"):
        raise HTTPException(409, "Approved marks are locked and cannot be changed")
    if submit and not assignment.reporting_manager_id:
        raise HTTPException(409, "Map an HOD/marks approver on the teacher assignment before submission")

    written = 0
    for student in students:
        entry = entries.get(student.id)
        existing = (await db.execute(select(Marks).where(
            Marks.tenant_id == user.tenant_id,
            Marks.exam_id == payload.exam_id,
            Marks.student_id == student.id,
            Marks.subject_id == assignment.subject_id,
        ))).scalars().first()
        if not entry or (entry.marks_obtained is None and not entry.is_absent):
            if submit:
                raise HTTPException(422, f"Enter marks or mark absent for {student.first_name}")
            if existing:
                existing.is_deleted = True
                existing.updated_by = user.id
            continue
        awarded = Decimal(0) if entry.is_absent else entry.marks_obtained
        if awarded is None or awarded < 0 or awarded > maximum:
            raise HTTPException(422, f"Marks for {student.first_name} must be between 0 and {maximum}")
        values = {
            "marks_obtained": awarded,
            "max_marks": maximum,
            "grade_letter": _mark_grade(awarded, maximum, entry.is_absent),
            "is_absent": entry.is_absent,
            "remarks": entry.remarks,
            "updated_by": user.id,
            "is_deleted": False,
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            db.add(Marks(
                tenant_id=user.tenant_id,
                exam_id=payload.exam_id,
                student_id=student.id,
                subject_id=assignment.subject_id,
                created_by=user.id,
                **values,
            ))
        written += 1

    batch.teacher_id = employee_id
    batch.reviewer_id = assignment.reporting_manager_id
    batch.batch_status = "submitted" if submit else "draft"
    batch.review_note = None if submit else batch.review_note
    batch.submitted_at = datetime.now(timezone.utc) if submit else None
    batch.updated_by = user.id
    await db.flush()
    await record_audit(
        db,
        action="submit_marks_sheet" if submit else "save_marks_sheet",
        entity="MarksBatch",
        entity_id=batch.id,
        actor=user,
        changes={"count": written, "assignment_id": str(assignment.id)},
    )
    return batch, written


@router.post("/teacher/marks-sheet")
async def teacher_save_marks_sheet(
    payload: TeacherMarkSheetIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    batch, written = await _save_teacher_marks(db, user, payload, submit=False)
    return {"id": str(batch.id), "status": batch.batch_status, "count": written}


@router.post("/teacher/marks-sheet/submit")
async def teacher_submit_marks_sheet(
    payload: TeacherMarkSheetIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    batch, written = await _save_teacher_marks(db, user, payload, submit=True)
    return {"id": str(batch.id), "status": batch.batch_status, "count": written}


@router.get("/teacher/marks-review/{batch_id}")
async def teacher_marks_review_sheet(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    employee_id = await _linked_employee_id(db, user)
    batch = await db.get(MarksBatch, batch_id)
    if (
        not batch
        or batch.tenant_id != user.tenant_id
        or batch.reviewer_id != employee_id
        or batch.is_deleted
    ):
        raise HTTPException(404, "Marks batch not found in your review queue")
    students = await _assignment_roster(
        db,
        user,
        type("ReviewScope", (), {"grade_id": batch.grade_id, "section_id": batch.section_id})(),
    )
    marks = (await db.execute(select(Marks).where(
        Marks.tenant_id == user.tenant_id,
        Marks.exam_id == batch.exam_id,
        Marks.subject_id == batch.subject_id,
        Marks.is_deleted.is_(False),
    ))).scalars().all()
    by_student = {m.student_id: m for m in marks}
    return {
        "id": str(batch.id),
        "status": batch.batch_status,
        "review_note": batch.review_note,
        "rows": [
            {
                "student_id": str(s.id),
                "roll_no": s.roll_no,
                "admission_no": s.admission_no,
                "student_name": f"{s.first_name} {s.last_name or ''}".strip(),
                "marks_obtained": str(by_student[s.id].marks_obtained) if s.id in by_student else "",
                "max_marks": str(by_student[s.id].max_marks) if s.id in by_student else "",
                "is_absent": by_student[s.id].is_absent if s.id in by_student else False,
                "grade": by_student[s.id].grade_letter if s.id in by_student else None,
            }
            for s in students
        ],
    }


@router.post("/teacher/marks-review/{batch_id}")
async def teacher_review_marks(
    batch_id: uuid.UUID,
    payload: MarksReviewIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be approved or rejected")
    employee_id = await _linked_employee_id(db, user)
    batch = await db.get(MarksBatch, batch_id)
    if (
        not batch
        or batch.tenant_id != user.tenant_id
        or batch.reviewer_id != employee_id
        or batch.is_deleted
    ):
        raise HTTPException(404, "Marks batch not found in your review queue")
    if batch.batch_status != "submitted":
        raise HTTPException(409, "Only submitted marks can be reviewed")
    # HOD approval is the academic publication gate for the teacher workflow.
    batch.batch_status = "published" if payload.decision == "approved" else "rejected"
    batch.review_note = payload.review_note
    batch.reviewed_at = datetime.now(timezone.utc)
    if payload.decision == "approved":
        batch.published_at = datetime.now(timezone.utc)
    batch.updated_by = user.id
    await db.flush()
    await record_audit(db, action=payload.decision, entity="MarksBatch", entity_id=batch.id, actor=user)
    return {"id": str(batch.id), "status": batch.batch_status}


# ===================================================== Principal portal (oversight + approvals)
def _require_principal(user: CurrentUser) -> str:
    kind = portal_for(user.roles, user.is_superadmin)
    if kind not in ("principal", "admin"):
        raise HTTPException(403, "Principal access only")
    return kind


async def _count_where(db: AsyncSession, model, *conds) -> int:
    return (await db.execute(select(func.count()).select_from(model).where(*conds))).scalar_one()


@router.get("/principal/dashboard")
async def principal_dashboard(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    _require_principal(user)
    tid = user.tenant_id
    db_user = await db.get(User, user.id)
    principal = None
    if db_user and db_user.person_id:
        emp = await db.get(Employee, db_user.person_id)
        if emp:
            principal = {"name": f"{emp.first_name} {emp.last_name or ''}".strip(),
                         "designation": emp.designation, "department": emp.department}

    students = await _count_where(db, Student, Student.tenant_id == tid, Student.is_deleted.is_(False))
    teachers = await _count_where(db, Employee, Employee.tenant_id == tid, Employee.is_deleted.is_(False))
    pending_marks = await _count_where(db, MarksBatch, MarksBatch.tenant_id == tid,
                                       MarksBatch.batch_status == "submitted", MarksBatch.is_deleted.is_(False))
    published_marks = await _count_where(db, MarksBatch, MarksBatch.tenant_id == tid,
                                         MarksBatch.batch_status == "published", MarksBatch.is_deleted.is_(False))
    pending_curriculum = await _count_where(db, CurriculumPlan, CurriculumPlan.tenant_id == tid,
                                            CurriculumPlan.plan_status == "submitted", CurriculumPlan.is_deleted.is_(False))
    open_complaints = await _count_where(db, Complaint, Complaint.tenant_id == tid,
                                         Complaint.complaint_status.in_(("open", "assigned", "in_progress", "reopened")),
                                         Complaint.is_deleted.is_(False))
    meetings = await _count_where(db, PtmMeeting, PtmMeeting.tenant_id == tid,
                                  PtmMeeting.meeting_status == "scheduled", PtmMeeting.is_deleted.is_(False))
    return {
        "principal": principal,
        "cards": [
            {"key": "students", "label": "Students", "value": students, "icon": "users"},
            {"key": "teachers", "label": "Staff", "value": teachers, "icon": "briefcase"},
            {"key": "pending_marks", "label": "Marksheets to Approve", "value": pending_marks, "icon": "check-square"},
            {"key": "pending_curriculum", "label": "Curriculum to Approve", "value": pending_curriculum, "icon": "book"},
            {"key": "open_complaints", "label": "Open Complaints", "value": open_complaints, "icon": "shield"},
            {"key": "meetings", "label": "Scheduled Meetings", "value": meetings, "icon": "calendar"},
            {"key": "published_marks", "label": "Marksheets Published", "value": published_marks, "icon": "trending-up"},
        ],
        "announcements": await _announcements(db, tid, "teachers"),
    }


@router.get("/principal/marks-approvals")
async def principal_marks_approvals(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    _require_principal(user)
    tid = user.tenant_id
    maps = await _name_maps(db, tid)
    exam_names = {e.id: e.name for e in (await db.execute(select(Exam).where(Exam.tenant_id == tid))).scalars().all()}
    emp_names = await _employee_names(db, tid)
    rows = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == tid, MarksBatch.batch_status == "submitted", MarksBatch.is_deleted.is_(False)
    ).order_by(MarksBatch.updated_at.desc()))).scalars().all()
    return [
        {
            "id": str(b.id), "exam": exam_names.get(b.exam_id, "Exam"),
            "subject": maps["subjects"].get(b.subject_id, "General"),
            "grade": maps["grades"].get(b.grade_id, "All"),
            "section": maps["sections"].get(b.section_id, "All"),
            "teacher": emp_names.get(b.teacher_id, "—"), "status": b.batch_status, "review_note": b.review_note,
        }
        for b in rows
    ]


@router.get("/principal/marks-approvals/{batch_id}")
async def principal_marks_sheet(
    batch_id: uuid.UUID, db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    _require_principal(user)
    batch = await db.get(MarksBatch, batch_id)
    if not batch or batch.tenant_id != user.tenant_id or batch.is_deleted:
        raise HTTPException(404, "Marks batch not found")
    students = await _assignment_roster(
        db, user, type("Scope", (), {"grade_id": batch.grade_id, "section_id": batch.section_id})())
    marks = (await db.execute(select(Marks).where(
        Marks.tenant_id == user.tenant_id, Marks.exam_id == batch.exam_id,
        Marks.subject_id == batch.subject_id, Marks.is_deleted.is_(False)))).scalars().all()
    by_student = {m.student_id: m for m in marks}
    return {
        "id": str(batch.id), "status": batch.batch_status, "review_note": batch.review_note,
        "rows": [
            {
                "student_id": str(s.id), "roll_no": s.roll_no, "admission_no": s.admission_no,
                "student_name": f"{s.first_name} {s.last_name or ''}".strip(),
                "marks_obtained": str(by_student[s.id].marks_obtained) if s.id in by_student else "",
                "max_marks": str(by_student[s.id].max_marks) if s.id in by_student else "",
                "is_absent": by_student[s.id].is_absent if s.id in by_student else False,
                "grade": by_student[s.id].grade_letter if s.id in by_student else None,
            }
            for s in students
        ],
    }


@router.post("/principal/marks-approvals/{batch_id}")
async def principal_review_marks(
    batch_id: uuid.UUID, payload: MarksReviewIn,
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user),
):
    _require_principal(user)
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be approved or rejected")
    batch = await db.get(MarksBatch, batch_id)
    if not batch or batch.tenant_id != user.tenant_id or batch.is_deleted:
        raise HTTPException(404, "Marks batch not found")
    if batch.batch_status != "submitted":
        raise HTTPException(409, "Only submitted marks can be reviewed")
    batch.batch_status = "published" if payload.decision == "approved" else "rejected"
    batch.review_note = payload.review_note
    batch.reviewed_at = datetime.now(timezone.utc)
    if payload.decision == "approved":
        batch.published_at = datetime.now(timezone.utc)
    batch.updated_by = user.id
    await db.flush()
    await record_audit(db, action=f"principal_{payload.decision}", entity="MarksBatch", entity_id=batch.id, actor=user)
    return {"id": str(batch.id), "status": batch.batch_status}


def _plan_brief(p: CurriculumPlan, maps: dict, emp_names: dict) -> dict:
    return {
        "id": str(p.id), "title": p.title, "term": p.term,
        "grade": maps["grades"].get(p.grade_id, "—"), "section": maps["sections"].get(p.section_id, "—"),
        "subject": maps["subjects"].get(p.subject_id, "General"),
        "teacher": emp_names.get(p.teacher_id, "—"),
        "objectives": p.objectives, "topics": p.topics or [],
        "status": p.plan_status, "review_note": p.review_note,
    }


@router.get("/principal/curriculum-approvals")
async def principal_curriculum_approvals(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    _require_principal(user)
    tid = user.tenant_id
    maps = await _name_maps(db, tid)
    emp_names = await _employee_names(db, tid)
    rows = (await db.execute(select(CurriculumPlan).where(
        CurriculumPlan.tenant_id == tid, CurriculumPlan.plan_status == "submitted",
        CurriculumPlan.is_deleted.is_(False)).order_by(CurriculumPlan.submitted_at.desc().nullslast()))).scalars().all()
    return [_plan_brief(p, maps, emp_names) for p in rows]


@router.post("/principal/curriculum-approvals/{plan_id}")
async def principal_review_curriculum(
    plan_id: uuid.UUID, payload: PlanReviewIn,
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user),
):
    _require_principal(user)
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
    await record_audit(db, action=f"principal_{payload.decision}", entity="CurriculumPlan", entity_id=plan.id, actor=user)
    return {"id": str(plan.id), "status": plan.plan_status}


@router.post("/teacher/submissions/{submission_id}/grade")
async def teacher_grade(
    submission_id: uuid.UUID,
    payload: GradeIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
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
    return {"id": str(sub.id), "status": sub.submission_status, "marks_awarded": str(sub.marks_awarded)}


@router.post("/teacher/attendance")
async def teacher_mark_attendance(
    payload: BulkAttIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Teacher bulk-marks attendance for a date (idempotent per student/date)."""
    tid = user.tenant_id
    written = 0
    for entry in payload.entries:
        existing = (await db.execute(select(Attendance).where(
            Attendance.tenant_id == tid, Attendance.person_type == "student",
            Attendance.person_id == entry.student_id,
            Attendance.att_date == payload.att_date))).scalars().first()
        if existing:
            existing.state = entry.state
            existing.marked_by = user.id
            existing.updated_by = user.id
        else:
            db.add(Attendance(
                tenant_id=tid, person_type="student", person_id=entry.student_id,
                student_id=entry.student_id, att_date=payload.att_date,
                state=entry.state, method="manual", marked_by=user.id,
                created_by=user.id, updated_by=user.id,
            ))
        written += 1
    await db.flush()
    await record_audit(db, action="bulk_mark", entity="Attendance", actor=user,
                       changes={"date": payload.att_date.isoformat(), "count": written})
    return {"detail": "attendance recorded", "count": written, "date": payload.att_date.isoformat()}


@router.get("/teacher/homework")
async def teacher_homework_list(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tid = user.tenant_id
    maps = await _name_maps(db, tid)
    rows = (await db.execute(select(Homework).where(
        Homework.tenant_id == tid, Homework.is_deleted.is_(False)
    ).order_by(Homework.created_at.desc()))).scalars().all()
    return [
        {
            "id": str(h.id), "title": h.title, "description": h.description,
            "subject": maps["subjects"].get(h.subject_id, "General"),
            "grade": maps["grades"].get(h.grade_id, "All classes"),
            "section": maps["sections"].get(h.section_id) if h.section_id else None,
            "assigned_date": h.assigned_date.isoformat() if h.assigned_date else None,
            "due_date": h.due_date.isoformat() if h.due_date else None,
            "max_marks": str(h.max_marks), "status": h.homework_status,
        }
        for h in rows
    ]


@router.post("/teacher/homework")
async def teacher_create_homework(
    payload: HomeworkCreateIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    from decimal import Decimal

    hw = Homework(
        tenant_id=user.tenant_id, title=payload.title, subject_id=payload.subject_id,
        grade_id=payload.grade_id, section_id=payload.section_id, due_date=payload.due_date,
        assigned_date=payload.assigned_date or date.today(), description=payload.description,
        max_marks=Decimal(str(payload.max_marks)), homework_status="assigned",
        created_by=user.id, updated_by=user.id,
    )
    db.add(hw)
    await db.flush()
    await record_audit(db, action="create", entity="Homework", entity_id=hw.id, actor=user)
    return {"id": str(hw.id), "title": hw.title}


@router.delete("/teacher/homework/{homework_id}")
async def teacher_delete_homework(
    homework_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    hw = await db.get(Homework, homework_id)
    if not hw or hw.tenant_id != user.tenant_id or hw.is_deleted:
        raise HTTPException(404, "Homework not found")
    hw.is_deleted = True
    hw.updated_by = user.id
    await db.flush()
    await record_audit(db, action="delete", entity="Homework", entity_id=hw.id, actor=user)
    return {"detail": "homework removed"}


# ----------------------------------------------------------------- Curriculum planning
def _completion(topics: list | None) -> int:
    items = topics or []
    if not items:
        return 0
    done = sum(1 for t in items if (t.get("status") if isinstance(t, dict) else None) == "done")
    return round(done / len(items) * 100)


async def _employee_names(db: AsyncSession, tid: uuid.UUID) -> dict:
    rows = (await db.execute(select(Employee).where(
        Employee.tenant_id == tid, Employee.is_deleted.is_(False)
    ))).scalars().all()
    return {e.id: f"{e.first_name} {e.last_name or ''}".strip() for e in rows}


async def _student_names_map(db: AsyncSession, tid: uuid.UUID) -> dict:
    rows = (await db.execute(select(Student).where(
        Student.tenant_id == tid, Student.is_deleted.is_(False)
    ))).scalars().all()
    return {s.id: f"{s.first_name} {s.last_name or ''}".strip() for s in rows}


def _plan_dict(p: CurriculumPlan, maps: dict, emp_names: dict) -> dict:
    return {
        "id": str(p.id),
        "title": p.title,
        "term": p.term,
        "academic_year_id": str(p.academic_year_id) if p.academic_year_id else None,
        "grade_id": str(p.grade_id) if p.grade_id else None,
        "section_id": str(p.section_id) if p.section_id else None,
        "subject_id": str(p.subject_id) if p.subject_id else None,
        "grade": maps["grades"].get(p.grade_id, "—"),
        "section": maps["sections"].get(p.section_id, "—"),
        "subject": maps["subjects"].get(p.subject_id, "General"),
        "objectives": p.objectives,
        "resources": p.resources,
        "topics": p.topics or [],
        "completion_percent": p.completion_percent,
        "status": p.plan_status,
        "teacher": emp_names.get(p.teacher_id, "—"),
        "reviewer": emp_names.get(p.reviewer_id, None),
        "reviewer_id": str(p.reviewer_id) if p.reviewer_id else None,
        "review_note": p.review_note,
        "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
        "reviewed_at": p.reviewed_at.isoformat() if p.reviewed_at else None,
    }


@router.get("/teacher/plan-options")
async def teacher_plan_options(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Dropdown data for the planning form: terms, years, the teacher's own
    class/subject combos (from active allocations) and possible reviewers."""
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    maps = await _name_maps(db, tid)
    years = (await db.execute(select(AcademicYear).where(
        AcademicYear.tenant_id == tid, AcademicYear.is_deleted.is_(False)
    ).order_by(AcademicYear.is_current.desc(), AcademicYear.name.desc()))).scalars().all()
    assignments = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == tid,
        TeacherAssignment.employee_id == emp_id,
        TeacherAssignment.assignment_status == "active",
        TeacherAssignment.is_deleted.is_(False),
    ))).scalars().all()
    classes, seen = [], set()
    for a in assignments:
        key = (a.grade_id, a.section_id, a.subject_id)
        if key in seen:
            continue
        seen.add(key)
        classes.append({
            "grade_id": str(a.grade_id) if a.grade_id else None,
            "section_id": str(a.section_id) if a.section_id else None,
            "subject_id": str(a.subject_id) if a.subject_id else None,
            "grade": maps["grades"].get(a.grade_id, "—"),
            "section": maps["sections"].get(a.section_id, "—"),
            "subject": maps["subjects"].get(a.subject_id, "General"),
        })
    emps = (await db.execute(select(Employee).where(
        Employee.tenant_id == tid, Employee.is_deleted.is_(False)
    ).order_by(Employee.first_name))).scalars().all()
    reviewers = [
        {"id": str(e.id), "name": f"{e.first_name} {e.last_name or ''}".strip(), "designation": e.designation}
        for e in emps if e.id != emp_id
    ]
    return {
        "terms": ["Quarter 1", "Quarter 2", "Quarter 3", "Quarter 4"],
        "academic_years": [{"id": str(y.id), "name": y.name, "is_current": y.is_current} for y in years],
        "classes": classes,
        "reviewers": reviewers,
    }


@router.get("/teacher/plans")
async def teacher_plans(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    maps = await _name_maps(db, tid)
    emp_names = await _employee_names(db, tid)
    rows = (await db.execute(select(CurriculumPlan).where(
        CurriculumPlan.tenant_id == tid,
        CurriculumPlan.teacher_id == emp_id,
        CurriculumPlan.is_deleted.is_(False),
    ).order_by(CurriculumPlan.created_at.desc()))).scalars().all()
    return [_plan_dict(p, maps, emp_names) for p in rows]


@router.post("/teacher/plans")
async def teacher_create_plan(
    payload: PlanIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    topics = [t.model_dump() for t in payload.topics]
    plan = CurriculumPlan(
        tenant_id=tid, title=payload.title, term=payload.term,
        academic_year_id=payload.academic_year_id, grade_id=payload.grade_id,
        section_id=payload.section_id, subject_id=payload.subject_id, teacher_id=emp_id,
        objectives=payload.objectives, resources=payload.resources, topics=topics,
        completion_percent=_completion(topics), plan_status="draft",
        created_by=user.id, updated_by=user.id,
    )
    db.add(plan)
    await db.flush()
    await record_audit(db, action="create", entity="CurriculumPlan", entity_id=plan.id, actor=user)
    return {"id": str(plan.id), "status": plan.plan_status}


async def _own_plan(db: AsyncSession, user: CurrentUser, emp_id: uuid.UUID, plan_id: uuid.UUID) -> CurriculumPlan:
    plan = await db.get(CurriculumPlan, plan_id)
    if not plan or plan.tenant_id != user.tenant_id or plan.is_deleted or plan.teacher_id != emp_id:
        raise HTTPException(404, "Plan not found")
    return plan


@router.put("/teacher/plans/{plan_id}")
async def teacher_update_plan(
    plan_id: uuid.UUID,
    payload: PlanIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    emp_id = await _linked_employee_id(db, user)
    plan = await _own_plan(db, user, emp_id, plan_id)
    if plan.plan_status not in ("draft", "rejected"):
        raise HTTPException(409, "Only draft or rejected plans can be edited")
    topics = [t.model_dump() for t in payload.topics]
    plan.title = payload.title
    plan.term = payload.term
    plan.academic_year_id = payload.academic_year_id
    plan.grade_id = payload.grade_id
    plan.section_id = payload.section_id
    plan.subject_id = payload.subject_id
    plan.objectives = payload.objectives
    plan.resources = payload.resources
    plan.topics = topics
    plan.completion_percent = _completion(topics)
    plan.updated_by = user.id
    await db.flush()
    await record_audit(db, action="update", entity="CurriculumPlan", entity_id=plan.id, actor=user)
    return {"id": str(plan.id), "status": plan.plan_status}


@router.post("/teacher/plans/{plan_id}/submit")
async def teacher_submit_plan(
    plan_id: uuid.UUID,
    payload: PlanSubmitIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    emp_id = await _linked_employee_id(db, user)
    plan = await _own_plan(db, user, emp_id, plan_id)
    if plan.plan_status not in ("draft", "rejected"):
        raise HTTPException(409, "Only draft or rejected plans can be submitted")
    if payload.reviewer_id:
        plan.reviewer_id = payload.reviewer_id
    if not plan.reviewer_id:
        raise HTTPException(422, "A reviewer is required to submit a plan")
    plan.plan_status = "submitted"
    plan.submitted_at = datetime.now(timezone.utc)
    plan.review_note = None
    plan.updated_by = user.id
    await db.flush()
    await record_audit(db, action="submit", entity="CurriculumPlan", entity_id=plan.id, actor=user)
    return {"id": str(plan.id), "status": plan.plan_status}


@router.delete("/teacher/plans/{plan_id}")
async def teacher_delete_plan(
    plan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    emp_id = await _linked_employee_id(db, user)
    plan = await _own_plan(db, user, emp_id, plan_id)
    if plan.plan_status not in ("draft", "rejected"):
        raise HTTPException(409, "Only draft or rejected plans can be deleted")
    plan.is_deleted = True
    plan.updated_by = user.id
    await record_audit(db, action="delete", entity="CurriculumPlan", entity_id=plan.id, actor=user)
    return {"detail": "deleted", "id": str(plan_id)}


@router.get("/teacher/plan-reviews")
async def teacher_plan_reviews(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Plans routed to the signed-in teacher (as HOD/reviewer) for approval."""
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    maps = await _name_maps(db, tid)
    emp_names = await _employee_names(db, tid)
    rows = (await db.execute(select(CurriculumPlan).where(
        CurriculumPlan.tenant_id == tid,
        CurriculumPlan.reviewer_id == emp_id,
        CurriculumPlan.plan_status.in_(("submitted", "approved", "rejected")),
        CurriculumPlan.is_deleted.is_(False),
    ).order_by(CurriculumPlan.submitted_at.desc()))).scalars().all()
    return [_plan_dict(p, maps, emp_names) for p in rows]


@router.post("/teacher/plans/{plan_id}/review")
async def teacher_review_plan(
    plan_id: uuid.UUID,
    payload: PlanReviewIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be approved or rejected")
    emp_id = await _linked_employee_id(db, user)
    plan = await db.get(CurriculumPlan, plan_id)
    if not plan or plan.tenant_id != user.tenant_id or plan.is_deleted or plan.reviewer_id != emp_id:
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


@router.get("/teacher/marks")
async def teacher_marks(
    exam_id: uuid.UUID | None = None,
    subject_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Subject-wise marks for the teacher's own students, filterable by exam/subject."""
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    maps = await _name_maps(db, tid)
    assignments = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == tid,
        TeacherAssignment.employee_id == emp_id,
        TeacherAssignment.assignment_status == "active",
        TeacherAssignment.is_deleted.is_(False),
    ))).scalars().all()
    grade_ids = {a.grade_id for a in assignments if a.grade_id}
    section_ids = {a.section_id for a in assignments if a.section_id}
    subject_ids = {a.subject_id for a in assignments if a.subject_id}

    sconds = [Student.tenant_id == tid, Student.is_deleted.is_(False)]
    if grade_ids:
        sconds.append(Student.grade_id.in_(grade_ids))
    if section_ids:
        sconds.append(Student.section_id.in_(section_ids))
    students = (await db.execute(select(Student).where(*sconds))).scalars().all()
    student_map = {s.id: s for s in students}

    subject_filter = [{"id": str(sid), "name": maps["subjects"].get(sid, "Subject")} for sid in subject_ids]
    exams = (await db.execute(select(Exam).where(
        Exam.tenant_id == tid, Exam.is_deleted.is_(False)
    ).order_by(Exam.start_date.desc()))).scalars().all()
    exam_names = {e.id: e.name for e in exams}

    rows = []
    if student_map:
        mconds = [Marks.tenant_id == tid, Marks.is_deleted.is_(False),
                  Marks.student_id.in_(set(student_map))]
        if subject_id:
            mconds.append(Marks.subject_id == subject_id)
        elif subject_ids:
            mconds.append(Marks.subject_id.in_(subject_ids))
        if exam_id:
            mconds.append(Marks.exam_id == exam_id)
        marks = (await db.execute(select(Marks).where(*mconds))).scalars().all()
        for m in marks:
            s = student_map.get(m.student_id)
            if not s:
                continue
            rows.append({
                "id": str(m.id),
                "student": f"{s.first_name} {s.last_name or ''}".strip(),
                "admission_no": s.admission_no,
                "grade": maps["grades"].get(s.grade_id, "—"),
                "section": maps["sections"].get(s.section_id, "—"),
                "exam": exam_names.get(m.exam_id, "Exam"),
                "subject": maps["subjects"].get(m.subject_id, "Subject"),
                "marks_obtained": str(m.marks_obtained),
                "max_marks": str(m.max_marks),
                "grade_letter": m.grade_letter,
                "is_absent": m.is_absent,
            })
        rows.sort(key=lambda r: (r["subject"], r["exam"], r["admission_no"] or ""))
    return {
        "filters": {
            "subjects": subject_filter,
            "exams": [{"id": str(e.id), "name": e.name} for e in exams],
        },
        "rows": rows,
    }


# ----------------------------------------------------------------- Staff self check-in
class CheckInIn(BaseModel):
    state: str = "present"  # present / late / on_duty / leave
    remarks: str | None = None


@router.get("/me/attendance")
async def my_attendance(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """The signed-in staff member's own attendance: today's status + recent history."""
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    today = date.today()
    rows = (await db.execute(select(Attendance).where(
        Attendance.tenant_id == tid, Attendance.person_type == "employee",
        Attendance.person_id == emp_id, Attendance.is_deleted.is_(False),
    ).order_by(Attendance.att_date.desc()).limit(30))).scalars().all()
    today_row = next((r for r in rows if r.att_date == today), None)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.state] = counts.get(r.state, 0) + 1
    return {
        "today": today.isoformat(),
        "today_state": today_row.state if today_row else None,
        "summary": counts,
        "history": [
            {"date": r.att_date.isoformat(), "state": r.state, "method": r.method, "remarks": r.remarks}
            for r in rows
        ],
    }


@router.post("/me/attendance/check-in")
async def my_check_in(
    payload: CheckInIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Self-mark the signed-in staff member's attendance for today (idempotent)."""
    tid = user.tenant_id
    emp_id = await _linked_employee_id(db, user)
    today = date.today()
    existing = (await db.execute(select(Attendance).where(
        Attendance.tenant_id == tid, Attendance.person_type == "employee",
        Attendance.person_id == emp_id, Attendance.att_date == today,
    ))).scalars().first()
    if existing:
        existing.state = payload.state
        existing.remarks = payload.remarks
        existing.method = "self"
        existing.marked_by = user.id
        existing.updated_by = user.id
        att = existing
    else:
        att = Attendance(
            tenant_id=tid, person_type="employee", person_id=emp_id, att_date=today,
            state=payload.state, method="self", remarks=payload.remarks,
            marked_by=user.id, created_by=user.id, updated_by=user.id,
        )
        db.add(att)
    await db.flush()
    await record_audit(db, action="self_check_in", entity="Attendance", entity_id=att.id, actor=user)
    return {"date": today.isoformat(), "state": att.state}
