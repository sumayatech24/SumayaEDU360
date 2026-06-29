"""HRMS — leave management and payroll."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class LeaveType(BaseEntity, Base):
    __tablename__ = "leave_type"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    max_days_per_year: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    is_paid: Mapped[bool] = mapped_column(__import__("sqlalchemy").Boolean, default=True, nullable=False)


class LeaveRequest(BaseEntity, Base):
    __tablename__ = "leave_request"

    employee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("employee.id"), index=True)
    leave_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    days: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_status: Mapped[str] = mapped_column(String(20), default="applied", nullable=False)
    # applied / approved / rejected / cancelled
    approver_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    decided_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class Payroll(BaseEntity, Base):
    __tablename__ = "payroll"

    employee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("employee.id"), index=True)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    basic: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    allowances: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payroll_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    # draft / finalized / paid


class SalaryStructure(BaseEntity, Base):
    """A pay-structure template applicable for a financial year. Splits an annual
    CTC into earnings/deductions components used to compute every payslip."""

    __tablename__ = "salary_structure"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    financial_year: Mapped[str] = mapped_column(String(12), nullable=False, index=True)  # e.g. 2025-26
    basic_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=40, nullable=False)  # % of CTC
    # [{code,name,kind:"earning"|"deduction",method:"percent_basic"|"percent_ctc"|"fixed",value}]
    components: Mapped[list | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PayrollRun(BaseEntity, Base):
    """A monthly payroll batch for the whole institution."""

    __tablename__ = "payroll_run"

    financial_year: Mapped[str] = mapped_column(String(12), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    run_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False, index=True)
    # draft / approved / processing / paid / cancelled
    employee_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_gross: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_deductions: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    total_net: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class Payslip(BaseEntity, Base):
    __tablename__ = "payslip"

    payroll_run_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("payroll_run.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("employee.id"), index=True)
    gross_earnings: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    statutory_deductions: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    adhoc_deduction: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    adhoc_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lop_days: Mapped[Decimal] = mapped_column(Numeric(5, 1), default=0, nullable=False)
    net_pay: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_regime: Mapped[str] = mapped_column(String(10), default="new", nullable=False)
    # earnings/deductions: [{name, amount}]
    earnings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    deductions: Mapped[list | None] = mapped_column(JSON, nullable=True)
