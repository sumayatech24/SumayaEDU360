"""Library management — catalog and issue/return lifecycle."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class LibraryBook(BaseEntity, Base):
    __tablename__ = "library_book"

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(150), nullable=True)
    shelf: Mapped[str | None] = mapped_column(String(50), nullable=True)
    total_copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    available_copies: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)


class BookIssue(BaseEntity, Base):
    __tablename__ = "book_issue"

    book_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("library_book.id"), index=True)
    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    issue_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    issue_status: Mapped[str] = mapped_column(String(20), default="issued", nullable=False)
    # issued / returned / overdue / lost
    fine_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    renew_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LibraryBookCopy(BaseEntity, Base):
    """An individually traceable physical copy of a catalog title."""

    __tablename__ = "library_book_copy"
    __table_args__ = (
        UniqueConstraint("tenant_id", "accession_no", name="uq_library_copy_accession"),
    )

    book_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("library_book.id"), index=True)
    accession_no: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    copy_status: Mapped[str] = mapped_column(String(24), default="available", nullable=False)
    # available / issued / lost / damaged / repair / withdrawn
    condition: Mapped[str] = mapped_column(String(24), default="good", nullable=False)
    acquired_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    acquisition_cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)


class LibraryAcquisitionRequest(BaseEntity, Base):
    __tablename__ = "library_acquisition_request"
    __table_args__ = (
        UniqueConstraint("tenant_id", "request_no", name="uq_library_acquisition_request_no"),
    )

    request_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("library_book.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    estimated_unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    requested_by_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    request_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    # pending / approved / rejected / ordered / fulfilled
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    decision_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchase_order_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True, index=True)


class LibraryPurchaseOrder(BaseEntity, Base):
    __tablename__ = "library_purchase_order"
    __table_args__ = (
        UniqueConstraint("tenant_id", "po_no", name="uq_library_purchase_order_no"),
    )

    po_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    vendor_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("vendor.id"), index=True)
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expected_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    shipping_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    po_status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False)
    # draft / approved / ordered / partially_received / received / cancelled
    approved_by: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class LibraryPurchaseOrderLine(BaseEntity, Base):
    __tablename__ = "library_purchase_order_line"

    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("library_purchase_order.id"), index=True
    )
    acquisition_request_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("library_acquisition_request.id"), nullable=True
    )
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("library_book.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    author: Mapped[str | None] = mapped_column(String(200), nullable=True)
    isbn: Mapped[str | None] = mapped_column(String(40), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    line_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    received_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class LibraryGoodsReceipt(BaseEntity, Base):
    __tablename__ = "library_goods_receipt"
    __table_args__ = (
        UniqueConstraint("tenant_id", "grn_no", name="uq_library_goods_receipt_no"),
    )

    grn_no: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    purchase_order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("library_purchase_order.id"), index=True
    )
    receipt_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    vendor_invoice_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    accepted_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class LibraryGoodsReceiptLine(BaseEntity, Base):
    __tablename__ = "library_goods_receipt_line"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("library_goods_receipt.id"), index=True
    )
    purchase_order_line_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("library_purchase_order_line.id"), index=True
    )
    accepted_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rejected_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
