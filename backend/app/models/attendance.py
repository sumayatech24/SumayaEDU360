"""Attendance — daily attendance for students and staff (multi-method capable).

One polymorphic table keyed by ``person_type`` (student | employee). ``person_id``
is the canonical subject id and drives uniqueness; ``student_id`` is kept populated
for student rows so existing student-scoped queries and joins keep working.
"""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class Attendance(BaseEntity, Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "person_type", "person_id", "att_date", name="uq_attendance_person_date"),
    )

    person_type: Mapped[str] = mapped_column(String(20), default="student", nullable=False, index=True)
    # student / employee
    person_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    student_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("student.id"), nullable=True, index=True)
    section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True, index=True)
    att_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(20), default="present", nullable=False)
    # present / absent / late / leave / holiday
    method: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    # manual / qr / rfid / biometric / face / geofence
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marked_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
