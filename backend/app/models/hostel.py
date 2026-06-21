"""Hostel — blocks, rooms and allocation lifecycle."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class HostelBlock(BaseEntity, Base):
    __tablename__ = "hostel_block"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    block_type: Mapped[str] = mapped_column(String(20), default="boys", nullable=False)  # boys/girls
    warden_name: Mapped[str | None] = mapped_column(String(150), nullable=True)


class HostelRoom(BaseEntity, Base):
    __tablename__ = "hostel_room"

    block_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hostel_block.id"), index=True)
    room_no: Mapped[str] = mapped_column(String(40), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(40), nullable=True)  # single/double/dorm


class HostelAllocation(BaseEntity, Base):
    __tablename__ = "hostel_allocation"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    room_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hostel_room.id"), index=True)
    allocation_date: Mapped[date] = mapped_column(Date, nullable=False)
    vacate_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    allocation_status: Mapped[str] = mapped_column(String(20), default="allocated", nullable=False)
    # allocated / vacated
