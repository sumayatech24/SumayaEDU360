"""Teacher-authored question bank, class practice assignments and student attempts."""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.academic import Grade, Section, Subject
from app.models.auth import User
from app.models.content import QuestionAssignment, QuestionAttempt, QuestionBankItem
from app.models.people import Employee, Student, TeacherAssignment

router = APIRouter(prefix="/question-bank", tags=["Question Bank"])


class QuestionIn(BaseModel):
    subject_id: uuid.UUID
    grade_id: uuid.UUID
    question_type: str = Field(pattern=r"^(mcq|true_false|short|long)$")
    difficulty: str = Field(default="medium", pattern=r"^(easy|medium|hard)$")
    marks: int = Field(default=1, ge=1, le=100)
    question_text: str = Field(min_length=3)
    answer_text: str
    options: list[str] = Field(default_factory=list)
    explanation: str | None = None


class AssignmentIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    instructions: str | None = None
    grade_id: uuid.UUID
    section_id: uuid.UUID | None = None
    subject_id: uuid.UUID
    question_ids: list[uuid.UUID] = Field(min_length=1)
    due_date: date | None = None
    publish: bool = True


class AttemptIn(BaseModel):
    answers: dict[str, str]


class GradeIn(BaseModel):
    score: int = Field(ge=0)
    feedback: str | None = None


async def _principal(db: AsyncSession, user: CurrentUser) -> User:
    row = await db.get(User, user.id)
    if not row or not row.person_id:
        raise HTTPException(403, "A linked teacher or student account is required")
    return row


async def _employee(db: AsyncSession, user: CurrentUser) -> Employee:
    principal = await _principal(db, user)
    if principal.person_type != "employee":
        raise HTTPException(403, "Teacher access required")
    row = await db.get(Employee, principal.person_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(403, "Teacher profile not found")
    return row


async def _student(db: AsyncSession, user: CurrentUser) -> Student:
    principal = await _principal(db, user)
    if principal.person_type != "student":
        raise HTTPException(403, "Student access required")
    row = await db.get(Student, principal.person_id)
    if not row or row.tenant_id != user.tenant_id:
        raise HTTPException(403, "Student profile not found")
    return row


async def _can_teach(db: AsyncSession, tid, employee_id, grade_id, subject_id, section_id=None):
    conditions = [
        TeacherAssignment.tenant_id == tid, TeacherAssignment.employee_id == employee_id,
        TeacherAssignment.grade_id == grade_id, TeacherAssignment.subject_id == subject_id,
        TeacherAssignment.assignment_status == "active", TeacherAssignment.is_deleted.is_(False),
    ]
    if section_id:
        conditions.append(TeacherAssignment.section_id == section_id)
    if not (await db.execute(select(TeacherAssignment.id).where(*conditions))).scalar_one_or_none():
        raise HTTPException(403, "This class and subject are not assigned to the teacher")


def _question_out(q: QuestionBankItem, include_answer=True):
    row = {"id": str(q.id), "subject_id": str(q.subject_id), "grade_id": str(q.grade_id),
           "question_type": q.question_type, "difficulty": q.difficulty, "marks": q.marks,
           "question_text": q.question_text, "options": q.options or []}
    if include_answer:
        row.update(answer_text=q.answer_text, explanation=q.explanation)
    return row


@router.get("/questions")
async def questions(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    employee = await _employee(db, user)
    rows = (await db.execute(select(QuestionBankItem).where(
        QuestionBankItem.tenant_id == user.tenant_id,
        QuestionBankItem.created_by_employee_id == employee.id,
        QuestionBankItem.is_deleted.is_(False),
    ).order_by(QuestionBankItem.created_at.desc()))).scalars().all()
    return [_question_out(q) for q in rows]


@router.post("/questions", status_code=201)
async def create_question(payload: QuestionIn, db: AsyncSession = Depends(get_db),
                          user: CurrentUser = Depends(get_current_user)):
    employee = await _employee(db, user)
    await _can_teach(db, user.tenant_id, employee.id, payload.grade_id, payload.subject_id)
    if payload.question_type in ("mcq", "true_false") and len(payload.options) < 2:
        raise HTTPException(422, "Objective questions require at least two options")
    row = QuestionBankItem(tenant_id=user.tenant_id, created_by_employee_id=employee.id,
                           created_by=user.id, updated_by=user.id, **payload.model_dump())
    db.add(row)
    await db.flush()
    await record_audit(db, action="create", entity="QuestionBankItem", entity_id=row.id, actor=user)
    return _question_out(row)


@router.post("/assignments", status_code=201)
async def create_assignment(payload: AssignmentIn, db: AsyncSession = Depends(get_db),
                            user: CurrentUser = Depends(get_current_user)):
    employee = await _employee(db, user)
    await _can_teach(db, user.tenant_id, employee.id, payload.grade_id, payload.subject_id, payload.section_id)
    rows = (await db.execute(select(QuestionBankItem).where(
        QuestionBankItem.tenant_id == user.tenant_id,
        QuestionBankItem.id.in_(payload.question_ids),
        QuestionBankItem.created_by_employee_id == employee.id,
        QuestionBankItem.grade_id == payload.grade_id,
        QuestionBankItem.subject_id == payload.subject_id,
        QuestionBankItem.is_deleted.is_(False),
    ))).scalars().all()
    if len(rows) != len(set(payload.question_ids)):
        raise HTTPException(422, "Every selected question must belong to this teacher, class and subject")
    row = QuestionAssignment(
        tenant_id=user.tenant_id, teacher_id=employee.id,
        assignment_status="published" if payload.publish else "draft",
        created_by=user.id, updated_by=user.id,
        **payload.model_dump(exclude={"publish"}),
    )
    row.question_ids = [str(qid) for qid in payload.question_ids]
    db.add(row)
    await db.flush()
    await record_audit(db, action="publish" if payload.publish else "create",
                       entity="QuestionAssignment", entity_id=row.id, actor=user)
    return {"id": str(row.id), "status": row.assignment_status}


@router.get("/teacher/assignments")
async def teacher_assignments(db: AsyncSession = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    employee = await _employee(db, user)
    rows = (await db.execute(select(QuestionAssignment).where(
        QuestionAssignment.tenant_id == user.tenant_id,
        QuestionAssignment.teacher_id == employee.id,
        QuestionAssignment.is_deleted.is_(False),
    ).order_by(QuestionAssignment.created_at.desc()))).scalars().all()
    return [{"id": str(r.id), "title": r.title, "status": r.assignment_status,
             "grade_id": str(r.grade_id), "section_id": str(r.section_id) if r.section_id else None,
             "subject_id": str(r.subject_id), "due_date": r.due_date,
             "question_count": len(r.question_ids or [])} for r in rows]


@router.get("/teacher/assignments/{assignment_id}/attempts")
async def assignment_attempts(assignment_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    employee = await _employee(db, user)
    assignment = await db.get(QuestionAssignment, assignment_id)
    if not assignment or assignment.tenant_id != user.tenant_id or assignment.teacher_id != employee.id:
        raise HTTPException(404, "Assignment not found")
    attempts = (await db.execute(select(QuestionAttempt).where(
        QuestionAttempt.assignment_id == assignment.id,
        QuestionAttempt.is_deleted.is_(False),
    ).order_by(QuestionAttempt.created_at.desc()))).scalars().all()
    students = {s.id: s for s in (await db.execute(select(Student).where(
        Student.id.in_([a.student_id for a in attempts]) if attempts else Student.id.is_(None)
    ))).scalars().all()}
    return [{"id": str(a.id), "student": f"{students[a.student_id].first_name} {students[a.student_id].last_name or ''}".strip()
             if a.student_id in students else "Student", "answers": a.answers,
             "status": a.attempt_status, "score": a.score, "max_score": a.max_score,
             "feedback": a.teacher_feedback} for a in attempts]


async def _student_assignment_view(db, assignment, student):
    ids = [uuid.UUID(x) for x in assignment.question_ids or []]
    questions = (await db.execute(select(QuestionBankItem).where(
        QuestionBankItem.id.in_(ids), QuestionBankItem.is_deleted.is_(False),
    ))).scalars().all()
    attempt = (await db.execute(select(QuestionAttempt).where(
        QuestionAttempt.assignment_id == assignment.id,
        QuestionAttempt.student_id == student.id,
        QuestionAttempt.is_deleted.is_(False),
    ))).scalars().first()
    completed = bool(attempt and attempt.attempt_status in ("submitted", "graded"))
    return {"id": str(assignment.id), "title": assignment.title, "instructions": assignment.instructions,
            "due_date": assignment.due_date, "status": assignment.assignment_status,
            "questions": [_question_out(q, include_answer=completed) for q in questions],
            "attempt": None if not attempt else {"id": str(attempt.id), "answers": attempt.answers,
                "status": attempt.attempt_status, "score": attempt.score,
                "max_score": attempt.max_score, "feedback": attempt.teacher_feedback}}


@router.get("/student/assignments")
async def student_assignments(db: AsyncSession = Depends(get_db),
                              user: CurrentUser = Depends(get_current_user)):
    student = await _student(db, user)
    rows = (await db.execute(select(QuestionAssignment).where(
        QuestionAssignment.tenant_id == user.tenant_id,
        QuestionAssignment.grade_id == student.grade_id,
        (QuestionAssignment.section_id == student.section_id) | (QuestionAssignment.section_id.is_(None)),
        QuestionAssignment.assignment_status.in_(("published", "closed")),
        QuestionAssignment.is_deleted.is_(False),
    ).order_by(QuestionAssignment.due_date, QuestionAssignment.created_at.desc()))).scalars().all()
    return [await _student_assignment_view(db, row, student) for row in rows]


@router.post("/student/assignments/{assignment_id}/submit")
async def submit_attempt(assignment_id: uuid.UUID, payload: AttemptIn,
                         db: AsyncSession = Depends(get_db),
                         user: CurrentUser = Depends(get_current_user)):
    student = await _student(db, user)
    assignment = await db.get(QuestionAssignment, assignment_id)
    if not assignment or assignment.tenant_id != user.tenant_id or assignment.assignment_status != "published":
        raise HTTPException(404, "Published assignment not found")
    if assignment.grade_id != student.grade_id or assignment.section_id not in (None, student.section_id):
        raise HTTPException(403, "Assignment is not for this student")
    view = await _student_assignment_view(db, assignment, student)
    if view["attempt"] and view["attempt"]["status"] in ("submitted", "graded"):
        raise HTTPException(409, "This assignment has already been submitted")
    ids = [uuid.UUID(x) for x in assignment.question_ids or []]
    question_rows = (await db.execute(select(QuestionBankItem).where(
        QuestionBankItem.id.in_(ids), QuestionBankItem.is_deleted.is_(False),
    ))).scalars().all()
    score = 0
    auto_gradable = True
    for q in question_rows:
        if q.question_type in ("mcq", "true_false"):
            if payload.answers.get(str(q.id), "").strip().casefold() == (q.answer_text or "").strip().casefold():
                score += q.marks
        else:
            auto_gradable = False
    max_score = sum(q.marks for q in question_rows)
    attempt = QuestionAttempt(
        tenant_id=user.tenant_id, assignment_id=assignment.id, student_id=student.id,
        answers=payload.answers, score=score if auto_gradable else None, max_score=max_score,
        attempt_status="graded" if auto_gradable else "submitted", submitted_at=date.today(),
        created_by=user.id, updated_by=user.id,
    )
    db.add(attempt)
    await db.flush()
    await record_audit(db, action="submit", entity="QuestionAttempt", entity_id=attempt.id, actor=user)
    return {"id": str(attempt.id), "status": attempt.attempt_status,
            "score": attempt.score, "max_score": attempt.max_score}


@router.post("/attempts/{attempt_id}/grade")
async def grade_attempt(attempt_id: uuid.UUID, payload: GradeIn,
                        db: AsyncSession = Depends(get_db),
                        user: CurrentUser = Depends(get_current_user)):
    employee = await _employee(db, user)
    attempt = await db.get(QuestionAttempt, attempt_id)
    assignment = await db.get(QuestionAssignment, attempt.assignment_id) if attempt else None
    if not attempt or not assignment or assignment.teacher_id != employee.id:
        raise HTTPException(404, "Attempt not found")
    if payload.score > attempt.max_score:
        raise HTTPException(422, "Score cannot exceed maximum marks")
    attempt.score, attempt.teacher_feedback = payload.score, payload.feedback
    attempt.attempt_status, attempt.updated_by = "graded", user.id
    await record_audit(db, action="grade", entity="QuestionAttempt", entity_id=attempt.id, actor=user)
    return {"id": str(attempt.id), "status": attempt.attempt_status,
            "score": attempt.score, "max_score": attempt.max_score}
