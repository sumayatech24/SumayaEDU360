"""HRMS — leave management and payroll."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
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
