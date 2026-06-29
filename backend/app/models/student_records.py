"""Student lifecycle records — academic history, achievements, discipline, remarks."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint
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


class StudentLifecycleRequest(BaseEntity, Base):
    """Guarded transfer, withdrawal, TC and re-enrollment case."""

    __tablename__ = "student_lifecycle_request"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_no", name="uq_student_lifecycle_request_no"),
        UniqueConstraint("tenant_id", "certificate_no", name="uq_student_lifecycle_certificate_no"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    request_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    request_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    # transfer / withdrawal / reenrollment
    request_status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False, index=True)
    # draft / submitted / approved / completed / rejected / cancelled
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    destination_school: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    target_section_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("section.id"), nullable=True)
    clearance_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    override_clearance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approval_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    approved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    certificate_no: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    certificate_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class StudentMedicalRecord(BaseEntity, Base):
    """Restricted student health record; portal exposure is explicitly controlled."""

    __tablename__ = "student_medical_record"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    record_type: Mapped[str] = mapped_column(String(40), nullable=False)
    recorded_on: Mapped[date] = mapped_column(Date, nullable=False)
    condition: Mapped[str] = mapped_column(String(200), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    medication: Mapped[str | None] = mapped_column(Text, nullable=True)
    doctor_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    emergency_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    visible_to_parent: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class StudentConsent(BaseEntity, Base):
    __tablename__ = "student_consent"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "consent_type", name="uq_student_consent_type"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    consent_type: Mapped[str] = mapped_column(String(60), nullable=False)
    consent_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending / granted / declined / revoked / expired
    policy_version: Mapped[str] = mapped_column(String(30), nullable=False)
    requested_on: Mapped[date] = mapped_column(Date, nullable=False)
    responded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    guardian_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    response_notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AlumniProfile(BaseEntity, Base):
    __tablename__ = "alumni_profile"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", name="uq_alumni_student"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    graduation_year: Mapped[int] = mapped_column(Integer, nullable=False)
    leaving_class: Mapped[str | None] = mapped_column(String(100), nullable=True)
    final_result: Mapped[str | None] = mapped_column(String(60), nullable=True)
    personal_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    personal_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    higher_education: Mapped[str | None] = mapped_column(String(255), nullable=True)
    occupation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    employer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    directory_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
