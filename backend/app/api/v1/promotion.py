"""Annual cumulative results and class promotion."""
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
from app.models.exams import Exam, ExamSubject, Marks, MarksBatch
from app.models.people import Employee, Student
from app.models.student_records import StudentAcademicHistory
from app.models.tenant import Institution

router = APIRouter(prefix="/promotion", tags=["Promotion"])


def _grade_label(percentage: float, passed: bool) -> str:
    """CBSE-style scholastic grade bands; eligibility still follows configured policy."""
    if not passed:
        return "E"
    if percentage >= 91:
        return "A1"
    if percentage >= 81:
        return "A2"
    if percentage >= 71:
        return "B1"
    if percentage >= 61:
        return "B2"
    if percentage >= 51:
        return "C1"
    if percentage >= 41:
        return "C2"
    return "D"


async def _eligibility(
    db: AsyncSession,
    tid: uuid.UUID,
    grade_id: uuid.UUID,
    exam_id: uuid.UUID,
    section_id: uuid.UUID | None = None,
) -> dict:
    final_exam = await db.get(Exam, exam_id)
    if not final_exam or final_exam.tenant_id != tid or final_exam.is_deleted:
        raise HTTPException(404, "Exam not found")
    if final_exam.grade_id and final_exam.grade_id != grade_id:
        raise HTTPException(409, "Selected exam does not belong to the source class")
    if not final_exam.is_final_exam:
        raise HTTPException(409, "Select an examination marked as the final examination")

    student_conditions = [
        Student.tenant_id == tid,
        Student.grade_id == grade_id,
        Student.enrollment_status == "enrolled",
        Student.is_deleted.is_(False),
    ]
    if section_id:
        student_conditions.append(Student.section_id == section_id)
    students = (await db.execute(select(Student).where(*student_conditions).order_by(
        Student.section_id, Student.roll_no, Student.admission_no
    ))).scalars().all()

    exam_conditions = [
        Exam.tenant_id == tid,
        Exam.academic_year_id == final_exam.academic_year_id,
        Exam.grade_id == grade_id,
        Exam.is_deleted.is_(False),
    ]
    if final_exam.end_date:
        exam_conditions.append(Exam.end_date <= final_exam.end_date)
    exams = (await db.execute(select(Exam).where(*exam_conditions).order_by(
        Exam.start_date, Exam.name
    ))).scalars().all()
    if final_exam.id not in {exam.id for exam in exams}:
        exams.append(final_exam)
    exam_ids = {exam.id for exam in exams}
    exam_map = {exam.id: exam for exam in exams}

    paper_conditions = [
        ExamSubject.tenant_id == tid,
        ExamSubject.exam_id.in_(exam_ids),
        ExamSubject.grade_id == grade_id,
        ExamSubject.is_deleted.is_(False),
    ]
    if section_id:
        paper_conditions.append(ExamSubject.section_id == section_id)
    papers = (await db.execute(select(ExamSubject).where(*paper_conditions))).scalars().all()
    subject_ids = {paper.subject_id for paper in papers}

    batch_conditions = [
        MarksBatch.tenant_id == tid,
        MarksBatch.exam_id.in_(exam_ids),
        MarksBatch.grade_id == grade_id,
        MarksBatch.is_deleted.is_(False),
    ]
    if section_id:
        batch_conditions.append(MarksBatch.section_id == section_id)
    batches = (await db.execute(select(MarksBatch).where(*batch_conditions))).scalars().all()
    batch_by_scope = {(b.exam_id, b.subject_id, b.section_id): b for b in batches}
    expected_scopes = {(p.exam_id, p.subject_id, p.section_id) for p in papers}
    all_published = bool(expected_scopes) and all(
        batch_by_scope.get(scope) is not None and batch_by_scope[scope].batch_status == "published"
        for scope in expected_scopes
    )

    marks = (await db.execute(select(Marks).where(
        Marks.tenant_id == tid,
        Marks.exam_id.in_(exam_ids),
        Marks.student_id.in_([student.id for student in students]) if students else Marks.student_id.is_(None),
        Marks.is_deleted.is_(False),
    ))).scalars().all()
    marks_by_student: dict[uuid.UUID, dict[tuple[uuid.UUID, uuid.UUID], Marks]] = defaultdict(dict)
    for mark in marks:
        marks_by_student[mark.student_id][(mark.exam_id, mark.subject_id)] = mark

    subjects = {
        subject.id: subject.name
        for subject in (await db.execute(select(Subject).where(Subject.tenant_id == tid))).scalars().all()
    }
    sections = {
        section.id: section.name
        for section in (await db.execute(select(Section).where(Section.tenant_id == tid))).scalars().all()
    }
    employees = {
        employee.id: f"{employee.first_name} {employee.last_name or ''}".strip()
        for employee in (await db.execute(select(Employee).where(Employee.tenant_id == tid))).scalars().all()
    }
    institution = (await db.execute(select(Institution).where(
        Institution.tenant_id == tid, Institution.is_deleted.is_(False)
    ))).scalars().first()
    board = (institution.board if institution and institution.board else "CBSE").upper()

    rows = []
    for student in students:
        student_marks = marks_by_student.get(student.id, {})
        missing: list[str] = []
        failed: list[str] = []
        subject_results = []
        for subject_id in subject_ids:
            subject_papers = [
                paper for paper in papers
                if paper.subject_id == subject_id and paper.section_id in (None, student.section_id)
            ]
            weighted_total = 0.0
            weight_total = 0.0
            pass_percentage = 40.0
            complete_subject = bool(subject_papers)
            for paper in subject_papers:
                batch = batch_by_scope.get((paper.exam_id, paper.subject_id, paper.section_id))
                mark = student_marks.get((paper.exam_id, subject_id))
                exam = exam_map[paper.exam_id]
                if not batch or batch.batch_status != "published" or not mark:
                    complete_subject = False
                    continue
                exam_percentage = 0.0 if mark.is_absent else (
                    float(mark.marks_obtained) / float(mark.max_marks) * 100 if mark.max_marks else 0.0
                )
                weight = float(exam.weightage_percent or 0)
                weighted_total += exam_percentage * weight
                weight_total += weight
                if paper.max_marks:
                    pass_percentage = max(
                        pass_percentage,
                        float(paper.pass_marks) / float(paper.max_marks) * 100,
                    )
            percentage = round(weighted_total / weight_total, 2) if weight_total else 0.0
            subject_name = subjects.get(subject_id, "Subject")
            if not complete_subject:
                missing.append(subject_name)
            elif percentage < pass_percentage:
                failed.append(subject_name)
            subject_results.append({
                "subject_id": str(subject_id),
                "subject": subject_name,
                "percentage": percentage,
                "pass_percentage": round(pass_percentage, 2),
                "status": "pending" if not complete_subject else (
                    "failed" if percentage < pass_percentage else "passed"
                ),
            })

        overall = round(
            sum(result["percentage"] for result in subject_results) / len(subject_results), 2
        ) if subject_results else 0.0
        overall_pass = float(final_exam.overall_pass_percentage or 40)
        complete = bool(student.grade_id and student.section_id and all_published and not missing and subject_ids)
        eligible = (
            complete
            and overall >= overall_pass
            and (not failed or not final_exam.require_subject_pass)
        )
        reasons = []
        if not student.grade_id or not student.section_id:
            reasons.append("Class/section not assigned")
        if not expected_scopes:
            reasons.append("No examination subjects configured")
        elif not all_published:
            reasons.append("Annual marks await HOD approval/publication")
        if missing:
            reasons.append("Missing: " + ", ".join(sorted(missing)))
        if failed:
            reasons.append("Below subject pass mark: " + ", ".join(sorted(failed)))
        if complete and overall < overall_pass:
            reasons.append(f"Overall below {overall_pass:g}%")
        result = "pending" if not complete else ("passed" if eligible else "failed")
        rows.append({
            "student_id": str(student.id),
            "admission_no": student.admission_no,
            "roll_no": student.roll_no,
            "student": f"{student.first_name} {student.last_name or ''}".strip(),
            "section": sections.get(student.section_id, "—"),
            "percentage": overall,
            "eligible": eligible,
            "reason": "; ".join(reasons) if reasons else "Eligible for promotion",
            "result": result,
            "grade": _grade_label(overall, eligible),
            "failed_subjects": failed,
            "subject_results": subject_results,
            "rank": None,
        })

    completed_rows = sorted(
        [row for row in rows if row["result"] != "pending"],
        key=lambda row: (-row["percentage"], row["student"]),
    )
    for rank, row in enumerate(completed_rows, start=1):
        row["rank"] = rank
    leaders = [row for row in completed_rows if row["eligible"]][:10]
    failed_students = [row for row in completed_rows if not row["eligible"]]
    reviewers = sorted({
        employees.get(batch.reviewer_id, "Academic reviewer")
        for batch in batches if batch.reviewer_id
    })

    return {
        "exam": {"id": str(final_exam.id), "name": final_exam.name},
        "academic_year_id": str(final_exam.academic_year_id) if final_exam.academic_year_id else None,
        "board": board,
        "policy": {
            "overall_pass_percentage": float(final_exam.overall_pass_percentage or 40),
            "require_subject_pass": final_exam.require_subject_pass,
            "default_subject_pass_percentage": 40,
        },
        "included_exams": [
            {"id": str(exam.id), "name": exam.name, "weightage_percent": float(exam.weightage_percent)}
            for exam in exams
        ],
        "review_status": "published" if all_published else (
            "pending_review" if batches else "not_started"
        ),
        "reviewers": reviewers,
        "subjects": [subjects.get(subject_id, "Subject") for subject_id in subject_ids],
        "rows": rows,
        "leaders": leaders,
        "failed_students": failed_students,
        "summary": {
            "students": len(rows),
            "eligible": sum(row["eligible"] for row in rows),
            "blocked": sum(not row["eligible"] for row in rows),
            "pending": sum(row["result"] == "pending" for row in rows),
            "failed": sum(row["result"] == "failed" for row in rows),
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
    if (
        not from_grade or not to_grade
        or from_grade.tenant_id != user.tenant_id
        or to_grade.tenant_id != user.tenant_id
    ):
        raise HTTPException(404, "Grade not found")
    if from_grade.id == to_grade.id:
        raise HTTPException(409, "Source and destination classes must differ")
    if not payload.mark_graduating and to_grade.sequence <= from_grade.sequence:
        raise HTTPException(409, "Destination class must be above the source class")

    eligibility_data = await _eligibility(
        db, user.tenant_id, payload.from_grade_id, payload.exam_id, payload.from_section_id
    )
    selected = set(payload.student_ids or [
        uuid.UUID(row["student_id"]) for row in eligibility_data["rows"] if row["eligible"]
    ])
    eligible_ids = {
        uuid.UUID(row["student_id"]) for row in eligibility_data["rows"] if row["eligible"]
    }
    blocked = selected - eligible_ids
    if blocked:
        names = [
            row["student"] for row in eligibility_data["rows"]
            if uuid.UUID(row["student_id"]) in blocked
        ]
        raise HTTPException(409, "Promotion blocked for: " + ", ".join(names))
    if not selected:
        raise HTTPException(409, "No eligible students selected")

    students = (await db.execute(select(Student).where(
        Student.tenant_id == user.tenant_id,
        Student.id.in_(selected),
        Student.grade_id == payload.from_grade_id,
        Student.enrollment_status == "enrolled",
        Student.is_deleted.is_(False),
    ))).scalars().all()
    years = {
        year.id: year.name
        for year in (await db.execute(select(AcademicYear).where(
            AcademicYear.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    sections = {
        section.id: section.name
        for section in (await db.execute(select(Section).where(
            Section.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    result_rows = {
        uuid.UUID(row["student_id"]): row for row in eligibility_data["rows"]
    }
    for student in students:
        result = result_rows[student.id]
        db.add(StudentAcademicHistory(
            tenant_id=user.tenant_id,
            student_id=student.id,
            academic_year=years.get(student.academic_year_id, "—"),
            grade=from_grade.name,
            section=sections.get(student.section_id),
            result="graduated" if payload.mark_graduating else "promoted",
            percentage=result["percentage"],
            rank=result["rank"],
            remarks=(
                f"Annual cumulative result ({eligibility_data['exam']['name']}): "
                f"{result['grade']} / {result['percentage']}%"
            ),
            created_by=user.id,
            updated_by=user.id,
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
        db,
        action="promote",
        entity="Student",
        actor=user,
        changes={
            "from_grade": str(payload.from_grade_id),
            "to_grade": str(payload.to_grade_id),
            "final_exam_id": str(payload.exam_id),
            "count": len(students),
        },
    )
    return {
        "detail": "promotion completed",
        "promoted": len(students),
        "from_grade": from_grade.name,
        "to_grade": to_grade.name,
        "status_set": "graduated" if payload.mark_graduating else "promoted",
    }
