"""Class-based student promotion gated by published, reviewed examination results."""
from __future__ import annotations

import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import AcademicYear, Grade, Section, Subject
from app.models.exams import Exam, Marks, MarksBatch
from app.models.people import Employee, Student
from app.models.student_records import StudentAcademicHistory

router = APIRouter(prefix="/promotion", tags=["Promotion"])


async def _eligibility(db: AsyncSession, tid: uuid.UUID, grade_id: uuid.UUID, exam_id: uuid.UUID,
                       section_id: uuid.UUID | None = None) -> dict:
    exam = await db.get(Exam, exam_id)
    if not exam or exam.tenant_id != tid or exam.is_deleted:
        raise HTTPException(404, "Exam not found")
    if exam.grade_id and exam.grade_id != grade_id:
        raise HTTPException(409, "Selected exam does not belong to the source class")
    conditions = [
        Student.tenant_id == tid, Student.grade_id == grade_id,
        Student.enrollment_status == "enrolled", Student.is_deleted.is_(False),
    ]
    if section_id:
        conditions.append(Student.section_id == section_id)
    students = (await db.execute(select(Student).where(*conditions).order_by(
        Student.section_id, Student.roll_no, Student.admission_no
    ))).scalars().all()
    batches = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == tid, MarksBatch.exam_id == exam_id,
        MarksBatch.grade_id == grade_id, MarksBatch.is_deleted.is_(False),
    ))).scalars().all()
    relevant_batches = [
        b for b in batches if not section_id or b.section_id in (None, section_id)
    ]
    subject_ids = {b.subject_id for b in relevant_batches}
    subjects = {s.id: s.name for s in (await db.execute(select(Subject).where(
        Subject.tenant_id == tid))).scalars().all()}
    employees = {e.id: f"{e.first_name} {e.last_name or ''}".strip() for e in (
        await db.execute(select(Employee).where(Employee.tenant_id == tid))
    ).scalars().all()}
    marks = (await db.execute(select(Marks).where(
        Marks.tenant_id == tid, Marks.exam_id == exam_id,
        Marks.student_id.in_([s.id for s in students]) if students else Marks.student_id.is_(None),
        Marks.is_deleted.is_(False),
    ))).scalars().all()
    by_student: dict[uuid.UUID, dict[uuid.UUID, Marks]] = defaultdict(dict)
    for mark in marks:
        by_student[mark.student_id][mark.subject_id] = mark
    sections = {s.id: s.name for s in (await db.execute(select(Section).where(
        Section.tenant_id == tid))).scalars().all()}
    all_published = bool(relevant_batches) and all(b.batch_status == "published" for b in relevant_batches)
    reviewers = sorted({employees.get(b.reviewer_id, "Academic reviewer") for b in relevant_batches if b.reviewer_id})
    rows = []
    for student in students:
        student_marks = by_student.get(student.id, {})
        missing = [subjects.get(subject_id, "Subject") for subject_id in subject_ids if subject_id not in student_marks]
        failed = []
        total, maximum = 0.0, 0.0
        for subject_id in subject_ids:
            mark = student_marks.get(subject_id)
            if not mark:
                continue
            obtained, max_marks = float(mark.marks_obtained), float(mark.max_marks)
            total += obtained
            maximum += max_marks
            pass_threshold = float(exam.pass_marks) / float(exam.max_marks) * max_marks if exam.max_marks else 0
            if mark.is_absent or obtained < pass_threshold:
                failed.append(subjects.get(subject_id, "Subject"))
        class_assigned = bool(student.grade_id and student.section_id)
        eligible = class_assigned and all_published and not missing and not failed and bool(subject_ids)
        reasons = []
        if not class_assigned:
            reasons.append("Class/section not assigned")
        if not relevant_batches:
            reasons.append("No marks sheets submitted")
        elif not all_published:
            reasons.append("Marks await academic review/publication")
        if missing:
            reasons.append("Missing: " + ", ".join(missing))
        if failed:
            reasons.append("Below pass mark: " + ", ".join(failed))
        rows.append({
            "student_id": str(student.id), "admission_no": student.admission_no,
            "roll_no": student.roll_no,
            "student": f"{student.first_name} {student.last_name or ''}".strip(),
            "section": sections.get(student.section_id, "—"),
            "percentage": round(total / maximum * 100, 2) if maximum else 0,
            "eligible": eligible, "reason": "; ".join(reasons) if reasons else "Eligible",
        })
    return {
        "exam": {"id": str(exam.id), "name": exam.name},
        "review_status": "published" if all_published else (
            "pending_review" if relevant_batches else "not_submitted"
        ),
        "reviewers": reviewers,
        "subjects": [subjects.get(subject_id, "Subject") for subject_id in subject_ids],
        "rows": rows,
        "summary": {
            "students": len(rows), "eligible": sum(r["eligible"] for r in rows),
            "blocked": sum(not r["eligible"] for r in rows),
        },
    }


@router.get("/eligibility")
async def eligibility(
    from_grade_id: uuid.UUID = Query(...),
    exam_id: uuid.UUID = Query(...),
    section_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("report_cards_transcripts:read")),
):
    return await _eligibility(db, user.tenant_id, from_grade_id, exam_id, section_id)


class PromotionIn(BaseModel):
    from_grade_id: uuid.UUID
    to_grade_id: uuid.UUID
    exam_id: uuid.UUID
    to_academic_year_id: uuid.UUID | None = None
    from_section_id: uuid.UUID | None = None
    to_section_id: uuid.UUID | None = None
    student_ids: list[uuid.UUID] | None = None
    mark_graduating: bool = False


@router.post("/run")
async def run_promotion(
    payload: PromotionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("report_cards_transcripts:update")),
):
    from_grade = await db.get(Grade, payload.from_grade_id)
    to_grade = await db.get(Grade, payload.to_grade_id)
    if not from_grade or not to_grade or from_grade.tenant_id != user.tenant_id or to_grade.tenant_id != user.tenant_id:
        raise HTTPException(404, "Grade not found")
    if from_grade.id == to_grade.id:
        raise HTTPException(409, "Source and destination classes must differ")
    if not payload.mark_graduating and to_grade.sequence <= from_grade.sequence:
        raise HTTPException(409, "Destination class must be above the source class")
    eligibility_data = await _eligibility(
        db, user.tenant_id, payload.from_grade_id, payload.exam_id, payload.from_section_id
    )
    selected = set(payload.student_ids or [uuid.UUID(r["student_id"]) for r in eligibility_data["rows"]])
    eligible_ids = {uuid.UUID(r["student_id"]) for r in eligibility_data["rows"] if r["eligible"]}
    blocked = selected - eligible_ids
    if blocked:
        names = [r["student"] for r in eligibility_data["rows"] if uuid.UUID(r["student_id"]) in blocked]
        raise HTTPException(409, "Promotion blocked for: " + ", ".join(names))
    if not selected:
        raise HTTPException(409, "No eligible students selected")
    students = (await db.execute(select(Student).where(
        Student.tenant_id == user.tenant_id, Student.id.in_(selected),
        Student.grade_id == payload.from_grade_id, Student.enrollment_status == "enrolled",
        Student.is_deleted.is_(False),
    ))).scalars().all()
    years = {y.id: y.name for y in (await db.execute(select(AcademicYear).where(
        AcademicYear.tenant_id == user.tenant_id))).scalars().all()}
    sections = {s.id: s.name for s in (await db.execute(select(Section).where(
        Section.tenant_id == user.tenant_id))).scalars().all()}
    percentages = {uuid.UUID(r["student_id"]): r["percentage"] for r in eligibility_data["rows"]}
    for student in students:
        db.add(StudentAcademicHistory(
            tenant_id=user.tenant_id, student_id=student.id,
            academic_year=years.get(student.academic_year_id, "—"), grade=from_grade.name,
            section=sections.get(student.section_id),
            result="graduated" if payload.mark_graduating else "promoted",
            percentage=percentages.get(student.id),
            remarks=f"Promotion based on published {eligibility_data['exam']['name']} results",
            created_by=user.id, updated_by=user.id,
        ))
        student.grade_id = payload.to_grade_id
        if payload.to_section_id:
            student.section_id = payload.to_section_id
        if payload.to_academic_year_id:
            student.academic_year_id = payload.to_academic_year_id
        student.enrollment_status = "graduated" if payload.mark_graduating else "enrolled"
        student.updated_by = user.id
    await db.flush()
    await record_audit(
        db, action="promote", entity="Student", actor=user,
        changes={"from_grade": str(payload.from_grade_id), "to_grade": str(payload.to_grade_id),
                 "exam_id": str(payload.exam_id), "count": len(students)},
    )
    return {
        "detail": "promotion completed", "promoted": len(students),
        "from_grade": from_grade.name, "to_grade": to_grade.name,
        "status_set": "graduated" if payload.mark_graduating else "promoted",
    }
