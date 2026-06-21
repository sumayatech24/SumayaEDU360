"""Examinations — exams, question papers and marks."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text, UniqueConstraint
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
