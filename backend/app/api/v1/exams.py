"""Examinations — marks entry and report-card generation."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import Grade, Section, Subject
from app.models.auth import User
from app.models.exams import Exam, Marks, MarksBatch
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


class MarkSheetIn(BaseModel):
    subject_id: uuid.UUID
    grade_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    reviewer_id: uuid.UUID | None = None
    entries: list[MarkEntry]


class BatchDecisionIn(BaseModel):
    decision: str
    review_note: str | None = None


async def _get_or_create_batch(
    db: AsyncSession,
    user: CurrentUser,
    exam_id: uuid.UUID,
    subject_id: uuid.UUID,
    grade_id: uuid.UUID | None,
    section_id: uuid.UUID | None,
    reviewer_id: uuid.UUID | None = None,
) -> MarksBatch:
    db_user = await db.get(User, user.id)
    teacher_id = db_user.person_id if db_user and db_user.person_type == "employee" else None
    existing = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == user.tenant_id,
        MarksBatch.exam_id == exam_id,
        MarksBatch.subject_id == subject_id,
        MarksBatch.grade_id == grade_id,
        MarksBatch.section_id == section_id,
        MarksBatch.is_deleted.is_(False),
    ))).scalars().first()
    if existing:
        if reviewer_id:
            existing.reviewer_id = reviewer_id
        return existing
    batch = MarksBatch(
        tenant_id=user.tenant_id,
        exam_id=exam_id,
        subject_id=subject_id,
        grade_id=grade_id,
        section_id=section_id,
        teacher_id=teacher_id,
        reviewer_id=reviewer_id,
        batch_status="draft",
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(batch)
    await db.flush()
    return batch


async def _write_marks(db: AsyncSession, user: CurrentUser, exam_id: uuid.UUID, entries: list[MarkEntry]) -> int:
    written = 0
    for e in entries:
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
    return written


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

    written = await _write_marks(db, user, exam_id, payload.entries)
    await db.flush()
    await record_audit(db, action="enter_marks", entity="Marks", entity_id=exam_id, actor=user,
                       changes={"count": written})
    return {"detail": "marks recorded", "count": written}


@router.get("/{exam_id}/marks-sheet")
async def marks_sheet(
    exam_id: uuid.UUID,
    subject_id: uuid.UUID = Query(...),
    grade_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("examination_management:read")),
):
    exam = await db.get(Exam, exam_id)
    if not exam or exam.tenant_id != user.tenant_id or exam.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    conditions = [Student.tenant_id == user.tenant_id, Student.is_deleted.is_(False)]
    if grade_id:
        conditions.append(Student.grade_id == grade_id)
    if section_id:
        conditions.append(Student.section_id == section_id)
    students = (await db.execute(select(Student).where(*conditions).order_by(Student.roll_no, Student.admission_no))).scalars().all()
    marks = (await db.execute(select(Marks).where(
        Marks.tenant_id == user.tenant_id,
        Marks.exam_id == exam_id,
        Marks.subject_id == subject_id,
        Marks.is_deleted.is_(False),
    ))).scalars().all()
    by_student = {m.student_id: m for m in marks}
    batch = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == user.tenant_id,
        MarksBatch.exam_id == exam_id,
        MarksBatch.subject_id == subject_id,
        MarksBatch.grade_id == grade_id,
        MarksBatch.section_id == section_id,
        MarksBatch.is_deleted.is_(False),
    ))).scalars().first()
    return {
        "exam": {"id": str(exam.id), "name": exam.name, "code": exam.code},
        "batch": None if not batch else {
            "id": str(batch.id), "status": batch.batch_status,
            "reviewer_id": str(batch.reviewer_id) if batch.reviewer_id else None,
            "review_note": batch.review_note,
        },
        "rows": [
            {
                "student_id": str(s.id),
                "admission_no": s.admission_no,
                "roll_no": s.roll_no,
                "student_name": f"{s.first_name} {s.last_name or ''}".strip(),
                "marks_obtained": str(by_student[s.id].marks_obtained) if s.id in by_student else "",
                "max_marks": str(by_student[s.id].max_marks) if s.id in by_student else str(exam.max_marks),
                "is_absent": by_student[s.id].is_absent if s.id in by_student else False,
                "remarks": by_student[s.id].remarks if s.id in by_student else None,
                "grade": by_student[s.id].grade_letter if s.id in by_student else None,
            }
            for s in students
        ],
    }


@router.post("/{exam_id}/marks-sheet")
async def save_marks_sheet(
    exam_id: uuid.UUID,
    payload: MarkSheetIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("examination_management:create")),
):
    exam = await db.get(Exam, exam_id)
    if not exam or exam.tenant_id != user.tenant_id or exam.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Exam not found")
    batch = await _get_or_create_batch(
        db, user, exam_id, payload.subject_id, payload.grade_id, payload.section_id, payload.reviewer_id
    )
    if batch.batch_status in ("approved", "published"):
        raise HTTPException(409, "Approved marks are locked and cannot be changed")
    written = await _write_marks(db, user, exam_id, payload.entries)
    batch.batch_status = "draft"
    batch.updated_by = user.id
    await db.flush()
    await record_audit(db, action="save_marks_sheet", entity="MarksBatch", entity_id=batch.id, actor=user,
                       changes={"count": written})
    return {"detail": "marks sheet saved", "count": written, "batch_id": str(batch.id), "status": batch.batch_status}


@router.post("/marks-batches/{batch_id}/submit")
async def submit_marks_batch(
    batch_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("examination_management:create")),
):
    batch = await db.get(MarksBatch, batch_id)
    if not batch or batch.tenant_id != user.tenant_id or batch.is_deleted:
        raise HTTPException(404, "Marks batch not found")
    if batch.batch_status not in ("draft", "rejected"):
        raise HTTPException(409, "Only draft or rejected batches can be submitted")
    batch.batch_status = "submitted"
    batch.submitted_at = datetime.now(timezone.utc)
    batch.updated_by = user.id
    await db.flush()
    await record_audit(db, action="submit", entity="MarksBatch", entity_id=batch.id, actor=user)
    return {"id": str(batch.id), "status": batch.batch_status}


@router.post("/marks-batches/{batch_id}/review")
async def review_marks_batch(
    batch_id: uuid.UUID,
    payload: BatchDecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("examination_management:approve")),
):
    if payload.decision not in ("approved", "rejected", "published"):
        raise HTTPException(422, "decision must be approved, rejected or published")
    batch = await db.get(MarksBatch, batch_id)
    if not batch or batch.tenant_id != user.tenant_id or batch.is_deleted:
        raise HTTPException(404, "Marks batch not found")
    if payload.decision == "published" and batch.batch_status != "approved":
        raise HTTPException(409, "Only approved batches can be published")
    if payload.decision in ("approved", "rejected") and batch.batch_status != "submitted":
        raise HTTPException(409, "Only submitted batches can be reviewed")
    batch.batch_status = payload.decision
    batch.reviewer_id = user.id
    batch.review_note = payload.review_note
    batch.reviewed_at = datetime.now(timezone.utc)
    if payload.decision == "published":
        batch.published_at = datetime.now(timezone.utc)
    batch.updated_by = user.id
    await db.flush()
    await record_audit(db, action=payload.decision, entity="MarksBatch", entity_id=batch.id, actor=user)
    return {"id": str(batch.id), "status": batch.batch_status}


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
    batches = (await db.execute(select(MarksBatch).where(
        MarksBatch.tenant_id == user.tenant_id,
        MarksBatch.exam_id == exam_id,
        MarksBatch.is_deleted.is_(False),
    ))).scalars().all()
    if batches:
        published_subjects = {b.subject_id for b in batches if b.batch_status == "published"}
        rows = [m for m in rows if m.subject_id in published_subjects]
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
