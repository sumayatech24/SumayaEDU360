"""Examinations — exams, question papers and marks."""
from __future__ import annotations

import uuid
from datetime import date, datetime, time

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class Exam(BaseEntity, Base):
    __tablename__ = "exam"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    exam_type: Mapped[str] = mapped_column(String(40), default="internal", nullable=False)
    # internal / unit_test / midterm / semester / final
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=True)
    max_marks: Mapped[Numeric] = mapped_column(Numeric(6, 2), default=100, nullable=False)
    pass_marks: Mapped[Numeric] = mapped_column(Numeric(6, 2), default=33, nullable=False)


class ExamSubject(BaseEntity, Base):
    """One scheduled paper within an exam plan."""

    __tablename__ = "exam_subject"
    __table_args__ = (
        UniqueConstraint("tenant_id", "exam_id", "subject_id", "grade_id", "section_id", name="uq_exam_subject"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("exam.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("subject.id"), index=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True, index=True)
    assigned_teacher_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("employee.id"), nullable=True)
    exam_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    room: Mapped[str | None] = mapped_column(String(60), nullable=True)
    max_marks: Mapped[Numeric] = mapped_column(Numeric(6, 2), default=100, nullable=False)
    pass_marks: Mapped[Numeric] = mapped_column(Numeric(6, 2), default=33, nullable=False)
    schedule_status: Mapped[str] = mapped_column(String(30), default="scheduled", nullable=False)


class MarksBatch(BaseEntity, Base):
    """Bulk mark-entry sheet lifecycle: draft -> submitted -> approved -> published."""

    __tablename__ = "marks_batch"
    __table_args__ = (
        UniqueConstraint("tenant_id", "exam_id", "subject_id", "grade_id", "section_id", name="uq_marks_batch_scope"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("exam.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("subject.id"), index=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True, index=True)
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("employee.id"), nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("employee.id"), nullable=True)
    batch_status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    # draft / submitted / approved / rejected / published
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class QuestionPaper(BaseEntity, Base):
    __tablename__ = "question_paper"

    exam_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("exam.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("subject.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    blueprint: Mapped[dict | None] = mapped_column(__import__("sqlalchemy").JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    # draft / moderation / approved / printed
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Marks(BaseEntity, Base):
    __tablename__ = "marks"
    __table_args__ = (
        UniqueConstraint("tenant_id", "exam_id", "student_id", "subject_id", name="uq_marks_unique"),
    )

    exam_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("exam.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("subject.id"), index=True)
    marks_obtained: Mapped[Numeric] = mapped_column(Numeric(6, 2), default=0, nullable=False)
    max_marks: Mapped[Numeric] = mapped_column(Numeric(6, 2), default=100, nullable=False)
    grade_letter: Mapped[str | None] = mapped_column(String(5), nullable=True)
    is_absent: Mapped[bool] = mapped_column(__import__("sqlalchemy").Boolean, default=False, nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
