"""Admissions CRM — leads/inquiries through to enrollment."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
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


class AdmissionApplicant(BaseEntity, Base):
    """Login used by an external applicant on the public admissions portal."""

    __tablename__ = "admission_applicant"
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_admission_applicant_tenant_email"),
    )

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdmissionApplication(BaseEntity, Base):
    """Operational admission case layered over the existing CRM lead."""

    __tablename__ = "admission_application"
    __table_args__ = (
        UniqueConstraint("tenant_id", "application_no", name="uq_admission_application_no"),
        UniqueConstraint("lead_id", name="uq_admission_application_lead"),
    )

    application_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("admission_lead.id"), index=True)
    applicant_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("admission_applicant.id"), nullable=True, index=True
    )
    application_type: Mapped[str] = mapped_column(String(24), default="new", nullable=False)
    # new / continuing
    channel: Mapped[str] = mapped_column(String(24), default="public", nullable=False)
    # public / internal / staff
    existing_student_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("student.id"), nullable=True, index=True
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("academic_year.id"), nullable=True
    )
    target_grade_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("grade.id"), nullable=True
    )
    target_section_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("section.id"), nullable=True
    )
    application_status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    # draft / submitted / under_review / approved / rejected / enrolled
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    # pending / in_progress / verified / issues
    fee_status: Mapped[str] = mapped_column(String(24), default="not_assigned", nullable=False)
    # not_assigned / unpaid / partial / paid / waived
    fee_category: Mapped[str] = mapped_column(String(40), default="regular", nullable=False)
    government_aid_percent: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    declaration_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AdmissionDocument(BaseEntity, Base):
    __tablename__ = "admission_document"

    application_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("admission_application.id"), index=True
    )
    document_type: Mapped[str] = mapped_column(String(64), nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdmissionVerification(BaseEntity, Base):
    __tablename__ = "admission_verification"
    __table_args__ = (
        UniqueConstraint("application_id", "check_type", name="uq_admission_check"),
    )

    application_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("admission_application.id"), index=True
    )
    check_type: Mapped[str] = mapped_column(String(64), nullable=False)
    check_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdmissionCharge(BaseEntity, Base):
    """Pre-enrollment charge; regular invoices begin once a student exists."""

    __tablename__ = "admission_charge"

    application_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("admission_application.id"), index=True
    )
    charge_type: Mapped[str] = mapped_column(String(64), default="admission_fee", nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    paid_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(24), default="unpaid", nullable=False)
    due_date: Mapped["Date"] = mapped_column(Date, nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(32), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    receipt_no: Mapped[str | None] = mapped_column(String(50), nullable=True)
    paid_at: Mapped["Date"] = mapped_column(Date, nullable=True)
