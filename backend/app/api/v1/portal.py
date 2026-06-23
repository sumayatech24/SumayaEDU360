"""Per-persona portals.

Resolves which portal a signed-in user belongs to (student / parent / teacher / admin)
and serves self-scoped dashboard data that does NOT require module-level RBAC — a student
or parent can always see their own child's data, a teacher their teaching summary.
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.reporting import student_360
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.academics_ops import Homework, HomeworkSubmission
from app.models.attendance import Attendance
from app.models.auth import User
from app.models.operations import Announcement
from app.models.people import Employee, Student

router = APIRouter(prefix="/portal", tags=["Portals"])


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
    db_user = await db.get(User, user.id)
    if not db_user.person_id:
        raise HTTPException(404, "No student linked to this account")
    data = await student_360(str(db_user.person_id), db, user)
    data["announcements"] = await _announcements(db, user.tenant_id,
                                                  "parents" if "parent" in user.roles else "students")
    return data


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
