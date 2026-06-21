"""Academic configuration masters — the backbone of the SIS."""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class AcademicYear(BaseEntity, Base):
    __tablename__ = "academic_year"

    name: Mapped[str] = mapped_column(String(50), nullable=False)  # 2025-2026
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    start_date: Mapped["Date"] = mapped_column(Date, nullable=True)
    end_date: Mapped["Date"] = mapped_column(Date, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Program(BaseEntity, Base):
    """Stream/program, e.g. Primary, Secondary, Science, Commerce, B.Tech."""

    __tablename__ = "program"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)  # school/college


class Grade(BaseEntity, Base):
    """Grade / class / standard (Nursery .. 12, or Sem 1..8)."""

    __tablename__ = "grade"

    program_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("program.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # drives promotion order


class Section(BaseEntity, Base):
    __tablename__ = "section"

    grade_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("grade.id"), index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # A / B / C
    capacity: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    class_teacher_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class Semester(BaseEntity, Base):
    __tablename__ = "semester"

    academic_year_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("academic_year.id"), index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Subject(BaseEntity, Base):
    __tablename__ = "subject"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    is_elective: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Topic(BaseEntity, Base):
    __tablename__ = "topic"

    subject_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("subject.id"), index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
