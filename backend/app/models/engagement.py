"""Family engagement — complaints / service requests and their audit trail.

A complaint is raised by a student or parent, auto-assigned to the student's
class teacher (or the HOD as fallback), and worked through a visible trail of
updates that parents, teachers, administrators and the principal can all follow.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class Complaint(BaseEntity, Base):
    __tablename__ = "complaint"

    ticket_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), default="general", nullable=False)
    # general / academic / fees / transport / hostel / discipline / facilities / other
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)  # low/normal/high/urgent
    complaint_status: Mapped[str] = mapped_column(String(20), default="open", nullable=False, index=True)
    # open / assigned / in_progress / resolved / closed / reopened

    raised_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    raised_by_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    raised_by_role: Mapped[str] = mapped_column(String(20), default="parent", nullable=False)  # student/parent
    student_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("student.id"), nullable=True, index=True)

    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)  # employee
    assigned_role: Mapped[str | None] = mapped_column(String(30), nullable=True)  # class_teacher / hod / admin
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ComplaintUpdate(BaseEntity, Base):
    """One entry on a complaint's trail: a comment, a status change or a reassignment."""

    __tablename__ = "complaint_update"

    complaint_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("complaint.id"), index=True)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    author_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_from: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status_to: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Internal notes are hidden from students/parents (staff-only).
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
