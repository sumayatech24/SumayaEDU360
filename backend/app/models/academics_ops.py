"""Academic operations — homework, submissions, timetable and lesson plans."""
from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class Homework(BaseEntity, Base):
    __tablename__ = "homework"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("subject.id"), nullable=True)
    assigned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_marks: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=10, nullable=False)
    homework_status: Mapped[str] = mapped_column(String(20), default="assigned", nullable=False)
    # assigned / closed


class HomeworkSubmission(BaseEntity, Base):
    __tablename__ = "homework_submission"

    homework_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("homework.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    submitted_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    marks_awarded: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
    submission_status: Mapped[str] = mapped_column(String(20), default="submitted", nullable=False)
    # submitted / graded / late / missing


class TimetablePeriod(BaseEntity, Base):
    __tablename__ = "timetable_period"

    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True, index=True)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("subject.id"), nullable=True)
    teacher_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    day_of_week: Mapped[str] = mapped_column(String(12), nullable=False)  # Monday..Saturday
    period_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    room: Mapped[str | None] = mapped_column(String(40), nullable=True)


class LessonPlan(BaseEntity, Base):
    __tablename__ = "lesson_plan"

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("subject.id"), nullable=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    week_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    resources: Mapped[str | None] = mapped_column(Text, nullable=True)
    completion_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    plan_status: Mapped[str] = mapped_column(String(20), default="planned", nullable=False)
    # planned / in_progress / completed
