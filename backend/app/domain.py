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
from app.models import (
    academics_ops,
    content,
    finance,
    hostel,
    hr,
    library,
    operations,
    student_records,
    transport,
)

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
    # ----------------------------------------------------------------- Homework & Assignments
    EntitySpec(
        academics_ops.Homework, "homework", "Homework", "homework_assignments",
        kind="transaction", icon="edit", search_fields=["title"],
        fields=[
            _f("title", "Title", required=True),
            _f("grade_id", "Grade", "reference", reference_entity="grade"),
            _f("section_id", "Section", "reference", reference_entity="section"),
            _f("subject_id", "Subject", "reference", reference_entity="subject"),
            _f("assigned_date", "Assigned", "date"),
            _f("due_date", "Due", "date"),
            _f("description", "Description", "text", list_visible=False),
            _f("max_marks", "Max Marks", "decimal"),
            _f("homework_status", "Status", "select", options_master="homework_status"),
        ],
    ),
    EntitySpec(
        academics_ops.HomeworkSubmission, "homework-submission", "Homework Submission", "homework_assignments",
        kind="transaction", icon="check-square", search_fields=[],
        fields=[
            _f("homework_id", "Homework", "reference", required=True, reference_entity="homework"),
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("submitted_date", "Submitted", "date"),
            _f("content", "Content", "text", list_visible=False),
            _f("marks_awarded", "Marks", "decimal"),
            _f("submission_status", "Status", "select", options_master="submission_status"),
        ],
    ),
    # ----------------------------------------------------------------- Timetable
    EntitySpec(
        academics_ops.TimetablePeriod, "timetable-period", "Timetable Period", "timetable_scheduling",
        kind="transaction", icon="grid", search_fields=["day_of_week", "room"],
        fields=[
            _f("grade_id", "Grade", "reference", reference_entity="grade"),
            _f("section_id", "Section", "reference", reference_entity="section"),
            _f("subject_id", "Subject", "reference", reference_entity="subject"),
            _f("day_of_week", "Day", "select", required=True, options_master="day_of_week"),
            _f("period_no", "Period", "number", required=True),
            _f("start_time", "Start", "time"),
            _f("end_time", "End", "time"),
            _f("room", "Room"),
        ],
    ),
    # ----------------------------------------------------------------- Lesson Plans
    EntitySpec(
        academics_ops.LessonPlan, "lesson-plan", "Lesson Plan", "curriculum_lesson_planning",
        kind="transaction", icon="book", search_fields=["title"],
        fields=[
            _f("title", "Title", required=True),
            _f("subject_id", "Subject", "reference", reference_entity="subject"),
            _f("grade_id", "Grade", "reference", reference_entity="grade"),
            _f("week_no", "Week", "number"),
            _f("objectives", "Objectives", "text", list_visible=False),
            _f("resources", "Resources", "text", list_visible=False),
            _f("completion_percent", "Completion %", "number"),
            _f("plan_status", "Status", "select", options_master="lesson_plan_status"),
        ],
    ),
    # ----------------------------------------------------------------- Finance & Accounting
    EntitySpec(
        finance.LedgerAccount, "ledger-account", "Ledger Account", "finance_accounting",
        kind="master", icon="credit-card", search_fields=["name", "code"],
        fields=[
            _f("name", "Name", required=True),
            _f("code", "Code", required=True),
            _f("account_type", "Type", "select", options_master="account_type"),
            _f("opening_balance", "Opening Balance", "decimal"),
        ],
    ),
    EntitySpec(
        finance.Vendor, "vendor", "Vendor", "finance_accounting",
        kind="master", icon="briefcase", search_fields=["name", "code", "phone"],
        fields=[
            _f("name", "Name", required=True),
            _f("code", "Code", required=True),
            _f("contact_person", "Contact"),
            _f("phone", "Phone", "phone"),
            _f("email", "Email", "email"),
            _f("gst_no", "GST No"),
        ],
    ),
    EntitySpec(
        finance.Expense, "expense", "Expense", "finance_accounting",
        kind="transaction", icon="credit-card", search_fields=["expense_no"],
        fields=[
            _f("expense_no", "Expense No", required=True),
            _f("account_id", "Account", "reference", reference_entity="ledger-account"),
            _f("vendor_id", "Vendor", "reference", reference_entity="vendor"),
            _f("expense_date", "Date", "date"),
            _f("amount", "Amount", "decimal", required=True),
            _f("description", "Description", "text", list_visible=False),
            _f("approval_status", "Status", "select", options_master="expense_status"),
        ],
    ),
    EntitySpec(
        finance.PurchaseOrder, "purchase-order", "Purchase Order", "finance_accounting",
        kind="transaction", icon="briefcase", search_fields=["po_no"],
        fields=[
            _f("po_no", "PO No", required=True),
            _f("vendor_id", "Vendor", "reference", reference_entity="vendor"),
            _f("order_date", "Order Date", "date"),
            _f("total_amount", "Total", "decimal"),
            _f("po_status", "Status", "select", options_master="po_status"),
            _f("notes", "Notes", "text", list_visible=False),
        ],
    ),
    # ----------------------------------------------------------------- Inventory / Store
    EntitySpec(
        operations.InventoryItem, "inventory-item", "Inventory Item", "finance_accounting",
        kind="master", icon="table", search_fields=["name", "code"],
        fields=[
            _f("name", "Name", required=True),
            _f("code", "Code", required=True),
            _f("category", "Category"),
            _f("unit", "Unit"),
            _f("quantity_on_hand", "Qty on Hand", "number"),
            _f("reorder_level", "Reorder Level", "number"),
            _f("unit_cost", "Unit Cost", "decimal"),
        ],
    ),
    EntitySpec(
        operations.StockMovement, "stock-movement", "Stock Movement", "finance_accounting",
        kind="transaction", icon="trending-up", search_fields=["reference"],
        fields=[
            _f("item_id", "Item", "reference", required=True, reference_entity="inventory-item"),
            _f("movement_type", "Type", "select", options_master="movement_type"),
            _f("quantity", "Quantity", "number", required=True),
            _f("reference", "Reference"),
            _f("movement_date", "Date", "date"),
        ],
    ),
    # ----------------------------------------------------------------- Activities & Events
    EntitySpec(
        operations.Activity, "activity", "Activity", "activities_events",
        kind="master", icon="trending-up", search_fields=["name", "code"],
        fields=[
            _f("name", "Name", required=True),
            _f("code", "Code", required=True),
            _f("activity_type", "Type", "select", options_master="activity_type"),
            _f("coordinator", "Coordinator"),
            _f("start_date", "Start Date", "date"),
            _f("fee", "Fee", "decimal"),
            _f("capacity", "Capacity", "number"),
        ],
    ),
    EntitySpec(
        operations.ActivityRegistration, "activity-registration", "Activity Registration", "activities_events",
        kind="transaction", icon="users", search_fields=[],
        fields=[
            _f("activity_id", "Activity", "reference", required=True, reference_entity="activity"),
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("registration_date", "Date", "date"),
            _f("registration_status", "Status", "select", options_master="registration_status"),
        ],
    ),
    # ----------------------------------------------------------------- Meal & Cafeteria
    EntitySpec(
        operations.MealPlan, "meal-plan", "Meal Plan", "meal_cafeteria",
        kind="master", icon="check-square", search_fields=["name", "code"],
        fields=[
            _f("name", "Name", required=True),
            _f("code", "Code", required=True),
            _f("meal_type", "Meal Type", "select", options_master="meal_type"),
            _f("price", "Price", "decimal"),
        ],
    ),
    EntitySpec(
        operations.MealMenu, "meal-menu", "Meal Menu", "meal_cafeteria",
        kind="transaction", icon="table", search_fields=["day_of_week"],
        fields=[
            _f("meal_plan_id", "Meal Plan", "reference", reference_entity="meal-plan"),
            _f("day_of_week", "Day", "select", required=True, options_master="day_of_week"),
            _f("items", "Items", "text"),
            _f("calories", "Calories", "number"),
        ],
    ),
    # ----------------------------------------------------------------- Communication
    EntitySpec(
        operations.Announcement, "announcement", "Announcement", "ptm_communication",
        kind="transaction", icon="activity", search_fields=["title"],
        fields=[
            _f("title", "Title", required=True),
            _f("body", "Body", "text", list_visible=False),
            _f("audience", "Audience", "select", options_master="audience"),
            _f("channel", "Channel", "select", options_master="comm_channel"),
            _f("publish_date", "Publish Date", "date"),
            _f("announcement_status", "Status", "select", options_master="announcement_status"),
        ],
    ),
    # ----------------------------------------------------------------- Public Website / CMS
    EntitySpec(
        operations.CmsPage, "cms-page", "CMS Page", "public_website_cms",
        kind="transaction", icon="book", search_fields=["title", "slug"],
        fields=[
            _f("title", "Title", required=True),
            _f("slug", "Slug", required=True),
            _f("page_type", "Type", "select", options_master="cms_page_type"),
            _f("body", "Body", "text", list_visible=False),
            _f("is_published", "Published", "bool"),
            _f("publish_date", "Publish Date", "date"),
        ],
    ),
    EntitySpec(
        operations.Banner, "banner", "Banner", "public_website_cms",
        kind="master", icon="grid", search_fields=["title"],
        fields=[
            _f("title", "Title", required=True),
            _f("image_url", "Image URL"),
            _f("link_url", "Link URL"),
            _f("sort_order", "Order", "number"),
            _f("is_active", "Active", "bool"),
        ],
    ),
    # ----------------------------------------------------------------- Digital Learning Repository
    EntitySpec(
        content.LearningResource, "learning-resource", "Learning Resource", "digital_learning_repository",
        kind="master", icon="book", search_fields=["title"],
        fields=[
            _f("title", "Title", required=True),
            _f("resource_type", "Type", "select", options_master="resource_type"),
            _f("subject_id", "Subject", "reference", reference_entity="subject"),
            _f("grade_id", "Grade", "reference", reference_entity="grade"),
            _f("url", "URL"),
            _f("description", "Description", "text", list_visible=False),
        ],
    ),
    # ----------------------------------------------------------------- Knowledge Base
    EntitySpec(
        content.KnowledgeArticle, "knowledge-article", "Knowledge Article", "knowledge_base",
        kind="transaction", icon="book", search_fields=["title", "category"],
        fields=[
            _f("title", "Title", required=True),
            _f("category", "Category"),
            _f("audience", "Audience", "select", options_master="audience"),
            _f("body", "Body", "text", list_visible=False),
            _f("is_published", "Published", "bool"),
        ],
    ),
    # ----------------------------------------------------------------- Question Paper / Bank
    EntitySpec(
        content.QuestionBankItem, "question-bank-item", "Question Bank", "question_paper_management",
        kind="transaction", icon="edit", search_fields=["question_text"],
        fields=[
            _f("subject_id", "Subject", "reference", reference_entity="subject"),
            _f("grade_id", "Grade", "reference", reference_entity="grade"),
            _f("question_type", "Type", "select", options_master="question_type"),
            _f("difficulty", "Difficulty", "select", options_master="difficulty"),
            _f("marks", "Marks", "number"),
            _f("question_text", "Question", "text", required=True),
            _f("answer_text", "Answer", "text", list_visible=False),
        ],
    ),
    # ----------------------------------------------------------------- Student records
    EntitySpec(
        student_records.StudentAcademicHistory, "academic-history", "Academic History",
        "student_information_system", kind="transaction", icon="trending-up", search_fields=["academic_year", "grade"],
        fields=[
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("academic_year", "Academic Year", required=True),
            _f("grade", "Class", required=True),
            _f("section", "Section"),
            _f("result", "Result", "select", options_master="academic_result"),
            _f("percentage", "Percentage", "decimal"),
            _f("rank", "Rank", "number"),
            _f("remarks", "Remarks"),
        ],
    ),
    EntitySpec(
        student_records.Achievement, "achievement", "Achievement", "student_information_system",
        kind="transaction", icon="trending-up", search_fields=["title"],
        fields=[
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("title", "Title", required=True),
            _f("category", "Category", "select", options_master="achievement_category"),
            _f("level", "Level", "select", options_master="achievement_level"),
            _f("achieved_on", "Date", "date"),
            _f("description", "Description", "text", list_visible=False),
        ],
    ),
    EntitySpec(
        student_records.DisciplinaryAction, "disciplinary-action", "Disciplinary Action",
        "student_information_system", kind="transaction", icon="shield", search_fields=["incident_type"],
        fields=[
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("incident_date", "Date", "date"),
            _f("incident_type", "Incident", required=True),
            _f("severity", "Severity", "select", options_master="discipline_severity"),
            _f("description", "Description", "text", list_visible=False),
            _f("action_taken", "Action Taken"),
            _f("reported_by", "Reported By"),
            _f("status", "Status", "select", options_master="discipline_status"),
        ],
    ),
    EntitySpec(
        student_records.StudentRemark, "student-remark", "Student Remark", "student_information_system",
        kind="transaction", icon="edit", search_fields=["remark"],
        fields=[
            _f("student_id", "Student", "reference", required=True, reference_entity="student"),
            _f("remark_type", "Type", "select", options_master="remark_type"),
            _f("remark", "Remark", "text", required=True),
            _f("remarked_by", "By"),
            _f("remarked_on", "Date", "date"),
            _f("is_visible_to_parent", "Visible to Parent", "bool"),
        ],
    ),
    # ----------------------------------------------------------------- PTM
    EntitySpec(
        content.PtmMeeting, "ptm-meeting", "PTM Meeting", "ptm_communication",
        kind="transaction", icon="users", search_fields=["title"],
        fields=[
            _f("title", "Title", required=True),
            _f("student_id", "Student", "reference", reference_entity="student"),
            _f("meeting_date", "Date", "date"),
            _f("slot_time", "Slot", "time"),
            _f("mode", "Mode", "select", options_master="meeting_mode"),
            _f("meeting_status", "Status", "select", options_master="meeting_status"),
            _f("notes", "Notes", "text", list_visible=False),
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
