"""Library management — catalog and issue/return lifecycle."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String
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
