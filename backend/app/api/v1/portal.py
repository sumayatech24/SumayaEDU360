"""Per-persona portals.

Resolves which portal a signed-in user belongs to (student / parent / teacher / admin)
and serves self-scoped dashboard data that does NOT require module-level RBAC — a student
or parent can always see their own child's data, a teacher their teaching summary.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.reporting import student_360
from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.academic import Grade, Section, Subject
from app.models.academics_ops import Homework, HomeworkSubmission, TimetablePeriod
from app.models.attendance import Attendance
from app.models.auth import User
from app.models.operations import Activity, ActivityRegistration, Announcement
from app.models.people import Employee, Student

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
    due_date: date | None = None
    description: str | None = None
    max_marks: float = 10


def portal_for(roles: list[str], is_super: bool) -> str:
    if is_super:
        return "admin"
    if "student" in roles:
        return "student"
    if "parent" in roles:
        return "parent"
    if "teacher" in roles:
        return "teacher"
    return "admin"  # principal, accountant, librarian, ... use the admin shell (RBAC-filtered)


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
    """Self-scoped 360 for a student or a parent (their linked child)."""
    student_id = await _linked_student_id(db, user)
    data = await student_360(str(student_id), db, user)
    data["announcements"] = await _announcements(db, user.tenant_id,
                                                  "parents" if "parent" in user.roles else "students")
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
    return [
        {
            "id": str(a.id),
            "name": a.name,
            "code": a.code,
            "activity_type": a.activity_type,
            "coordinator": a.coordinator,
            "start_date": a.start_date.isoformat() if a.start_date else None,
            "fee": str(a.fee),
            "capacity": a.capacity,
            "registered_count": counts.get(a.id, 0),
            "registered": a.id in registered,
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
    if existing:
        existing.registration_status = "registered"
        existing.registration_date = date.today()
        existing.updated_by = user.id
        reg = existing
    else:
        reg = ActivityRegistration(
            tenant_id=user.tenant_id, activity_id=activity.id, student_id=student_id,
            registration_date=date.today(), registration_status="registered",
            created_by=user.id, updated_by=user.id,
        )
        db.add(reg)
    await db.flush()
    await record_audit(db, action="self_register", entity="ActivityRegistration", entity_id=reg.id, actor=user)
    return {"id": str(reg.id), "status": reg.registration_status}


@router.get("/teacher/dashboard")
async def teacher_dashboard(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tid = user.tenant_id
    db_user = await db.get(User, user.id)
    teacher = None
    if db_user.person_id:
        emp = await db.get(Employee, db_user.person_id)
        if emp:
            teacher = {"name": f"{emp.first_name} {emp.last_name or ''}".strip(),
                       "designation": emp.designation, "department": emp.department}

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
        "cards": [
            {"key": "students", "label": "Students", "value": students, "icon": "users"},
            {"key": "marked_today", "label": "Attendance Marked Today", "value": marked_today, "icon": "check-square"},
            {"key": "homework_open", "label": "Open Homework", "value": homework_open, "icon": "edit"},
            {"key": "to_grade", "label": "Submissions to Grade", "value": to_grade, "icon": "book"},
        ],
        "announcements": await _announcements(db, tid, "teachers"),
    }


@router.get("/teacher/students")
async def teacher_students(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    """Class roster for the teacher portal (read-only)."""
    tid = user.tenant_id
    maps = await _name_maps(db, tid)
    rows = (
        await db.execute(select(Student).where(Student.tenant_id == tid, Student.is_deleted.is_(False))
                         .order_by(Student.admission_no))
    ).scalars().all()
    return [
        {
            "id": str(s.id), "admission_no": s.admission_no,
            "name": f"{s.first_name} {s.last_name or ''}".strip(),
            "grade": maps["grades"].get(s.grade_id, "—"), "section": maps["sections"].get(s.section_id, "—"),
            "status": s.enrollment_status,
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
            Attendance.tenant_id == tid, Attendance.student_id == entry.student_id,
            Attendance.att_date == payload.att_date))).scalars().first()
        if existing:
            existing.state = entry.state
            existing.marked_by = user.id
            existing.updated_by = user.id
        else:
            db.add(Attendance(
                tenant_id=tid, student_id=entry.student_id, att_date=payload.att_date,
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
            "id": str(h.id), "title": h.title,
            "subject": maps["subjects"].get(h.subject_id, "General"),
            "grade": maps["grades"].get(h.grade_id, "All"),
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
        assigned_date=date.today(), description=payload.description,
        max_marks=Decimal(str(payload.max_marks)), homework_status="assigned",
        created_by=user.id, updated_by=user.id,
    )
    db.add(hw)
    await db.flush()
    await record_audit(db, action="create", entity="Homework", entity_id=hw.id, actor=user)
    return {"id": str(hw.id), "title": hw.title}
