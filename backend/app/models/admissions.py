"""Admissions CRM — leads/inquiries through to enrollment."""
from __future__ import annotations

import uuid

from sqlalchemy import JSON, Date, ForeignKey, String, Text
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

    # Full application details (carried over to the Student on enrollment)
    date_of_birth: Mapped["Date"] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    religion: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nationality: Mapped[str | None] = mapped_column(String(40), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    state: Mapped[str | None] = mapped_column(String(80), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    father_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    father_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mother_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    mother_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    previous_school: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # [{name, data}] — uploaded document data URIs (birth cert, TC, photo, ...)
    documents: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Set once converted to a Student
    converted_student_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
