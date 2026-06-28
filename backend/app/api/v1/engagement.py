"""Family engagement — Parent-Teacher Meetings and Complaints / Service Requests.

Role-aware: the same endpoints serve students, parents, teachers and admins/principal;
the response is scoped to what the caller is allowed to see. Complaints are
auto-assigned to the student's class teacher (HOD as fallback) and carry a visible
trail that parents, teachers, administrators and the principal can all follow.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.portal import portal_for
from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.academic import Section
from app.models.auth import User
from app.models.content import PtmMeeting
from app.models.engagement import Complaint, ComplaintUpdate
from app.models.people import Employee, Student, TeacherAssignment

router = APIRouter(prefix="/engagement", tags=["Engagement"])

CATEGORIES = ["general", "academic", "fees", "transport", "hostel", "discipline", "facilities", "other"]
PRIORITIES = ["low", "normal", "high", "urgent"]
OPEN_STATES = ("open", "assigned", "in_progress", "reopened")


# --------------------------------------------------------------------------- helpers
def _kind(user: CurrentUser) -> str:
    return portal_for(user.roles, user.is_superadmin)


async def _db_user(db: AsyncSession, user: CurrentUser) -> User:
    return await db.get(User, user.id)


async def _linked_student(db: AsyncSession, user: CurrentUser) -> Student:
    du = await _db_user(db, user)
    if not du or du.person_type != "student" or not du.person_id:
        raise HTTPException(404, "No student linked to this account")
    student = await db.get(Student, du.person_id)
    if not student or student.tenant_id != user.tenant_id:
        raise HTTPException(404, "Student not found")
    return student


async def _linked_employee_id(db: AsyncSession, user: CurrentUser) -> uuid.UUID:
    du = await _db_user(db, user)
    if not du or du.person_type != "employee" or not du.person_id:
        raise HTTPException(404, "No employee linked to this account")
    return du.person_id


async def _emp_names(db: AsyncSession, tid: uuid.UUID) -> dict:
    rows = (await db.execute(select(Employee).where(
        Employee.tenant_id == tid, Employee.is_deleted.is_(False)))).scalars().all()
    return {e.id: f"{e.first_name} {e.last_name or ''}".strip() for e in rows}


async def _student_map(db: AsyncSession, tid: uuid.UUID) -> dict:
    rows = (await db.execute(select(Student).where(
        Student.tenant_id == tid, Student.is_deleted.is_(False)))).scalars().all()
    return {s.id: s for s in rows}


def _student_label(s: Student | None) -> str:
    if not s:
        return "—"
    name = f"{s.first_name} {s.last_name or ''}".strip()
    return f"{name} ({s.admission_no})" if s.admission_no else name


async def _default_assignee(db: AsyncSession, tid: uuid.UUID, student: Student | None):
    """Class teacher of the student's section, else the section's HOD."""
    if student and student.section_id:
        sec = await db.get(Section, student.section_id)
        if sec and sec.class_teacher_id:
            return sec.class_teacher_id, "class_teacher"
        ta = (await db.execute(select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tid,
            TeacherAssignment.section_id == student.section_id,
            TeacherAssignment.reporting_manager_id.isnot(None),
            TeacherAssignment.is_deleted.is_(False),
        ))).scalars().first()
        if ta and ta.reporting_manager_id:
            return ta.reporting_manager_id, "hod"
    return None, None


# =========================================================== Complaints / Service requests
class ComplaintIn(BaseModel):
    subject: str
    category: str = "general"
    description: str | None = None
    priority: str = "normal"


class ComplaintUpdateIn(BaseModel):
    note: str | None = None
    status: str | None = None          # staff: in_progress/resolved/closed ; family: reopened
    assigned_to_id: uuid.UUID | None = None  # staff only — reassign
    is_internal: bool = False          # staff-only note hidden from family


def _complaint_dict(c: Complaint, emp_names: dict, students: dict, updates: list, show_internal: bool) -> dict:
    trail = [
        {
            "id": str(u.id),
            "author": u.author_name or "—",
            "role": u.author_role,
            "note": u.note,
            "status_from": u.status_from,
            "status_to": u.status_to,
            "at": u.created_at.isoformat() if u.created_at else None,
            "is_internal": u.is_internal,
        }
        for u in updates
        if show_internal or not u.is_internal
    ]
    return {
        "id": str(c.id),
        "ticket_no": c.ticket_no,
        "subject": c.subject,
        "category": c.category,
        "description": c.description,
        "priority": c.priority,
        "status": c.complaint_status,
        "raised_by": c.raised_by_name,
        "raised_by_role": c.raised_by_role,
        "student_id": str(c.student_id) if c.student_id else None,
        "student": _student_label(students.get(c.student_id)) if c.student_id else None,
        "assigned_to_id": str(c.assigned_to_id) if c.assigned_to_id else None,
        "assigned_to": emp_names.get(c.assigned_to_id) if c.assigned_to_id else None,
        "assigned_role": c.assigned_role,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        "updates": trail,
    }


@router.get("/complaint-options")
async def complaint_options(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    kind = _kind(user)
    staff = []
    if kind in ("teacher", "admin"):
        emps = (await db.execute(select(Employee).where(
            Employee.tenant_id == user.tenant_id, Employee.is_deleted.is_(False)
        ).order_by(Employee.first_name))).scalars().all()
        staff = [{"id": str(e.id), "name": f"{e.first_name} {e.last_name or ''}".strip(),
                  "designation": e.designation} for e in emps]
    return {"categories": CATEGORIES, "priorities": PRIORITIES, "role": kind, "staff": staff}


@router.post("/complaints")
async def raise_complaint(
    payload: ComplaintIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    kind = _kind(user)
    if kind not in ("student", "parent"):
        raise HTTPException(403, "Only students and parents can raise complaints here.")
    student = await _linked_student(db, user)
    assignee, assigned_role = await _default_assignee(db, user.tenant_id, student)
    n = (await db.execute(select(func.count()).select_from(Complaint).where(
        Complaint.tenant_id == user.tenant_id))).scalar_one()
    complaint = Complaint(
        tenant_id=user.tenant_id,
        ticket_no=f"CR-{n + 1:05d}",
        subject=payload.subject,
        category=payload.category if payload.category in CATEGORIES else "general",
        description=payload.description,
        priority=payload.priority if payload.priority in PRIORITIES else "normal",
        complaint_status="assigned" if assignee else "open",
        raised_by_user_id=user.id,
        raised_by_name=user.full_name,
        raised_by_role=kind,
        student_id=student.id,
        assigned_to_id=assignee,
        assigned_role=assigned_role,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(complaint)
    await db.flush()
    db.add(ComplaintUpdate(
        tenant_id=user.tenant_id, complaint_id=complaint.id,
        author_user_id=user.id, author_name=user.full_name, author_role=kind,
        note="Complaint raised." + (" Auto-assigned to the class teacher." if assigned_role == "class_teacher"
                                    else " Auto-assigned to the HOD." if assigned_role == "hod" else ""),
        status_from=None, status_to=complaint.complaint_status,
        created_by=user.id, updated_by=user.id,
    ))
    await db.flush()
    await record_audit(db, action="create", entity="Complaint", entity_id=complaint.id, actor=user)
    return {"id": str(complaint.id), "ticket_no": complaint.ticket_no, "status": complaint.complaint_status}


@router.get("/complaints")
async def list_complaints(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    kind = _kind(user)
    tid = user.tenant_id
    conds = [Complaint.tenant_id == tid, Complaint.is_deleted.is_(False)]
    if kind in ("student", "parent"):
        student = await _linked_student(db, user)
        conds.append(Complaint.student_id == student.id)
    elif kind == "teacher":
        emp_id = await _linked_employee_id(db, user)
        conds.append(Complaint.assigned_to_id == emp_id)
    # admin/principal: all tenant complaints
    complaints = (await db.execute(select(Complaint).where(*conds)
                  .order_by(Complaint.created_at.desc()))).scalars().all()
    ids = [c.id for c in complaints]
    updates_by_complaint: dict = {cid: [] for cid in ids}
    if ids:
        ups = (await db.execute(select(ComplaintUpdate).where(
            ComplaintUpdate.complaint_id.in_(ids), ComplaintUpdate.is_deleted.is_(False)
        ).order_by(ComplaintUpdate.created_at.asc()))).scalars().all()
        for u in ups:
            updates_by_complaint.setdefault(u.complaint_id, []).append(u)
    emp_names = await _emp_names(db, tid)
    students = await _student_map(db, tid)
    show_internal = kind in ("teacher", "admin")
    return [
        _complaint_dict(c, emp_names, students, updates_by_complaint.get(c.id, []), show_internal)
        for c in complaints
    ]


async def _authorize_complaint(db: AsyncSession, user: CurrentUser, complaint_id: uuid.UUID) -> Complaint:
    c = await db.get(Complaint, complaint_id)
    if not c or c.tenant_id != user.tenant_id or c.is_deleted:
        raise HTTPException(404, "Complaint not found")
    kind = _kind(user)
    if kind in ("student", "parent"):
        student = await _linked_student(db, user)
        if c.student_id != student.id:
            raise HTTPException(403, "Not your complaint")
    elif kind == "teacher":
        emp_id = await _linked_employee_id(db, user)
        if c.assigned_to_id != emp_id:
            raise HTTPException(403, "Complaint not assigned to you")
    return c


@router.post("/complaints/{complaint_id}/updates")
async def add_complaint_update(
    complaint_id: uuid.UUID,
    payload: ComplaintUpdateIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    c = await _authorize_complaint(db, user, complaint_id)
    kind = _kind(user)
    staff = kind in ("teacher", "admin")
    status_from = c.complaint_status
    status_to = None

    if payload.status:
        target = payload.status
        if staff and target in ("open", "assigned", "in_progress", "resolved", "closed", "reopened"):
            status_to = target
        elif not staff and target == "reopened" and c.complaint_status in ("resolved", "closed"):
            status_to = "reopened"
        else:
            raise HTTPException(403, "You cannot set that status.")

    if payload.assigned_to_id is not None:
        if not staff:
            raise HTTPException(403, "Only staff can reassign a complaint.")
        emp = await db.get(Employee, payload.assigned_to_id)
        if not emp or emp.tenant_id != user.tenant_id:
            raise HTTPException(404, "Assignee not found")
        c.assigned_to_id = emp.id
        c.assigned_role = "admin" if kind == "admin" else "teacher"
        if c.complaint_status == "open":
            status_to = status_to or "assigned"

    if not payload.note and status_to is None and payload.assigned_to_id is None:
        raise HTTPException(422, "Add a note, change status, or reassign.")

    if status_to:
        c.complaint_status = status_to
        if status_to == "resolved":
            c.resolved_at = datetime.now(timezone.utc)
        if status_to == "closed":
            c.closed_at = datetime.now(timezone.utc)
    c.updated_by = user.id

    db.add(ComplaintUpdate(
        tenant_id=user.tenant_id, complaint_id=c.id,
        author_user_id=user.id, author_name=user.full_name, author_role=kind,
        note=payload.note, status_from=status_from if status_to else None, status_to=status_to,
        is_internal=bool(payload.is_internal) and staff,
        created_by=user.id, updated_by=user.id,
    ))
    await db.flush()
    await record_audit(db, action="update", entity="Complaint", entity_id=c.id, actor=user)
    return {"id": str(c.id), "status": c.complaint_status}


# ====================================================== Parent-Teacher Meetings (PTM)
class MeetingIn(BaseModel):
    student_id: uuid.UUID
    title: str
    teacher_id: uuid.UUID | None = None
    meeting_date: date | None = None
    slot_time: time | None = None
    mode: str = "in_person"
    location: str | None = None
    agenda: str | None = None


class MeetingFeedbackIn(BaseModel):
    teacher_feedback: str | None = None
    parent_feedback: str | None = None
    action_items: list[dict] | None = None
    follow_up_date: date | None = None
    notes: str | None = None
    status: str | None = None       # staff: completed/cancelled/no_show
    parent_ack: bool | None = None


def _meeting_dict(m: PtmMeeting, emp_names: dict, students: dict) -> dict:
    return {
        "id": str(m.id),
        "title": m.title,
        "student_id": str(m.student_id) if m.student_id else None,
        "student": _student_label(students.get(m.student_id)) if m.student_id else None,
        "teacher_id": str(m.teacher_id) if m.teacher_id else None,
        "teacher": emp_names.get(m.teacher_id) if m.teacher_id else None,
        "meeting_date": m.meeting_date.isoformat() if m.meeting_date else None,
        "slot_time": m.slot_time.isoformat() if m.slot_time else None,
        "mode": m.mode,
        "location": m.location,
        "status": m.meeting_status,
        "agenda": m.agenda,
        "notes": m.notes,
        "teacher_feedback": m.teacher_feedback,
        "parent_feedback": m.parent_feedback,
        "action_items": m.action_items or [],
        "follow_up_date": m.follow_up_date.isoformat() if m.follow_up_date else None,
        "parent_ack": m.parent_ack,
    }


@router.get("/meeting-options")
async def meeting_options(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    kind = _kind(user)
    if kind not in ("teacher", "admin"):
        raise HTTPException(403, "Only teachers and admins schedule meetings.")
    students = (await db.execute(select(Student).where(
        Student.tenant_id == user.tenant_id, Student.is_deleted.is_(False)
    ).order_by(Student.first_name))).scalars().all()
    scope = students
    if kind == "teacher":
        emp_id = await _linked_employee_id(db, user)
        section_ids = {a.section_id for a in (await db.execute(select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == user.tenant_id, TeacherAssignment.employee_id == emp_id,
            TeacherAssignment.is_deleted.is_(False)))).scalars().all() if a.section_id}
        if section_ids:
            scope = [s for s in students if s.section_id in section_ids] or students
    return {
        "students": [{"id": str(s.id), "label": _student_label(s)} for s in scope],
        "modes": ["in_person", "online", "phone"],
    }


@router.post("/meetings")
async def schedule_meeting(
    payload: MeetingIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    kind = _kind(user)
    if kind not in ("teacher", "admin"):
        raise HTTPException(403, "Only teachers and admins can schedule meetings.")
    student = await db.get(Student, payload.student_id)
    if not student or student.tenant_id != user.tenant_id:
        raise HTTPException(404, "Student not found")
    teacher_id = payload.teacher_id
    if kind == "teacher":
        teacher_id = await _linked_employee_id(db, user)
    m = PtmMeeting(
        tenant_id=user.tenant_id, title=payload.title, student_id=student.id, teacher_id=teacher_id,
        meeting_date=payload.meeting_date, slot_time=payload.slot_time,
        mode=payload.mode, location=payload.location, agenda=payload.agenda,
        meeting_status="scheduled", created_by=user.id, updated_by=user.id,
    )
    db.add(m)
    await db.flush()
    await record_audit(db, action="create", entity="PtmMeeting", entity_id=m.id, actor=user)
    return {"id": str(m.id), "title": m.title}


@router.get("/meetings")
async def list_meetings(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    kind = _kind(user)
    tid = user.tenant_id
    conds = [PtmMeeting.tenant_id == tid, PtmMeeting.is_deleted.is_(False)]
    if kind in ("student", "parent"):
        student = await _linked_student(db, user)
        conds.append(PtmMeeting.student_id == student.id)
    elif kind == "teacher":
        emp_id = await _linked_employee_id(db, user)
        conds.append(PtmMeeting.teacher_id == emp_id)
    meetings = (await db.execute(select(PtmMeeting).where(*conds)
                .order_by(PtmMeeting.meeting_date.desc().nullslast(), PtmMeeting.created_at.desc()))).scalars().all()
    emp_names = await _emp_names(db, tid)
    students = await _student_map(db, tid)
    return [_meeting_dict(m, emp_names, students) for m in meetings]


@router.post("/meetings/{meeting_id}/feedback")
async def meeting_feedback(
    meeting_id: uuid.UUID,
    payload: MeetingFeedbackIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    m = await db.get(PtmMeeting, meeting_id)
    if not m or m.tenant_id != user.tenant_id or m.is_deleted:
        raise HTTPException(404, "Meeting not found")
    kind = _kind(user)

    if kind in ("teacher", "admin"):
        if kind == "teacher":
            emp_id = await _linked_employee_id(db, user)
            if m.teacher_id and m.teacher_id != emp_id:
                raise HTTPException(403, "Not your meeting")
        if payload.teacher_feedback is not None:
            m.teacher_feedback = payload.teacher_feedback
        if payload.notes is not None:
            m.notes = payload.notes
        if payload.action_items is not None:
            m.action_items = payload.action_items
        if payload.follow_up_date is not None:
            m.follow_up_date = payload.follow_up_date
        if payload.status in ("completed", "cancelled", "no_show", "scheduled"):
            m.meeting_status = payload.status
    elif kind in ("student", "parent"):
        student = await _linked_student(db, user)
        if m.student_id != student.id:
            raise HTTPException(403, "Not your meeting")
        if payload.parent_feedback is not None:
            m.parent_feedback = payload.parent_feedback
        if payload.parent_ack is not None:
            m.parent_ack = payload.parent_ack
    else:
        raise HTTPException(403, "Not permitted")

    m.updated_by = user.id
    await db.flush()
    await record_audit(db, action="feedback", entity="PtmMeeting", entity_id=m.id, actor=user)
    return {"id": str(m.id), "status": m.meeting_status}
