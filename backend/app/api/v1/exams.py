"""Examinations — marks entry and report-card generation."""
from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.exams import Exam, Marks
from app.models.people import Student

router = APIRouter(prefix="/exams", tags=["Exams"])


def _grade_letter(pct: float) -> str:
    if pct >= 90: return "A+"
    if pct >= 80: return "A"
    if pct >= 70: return "B+"
    if pct >= 60: return "B"
    if pct >= 50: return "C"
    if pct >= 40: return "D"
    return "E"


class MarkEntry(BaseModel):
    student_id: uuid.UUID
    subject_id: uuid.UUID
    marks_obtained: Decimal
    max_marks: Decimal = Decimal(100)
    is_absent: bool = False
    remarks: str | None = None


class MarksBulkIn(BaseModel):
    entries: list[MarkEntry]


@router.post("/{exam_id}/marks")
async def enter_marks(
    exam_id: uuid.UUID,
    payload: MarksBulkIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("examination_management:create")),
):
    exam = await db.get(Exam, exam_id)
    if not exam or exam.tenant_id != user.tenant_id or exam.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")

    written = 0
    for e in payload.entries:
        pct = float(e.marks_obtained) / float(e.max_marks) * 100 if e.max_marks else 0
        letter = "AB" if e.is_absent else _grade_letter(pct)
        existing = (
            await db.execute(
                select(Marks).where(
                    Marks.tenant_id == user.tenant_id, Marks.exam_id == exam_id,
                    Marks.student_id == e.student_id, Marks.subject_id == e.subject_id,
                )
            )
        ).scalars().first()
        if existing:
            existing.marks_obtained = e.marks_obtained
            existing.max_marks = e.max_marks
            existing.grade_letter = letter
            existing.is_absent = e.is_absent
            existing.remarks = e.remarks
            existing.updated_by = user.id
        else:
            db.add(Marks(
                tenant_id=user.tenant_id, exam_id=exam_id, student_id=e.student_id, subject_id=e.subject_id,
                marks_obtained=e.marks_obtained, max_marks=e.max_marks, grade_letter=letter,
                is_absent=e.is_absent, remarks=e.remarks, created_by=user.id, updated_by=user.id,
            ))
        written += 1
    await db.flush()
    await record_audit(db, action="enter_marks", entity="Marks", entity_id=exam_id, actor=user,
                       changes={"count": written})
    return {"detail": "marks recorded", "count": written}


@router.get("/{exam_id}/report-card/{student_id}")
async def report_card(
    exam_id: uuid.UUID,
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("report_cards_transcripts:read")),
):
    exam = await db.get(Exam, exam_id)
    student = await db.get(Student, student_id)
    if not exam or not student or exam.tenant_id != user.tenant_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam or student not found")
    rows = (
        await db.execute(
            select(Marks).where(
                Marks.tenant_id == user.tenant_id, Marks.exam_id == exam_id, Marks.student_id == student_id,
                Marks.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    total_obtained = sum(float(m.marks_obtained) for m in rows)
    total_max = sum(float(m.max_marks) for m in rows) or 1
    pct = round(total_obtained / total_max * 100, 2)
    return {
        "exam": {"id": str(exam.id), "name": exam.name, "type": exam.exam_type},
        "student": {"id": str(student.id), "name": f"{student.first_name} {student.last_name or ''}".strip(),
                    "admission_no": student.admission_no},
        "subjects": [
            {"subject_id": str(m.subject_id), "marks_obtained": str(m.marks_obtained),
             "max_marks": str(m.max_marks), "grade": m.grade_letter, "is_absent": m.is_absent}
            for m in rows
        ],
        "total_obtained": total_obtained,
        "total_max": total_max,
        "percentage": pct,
        "overall_grade": _grade_letter(pct),
        "result": "PASS" if total_obtained >= float(exam.pass_marks) * len(rows) else "FAIL" if rows else "N/A",
    }
