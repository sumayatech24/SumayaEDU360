"""Typed-domain registry.

Declares typed entities (real tables) for the operational modules and generates
their Pydantic schemas dynamically, so new modules become first-class — saving real
data, validated, audited, RBAC-guarded — without hand-writing schemas for each.

Both the API (router builder) and the seeder (entity_def/field_def) read this registry,
so a module's data model is defined in exactly one place.
"""
from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional, Type

from pydantic import BaseModel, ConfigDict, create_model

from app.core.database import Base
from app.models import hostel, hr, library, transport

# --------------------------------------------------------------------------- specs
PY_TYPES: dict[str, type] = {
    "string": str,
    "text": str,
    "email": str,
    "phone": str,
    "select": str,
    "number": int,
    "decimal": Decimal,
    "bool": bool,
    "date": datetime.date,
    "datetime": datetime.datetime,
    "time": datetime.time,
    "json": dict,
    "reference": uuid.UUID,
}


@dataclass
class FieldSpec:
    name: str
    label: str
    type: str = "string"
    required: bool = False
    list_visible: bool = True
    options_master: Optional[str] = None
    reference_entity: Optional[str] = None
    help_text: Optional[str] = None


@dataclass
class EntitySpec:
    model: Type[Base]
    slug: str
    name: str
    module_slug: str
    kind: str = "master"
    icon: str = "table"
    search_fields: list[str] = field(default_factory=list)
    fields: list[FieldSpec] = field(default_factory=list)


def _f(*a, **k) -> FieldSpec:
    return FieldSpec(*a, **k)


# Registry — one entry per typed operational entity.
DOMAIN_SPECS: list[EntitySpec] = [
    # ----------------------------------------------------------------- Library
    EntitySpec(
        library.LibraryBook, "library-book", "Library Book", "library_management",
        kind="master", icon="book", search_fields=["title", "author", "isbn"],
        fields=[
            _f("title", "Title", required=True),
            _f("author", "Author"),
            _f("isbn", "ISBN"),
            _f("category", "Category"),
            _f("publisher", "Publisher"),
            _f("shelf", "Shelf"),
            _f("total_copies", "Total Copies", "number"),
            _f("available_copies", "Available", "number"),
            _f("price", "Price", "decimal", list_visible=False),
        ],
    ),
    EntitySpec(
        library.BookIssue, "book-issue", "Book Issue", "library_management",
        kind="transaction", icon="book", search_fields=[],
        fields=[
            _f("book_id", "Book", "reference", required=True, reference_entity="library-book"),
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("issue_date", "Issue Date", "date", required=True),
            _f("due_date", "Due Date", "date", required=True),
            _f("return_date", "Return Date", "date"),
            _f("issue_status", "Status", "select", options_master="book_issue_status"),
            _f("fine_amount", "Fine", "decimal"),
            _f("renew_count", "Renewals", "number", list_visible=False),
        ],
    ),
    # ----------------------------------------------------------------- Transport
    EntitySpec(
        transport.TransportRoute, "transport-route", "Transport Route", "transport",
        kind="master", icon="trending-up", search_fields=["name", "code"],
        fields=[
            _f("name", "Route Name", required=True),
            _f("code", "Code", required=True),
            _f("start_point", "Start Point"),
            _f("end_point", "End Point"),
            _f("distance_km", "Distance (km)", "decimal", list_visible=False),
            _f("fare", "Fare", "decimal"),
        ],
    ),
    EntitySpec(
        transport.Vehicle, "vehicle", "Vehicle", "transport",
        kind="master", icon="briefcase", search_fields=["registration_no", "model", "driver_name"],
        fields=[
            _f("registration_no", "Registration No", required=True),
            _f("model", "Model"),
            _f("capacity", "Capacity", "number"),
            _f("driver_name", "Driver"),
            _f("driver_phone", "Driver Phone", "phone"),
            _f("route_id", "Route", "reference", reference_entity="transport-route"),
        ],
    ),
    EntitySpec(
        transport.RouteStop, "route-stop", "Route Stop", "transport",
        kind="master", icon="check-square", search_fields=["name"],
        fields=[
            _f("route_id", "Route", "reference", required=True, reference_entity="transport-route"),
            _f("name", "Stop Name", required=True),
            _f("sequence", "Sequence", "number"),
            _f("pickup_time", "Pickup Time", "time"),
            _f("drop_time", "Drop Time", "time"),
            _f("fare", "Fare", "decimal"),
        ],
    ),
    EntitySpec(
        transport.StudentTransportAssignment, "transport-assignment", "Transport Assignment", "transport",
        kind="transaction", icon="users", search_fields=[],
        fields=[
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("route_id", "Route", "reference", required=True, reference_entity="transport-route"),
            _f("stop_id", "Stop", "reference", reference_entity="route-stop"),
            _f("fee_amount", "Fee", "decimal"),
            _f("assignment_status", "Status", "select", options_master="active_status"),
        ],
    ),
    # ----------------------------------------------------------------- Hostel
    EntitySpec(
        hostel.HostelBlock, "hostel-block", "Hostel Block", "hostel",
        kind="master", icon="grid", search_fields=["name", "code"],
        fields=[
            _f("name", "Block Name", required=True),
            _f("code", "Code", required=True),
            _f("block_type", "Type", "select", options_master="hostel_block_type"),
            _f("warden_name", "Warden"),
        ],
    ),
    EntitySpec(
        hostel.HostelRoom, "hostel-room", "Hostel Room", "hostel",
        kind="master", icon="table", search_fields=["room_no"],
        fields=[
            _f("block_id", "Block", "reference", required=True, reference_entity="hostel-block"),
            _f("room_no", "Room No", required=True),
            _f("capacity", "Capacity", "number"),
            _f("occupied", "Occupied", "number"),
            _f("room_type", "Room Type"),
        ],
    ),
    EntitySpec(
        hostel.HostelAllocation, "hostel-allocation", "Hostel Allocation", "hostel",
        kind="transaction", icon="users", search_fields=[],
        fields=[
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("room_id", "Room", "reference", required=True, reference_entity="hostel-room"),
            _f("allocation_date", "Allocation Date", "date", required=True),
            _f("vacate_date", "Vacate Date", "date"),
            _f("allocation_status", "Status", "select", options_master="hostel_allocation_status"),
        ],
    ),
    # ----------------------------------------------------------------- HR
    EntitySpec(
        hr.LeaveType, "leave-type", "Leave Type", "employee_hrms",
        kind="master", icon="sliders", search_fields=["name", "code"],
        fields=[
            _f("name", "Name", required=True),
            _f("code", "Code", required=True),
            _f("max_days_per_year", "Max Days / Year", "number"),
            _f("is_paid", "Paid", "bool"),
        ],
    ),
    EntitySpec(
        hr.LeaveRequest, "leave-request", "Leave Request", "employee_hrms",
        kind="transaction", icon="calendar", search_fields=[],
        fields=[
            _f("employee_id", "Employee", "reference", required=True, reference_entity="employee"),
            _f("leave_type", "Leave Type"),
            _f("from_date", "From Date", "date", required=True),
            _f("to_date", "To Date", "date", required=True),
            _f("days", "Days", "number"),
            _f("reason", "Reason", "text", list_visible=False),
            _f("request_status", "Status", "select", options_master="leave_status"),
        ],
    ),
    EntitySpec(
        hr.Payroll, "payroll", "Payroll", "employee_hrms",
        kind="transaction", icon="credit-card", search_fields=[],
        fields=[
            _f("employee_id", "Employee", "reference", required=True, reference_entity="employee"),
            _f("month", "Month", "number", required=True),
            _f("year", "Year", "number", required=True),
            _f("basic", "Basic", "decimal"),
            _f("allowances", "Allowances", "decimal"),
            _f("deductions", "Deductions", "decimal"),
            _f("net_pay", "Net Pay", "decimal"),
            _f("payroll_status", "Status"),
        ],
    ),
]

SPEC_BY_SLUG: dict[str, EntitySpec] = {s.slug: s for s in DOMAIN_SPECS}


# --------------------------------------------------------------------------- schema generation
def _opt(t: type):
    return (Optional[t], None)


def build_schemas(spec: EntitySpec) -> tuple[type[BaseModel], type[BaseModel], type[BaseModel]]:
    create_fields: dict[str, tuple] = {}
    update_fields: dict[str, tuple] = {}
    out_fields: dict[str, tuple] = {
        "id": (uuid.UUID, ...),
        "tenant_id": (Optional[uuid.UUID], None),
        "status": (Optional[str], None),
        "created_at": (Optional[datetime.datetime], None),
        "updated_at": (Optional[datetime.datetime], None),
    }
    for fs in spec.fields:
        py = PY_TYPES.get(fs.type, str)
        create_fields[fs.name] = (py, ...) if fs.required else _opt(py)
        update_fields[fs.name] = _opt(py)
        out_fields[fs.name] = _opt(py)

    name = spec.model.__name__
    Create = create_model(f"{name}Create", **create_fields)  # type: ignore[call-overload]
    Update = create_model(f"{name}Update", **update_fields)  # type: ignore[call-overload]
    Out = create_model(  # type: ignore[call-overload]
        f"{name}Out", __config__=ConfigDict(from_attributes=True), **out_fields
    )
    return Create, Update, Out
