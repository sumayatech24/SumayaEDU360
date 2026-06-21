"""Transport — routes, vehicles, stops and student assignments."""
from __future__ import annotations

import uuid
from datetime import time
from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import BaseEntity, GUID


class TransportRoute(BaseEntity, Base):
    __tablename__ = "transport_route"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    start_point: Mapped[str | None] = mapped_column(String(150), nullable=True)
    end_point: Mapped[str | None] = mapped_column(String(150), nullable=True)
    distance_km: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), nullable=True)
    fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)


class Vehicle(BaseEntity, Base):
    __tablename__ = "vehicle"

    registration_no: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    driver_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    driver_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    route_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("transport_route.id"), nullable=True)


class RouteStop(BaseEntity, Base):
    __tablename__ = "route_stop"

    route_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("transport_route.id"), index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    pickup_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    drop_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    fare: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)


class StudentTransportAssignment(BaseEntity, Base):
    __tablename__ = "student_transport_assignment"

    student_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("student.id"), index=True)
    route_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("transport_route.id"), index=True)
    stop_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("route_stop.id"), nullable=True)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    assignment_status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
