"""Fees & billing — fee plans, invoices and payments."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class FeePlan(BaseEntity, Base):
    __tablename__ = "fee_plan"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    grade_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("grade.id"), nullable=True)
    frequency: Mapped[str] = mapped_column(String(32), default="annual", nullable=False)
    # annual / half_yearly / quarterly
    installment_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    allow_partial_payment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeePlanComponent(BaseEntity, Base):
    """Line items of a fee plan (tuition, transport, activity, ...)."""

    __tablename__ = "fee_plan_component"

    fee_plan_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("fee_plan.id"), index=True)
    head: Mapped[str] = mapped_column(String(100), nullable=False)  # fee head/master
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    aid_eligible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class FeeInstallment(BaseEntity, Base):
    __tablename__ = "fee_installment"
    __table_args__ = (
        UniqueConstraint("tenant_id", "fee_plan_id", "sequence", name="uq_fee_installment_sequence"),
    )

    fee_plan_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("fee_plan.id"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    percentage: Mapped[Numeric] = mapped_column(Numeric(5, 2), nullable=False)


class StudentFeeAccount(BaseEntity, Base):
    __tablename__ = "student_fee_account"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "fee_plan_id", name="uq_student_fee_plan"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    fee_plan_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("fee_plan.id"), index=True)
    academic_year_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("academic_year.id"), index=True)
    fee_category: Mapped[str] = mapped_column(String(40), default="regular", nullable=False)
    government_aid_percent: Mapped[Numeric] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    scholarship_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    account_status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)


class Invoice(BaseEntity, Base):
    __tablename__ = "invoice"

    invoice_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    fee_plan_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("fee_plan.id"), nullable=True)
    fee_account_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("student_fee_account.id"), nullable=True, index=True
    )
    installment_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("fee_installment.id"), nullable=True, index=True
    )
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=True)
    gross_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    government_aid_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    net_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    paid_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)
    # unpaid / partial / paid / overdue / cancelled


class InvoiceLineItem(BaseEntity, Base):
    __tablename__ = "invoice_line_item"

    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("invoice.id"), index=True)
    fee_component_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("fee_plan_component.id"), nullable=True
    )
    head: Mapped[str] = mapped_column(String(100), nullable=False)
    gross_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    government_aid_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    net_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)


class Payment(BaseEntity, Base):
    __tablename__ = "payment"

    receipt_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("invoice.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    method: Mapped[str] = mapped_column(String(32), default="cash", nullable=False)
    # cash / card / upi / netbanking / cheque / gateway
    reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    paid_at: Mapped[date] = mapped_column(Date, nullable=True)


class FeeReminder(BaseEntity, Base):
    __tablename__ = "fee_reminder"

    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("invoice.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    guardian_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("guardian.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(24), nullable=False)
    destination: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
