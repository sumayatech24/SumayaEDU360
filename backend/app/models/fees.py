"""Fees & billing — fee plans, invoices and payments."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
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
    # annual / term / monthly / one_time
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class FeePlanComponent(BaseEntity, Base):
    """Line items of a fee plan (tuition, transport, activity, ...)."""

    __tablename__ = "fee_plan_component"

    fee_plan_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("fee_plan.id"), index=True)
    head: Mapped[str] = mapped_column(String(100), nullable=False)  # fee head/master
    amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    is_optional: Mapped[bool] = mapped_column(__import__("sqlalchemy").Boolean, default=False, nullable=False)


class Invoice(BaseEntity, Base):
    __tablename__ = "invoice"

    invoice_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    fee_plan_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("fee_plan.id"), nullable=True)
    academic_year_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=True)
    gross_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    net_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    paid_amount: Mapped[Numeric] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)
    # unpaid / partial / paid / overdue / cancelled


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
