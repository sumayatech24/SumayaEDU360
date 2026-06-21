"""Admissions CRM — leads/inquiries through to enrollment."""
from __future__ import annotations

import uuid

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class AdmissionLead(BaseEntity, Base):
    __tablename__ = "admission_lead"

    lead_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    student_name: Mapped[str] = mapped_column(String(200), nullable=False)
    guardian_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    grade_applied_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)  # website/walk-in/referral
    stage: Mapped[str] = mapped_column(String(40), default="inquiry", nullable=False)
    # inquiry -> counseling -> entrance_test -> document_collection -> approved -> enrolled -> rejected
    counselor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    follow_up_date: Mapped["Date"] = mapped_column(Date, nullable=True)
    test_score: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Set once converted to a Student
    converted_student_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
