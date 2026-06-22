"""Finance & accounting — ledger accounts, vendors, expenses and purchase orders."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class LedgerAccount(BaseEntity, Base):
    __tablename__ = "ledger_account"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    account_type: Mapped[str] = mapped_column(String(30), default="expense", nullable=False)
    # asset / liability / income / expense / equity
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)


class Vendor(BaseEntity, Base):
    __tablename__ = "vendor"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    gst_no: Mapped[str | None] = mapped_column(String(40), nullable=True)


class Expense(BaseEntity, Base):
    __tablename__ = "expense"

    expense_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("ledger_account.id"), nullable=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("vendor.id"), nullable=True)
    expense_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # pending / approved / rejected / paid
    approver_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)


class PurchaseOrder(BaseEntity, Base):
    __tablename__ = "purchase_order"

    po_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("vendor.id"), nullable=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    po_status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)
    # draft / ordered / received / cancelled
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
