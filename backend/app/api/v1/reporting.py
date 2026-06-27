"""Reporting subsystem.

A registry of cross-module reports exposed through two generic endpoints:
  * ``GET /reports/catalog``      → list of available reports (grouped by module)
  * ``GET /reports/run/{key}``    → { columns, rows, total } for one report

Each report is a builder ``async (db, tenant_id, params) -> (columns, rows)``.
The React Reports screen renders any of them generically with filters + CSV export.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.models.academic import Grade, Section, Subject
from app.models.admissions import AdmissionLead
from app.models.attendance import Attendance
from app.models.content import PtmMeeting
from app.models.exams import Exam, Marks, MarksBatch
from app.models.fees import Invoice, Payment
from app.models.finance import Expense, Vendor
from app.models.hostel import HostelBlock, HostelRoom
from app.models.hr import LeaveRequest, Payroll
from app.models.library import BookIssue, LibraryBook
from app.models.operations import Activity, ActivityRegistration, Announcement, AssetAssignment, InventoryItem
from app.models.people import Employee, Guardian, Student
from app.models.student_records import (
    Achievement,
    DisciplinaryAction,
    StudentAcademicHistory,
    StudentRemark,
)
from app.models.transport import StudentTransportAssignment, TransportRoute

router = APIRouter(prefix="/reports", tags=["Reports & Dashboards"])


def col(key: str, label: str) -> dict[str, str]:
    return {"key": key, "label": label}


def _s(v: Any) -> Any:
    if isinstance(v, Decimal):
        return str(v)
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def _mask_identifier(value: str | None) -> str | None:
    if not value:
        return value
    compact = "".join(ch for ch in value if ch.isalnum())
    if len(compact) <= 4:
        return "*" * len(compact)
    return f"{'*' * (len(compact) - 4)}{compact[-4:]}"


async def _name_map(db: AsyncSession, model, tid, fmt):
    rows = (
        await db.execute(select(model).where(model.tenant_id == tid, model.is_deleted.is_(False)))
    ).scalars().all()
    return {r.id: fmt(r) for r in rows}


# ----------------------------------------------------------------------- builders
async def students_roster(db, tid, p):
    grades = await _name_map(db, Grade, tid, lambda g: g.name)
    sections = await _name_map(db, Section, tid, lambda s: s.name)
    rows = (
        await db.execute(select(Student).where(Student.tenant_id == tid, Student.is_deleted.is_(False))
                         .order_by(Student.admission_no))
    ).scalars().all()
    return ([col("admission_no", "Admission No"), col("name", "Name"), col("grade", "Grade"),
             col("section", "Section"), col("gender", "Gender"), col("status", "Status")],
            [{"admission_no": s.admission_no, "name": f"{s.first_name} {s.last_name or ''}".strip(),
              "grade": grades.get(s.grade_id, "—"), "section": sections.get(s.section_id, "—"),
              "gender": s.gender or "—", "status": s.enrollment_status} for s in rows])


async def admission_funnel(db, tid, p):
    rows = (
        await db.execute(select(AdmissionLead.stage, func.count()).where(
            AdmissionLead.tenant_id == tid, AdmissionLead.is_deleted.is_(False)).group_by(AdmissionLead.stage))
    ).all()
    order = ["inquiry", "counseling", "entrance_test", "document_collection", "approved", "enrolled", "rejected"]
    counts = {s: c for s, c in rows}
    return ([col("stage", "Stage"), col("count", "Leads")],
            [{"stage": s.replace("_", " ").title(), "count": counts.get(s, 0)} for s in order])


async def fee_collection_summary(db, tid, p):
    rows = (
        await db.execute(select(Invoice.payment_status, func.count(),
                                func.coalesce(func.sum(Invoice.net_amount), 0),
                                func.coalesce(func.sum(Invoice.paid_amount), 0))
                         .where(Invoice.tenant_id == tid, Invoice.is_deleted.is_(False))
                         .group_by(Invoice.payment_status))
    ).all()
    return ([col("status", "Status"), col("count", "Invoices"), col("billed", "Billed"),
             col("collected", "Collected"), col("outstanding", "Outstanding")],
            [{"status": s, "count": c, "billed": _s(b), "collected": _s(pd),
              "outstanding": _s(b - pd)} for s, c, b, pd in rows])


async def fee_defaulters(db, tid, p):
    invs = (
        await db.execute(select(Invoice).where(Invoice.tenant_id == tid, Invoice.is_deleted.is_(False)))
    ).scalars().all()
    students = await _name_map(db, Student, tid, lambda s: f"{s.first_name} {s.last_name or ''}".strip())
    out = []
    for i in invs:
        bal = (i.net_amount or Decimal(0)) - (i.paid_amount or Decimal(0))
        if bal > 0:
            out.append({"student": students.get(i.student_id, "—"), "invoice_no": i.invoice_no,
                        "net": _s(i.net_amount), "paid": _s(i.paid_amount), "balance": _s(bal),
                        "due_date": _s(i.due_date), "status": i.payment_status})
    out.sort(key=lambda r: float(r["balance"]), reverse=True)
    return ([col("student", "Student"), col("invoice_no", "Invoice"), col("net", "Billed"),
             col("paid", "Paid"), col("balance", "Balance"), col("due_date", "Due"),
             col("status", "Status")], out)


async def attendance_register(db, tid, p):
    d = p.get("date") or _s(__import__("datetime").date.today())
    students = await _name_map(db, Student, tid, lambda s: f"{s.first_name} {s.last_name or ''}".strip())
    rows = (
        await db.execute(select(Attendance).where(
            Attendance.tenant_id == tid, Attendance.att_date == d, Attendance.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("student", "Student"), col("date", "Date"), col("state", "State"), col("method", "Method")],
            [{"student": students.get(a.student_id, "—"), "date": _s(a.att_date),
              "state": a.state, "method": a.method} for a in rows])


async def exam_results(db, tid, p):
    students = await _name_map(db, Student, tid, lambda s: f"{s.first_name} {s.last_name or ''}".strip())
    subjects = await _name_map(db, Subject, tid, lambda s: s.name)
    exams = await _name_map(db, Exam, tid, lambda e: e.name)
    rows = (
        await db.execute(select(Marks).where(Marks.tenant_id == tid, Marks.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("exam", "Exam"), col("student", "Student"), col("subject", "Subject"),
             col("marks", "Marks"), col("max", "Max"), col("grade", "Grade")],
            [{"exam": exams.get(m.exam_id, "—"), "student": students.get(m.student_id, "—"),
              "subject": subjects.get(m.subject_id, "—"), "marks": _s(m.marks_obtained),
              "max": _s(m.max_marks), "grade": m.grade_letter or "—"} for m in rows])


async def library_circulation(db, tid, p):
    students = await _name_map(db, Student, tid, lambda s: f"{s.first_name} {s.last_name or ''}".strip())
    books = await _name_map(db, LibraryBook, tid, lambda b: b.title)
    rows = (
        await db.execute(select(BookIssue).where(BookIssue.tenant_id == tid, BookIssue.is_deleted.is_(False))
                         .order_by(BookIssue.issue_date.desc()))
    ).scalars().all()
    only_overdue = p.get("overdue") in ("1", "true", "yes")
    today = __import__("datetime").date.today()
    out = []
    for i in rows:
        overdue = i.issue_status != "returned" and i.due_date and i.due_date < today
        if only_overdue and not overdue:
            continue
        out.append({"book": books.get(i.book_id, "—"), "student": students.get(i.student_id, "—"),
                    "issue_date": _s(i.issue_date), "due_date": _s(i.due_date),
                    "status": "overdue" if overdue else i.issue_status, "fine": _s(i.fine_amount)})
    return ([col("book", "Book"), col("student", "Student"), col("issue_date", "Issued"),
             col("due_date", "Due"), col("status", "Status"), col("fine", "Fine")], out)


async def transport_roster(db, tid, p):
    students = await _name_map(db, Student, tid, lambda s: f"{s.first_name} {s.last_name or ''}".strip())
    routes = await _name_map(db, TransportRoute, tid, lambda r: r.name)
    rows = (
        await db.execute(select(StudentTransportAssignment).where(
            StudentTransportAssignment.tenant_id == tid, StudentTransportAssignment.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("student", "Student"), col("route", "Route"), col("fee", "Fee"), col("status", "Status")],
            [{"student": students.get(a.student_id, "—"), "route": routes.get(a.route_id, "—"),
              "fee": _s(a.fee_amount), "status": a.assignment_status} for a in rows])


async def hostel_occupancy(db, tid, p):
    blocks = await _name_map(db, HostelBlock, tid, lambda b: b.name)
    rows = (
        await db.execute(select(HostelRoom).where(HostelRoom.tenant_id == tid, HostelRoom.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("block", "Block"), col("room", "Room"), col("capacity", "Capacity"),
             col("occupied", "Occupied"), col("free", "Free")],
            [{"block": blocks.get(r.block_id, "—"), "room": r.room_no, "capacity": r.capacity,
              "occupied": r.occupied, "free": r.capacity - r.occupied} for r in rows])


async def leave_register(db, tid, p):
    emps = await _name_map(db, Employee, tid, lambda e: f"{e.first_name} {e.last_name or ''}".strip())
    rows = (
        await db.execute(select(LeaveRequest).where(LeaveRequest.tenant_id == tid, LeaveRequest.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("employee", "Employee"), col("type", "Type"), col("from", "From"), col("to", "To"),
             col("days", "Days"), col("status", "Status")],
            [{"employee": emps.get(l.employee_id, "—"), "type": l.leave_type or "—", "from": _s(l.from_date),
              "to": _s(l.to_date), "days": l.days, "status": l.request_status} for l in rows])


async def payroll_register(db, tid, p):
    emps = await _name_map(db, Employee, tid, lambda e: f"{e.first_name} {e.last_name or ''}".strip())
    rows = (
        await db.execute(select(Payroll).where(Payroll.tenant_id == tid, Payroll.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("employee", "Employee"), col("period", "Period"), col("basic", "Basic"),
             col("net", "Net Pay"), col("status", "Status")],
            [{"employee": emps.get(p2.employee_id, "—"), "period": f"{p2.month}/{p2.year}",
              "basic": _s(p2.basic), "net": _s(p2.net_pay), "status": p2.payroll_status} for p2 in rows])


async def inventory_stock(db, tid, p):
    rows = (
        await db.execute(select(InventoryItem).where(InventoryItem.tenant_id == tid, InventoryItem.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("name", "Item"), col("category", "Category"), col("on_hand", "On Hand"),
             col("reorder", "Reorder"), col("status", "Status")],
            [{"name": it.name, "category": it.category or "—", "on_hand": it.quantity_on_hand,
              "reorder": it.reorder_level,
              "status": "LOW" if it.quantity_on_hand <= it.reorder_level else "OK"} for it in rows])


async def expense_ledger(db, tid, p):
    vendors = await _name_map(db, Vendor, tid, lambda v: v.name)
    rows = (
        await db.execute(select(Expense).where(Expense.tenant_id == tid, Expense.is_deleted.is_(False))
                         .order_by(Expense.expense_date.desc()))
    ).scalars().all()
    return ([col("expense_no", "Expense No"), col("vendor", "Vendor"), col("amount", "Amount"),
             col("date", "Date"), col("status", "Status")],
            [{"expense_no": e.expense_no, "vendor": vendors.get(e.vendor_id, "—"), "amount": _s(e.amount),
              "date": _s(e.expense_date), "status": e.approval_status} for e in rows])


async def activity_enrollment(db, tid, p):
    acts = (
        await db.execute(select(Activity).where(Activity.tenant_id == tid, Activity.is_deleted.is_(False)))
    ).scalars().all()
    regs = (
        await db.execute(select(ActivityRegistration.activity_id, func.count()).where(
            ActivityRegistration.tenant_id == tid, ActivityRegistration.registration_status == "registered",
            ActivityRegistration.is_deleted.is_(False)).group_by(ActivityRegistration.activity_id))
    ).all()
    counts = {a: c for a, c in regs}
    return ([col("activity", "Activity"), col("type", "Type"), col("capacity", "Capacity"),
             col("registered", "Registered"), col("fee", "Fee")],
            [{"activity": a.name, "type": a.activity_type or "—", "capacity": a.capacity,
              "registered": counts.get(a.id, 0), "fee": _s(a.fee)} for a in acts])


async def staff_directory(db, tid, p):
    rows = (
        await db.execute(select(Employee).where(Employee.tenant_id == tid, Employee.is_deleted.is_(False))
                         .order_by(Employee.employee_no))
    ).scalars().all()
    return ([col("employee_no", "Emp No"), col("name", "Name"), col("designation", "Designation"),
             col("department", "Department"), col("status", "Status")],
            [{"employee_no": e.employee_no, "name": f"{e.first_name} {e.last_name or ''}".strip(),
              "designation": e.designation or "—", "department": e.department or "—",
              "status": e.employment_status} for e in rows])


async def communication_log(db, tid, p):
    rows = (
        await db.execute(select(Announcement).where(Announcement.tenant_id == tid, Announcement.is_deleted.is_(False))
                         .order_by(Announcement.created_at.desc()))
    ).scalars().all()
    return ([col("title", "Title"), col("audience", "Audience"), col("channel", "Channel"),
             col("status", "Status"), col("publish_date", "Publish Date")],
            [{"title": a.title, "audience": a.audience, "channel": a.channel,
              "status": a.announcement_status, "publish_date": _s(a.publish_date)} for a in rows])


async def ptm_schedule(db, tid, p):
    students = await _name_map(db, Student, tid, lambda s: f"{s.first_name} {s.last_name or ''}".strip())
    rows = (
        await db.execute(select(PtmMeeting).where(PtmMeeting.tenant_id == tid, PtmMeeting.is_deleted.is_(False)))
    ).scalars().all()
    return ([col("title", "Title"), col("student", "Student"), col("date", "Date"),
             col("mode", "Mode"), col("status", "Status")],
            [{"title": m.title, "student": students.get(m.student_id, "—"), "date": _s(m.meeting_date),
              "mode": m.mode, "status": m.meeting_status} for m in rows])


# ----------------------------------------------------------------------- registry
REPORTS: dict[str, dict] = {
    "students_roster": {"name": "Student Roster", "module": "Student Information System", "builder": students_roster},
    "admission_funnel": {"name": "Admissions Funnel", "module": "Admissions CRM", "builder": admission_funnel},
    "fee_collection_summary": {"name": "Fee Collection Summary", "module": "Fees & Billing", "builder": fee_collection_summary},
    "fee_defaulters": {"name": "Fee Defaulters", "module": "Fees & Billing", "builder": fee_defaulters},
    "attendance_register": {"name": "Attendance Register", "module": "Attendance", "builder": attendance_register,
                            "filters": [{"key": "date", "label": "Date", "type": "date"}]},
    "exam_results": {"name": "Exam Results", "module": "Examination Management", "builder": exam_results},
    "library_circulation": {"name": "Library Circulation", "module": "Library Management", "builder": library_circulation,
                            "filters": [{"key": "overdue", "label": "Overdue only", "type": "bool"}]},
    "transport_roster": {"name": "Transport Roster", "module": "Transport", "builder": transport_roster},
    "hostel_occupancy": {"name": "Hostel Occupancy", "module": "Hostel", "builder": hostel_occupancy},
    "leave_register": {"name": "Leave Register", "module": "Employee HRMS", "builder": leave_register},
    "payroll_register": {"name": "Payroll Register", "module": "Employee HRMS", "builder": payroll_register},
    "inventory_stock": {"name": "Inventory & Low Stock", "module": "Store / Inventory", "builder": inventory_stock},
    "expense_ledger": {"name": "Expense Ledger", "module": "Finance & Accounting", "builder": expense_ledger},
    "activity_enrollment": {"name": "Activity Enrollment", "module": "Activities & Events", "builder": activity_enrollment},
    "staff_directory": {"name": "Staff Directory", "module": "Employee HRMS", "builder": staff_directory},
    "communication_log": {"name": "Communication Log", "module": "PTM & Communication", "builder": communication_log},
    "ptm_schedule": {"name": "PTM Schedule", "module": "PTM & Communication", "builder": ptm_schedule},
}


@router.get("/catalog")
async def catalog(user: CurrentUser = Depends(get_current_user)):
    return [
        {"key": k, "name": r["name"], "module": r["module"], "filters": r.get("filters", [])}
        for k, r in REPORTS.items()
    ]


@router.get("/student-360/{student_id}")
async def student_360(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Consolidated parent-portal view for one student across modules."""
    import uuid as _uuid

    student = await db.get(Student, _uuid.UUID(student_id))
    if not student or student.tenant_id != user.tenant_id or student.is_deleted:
        raise HTTPException(404, "Student not found")
    tid = user.tenant_id
    grades = await _name_map(db, Grade, tid, lambda g: g.name)
    sections = await _name_map(db, Section, tid, lambda s: s.name)
    subjects = await _name_map(db, Subject, tid, lambda s: s.name)
    exams = await _name_map(db, Exam, tid, lambda e: e.name)

    invoices = (
        await db.execute(select(Invoice).where(Invoice.tenant_id == tid, Invoice.student_id == student.id,
                                                Invoice.is_deleted.is_(False)))
    ).scalars().all()
    billed = sum((i.net_amount or Decimal(0)) for i in invoices)
    paid = sum((i.paid_amount or Decimal(0)) for i in invoices)

    att = (
        await db.execute(select(Attendance.state, func.count()).where(
            Attendance.tenant_id == tid, Attendance.student_id == student.id,
            Attendance.is_deleted.is_(False)).group_by(Attendance.state))
    ).all()
    att_summary = {s: c for s, c in att}

    marks = (
        await db.execute(select(Marks).where(Marks.tenant_id == tid, Marks.student_id == student.id,
                                             Marks.is_deleted.is_(False)))
    ).scalars().all()
    batches = (
        await db.execute(select(MarksBatch).where(MarksBatch.tenant_id == tid, MarksBatch.is_deleted.is_(False)))
    ).scalars().all()
    if batches:
        published = {(b.exam_id, b.subject_id) for b in batches if b.batch_status == "published"}
        marks = [m for m in marks if (m.exam_id, m.subject_id) in published]
    guardians = (
        await db.execute(select(Guardian).where(Guardian.tenant_id == tid, Guardian.student_id == student.id,
                                                Guardian.is_deleted.is_(False)))
    ).scalars().all()

    history = (
        await db.execute(select(StudentAcademicHistory).where(
            StudentAcademicHistory.tenant_id == tid, StudentAcademicHistory.student_id == student.id,
            StudentAcademicHistory.is_deleted.is_(False)).order_by(StudentAcademicHistory.academic_year))
    ).scalars().all()
    achievements = (
        await db.execute(select(Achievement).where(
            Achievement.tenant_id == tid, Achievement.student_id == student.id,
            Achievement.is_deleted.is_(False)).order_by(Achievement.achieved_on.desc()))
    ).scalars().all()
    discipline = (
        await db.execute(select(DisciplinaryAction).where(
            DisciplinaryAction.tenant_id == tid, DisciplinaryAction.student_id == student.id,
            DisciplinaryAction.is_deleted.is_(False)).order_by(DisciplinaryAction.incident_date.desc()))
    ).scalars().all()
    remarks = (
        await db.execute(select(StudentRemark).where(
            StudentRemark.tenant_id == tid, StudentRemark.student_id == student.id,
            StudentRemark.is_deleted.is_(False)).order_by(StudentRemark.remarked_on.desc()))
    ).scalars().all()

    # Activities the student is enrolled in
    activity_names = await _name_map(db, Activity, tid, lambda a: a.name)
    regs = (
        await db.execute(select(ActivityRegistration).where(
            ActivityRegistration.tenant_id == tid, ActivityRegistration.student_id == student.id,
            ActivityRegistration.is_deleted.is_(False)))
    ).scalars().all()
    inventory_names = await _name_map(db, InventoryItem, tid, lambda i: i.name)
    asset_rows = (
        await db.execute(select(AssetAssignment).where(
            AssetAssignment.tenant_id == tid,
            AssetAssignment.student_id == student.id,
            AssetAssignment.assignment_status == "issued",
            AssetAssignment.is_deleted.is_(False)))
    ).scalars().all()
    book_names = await _name_map(db, LibraryBook, tid, lambda b: b.title)
    book_issues = (
        await db.execute(select(BookIssue).where(
            BookIssue.tenant_id == tid,
            BookIssue.student_id == student.id,
            BookIssue.issue_status == "issued",
            BookIssue.is_deleted.is_(False)))
    ).scalars().all()

    # Payments (for receipts) + per-invoice rows
    payments = (
        await db.execute(select(Payment).where(Payment.tenant_id == tid, Payment.student_id == student.id,
                                               Payment.is_deleted.is_(False)).order_by(Payment.paid_at.desc()))
    ).scalars().all()

    # Teachers: derived from the actual teacher→class/subject mappings for the
    # student's grade & section (falls back to class teacher on the section).
    from app.models.people import TeacherAssignment

    class_teacher = None
    section_obj = await db.get(Section, student.section_id) if student.section_id else None
    if section_obj and section_obj.class_teacher_id:
        ct = await db.get(Employee, section_obj.class_teacher_id)
        if ct:
            class_teacher = f"{ct.first_name} {ct.last_name or ''}".strip()

    assignments = (
        await db.execute(select(TeacherAssignment).where(
            TeacherAssignment.tenant_id == tid, TeacherAssignment.is_deleted.is_(False),
            TeacherAssignment.assignment_status == "active",
            (TeacherAssignment.grade_id == student.grade_id) | (TeacherAssignment.grade_id.is_(None)),
            (TeacherAssignment.section_id == student.section_id) | (TeacherAssignment.section_id.is_(None))))
    ).scalars().all()
    seen: set = set()
    teacher_rows: list[dict] = []
    for a in assignments:
        emp = await db.get(Employee, a.employee_id)
        if not emp:
            continue
        key = (emp.id, a.subject_id)
        if key in seen:
            continue
        seen.add(key)
        teacher_rows.append({
            "name": f"{emp.first_name} {emp.last_name or ''}".strip(),
            "designation": emp.designation,
            "subject": subjects.get(a.subject_id, "Class Teacher" if not a.subject_id else "—"),
        })

    return {
        "student": {
            "id": str(student.id), "admission_no": student.admission_no, "roll_no": student.roll_no,
            "name": f"{student.first_name} {student.last_name or ''}".strip(),
            "grade": grades.get(student.grade_id, "—"), "section": sections.get(student.section_id, "—"),
            "gender": student.gender, "status": student.enrollment_status,
            "phone": student.phone, "email": student.email,
            "date_of_birth": _s(student.date_of_birth), "blood_group": student.blood_group,
            "admission_date": _s(student.admission_date), "category": student.category,
            "religion": student.religion, "nationality": student.nationality,
            "mother_tongue": student.mother_tongue, "id_number": student.id_number,
            "government_id_type": student.government_id_type,
            "government_id_masked": _mask_identifier(student.government_id_number),
            "emergency_contact_name": student.emergency_contact_name,
            "emergency_contact_phone": student.emergency_contact_phone,
            "house": student.house, "previous_school": student.previous_school,
            "address": student.address, "city": student.city, "state": student.state,
            "pincode": student.pincode, "photo_url": student.photo_url,
            "class_teacher": class_teacher,
        },
        "guardians": [
            {"name": g.full_name, "relation": g.relation, "phone": g.phone, "email": g.email,
             "occupation": g.occupation, "address": g.address,
             "government_id_type": g.government_id_type,
             "government_id_masked": _mask_identifier(g.government_id_number)}
            for g in guardians
        ],
        "fees": {"billed": _s(billed), "paid": _s(paid), "balance": _s(billed - paid),
                 "invoices": len(invoices)},
        "invoices": [
            {"id": str(i.id), "invoice_no": i.invoice_no, "net": _s(i.net_amount),
             "paid": _s(i.paid_amount), "status": i.payment_status, "due_date": _s(i.due_date)}
            for i in invoices
        ],
        "payments": [
            {"id": str(p.id), "receipt_no": p.receipt_no, "amount": _s(p.amount),
             "method": p.method, "paid_at": _s(p.paid_at)}
            for p in payments
        ],
        "attendance": att_summary,
        "marks": [
            {"exam": exams.get(m.exam_id, "—"), "subject": subjects.get(m.subject_id, "—"),
             "marks": _s(m.marks_obtained), "max": _s(m.max_marks), "grade": m.grade_letter}
            for m in marks
        ],
        "academic_history": [
            {"year": h.academic_year, "grade": h.grade, "section": h.section, "result": h.result,
             "percentage": _s(h.percentage), "rank": h.rank, "remarks": h.remarks}
            for h in history
        ],
        "achievements": [
            {"title": a.title, "category": a.category, "level": a.level,
             "date": _s(a.achieved_on), "description": a.description}
            for a in achievements
        ],
        "discipline": [
            {"date": _s(d.incident_date), "incident": d.incident_type, "severity": d.severity,
             "description": d.description, "action": d.action_taken, "status": d.status}
            for d in discipline
        ],
        "remarks": [
            {"type": r.remark_type, "remark": r.remark, "by": r.remarked_by, "date": _s(r.remarked_on),
             "visible_to_parent": r.is_visible_to_parent}
            for r in remarks
        ],
        "activities": [
            {"name": activity_names.get(r.activity_id, "—"), "status": r.registration_status,
             "date": _s(r.registration_date)}
            for r in regs
        ],
        "assets": [
            {"type": "inventory", "name": inventory_names.get(a.item_id, "—"), "quantity": a.quantity,
             "status": a.assignment_status, "issue_date": _s(a.issue_date), "due_date": _s(a.due_date)}
            for a in asset_rows
        ] + [
            {"type": "library", "name": book_names.get(b.book_id, "—"), "quantity": 1,
             "status": b.issue_status, "issue_date": _s(b.issue_date), "due_date": _s(b.due_date)}
            for b in book_issues
        ],
        "teachers": teacher_rows,
    }


@router.get("/employee-360/{employee_id}")
async def employee_360(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Consolidated staff profile: employment, teaching, leave, payroll, assets, docs."""
    import uuid as _uuid

    from app.models.hr import LeaveRequest, LeaveType, Payroll
    from app.models.meta import Document
    from app.models.operations import AssetAssignment, InventoryItem
    from app.models.people import Employee, TeacherAssignment, TeacherProfile

    emp = await db.get(Employee, _uuid.UUID(employee_id))
    if not emp or emp.tenant_id != user.tenant_id or emp.is_deleted:
        raise HTTPException(404, "Employee not found")
    tid = user.tenant_id
    grades = await _name_map(db, Grade, tid, lambda g: g.name)
    sections = await _name_map(db, Section, tid, lambda s: s.name)
    subjects = await _name_map(db, Subject, tid, lambda s: s.name)

    tp = (await db.execute(select(TeacherProfile).where(
        TeacherProfile.tenant_id == tid, TeacherProfile.employee_id == emp.id,
        TeacherProfile.is_deleted.is_(False)))).scalars().first()
    manager_name = None
    if tp and tp.reporting_manager_id:
        m = await db.get(Employee, tp.reporting_manager_id)
        manager_name = f"{m.first_name} {m.last_name or ''}".strip() if m else None

    assignments = (await db.execute(select(TeacherAssignment).where(
        TeacherAssignment.tenant_id == tid, TeacherAssignment.employee_id == emp.id,
        TeacherAssignment.is_deleted.is_(False)))).scalars().all()

    leave_types = (await db.execute(select(LeaveType).where(
        LeaveType.tenant_id == tid, LeaveType.is_deleted.is_(False)))).scalars().all()
    leaves = (await db.execute(select(LeaveRequest).where(
        LeaveRequest.tenant_id == tid, LeaveRequest.employee_id == emp.id,
        LeaveRequest.is_deleted.is_(False)).order_by(LeaveRequest.from_date.desc()))).scalars().all()
    taken = {}
    for l in leaves:
        if l.request_status == "approved":
            taken[l.leave_type] = taken.get(l.leave_type, 0) + l.days

    payroll = (await db.execute(select(Payroll).where(
        Payroll.tenant_id == tid, Payroll.employee_id == emp.id, Payroll.is_deleted.is_(False))
        .order_by(Payroll.year.desc(), Payroll.month.desc()))).scalars().all()

    item_names = await _name_map(db, InventoryItem, tid, lambda i: i.name)
    assets = (await db.execute(select(AssetAssignment).where(
        AssetAssignment.tenant_id == tid, AssetAssignment.employee_id == emp.id,
        AssetAssignment.assignment_status == "issued", AssetAssignment.is_deleted.is_(False)))).scalars().all()

    docs = (await db.execute(select(Document).where(
        Document.tenant_id == tid, Document.owner_type == "employee", Document.owner_id == emp.id,
        Document.is_deleted.is_(False)))).scalars().all()

    return {
        "employee": {
            "id": str(emp.id), "employee_no": emp.employee_no,
            "name": f"{emp.first_name} {emp.last_name or ''}".strip(),
            "designation": emp.designation, "department": emp.department,
            "gender": emp.gender, "email": emp.email, "phone": emp.phone, "address": emp.address,
            "government_id_type": emp.government_id_type,
            "government_id_masked": _mask_identifier(emp.government_id_number),
            "date_of_joining": _s(emp.date_of_joining), "employment_type": emp.employment_type,
            "employment_status": emp.employment_status, "salary": _s(emp.salary),
            "reporting_manager": manager_name,
        },
        "teaching_profile": None if not tp else {
            "qualification": tp.qualification, "expertise": tp.expertise,
            "certifications": tp.certifications, "subjects_can_teach": tp.subjects_can_teach,
        },
        "classes": [
            {"grade": grades.get(a.grade_id, "—"), "section": sections.get(a.section_id, "—"),
             "subject": subjects.get(a.subject_id, "—"), "status": a.assignment_status}
            for a in assignments
        ],
        "leave_balance": [
            {"type": lt.name, "code": lt.code, "allowance": lt.max_days_per_year,
             "taken": taken.get(lt.code, 0), "balance": lt.max_days_per_year - taken.get(lt.code, 0)}
            for lt in leave_types
        ],
        "leave_history": [
            {"type": l.leave_type, "from": _s(l.from_date), "to": _s(l.to_date),
             "days": l.days, "status": l.request_status}
            for l in leaves
        ],
        "payroll": [
            {"period": f"{p.month}/{p.year}", "basic": _s(p.basic), "net": _s(p.net_pay),
             "status": p.payroll_status}
            for p in payroll
        ],
        "assets": [
            {"name": item_names.get(a.item_id, "—"), "quantity": a.quantity,
             "status": a.assignment_status, "due_date": _s(a.due_date)}
            for a in assets
        ],
        "documents": [{"name": d.name, "category": d.category, "url": d.url} for d in docs],
    }


@router.get("/run/{key}")
async def run_report(
    key: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    report = REPORTS.get(key)
    if not report:
        raise HTTPException(404, "Unknown report")
    params = dict(request.query_params)
    columns, rows = await report["builder"](db, user.tenant_id, params)
    return {"key": key, "name": report["name"], "columns": columns, "rows": rows, "total": len(rows)}
