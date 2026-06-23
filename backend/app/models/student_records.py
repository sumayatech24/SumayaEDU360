"""Student lifecycle records — academic history, achievements, discipline, remarks."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class StudentAcademicHistory(BaseEntity, Base):
    """One row per academic year the student has completed at the institution."""

    __tablename__ = "student_academic_history"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    academic_year: Mapped[str] = mapped_column(String(20), nullable=False)  # "2024-2025"
    grade: Mapped[str] = mapped_column(String(100), nullable=False)  # snapshot of class name
    section: Mapped[str | None] = mapped_column(String(40), nullable=True)
    result: Mapped[str] = mapped_column(String(30), default="promoted", nullable=False)
    # promoted / passed / failed / detained
    percentage: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Achievement(BaseEntity, Base):
    __tablename__ = "achievement"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)  # academic/sports/cultural
    level: Mapped[str | None] = mapped_column(String(40), nullable=True)  # school/district/state/national
    achieved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class DisciplinaryAction(BaseEntity, Base):
    __tablename__ = "disciplinary_action"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    incident_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    incident_type: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="minor", nullable=False)  # minor/major/severe
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action_taken: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reported_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)  # open/closed


class StudentRemark(BaseEntity, Base):
    __tablename__ = "student_remark"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    remark_type: Mapped[str] = mapped_column(String(30), default="general", nullable=False)
    # general / special / health / counseling / appreciation
    remark: Mapped[str] = mapped_column(Text, nullable=False)
    remarked_by: Mapped[str | None] = mapped_column(String(150), nullable=True)
    remarked_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_visible_to_parent: Mapped[bool] = mapped_column(
        __import__("sqlalchemy").Boolean, default=True, nullable=False
    )
