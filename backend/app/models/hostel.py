"""Hostel — blocks, rooms and allocation lifecycle."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
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


class HostelBed(BaseEntity, Base):
    __tablename__ = "hostel_bed"
    __table_args__ = (UniqueConstraint("tenant_id", "room_id", "bed_no", name="uq_hostel_bed"),)

    room_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("hostel_room.id"), index=True)
    bed_no: Mapped[str] = mapped_column(String(40), nullable=False)
    bed_status: Mapped[str] = mapped_column(String(20), default="available", nullable=False)
    current_allocation_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("hostel_allocation.id"), nullable=True, index=True
    )


class HostelAttendance(BaseEntity, Base):
    __tablename__ = "hostel_attendance"
    __table_args__ = (
        UniqueConstraint("tenant_id", "student_id", "attendance_date", name="uq_hostel_attendance"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    attendance_status: Mapped[str] = mapped_column(String(20), default="present", nullable=False)
    remarks: Mapped[str | None] = mapped_column(String(255), nullable=True)


class HostelVisitor(BaseEntity, Base):
    __tablename__ = "hostel_visitor"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    visitor_name: Mapped[str] = mapped_column(String(150), nullable=False)
    relation: Mapped[str | None] = mapped_column(String(60), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    visitor_status: Mapped[str] = mapped_column(String(20), default="checked_in", nullable=False)


class HostelIncident(BaseEntity, Base):
    __tablename__ = "hostel_incident"

    student_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("student.id"), nullable=True, index=True
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("hostel_room.id"), nullable=True, index=True
    )
    incident_date: Mapped[date] = mapped_column(Date, nullable=False)
    incident_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="low", nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    incident_status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
