"""Student promotion — move a cohort to the next grade / academic year."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import AcademicYear, Grade, Section
from app.models.people import Student
from app.models.student_records import StudentAcademicHistory

router = APIRouter(prefix="/promotion", tags=["Promotion"])


class PromotionIn(BaseModel):
    from_grade_id: uuid.UUID
    to_grade_id: uuid.UUID
    to_academic_year_id: uuid.UUID | None = None
    to_section_id: uuid.UUID | None = None
    student_ids: list[uuid.UUID] | None = None  # None => promote all in from_grade
    mark_graduating: bool = False  # if target is final grade, mark as graduated


@router.post("/run")
async def run_promotion(
    payload: PromotionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("report_cards_transcripts:update")),
):
    from_grade = await db.get(Grade, payload.from_grade_id)
    to_grade = await db.get(Grade, payload.to_grade_id)
    if not from_grade or not to_grade or from_grade.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")

    conditions = [
        Student.tenant_id == user.tenant_id,
        Student.grade_id == payload.from_grade_id,
        Student.is_deleted.is_(False),
        Student.enrollment_status == "enrolled",
    ]
    if payload.student_ids:
        conditions.append(Student.id.in_(payload.student_ids))
    students = (await db.execute(select(Student).where(*conditions))).scalars().all()

    # Lookups to snapshot the completed year into academic history.
    years = {y.id: y.name for y in (await db.execute(
        select(AcademicYear).where(AcademicYear.tenant_id == user.tenant_id))).scalars().all()}
    sections = {s.id: s.name for s in (await db.execute(
        select(Section).where(Section.tenant_id == user.tenant_id))).scalars().all()}

    promoted = 0
    for st in students:
        # Record the year/grade the student just completed.
        db.add(StudentAcademicHistory(
            tenant_id=user.tenant_id, student_id=st.id,
            academic_year=years.get(st.academic_year_id, "—"),
            grade=from_grade.name, section=sections.get(st.section_id),
            result="graduated" if payload.mark_graduating else "promoted",
            created_by=user.id, updated_by=user.id,
        ))
        st.grade_id = payload.to_grade_id
        if payload.to_section_id:
            st.section_id = payload.to_section_id
        if payload.to_academic_year_id:
            st.academic_year_id = payload.to_academic_year_id
        # Promoted students stay 'enrolled' in the new grade (so they can be promoted
        # again next year); only graduating students exit the active roll.
        st.enrollment_status = "graduated" if payload.mark_graduating else "enrolled"
        st.updated_by = user.id
        promoted += 1

    await db.flush()
    await record_audit(
        db, action="promote", entity="Student", actor=user,
        changes={"from_grade": str(payload.from_grade_id), "to_grade": str(payload.to_grade_id),
                 "count": promoted, "graduating": payload.mark_graduating},
    )
    return {
        "detail": "promotion completed",
        "promoted": promoted,
        "from_grade": from_grade.name,
        "to_grade": to_grade.name,
        "status_set": "graduated" if payload.mark_graduating else "promoted",
    }
