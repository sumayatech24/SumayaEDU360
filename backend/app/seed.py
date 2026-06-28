"""Idempotent database seeder.

Loads the parsed requirements spec (``seed_data/spec.json``) plus demo operational
data so the running system is entirely database-driven:

  * modules + capabilities (from the catalog)
  * roles + permissions + RBAC (from the matrix)
  * entity & field metadata (typed + generic)
  * configurable masters (gender, fee frequency, exam type, ...)
  * DB-driven navigation menu
  * a demo tenant with academic config, students, fees, attendance, an exam

Run with:  ``python -m app.seed``
"""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_models
from app.core.security import hash_password
from app.models import (
    AcademicYear,
    AdmissionLead,
    Attendance,
    CurriculumPlan,
    Employee,
    EntityDef,
    Exam,
    ExamSubject,
    FeePlan,
    FieldDef,
    Grade,
    Homework,
    HomeworkSubmission,
    HostelBlock,
    HostelRoom,
    LeaveType,
    BookIssue,
    LibraryBook,
    MarksBatch,
    Activity,
    AssetAssignment,
    InventoryItem,
    TransportRoute,
    TimetablePeriod,
    Vehicle,
    Institution,
    Invoice,
    MasterType,
    MasterValue,
    MenuItem,
    Module,
    ModuleCapability,
    Permission,
    Role,
    RolePermission,
    Section,
    Setting,
    Student,
    Subject,
    Tenant,
    TeacherAssignment,
    TeacherProfile,
    User,
    UserRole,
)

SPEC_PATH = Path(__file__).parent / "seed_data" / "spec.json"
ACTIONS = ["read", "create", "update", "delete", "approve", "export"]


def role_code(name: str) -> str:
    return name.strip().lower().replace(" & ", "_").replace(" ", "_").replace("/", "_")


# Map a core entity name -> (module_slug, typed_table, kind)
TYPED_ENTITIES = {
    "Institution": ("student_information_system", "institution", "master"),
    "AcademicYear": ("academic_configuration", "academic_year", "master"),
    "Program": ("academic_configuration", "program", "master"),
    "Grade": ("academic_configuration", "grade", "master"),
    "Section": ("academic_configuration", "section", "master"),
    "Subject": ("academic_configuration", "subject", "master"),
    "Student": ("student_information_system", "student", "transaction"),
    "Guardian": ("parent_guardian_portal", "guardian", "master"),
    "Employee": ("employee_hrms", "employee", "transaction"),
    "AdmissionLead": ("admissions_crm", "admission_lead", "transaction"),
    "FeePlan": ("fees_billing", "fee_plan", "master"),
    "Invoice": ("fees_billing", "invoice", "transaction"),
    "Exam": ("examination_management", "exam", "transaction"),
}

# Field metadata for typed entities (drives dynamic list/forms in the client).
TYPED_FIELDS: dict[str, list[tuple]] = {
    # (name, label, data_type, required, list_visible, options_master, reference_entity)
    "institution": [
        ("name", "Name", "string", True, True, None, None),
        ("code", "Code", "string", True, True, None, None),
        ("type", "Type", "string", False, True, None, None),
        ("board", "Board", "string", False, True, None, None),
        ("address", "Address", "text", False, False, None, None),
        ("status", "Status", "select", False, True, "active_status", None),
    ],
    "academic_year": [
        ("name", "Name", "string", True, True, None, None),
        ("code", "Code", "string", True, True, None, None),
        ("start_date", "Start Date", "date", False, True, None, None),
        ("end_date", "End Date", "date", False, True, None, None),
        ("is_current", "Current", "bool", False, True, None, None),
    ],
    "program": [
        ("name", "Name", "string", True, True, None, None),
        ("code", "Code", "string", True, True, None, None),
        ("level", "Level", "string", False, True, None, None),
    ],
    "student": [
        ("admission_no", "Admission No", "string", True, True, None, None),
        ("roll_no", "Roll No", "string", False, True, None, None),
        ("first_name", "First Name", "string", True, True, None, None),
        ("last_name", "Last Name", "string", False, True, None, None),
        ("gender", "Gender", "select", False, True, "gender", None),
        ("date_of_birth", "Date of Birth", "date", False, False, None, None),
        ("academic_year_id", "Academic Year", "reference", False, False, None, "academic-year"),
        ("grade_id", "Grade", "reference", False, True, None, "grade"),
        ("section_id", "Section", "reference", False, True, None, "section"),
        ("enrollment_status", "Status", "select", False, True, "enrollment_status", None),
        ("phone", "Phone", "phone", False, True, None, None),
        ("email", "Email", "email", False, False, None, None),
        ("blood_group", "Blood Group", "select", False, False, "blood_group", None),
        ("category", "Category", "select", False, False, "category", None),
        ("religion", "Religion", "select", False, False, "religion", None),
        ("nationality", "Nationality", "select", False, False, "nationality", None),
        ("mother_tongue", "Mother Tongue", "string", False, False, None, None),
        ("id_number", "ID / Aadhaar No", "string", False, False, None, None),
        ("house", "House", "string", False, False, None, None),
        ("admission_date", "Admission Date", "date", False, False, None, None),
        ("previous_school", "Previous School", "string", False, False, None, None),
        ("address", "Address", "text", False, False, None, None),
        ("city", "City", "string", False, False, None, None),
        ("state", "State", "string", False, False, None, None),
        ("pincode", "Pincode", "string", False, False, None, None),
    ],
    "guardian": [
        ("student_id", "Student", "reference", True, True, None, "student"),
        ("relation", "Relation", "select", False, True, "relation", None),
        ("full_name", "Full Name", "string", True, True, None, None),
        ("phone", "Phone", "phone", False, True, None, None),
        ("email", "Email", "email", False, False, None, None),
        ("occupation", "Occupation", "string", False, False, None, None),
        ("is_primary", "Primary", "bool", False, True, None, None),
    ],
    "employee": [
        ("employee_no", "Employee No", "string", True, True, None, None),
        ("first_name", "First Name", "string", True, True, None, None),
        ("last_name", "Last Name", "string", False, True, None, None),
        ("gender", "Gender", "select", False, False, "gender", None),
        ("email", "Email", "email", False, False, None, None),
        ("phone", "Phone", "phone", False, True, None, None),
        ("staff_role", "Staff Role", "select", False, True, "staff_role", None),
        ("designation", "Designation", "select", False, True, "designation", None),
        ("department", "Department", "select", False, True, "department", None),
        ("date_of_joining", "Joining Date", "date", False, False, None, None),
        ("employment_type", "Type", "select", False, True, "employment_type", None),
        ("salary", "Salary", "decimal", False, False, None, None),
        ("employment_status", "Status", "select", False, True, "active_status", None),
    ],
    "grade": [
        ("program_id", "Program", "reference", False, False, None, "program"),
        ("name", "Name", "string", True, True, None, None),
        ("code", "Code", "string", True, True, None, None),
        ("sequence", "Sequence", "number", False, True, None, None),
    ],
    "section": [
        ("grade_id", "Grade", "reference", True, True, None, "grade"),
        ("name", "Name", "string", True, True, None, None),
        ("capacity", "Capacity", "number", False, True, None, None),
        ("class_teacher_id", "Class Teacher", "reference", False, False, None, "employee"),
    ],
    "subject": [
        ("name", "Name", "string", True, True, None, None),
        ("code", "Code", "string", True, True, None, None),
        ("grade_id", "Grade", "reference", False, True, None, "grade"),
        ("is_elective", "Elective", "bool", False, True, None, None),
        ("credits", "Credits", "number", False, True, None, None),
    ],
    "fee_plan": [
        ("name", "Name", "string", True, True, None, None),
        ("code", "Code", "string", True, True, None, None),
        ("academic_year_id", "Academic Year", "reference", False, False, None, "academic-year"),
        ("grade_id", "Grade", "reference", False, True, None, "grade"),
        ("frequency", "Frequency", "select", False, True, "fee_frequency", None),
        ("amount", "Amount", "decimal", True, True, None, None),
        ("description", "Description", "text", False, False, None, None),
    ],
    "invoice": [
        ("invoice_no", "Invoice No", "string", True, True, None, None),
        ("student_id", "Student", "reference", True, True, None, "student"),
        ("fee_plan_id", "Fee Plan", "reference", False, False, None, "fee-plan"),
        ("academic_year_id", "Academic Year", "reference", False, False, None, "academic-year"),
        ("issue_date", "Issue Date", "date", False, True, None, None),
        ("due_date", "Due Date", "date", False, True, None, None),
        ("gross_amount", "Gross", "decimal", False, True, None, None),
        ("discount_amount", "Discount", "decimal", False, False, None, None),
        ("net_amount", "Net", "decimal", False, True, None, None),
        ("payment_status", "Status", "select", False, True, "payment_status", None),
    ],
    "admission_lead": [
        ("lead_no", "Lead No", "string", True, True, None, None),
        ("student_name", "Student Name", "string", True, True, None, None),
        ("guardian_name", "Guardian", "string", False, False, None, None),
        ("phone", "Phone", "phone", False, True, None, None),
        ("email", "Email", "email", False, False, None, None),
        ("grade_applied_id", "Grade Applied", "reference", False, True, None, "grade"),
        ("source", "Source", "select", False, True, "lead_source", None),
        ("stage", "Stage", "select", False, True, "lead_stage", None),
        ("follow_up_date", "Follow Up", "date", False, False, None, None),
        ("test_score", "Test Score", "string", False, False, None, None),
        ("notes", "Notes", "text", False, False, None, None),
    ],
    "exam": [
        ("name", "Name", "string", True, True, None, None),
        ("code", "Code", "string", True, True, None, None),
        ("academic_year_id", "Academic Year", "reference", False, False, None, "academic-year"),
        ("exam_type", "Exam Type", "select", False, True, "exam_type", None),
        ("grade_id", "Grade", "reference", False, True, None, "grade"),
        ("start_date", "Start Date", "date", False, True, None, None),
        ("end_date", "End Date", "date", False, True, None, None),
        ("max_marks", "Max Marks", "decimal", False, True, None, None),
        ("pass_marks", "Pass Marks", "decimal", False, False, None, None),
    ],
}

# Configurable masters seeded for every tenant.
MASTERS: dict[str, tuple[str, list[str]]] = {
    "gender": ("Gender", ["Male", "Female", "Other"]),
    "blood_group": ("Blood Group", ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]),
    "religion": ("Religion", ["Hindu", "Muslim", "Christian", "Sikh", "Other"]),
    "category": ("Category", ["General", "OBC", "SC", "ST", "EWS"]),
    "relation": ("Guardian Relation", ["Father", "Mother", "Guardian", "Sibling"]),
    "fee_frequency": ("Fee Frequency", ["Annual", "Term", "Monthly", "One Time"]),
    "payment_method": ("Payment Method", ["Cash", "Card", "UPI", "Netbanking", "Cheque", "Gateway"]),
    "payment_status": ("Payment Status", ["Unpaid", "Partial", "Paid", "Overdue", "Cancelled"]),
    "attendance_state": ("Attendance State", ["Present", "Absent", "Late", "Leave", "Holiday", "Half Day", "On Duty"]),
    "attendance_method": ("Attendance Method", ["Manual", "QR", "RFID", "Biometric", "Face", "Geofence"]),
    "exam_type": ("Exam Type", ["Internal", "Unit Test", "Midterm", "Semester", "Final"]),
    "employment_type": ("Employment Type", ["Full Time", "Part Time", "Contract", "Visiting"]),
    "staff_role": ("Staff Role", ["Teacher", "Admin Staff", "Accountant", "Librarian", "Management",
                                   "Support Staff", "Counselor", "Nurse", "Lab Assistant",
                                   "Transport Staff", "Security", "IT Staff"]),
    "designation": ("Designation", ["Principal", "Vice Principal", "Head of Department", "Senior Teacher",
                                     "Teacher", "Assistant Teacher", "Administrative Officer", "Accountant",
                                     "Librarian", "Office Clerk", "Lab Assistant", "Counselor", "Nurse",
                                     "Transport Incharge", "Security Guard"]),
    "department": ("Department", ["Academics", "Administration", "Accounts", "Examination", "Admissions",
                                  "Library", "Transport", "Hostel", "IT", "Sports", "Counseling", "Maintenance"]),
    "enrollment_status": ("Enrollment Status", ["Enrolled", "Promoted", "Graduated", "Transferred", "Dropped"]),
    "lead_source": ("Lead Source", ["Website", "Walk-in", "Referral", "Advertisement", "Social Media"]),
    "lead_stage": ("Lead Stage", ["Inquiry", "Counseling", "Entrance Test", "Document Collection", "Approved", "Enrolled", "Rejected"]),
    "document_category": ("Document Category", ["Birth Certificate", "Transfer Certificate", "Photo", "ID Proof", "Report Card"]),
    "active_status": ("Active Status", ["Active", "Inactive"]),
    "hostel_block_type": ("Hostel Block Type", ["Boys", "Girls", "Co-ed"]),
    "book_category": ("Book Category", ["Fiction", "Non-Fiction", "Reference", "Textbook", "Periodical"]),
    "book_issue_status": ("Book Issue Status", ["Issued", "Returned", "Overdue", "Lost"]),
    "hostel_allocation_status": ("Hostel Allocation Status", ["Allocated", "Vacated"]),
    "leave_status": ("Leave Status", ["Applied", "Approved", "Rejected", "Cancelled"]),
    "homework_status": ("Homework Status", ["Assigned", "Closed"]),
    "submission_status": ("Submission Status", ["Submitted", "Graded", "Late", "Missing"]),
    "lesson_plan_status": ("Lesson Plan Status", ["Planned", "In Progress", "Completed"]),
    "curriculum_plan_status": ("Curriculum Plan Status", ["Draft", "Submitted", "Approved", "Rejected", "In Progress", "Completed"]),
    "curriculum_term": ("Curriculum Term", ["Quarter 1", "Quarter 2", "Quarter 3", "Quarter 4"]),
    "day_of_week": ("Day of Week", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]),
    "account_type": ("Account Type", ["Asset", "Liability", "Income", "Expense", "Equity"]),
    "expense_status": ("Expense Status", ["Pending", "Approved", "Rejected", "Paid"]),
    "po_status": ("PO Status", ["Draft", "Ordered", "Received", "Cancelled"]),
    "movement_type": ("Stock Movement Type", ["In", "Out"]),
    "activity_type": ("Activity Type", ["Club", "Sport", "Competition", "Camp", "Cultural"]),
    "registration_status": ("Registration Status", ["Registered", "Cancelled", "Attended"]),
    "meal_type": ("Meal Type", ["Breakfast", "Lunch", "Snacks", "Dinner"]),
    "audience": ("Audience", ["All", "Students", "Parents", "Teachers", "Staff"]),
    "comm_channel": ("Communication Channel", ["In App", "Email", "SMS", "WhatsApp", "Push"]),
    "announcement_status": ("Announcement Status", ["Draft", "Published", "Archived"]),
    "cms_page_type": ("CMS Page Type", ["Page", "News", "Event", "Blog"]),
    "resource_type": ("Resource Type", ["Document", "Video", "Ebook", "Notes", "Recording", "Link"]),
    "question_type": ("Question Type", ["MCQ", "Short", "Long", "True/False", "Fill in the Blank"]),
    "difficulty": ("Difficulty", ["Easy", "Medium", "Hard"]),
    "meeting_mode": ("Meeting Mode", ["In Person", "Online"]),
    "meeting_status": ("Meeting Status", ["Scheduled", "Completed", "Cancelled", "No Show"]),
    "academic_result": ("Academic Result", ["Promoted", "Passed", "Failed", "Detained"]),
    "achievement_category": ("Achievement Category", ["Academic", "Sports", "Cultural", "Arts", "Leadership", "Other"]),
    "achievement_level": ("Achievement Level", ["School", "District", "State", "National", "International"]),
    "discipline_severity": ("Discipline Severity", ["Minor", "Major", "Severe"]),
    "discipline_status": ("Discipline Status", ["Open", "Closed"]),
    "remark_type": ("Remark Type", ["General", "Special", "Health", "Counseling", "Appreciation"]),
    "nationality": ("Nationality", ["Indian", "Other"]),
    "government_id_type": ("Government ID Type", ["Aadhaar", "PAN", "Passport", "Voter ID", "Other"]),
    "asset_assignee_type": ("Asset Assignee Type", ["Student", "Employee", "Location"]),
    "asset_assignment_status": ("Asset Assignment Status", ["Issued", "Returned", "Lost", "Damaged"]),
    "exam_schedule_status": ("Exam Schedule Status", ["Scheduled", "Completed", "Cancelled"]),
    "marks_batch_status": ("Marks Batch Status", ["Draft", "Submitted", "Approved", "Rejected", "Published"]),
}

# Typed module pages handled by dedicated React screens (slug -> path).
CORE_NAV = [
    ("Dashboard", "grid", "/dashboard", None, None, 1),
    ("Admissions", "user-plus", "/admissions", "admissions_crm", "admissions_crm:read", 10),
    ("Students", "users", "/students", "student_information_system", "student_information_system:read", 11),
    ("Parent Portal", "users", "/parent-portal", "parent_guardian_portal", "parent_guardian_portal:read", 11),
    ("Academic Setup", "book", "/academic", "academic_configuration", "academic_configuration:read", 12),
    ("Employees / HR", "briefcase", "/employees", "employee_hrms", "employee_hrms:read", 13),
    ("Fees & Billing", "credit-card", "/fees", "fees_billing", "fees_billing:read", 14),
    ("Attendance", "check-square", "/attendance", "attendance", "attendance:read", 15),
    ("Examinations", "edit", "/exams", "examination_management", "examination_management:read", 16),
    ("Promotion / Grade Upgrade", "trending-up", "/promotion", "report_cards_transcripts", "report_cards_transcripts:read", 17),
    ("Teacher Allocation", "users", "/teacher-allocation", "teacher_management", "teacher_management:read", 13),
    ("Library", "book", "/library", "library_management", "library_management:read", 18),
    ("HR Operations", "briefcase", "/hr", "employee_hrms", "employee_hrms:read", 19),
    ("Hostel", "grid", "/hostel", "hostel", "hostel:read", 20),
    ("Homework", "edit", "/homework", "homework_assignments", "homework_assignments:read", 21),
    ("Activities", "trending-up", "/activities", "activities_events", "activities_events:read", 22),
    ("Finance", "credit-card", "/finance", "finance_accounting", "finance_accounting:read", 23),
    ("Store / Inventory", "table", "/store", "finance_accounting", "finance_accounting:read", 24),
    ("Asset Tracking", "briefcase", "/asset-tracking", "finance_accounting", "finance_accounting:read", 24),
    ("Communication", "activity", "/communication", "ptm_communication", "ptm_communication:read", 25),
    ("Transport", "trending-up", "/transport", "transport", "transport:read", 26),
    ("Timetable", "grid", "/timetable", "timetable_scheduling", "timetable_scheduling:read", 27),
    ("Curriculum", "book", "/curriculum", "curriculum_lesson_planning", "curriculum_lesson_planning:read", 28),
    ("Question Bank", "edit", "/question-bank", "question_paper_management", "question_paper_management:read", 29),
    ("Meals & Cafeteria", "check-square", "/meals", "meal_cafeteria", "meal_cafeteria:read", 30),
    ("Knowledge & Library", "book", "/knowledge", "knowledge_base", "knowledge_base:read", 31),
    ("Website & CMS", "grid", "/cms", "public_website_cms", "public_website_cms:read", 32),
    ("Reports", "activity", "/reports", "dashboards_analytics", "dashboards_analytics:read", 80),
    ("Masters", "sliders", "/masters", "academic_configuration", "academic_configuration:read", 90),
    ("Customize Fields", "edit", "/customize-fields", "academic_configuration", "academic_configuration:read", 88),
    ("Branding", "grid", "/branding", "security_compliance", "security_compliance:read", 89),
    ("Integrations", "cube", "/integrations", "integrations", "integrations:read", 93),
    ("Users & Roles", "shield", "/users", "security_compliance", "security_compliance:read", 91),
    ("Audit Log", "activity", "/audit", "security_compliance", "security_compliance:read", 92),
]


async def get_or_create(db: AsyncSession, model, defaults: dict | None = None, **filters):
    stmt = select(model).filter_by(**filters)
    obj = (await db.execute(stmt)).scalars().first()
    if obj:
        return obj, False
    params = {**filters, **(defaults or {})}
    obj = model(**params)
    db.add(obj)
    await db.flush()
    return obj, True


async def ensure_runtime_schema(db: AsyncSession) -> None:
    """Idempotent column upgrades for existing PostgreSQL dev databases."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    statements = [
        "ALTER TABLE student ADD COLUMN IF NOT EXISTS permanent_address TEXT",
        "ALTER TABLE student ADD COLUMN IF NOT EXISTS government_id_type VARCHAR(40)",
        "ALTER TABLE student ADD COLUMN IF NOT EXISTS government_id_number VARCHAR(80)",
        "ALTER TABLE student ADD COLUMN IF NOT EXISTS emergency_contact_name VARCHAR(150)",
        "ALTER TABLE student ADD COLUMN IF NOT EXISTS emergency_contact_phone VARCHAR(32)",
        "ALTER TABLE guardian ADD COLUMN IF NOT EXISTS address TEXT",
        "ALTER TABLE guardian ADD COLUMN IF NOT EXISTS government_id_type VARCHAR(40)",
        "ALTER TABLE guardian ADD COLUMN IF NOT EXISTS government_id_number VARCHAR(80)",
        "ALTER TABLE employee ADD COLUMN IF NOT EXISTS address TEXT",
        "ALTER TABLE employee ADD COLUMN IF NOT EXISTS government_id_type VARCHAR(40)",
        "ALTER TABLE employee ADD COLUMN IF NOT EXISTS government_id_number VARCHAR(80)",
        "ALTER TABLE exam ADD COLUMN IF NOT EXISTS weightage_percent NUMERIC(5,2) NOT NULL DEFAULT 100",
        "ALTER TABLE exam ADD COLUMN IF NOT EXISTS is_final_exam BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE exam ADD COLUMN IF NOT EXISTS overall_pass_percentage NUMERIC(5,2) NOT NULL DEFAULT 40",
        "ALTER TABLE exam ADD COLUMN IF NOT EXISTS require_subject_pass BOOLEAN NOT NULL DEFAULT TRUE",
    ]
    for stmt in statements:
        await db.execute(text(stmt))


async def seed() -> None:
    await init_models()
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    async with AsyncSessionLocal() as db:
        await ensure_runtime_schema(db)
        # ---------------------------------------------------------------- tenant
        tenant, _ = await get_or_create(
            db, Tenant, code="SUMAYA",
            defaults={"name": "Sumaya Group of Institutions", "plan": "enterprise"},
        )
        tid = tenant.id

        institution, _ = await get_or_create(
            db, Institution, tenant_id=tid, code="SUMAYA-MAIN",
            defaults={"name": "Sumaya International School", "type": "school", "board": "CBSE"},
        )

        # ---------------------------------------------------------------- modules + capabilities
        module_by_slug: dict[str, Module] = {}
        for i, m in enumerate(spec["modules"]):
            mod, _ = await get_or_create(
                db, Module, tenant_id=tid, slug=m["slug"],
                defaults={
                    "code": m["id"], "name": m["name"], "description": m.get("description"),
                    "priority": m.get("priority"), "release_bucket": m.get("bucket"),
                    "sort_order": i + 1,
                },
            )
            module_by_slug[m["slug"]] = mod

        module_by_name = {mo.name: mo for mo in module_by_slug.values()}
        for module_name, caps in spec["module_capabilities"].items():
            mod = module_by_name.get(module_name)
            if not mod:
                continue
            for cap in caps[:40]:  # cap to keep seed lean
                await get_or_create(
                    db, ModuleCapability, tenant_id=tid, module_id=mod.id, slug=cap["slug"],
                    defaults={"name": cap["capability"], "persona": cap.get("persona"),
                              "priority": cap.get("priority")},
                )

        # ---------------------------------------------------------------- permissions
        perm_by_code: dict[str, Permission] = {}
        for slug, mod in module_by_slug.items():
            for action in ACTIONS:
                code = f"{slug}:{action}"
                perm, _ = await get_or_create(
                    db, Permission, code=code,
                    defaults={"module": slug, "action": action,
                              "description": f"{action.title()} on {mod.name}"},
                )
                perm_by_code[code] = perm

        # ---------------------------------------------------------------- roles + RBAC
        role_by_code: dict[str, Role] = {}
        for rname in spec["roles"]:
            rc = role_code(rname)
            role, _ = await get_or_create(
                db, Role, tenant_id=tid, code=rc,
                defaults={"name": rname, "is_system": True,
                          "description": f"{rname} system role"},
            )
            role_by_code[rc] = role

        # Apply RBAC matrix: a role allowed on a module gets all CRUD actions there.
        rbac = spec["rbac"]  # {module_name: [role names allowed]}
        name_to_slug = {m["name"]: m["slug"] for m in spec["modules"]}
        for module_name, allowed_roles in rbac.items():
            slug = name_to_slug.get(module_name)
            if not slug:
                continue
            for rname in allowed_roles:
                role = role_by_code.get(role_code(rname))
                if not role:
                    continue
                for action in ACTIONS:
                    perm = perm_by_code.get(f"{slug}:{action}")
                    if perm:
                        await get_or_create(db, RolePermission, role_id=role.id, permission_id=perm.id)

        # ---------------------------------------------------------------- admin user (superadmin)
        admin_email = settings.SEED_ADMIN_EMAIL
        admin = (await db.execute(select(User).where(User.email == admin_email))).scalars().first()
        if not admin:
            admin = User(
                tenant_id=tid, email=admin_email, full_name="System Administrator",
                hashed_password=hash_password(settings.SEED_ADMIN_PASSWORD),
                is_active=True, is_superadmin=True,
            )
            db.add(admin)
            await db.flush()
            sa = role_by_code.get("super_admin")
            if sa:
                await get_or_create(db, UserRole, user_id=admin.id, role_id=sa.id)
        else:
            # Keep the documented bootstrap login usable on existing local databases.
            admin.hashed_password = hash_password(settings.SEED_ADMIN_PASSWORD)
            admin.is_active = True
            admin.is_superadmin = True

        # ---------------------------------------------------------------- masters
        for code, (name, values) in MASTERS.items():
            mt, _ = await get_or_create(
                db, MasterType, tenant_id=tid, code=code,
                defaults={"name": name, "is_system": True},
            )
            for idx, val in enumerate(values):
                await get_or_create(
                    db, MasterValue, tenant_id=tid, master_type_id=mt.id,
                    code=val.lower().replace(" ", "_"),
                    defaults={"label": val, "sort_order": idx + 1},
                )

        # ---------------------------------------------------------------- entity defs (typed)
        for ent_name, (slug, table, kind) in TYPED_ENTITIES.items():
            mod = module_by_slug.get(slug)
            if not mod:
                continue
            ent_slug = table.replace("_", "-")
            ent, created = await get_or_create(
                db, EntityDef, tenant_id=tid, slug=ent_slug,
                defaults={"module_id": mod.id, "name": ent_name, "kind": kind,
                          "is_typed": True, "typed_table": table},
            )
            if not created:
                ent.module_id = mod.id
                ent.kind = kind
                ent.is_typed = True
                ent.typed_table = table
            existing_fields = {
                f.name: f for f in (
                    await db.execute(select(FieldDef).where(FieldDef.entity_id == ent.id))
                ).scalars().all()
            }
            for order, fd in enumerate(TYPED_FIELDS.get(table, [])):
                n, label, dtype, req, lv, opt, ref = fd
                field = existing_fields.get(n)
                if field:
                    field.label = label
                    field.data_type = dtype
                    field.is_required = req
                    field.is_list_visible = lv
                    field.options_master = opt
                    field.reference_entity = ref
                    field.sort_order = order + 1
                    continue
                db.add(FieldDef(
                    tenant_id=tid, entity_id=ent.id, name=n, label=label, data_type=dtype,
                    is_required=req, is_list_visible=lv, options_master=opt, reference_entity=ref,
                    sort_order=order + 1,
                ))

        # ---------------------------------------------------------------- entity defs (generic / metadata)
        DEFAULT_FIELDS = [
            ("name", "Name", "string", True, True, None),
            ("code", "Code", "string", False, True, None),
            ("description", "Description", "text", False, False, None),
            ("status", "Status", "string", False, True, None),
        ]
        for me in spec["meta_entities"]:
            name = me["entity"]
            mod = next((mo for mo in module_by_slug.values() if mo.name == me["module"]), None)
            if not mod:
                mod = module_by_slug.get("administration_workflow")
            ent_slug = name.lower()
            ent, created = await get_or_create(
                db, EntityDef, tenant_id=tid, slug=ent_slug,
                defaults={"module_id": mod.id, "name": name, "kind": "master",
                          "is_typed": False, "purpose": me.get("purpose")},
            )
            if created:
                for order, fd in enumerate(DEFAULT_FIELDS):
                    n, label, dtype, req, lv, opt = fd
                    db.add(FieldDef(tenant_id=tid, entity_id=ent.id, name=n, label=label,
                                    data_type=dtype, is_required=req, is_list_visible=lv, sort_order=order + 1))

        # ---------------------------------------------------------------- entity defs (domain registry / typed workflows)
        from app.domain import DOMAIN_SPECS

        for spec in DOMAIN_SPECS:
            mod = module_by_slug.get(spec.module_slug)
            if not mod:
                continue
            ent, created = await get_or_create(
                db, EntityDef, tenant_id=tid, slug=spec.slug,
                defaults={"module_id": mod.id, "name": spec.name, "kind": spec.kind,
                          "is_typed": True, "typed_table": spec.model.__tablename__, "icon": spec.icon},
            )
            if not created:
                # Ensure pre-existing rows are flagged typed (idempotent upgrades).
                ent.is_typed = True
                ent.typed_table = spec.model.__tablename__
                ent.module_id = mod.id
                ent.kind = spec.kind
            existing_fields = {
                f.name for f in (
                    await db.execute(select(FieldDef).where(FieldDef.entity_id == ent.id))
                ).scalars().all()
            }
            for order, fs in enumerate(spec.fields):
                if fs.name in existing_fields:
                    continue
                db.add(FieldDef(
                    tenant_id=tid, entity_id=ent.id, name=fs.name, label=fs.label, data_type=fs.type,
                    is_required=fs.required, is_list_visible=fs.list_visible, options_master=fs.options_master,
                    reference_entity=fs.reference_entity, help_text=fs.help_text, sort_order=order + 1,
                ))

        await db.flush()

        # Prune placeholder/duplicate metadata entities created from the spec's
        # (column-shifted) rows so module tabs only show meaningful entities:
        #  * "*Config" placeholder rows
        #  * metadata entities that duplicate a typed entity (e.g. "LibraryBook"
        #    vs typed "Library Book") — often misfiled under the wrong module
        all_ents = (
            await db.execute(
                select(EntityDef).where(EntityDef.tenant_id == tid, EntityDef.is_deleted.is_(False))
            )
        ).scalars().all()

        def _norm(s: str) -> str:
            return "".join(ch for ch in s.lower() if ch.isalnum())

        typed_names = {_norm(e.name) for e in all_ents if e.is_typed}
        for e in all_ents:
            if e.is_typed:
                continue
            if e.name.endswith("Config") or _norm(e.name) in typed_names:
                e.is_deleted = True
        await db.flush()

        # ---------------------------------------------------------------- catch-all & cleanup
        # A module only needs a generic "<Module> Record" entity when it has NO real
        # (typed or metadata) entity. Drop stale catch-alls for modules that now have
        # proper typed entities so the module tabs aren't cluttered.
        for slug, mod in module_by_slug.items():
            ents = (
                await db.execute(
                    select(EntityDef).where(EntityDef.module_id == mod.id, EntityDef.is_deleted.is_(False))
                )
            ).scalars().all()
            real = [e for e in ents if e.slug != f"{slug}-record"]
            catchall = next((e for e in ents if e.slug == f"{slug}-record"), None)
            if real and catchall:
                catchall.is_deleted = True  # superseded by typed/metadata entities
            elif not real and not catchall:
                ent = EntityDef(
                    tenant_id=tid, module_id=mod.id, slug=f"{slug}-record",
                    name=f"{mod.name} Record", kind="transaction", is_typed=False, purpose=mod.description,
                )
                db.add(ent)
                await db.flush()
                for order, fd in enumerate(DEFAULT_FIELDS):
                    n, label, dtype, req, lv, opt = fd
                    db.add(FieldDef(tenant_id=tid, entity_id=ent.id, name=n, label=label,
                                    data_type=dtype, is_required=req, is_list_visible=lv, sort_order=order + 1))

        # ---------------------------------------------------------------- navigation
        for label, icon, path, mslug, perm, order in CORE_NAV:
            await get_or_create(
                db, MenuItem, tenant_id=tid, path=path,
                defaults={"label": label, "icon": icon, "module_slug": mslug,
                          "permission_code": perm, "sort_order": order},
            )
        # Modules with dedicated workflow screens must not also appear as a second,
        # generic CRUD module. Keeping both made completed work look detached from
        # the base ERP.
        dedicated_modules = {
            "public_website_cms", "admissions_crm", "student_information_system",
            "parent_guardian_portal", "teacher_management", "employee_hrms",
            "academic_configuration", "curriculum_lesson_planning",
            "timetable_scheduling", "attendance", "homework_assignments",
            "examination_management", "question_paper_management",
            "report_cards_transcripts", "library_management",
            "digital_learning_repository", "fees_billing", "finance_accounting",
            "meal_cafeteria", "transport", "hostel", "activities_events",
            "ptm_communication", "knowledge_base", "dashboards_analytics",
            "security_compliance", "integrations",
        }
        # One catch-all nav entry per remaining module -> generic module page.
        for i, (slug, mod) in enumerate(module_by_slug.items()):
            path = f"/m/{slug}"
            item, _ = await get_or_create(
                db, MenuItem, tenant_id=tid, path=path,
                defaults={"label": mod.name, "icon": mod.icon, "module_slug": slug,
                          "permission_code": f"{slug}:read", "sort_order": 200 + i},
            )
            item.is_enabled = slug not in dedicated_modules

        # ---------------------------------------------------------------- settings
        _logo = (
            "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
            "%3Crect width='64' height='64' rx='14' fill='%232563eb'/%3E"
            "%3Cpath d='M32 16 8 26l24 10 24-10z' fill='white'/%3E"
            "%3Cpath d='M18 33v9c0 4 28 4 28 0v-9' fill='none' stroke='white' stroke-width='3'/%3E%3C/svg%3E"
        )
        for key, value in {
            "general.institution_name": "Sumaya International School",
            "general.academic_board": "CBSE",
            "fees.currency": "INR",
            "fees.late_fee_percent": 2,
            "attendance.methods_enabled": ["manual", "qr", "rfid", "biometric"],
            "branding.institution_name": "Sumaya International School",
            "branding.logo_url": _logo,
            "branding.tagline": "Excellence in Education",
            "branding.primary_color": "#2563eb",
        }.items():
            await get_or_create(
                db, Setting, tenant_id=tid, key=key,
                defaults={"value_json": {"value": value}, "data_type": "json"},
            )

        await db.commit()

        # ---------------------------------------------------------------- demo operational data
        await _seed_demo(db, tid)
        await db.commit()

    print("\n[OK] Seed complete.")
    print(f"     Login: {settings.SEED_ADMIN_EMAIL} / {settings.SEED_ADMIN_PASSWORD}")


async def _seed_demo(db: AsyncSession, tid: uuid.UUID) -> None:
    """Demo academic config + students + fees + attendance so dashboards are populated."""
    ay, _ = await get_or_create(
        db, AcademicYear, tenant_id=tid, code="2025-26",
        defaults={"name": "2025-2026", "is_current": True,
                  "start_date": date(2025, 4, 1), "end_date": date(2026, 3, 31)},
    )

    grades: list[Grade] = []
    for seq, gname in enumerate(["Nursery", "LKG", "UKG", "Grade 1", "Grade 2", "Grade 3",
                                 "Grade 4", "Grade 5", "Grade 6", "Grade 7", "Grade 8"], start=1):
        g, _ = await get_or_create(
            db, Grade, tenant_id=tid, code=f"G{seq:02d}",
            defaults={"name": gname, "sequence": seq},
        )
        grades.append(g)

    sections: list[Section] = []
    for g in grades[:5]:
        for sec in ["A", "B"]:
            s, _ = await get_or_create(
                db, Section, tenant_id=tid, grade_id=g.id, name=sec,
                defaults={"capacity": 40},
            )
            sections.append(s)

    for sub in ["English", "Mathematics", "Science", "Social Studies", "Hindi", "Computer Science"]:
        await get_or_create(db, Subject, tenant_id=tid, code=sub[:3].upper(), defaults={"name": sub})

    # Fee plan
    fee_plan, _ = await get_or_create(
        db, FeePlan, tenant_id=tid, code="FP-ANNUAL-2526",
        defaults={"name": "Annual Fee 2025-26", "frequency": "annual",
                  "amount": Decimal("60000"), "academic_year_id": ay.id},
    )

    # Employees — designation/department/staff_role carry master CODES (see MASTERS)
    _staff = [
        ("Anita Sharma", "principal", "management", "administration"),
        ("Rahul Verma", "teacher", "teacher", "academics"),
        ("Sneha Iyer", "accountant", "accountant", "accounts"),
        ("Imran Khan", "teacher", "teacher", "academics"),
        ("Meera Nair", "librarian", "librarian", "library"),
        ("Vikram Rao", "office_clerk", "admin_staff", "administration"),
    ]
    for i, (fn, desig, role, dept) in enumerate(_staff, start=1):
        await get_or_create(
            db, Employee, tenant_id=tid, employee_no=f"EMP{i:04d}",
            defaults={"first_name": fn.split()[0], "last_name": fn.split()[1],
                      "designation": desig, "department": dept, "staff_role": role,
                      "date_of_joining": date(2024, 6, 1), "salary": Decimal("45000")},
        )

    # Students + invoices + attendance
    demo_students = [
        ("Aarav", "Gupta", "Male"), ("Diya", "Singh", "Female"), ("Vihaan", "Patel", "Male"),
        ("Ananya", "Reddy", "Female"), ("Kabir", "Nair", "Male"), ("Ishita", "Joshi", "Female"),
        ("Arjun", "Mehta", "Male"), ("Saanvi", "Rao", "Female"),
    ]
    for i, (fn, ln, gender) in enumerate(demo_students, start=1):
        grade = grades[(i - 1) % len(grades[:5])]
        section = next((s for s in sections if s.grade_id == grade.id), None)
        st, created = await get_or_create(
            db, Student, tenant_id=tid, admission_no=f"ADM{2025}{i:04d}",
            defaults={"first_name": fn, "last_name": ln, "gender": gender,
                      "grade_id": grade.id, "section_id": section.id if section else None,
                      "academic_year_id": ay.id, "roll_no": str(i),
                      "enrollment_status": "enrolled"},
        )
        if created:
            inv, _ = await get_or_create(
                db, Invoice, tenant_id=tid, invoice_no=f"INV-2526-{i:04d}",
                defaults={"student_id": st.id, "fee_plan_id": fee_plan.id, "academic_year_id": ay.id,
                          "issue_date": date(2025, 4, 5), "due_date": date(2025, 5, 5),
                          "gross_amount": Decimal("60000"), "net_amount": Decimal("60000"),
                          "payment_status": "unpaid"},
            )
            # Mark some present today
            await get_or_create(
                db, Attendance, tenant_id=tid, person_type="student", person_id=st.id, att_date=date.today(),
                defaults={"student_id": st.id, "section_id": section.id if section else None,
                          "state": "present" if i % 4 else "absent", "method": "manual"},
            )

    # Keep every configured class/section testable with a small but meaningful roster.
    roster_names = [
        ("Advait", "Kapoor", "Male"),
        ("Myra", "Menon", "Female"),
        ("Reyansh", "Das", "Male"),
    ]
    for section_index, section in enumerate(sections, start=1):
        for student_index, (fn, ln, gender) in enumerate(roster_names, start=1):
            await get_or_create(
                db,
                Student,
                tenant_id=tid,
                admission_no=f"DEMO-{section_index:02d}-{student_index:02d}",
                defaults={
                    "first_name": fn,
                    "last_name": f"{ln} {section.name}",
                    "gender": gender,
                    "grade_id": section.grade_id,
                    "section_id": section.id,
                    "academic_year_id": ay.id,
                    "roll_no": str(10 + student_index),
                    "enrollment_status": "enrolled",
                },
            )

    # Demo staff attendance for today (mirrors the student flow)
    for j, emp in enumerate((await db.execute(select(Employee).where(
        Employee.tenant_id == tid, Employee.is_deleted.is_(False)
    ).order_by(Employee.employee_no))).scalars().all()):
        await get_or_create(
            db, Attendance, tenant_id=tid, person_type="employee", person_id=emp.id, att_date=date.today(),
            defaults={"state": "present" if j % 5 else "leave", "method": "biometric"},
        )

    # Demo exam
    await get_or_create(
        db, Exam, tenant_id=tid, code="UT1-2526",
        defaults={"name": "Unit Test 1", "exam_type": "unit_test", "academic_year_id": ay.id,
                  "max_marks": Decimal("100"), "pass_marks": Decimal("40")},
    )

    # Admissions pipeline demo leads
    for i, (nm, stage) in enumerate(
        [("Rohan Malhotra", "inquiry"), ("Tara Bhatt", "counseling"),
         ("Zoya Sheikh", "entrance_test"), ("Dev Anand", "approved")], start=1
    ):
        await get_or_create(
            db, AdmissionLead, tenant_id=tid, lead_no=f"LEAD-{i:04d}",
            defaults={"student_name": nm, "stage": stage, "source": "website",
                      "grade_applied_id": grades[0].id, "phone": f"90000000{i:02d}"},
        )

    # Library catalog
    for i, (title, author, cat) in enumerate([
        ("Introduction to Algorithms", "Cormen", "Reference"),
        ("Wings of Fire", "A.P.J. Abdul Kalam", "Non-Fiction"),
        ("NCERT Mathematics VIII", "NCERT", "Textbook"),
        ("Harry Potter", "J.K. Rowling", "Fiction"),
    ], start=1):
        await get_or_create(
            db, LibraryBook, tenant_id=tid, isbn=f"ISBN-{1000 + i}",
            defaults={"title": title, "author": author, "category": cat,
                      "total_copies": 5, "available_copies": 5, "shelf": f"S{i}"},
        )

    # Transport
    route, _ = await get_or_create(
        db, TransportRoute, tenant_id=tid, code="R1",
        defaults={"name": "Route 1 - City Center", "start_point": "Campus", "end_point": "City Center",
                  "fare": Decimal("1500")},
    )
    await get_or_create(
        db, Vehicle, tenant_id=tid, registration_no="KA01AB1234",
        defaults={"model": "Tata Bus 40", "capacity": 40, "driver_name": "Ramesh",
                  "driver_phone": "9876500001", "route_id": route.id},
    )

    # Hostel
    block, _ = await get_or_create(
        db, HostelBlock, tenant_id=tid, code="HB-A",
        defaults={"name": "Block A", "block_type": "boys", "warden_name": "Mr. Suresh"},
    )
    for rn in ["101", "102", "103"]:
        await get_or_create(
            db, HostelRoom, tenant_id=tid, block_id=block.id, room_no=rn,
            defaults={"capacity": 3, "occupied": 0, "room_type": "triple"},
        )

    # HR leave types
    for nm, code, days in [("Casual Leave", "CL", 12), ("Sick Leave", "SL", 10), ("Earned Leave", "EL", 15)]:
        await get_or_create(
            db, LeaveType, tenant_id=tid, code=code,
            defaults={"name": nm, "max_days_per_year": days, "is_paid": True},
        )

    # ---- Richer data for portals: guardian, marks, a published announcement ----
    from app.models import Announcement, Guardian, Marks

    first_student = (
        await db.execute(select(Student).where(Student.tenant_id == tid, Student.admission_no == "ADM20250001"))
    ).scalars().first()
    exam = (await db.execute(select(Exam).where(Exam.tenant_id == tid, Exam.code == "UT1-2526"))).scalars().first()
    subs = (await db.execute(select(Subject).where(Subject.tenant_id == tid).limit(3))).scalars().all()
    if first_student:
        await get_or_create(
            db, Guardian, tenant_id=tid, student_id=first_student.id, relation="father",
            defaults={"full_name": "Rakesh Gupta", "phone": "9810000001",
                      "email": "rakesh@example.com", "is_primary": True},
        )
        grade_id = first_student.grade_id
        section_id = first_student.section_id
        for j, sub in enumerate(subs[:3], start=1):
            await get_or_create(
                db, TimetablePeriod, tenant_id=tid, grade_id=grade_id, section_id=section_id,
                day_of_week=["Monday", "Tuesday", "Wednesday"][j - 1], period_no=j,
                defaults={
                    "subject_id": sub.id,
                    "start_time": time(8 + j, 0),
                    "end_time": time(8 + j, 45),
                    "room": f"G1-{j}",
                },
            )
        for j, sub in enumerate(subs[:2], start=1):
            hw, _ = await get_or_create(
                db, Homework, tenant_id=tid, title=f"{sub.name} practice set {j}",
                defaults={
                    "grade_id": grade_id,
                    "section_id": section_id,
                    "subject_id": sub.id,
                    "assigned_date": date.today(),
                    "due_date": date(2026, 7, 15 + j),
                    "description": f"Complete the workbook exercise and submit your answer notes for {sub.name}.",
                    "max_marks": Decimal("10"),
                    "homework_status": "assigned",
                },
            )
            if j == 1:
                await get_or_create(
                    db, HomeworkSubmission, tenant_id=tid, homework_id=hw.id, student_id=first_student.id,
                    defaults={
                        "submitted_date": date.today(),
                        "content": "Completed and uploaded through the student portal.",
                        "submission_status": "submitted",
                    },
                )
        for code, name, kind, fee, cap in [
            ("ACT-ROB", "Robotics Club", "club", Decimal("2500"), 30),
            ("ACT-FOOT", "Inter-house Football", "sport", Decimal("0"), 22),
            ("ACT-MUN", "Model United Nations", "competition", Decimal("1500"), 40),
        ]:
            await get_or_create(
                db, Activity, tenant_id=tid, code=code,
                defaults={
                    "name": name,
                    "activity_type": kind,
                    "coordinator": "Rahul Verma",
                    "start_date": date(2026, 8, 1),
                    "fee": fee,
                    "capacity": cap,
                },
            )
        if exam:
            for j, sub in enumerate(subs):
                await get_or_create(
                    db, Marks, tenant_id=tid, exam_id=exam.id, student_id=first_student.id, subject_id=sub.id,
                    defaults={"marks_obtained": Decimal(str(72 + j * 6)), "max_marks": Decimal("100"),
                              "grade_letter": "B+"},
                )
                await get_or_create(
                    db, ExamSubject, tenant_id=tid, exam_id=exam.id, subject_id=sub.id,
                    grade_id=first_student.grade_id, section_id=first_student.section_id,
                    defaults={"exam_date": date(2026, 9, 10 + j), "max_marks": Decimal("100"),
                              "pass_marks": Decimal("40"), "schedule_status": "scheduled"},
                )
                await get_or_create(
                    db, MarksBatch, tenant_id=tid, exam_id=exam.id, subject_id=sub.id,
                    grade_id=first_student.grade_id, section_id=first_student.section_id,
                    defaults={"batch_status": "published", "submitted_at": datetime.now(timezone.utc),
                              "reviewed_at": datetime.now(timezone.utc), "published_at": datetime.now(timezone.utc),
                              "review_note": "Demo marks approved and published."},
                )

        # Enrich the demo student's full profile
        first_student.admission_date = date(2023, 4, 1)
        first_student.category = "general"
        first_student.religion = "hindu"
        first_student.nationality = "indian"
        first_student.mother_tongue = "Hindi"
        first_student.government_id_type = "aadhaar"
        first_student.government_id_number = "123412341234"
        first_student.emergency_contact_name = "Rakesh Gupta"
        first_student.emergency_contact_phone = "9810000001"
        first_student.house = "Blue House"
        first_student.address = "12, Rose Lane, Sector 4"
        first_student.city = "Bengaluru"
        first_student.state = "Karnataka"
        first_student.pincode = "560001"

        from app.models import (
            Achievement,
            DisciplinaryAction,
            StudentAcademicHistory,
            StudentRemark,
        )

        for yr, gr, res, pct in [("2023-2024", "LKG", "promoted", "88.50"),
                                 ("2024-2025", "UKG", "promoted", "91.20")]:
            await get_or_create(
                db, StudentAcademicHistory, tenant_id=tid, student_id=first_student.id, academic_year=yr,
                defaults={"grade": gr, "section": "A", "result": res, "percentage": Decimal(pct), "rank": 3},
            )
        await get_or_create(
            db, Achievement, tenant_id=tid, student_id=first_student.id, title="1st Prize - Inter-school Quiz",
            defaults={"category": "academic", "level": "district", "achieved_on": date(2025, 11, 20),
                      "description": "Won the district-level science quiz."},
        )
        await get_or_create(
            db, DisciplinaryAction, tenant_id=tid, student_id=first_student.id, incident_type="Late submission",
            defaults={"incident_date": date(2025, 9, 5), "severity": "minor",
                      "description": "Repeated late homework submission.", "action_taken": "Counseled",
                      "reported_by": "Rahul Verma", "status": "closed"},
        )
        await get_or_create(
            db, StudentRemark, tenant_id=tid, student_id=first_student.id,
            remark="Consistently helpful and disciplined; a class monitor candidate.",
            defaults={"remark_type": "appreciation", "remarked_by": "Anita Sharma (Principal)",
                      "remarked_on": date.today(), "is_visible_to_parent": True},
        )

        # A part-payment so the parent portal shows a receipt
        from app.models import Payment

        inv = (
            await db.execute(select(Invoice).where(Invoice.tenant_id == tid, Invoice.student_id == first_student.id))
        ).scalars().first()
        if inv and (inv.paid_amount or Decimal(0)) <= 0:
            pay, created = await get_or_create(
                db, Payment, tenant_id=tid, receipt_no="RCPT-000001",
                defaults={"invoice_id": inv.id, "student_id": first_student.id, "amount": Decimal("25000"),
                          "method": "upi", "reference": "UPI-DEMO-001", "paid_at": date.today()},
            )
            if created:
                inv.paid_amount = Decimal("25000")
                inv.payment_status = "partial"

        ball, _ = await get_or_create(
            db, InventoryItem, tenant_id=tid, code="SPORT-FOOTBALL-01",
            defaults={"name": "Football", "category": "Sports", "unit": "pcs",
                      "quantity_on_hand": 20, "reorder_level": 5, "unit_cost": Decimal("900")},
        )
        await get_or_create(
            db, AssetAssignment, tenant_id=tid, item_id=ball.id, student_id=first_student.id,
            assignee_type="student",
            defaults={"quantity": 1, "issue_date": date.today(), "due_date": date(2026, 8, 31),
                      "assignment_status": "issued", "remarks": "Issued for inter-house practice."},
        )
        first_book = (
            await db.execute(select(LibraryBook).where(LibraryBook.tenant_id == tid).order_by(LibraryBook.isbn))
        ).scalars().first()
        if first_book:
            await get_or_create(
                db, BookIssue, tenant_id=tid, book_id=first_book.id, student_id=first_student.id,
                defaults={"issue_date": date.today(), "due_date": date(2026, 7, 31),
                          "issue_status": "issued"},
            )

    await get_or_create(
        db, Announcement, tenant_id=tid, title="Annual Sports Day on the 15th",
        defaults={"audience": "all", "channel": "in_app", "announcement_status": "published",
                  "publish_date": date.today(), "body": "All students and parents are invited to attend."},
    )

    # ---- Public website / CMS content ----
    from app.models import Banner, CmsPage

    for i, (title, link) in enumerate([
        ("Admissions Open for 2026–27 — Apply Today!", "/apply/SUMAYA"),
        ("CBSE Board Results: 100% Pass, 40+ Distinctions", None),
    ]):
        await get_or_create(
            db, Banner, tenant_id=tid, title=title,
            defaults={"link_url": link, "sort_order": i, "is_active": True},
        )
    for title, slug, body in [
        ("About Us", "about-us",
         "Sumaya International School is a CBSE-affiliated institution committed to holistic "
         "education from Nursery to Grade 12. Our campus blends academic rigour with sports, "
         "arts and values-based learning, supported by experienced faculty and modern facilities."),
        ("Academics", "academics",
         "We follow the CBSE curriculum with a focus on conceptual learning, continuous assessment "
         "and individual mentoring. Streams offered at senior secondary include Science, Commerce and Humanities."),
        ("Facilities", "facilities",
         "Smart classrooms, science and computer labs, a 20,000-book library, sports grounds, "
         "music and art studios, transport across the city, and a hygienic cafeteria."),
        ("Contact", "contact",
         "Sumaya International School, 12 Campus Road, Bengaluru 560001. Phone: +91 80 1234 5678. "
         "Email: info@sumaya.edu. Office hours: Mon–Sat, 8:00 AM – 4:00 PM."),
    ]:
        await get_or_create(
            db, CmsPage, tenant_id=tid, slug=slug,
            defaults={"title": title, "page_type": "page", "body": body, "is_published": True,
                      "publish_date": date.today()},
        )
    for title, slug, ptype, body in [
        ("Annual Day 2026 Celebrated with Grandeur", "annual-day-2026", "news",
         "Students dazzled audiences with music, dance and drama at our Annual Day, graced by "
         "distinguished guests and proud parents."),
        ("Inter-school Science Fair — Our Students Win Gold", "science-fair-gold", "news",
         "Team Sumaya bagged first place at the district science fair with an innovative project "
         "on renewable energy."),
        ("Parent–Teacher Meeting on Saturday", "ptm-saturday", "event",
         "The next PTM is scheduled this Saturday from 9 AM. Please book your slot via the parent portal."),
    ]:
        await get_or_create(
            db, CmsPage, tenant_id=tid, slug=slug,
            defaults={"title": title, "page_type": ptype, "body": body, "is_published": True,
                      "publish_date": date.today()},
        )

    # ---- Portal demo users (one per persona) ----
    principal_emp = (
        await db.execute(select(Employee).where(
            Employee.tenant_id == tid, Employee.designation.ilike("%principal%")
        ).order_by(Employee.employee_no))
    ).scalars().first()
    teacher_emp = (
        await db.execute(select(Employee).where(
            Employee.tenant_id == tid, Employee.designation.ilike("%teacher%")
        ).order_by(Employee.employee_no))
    ).scalars().first()
    if teacher_emp:
        teacher_emp.address = teacher_emp.address or "Faculty Quarters, Sumaya Campus"
        teacher_emp.government_id_type = teacher_emp.government_id_type or "pan"
        teacher_emp.government_id_number = teacher_emp.government_id_number or "ABCDE1234F"
        await get_or_create(
            db, TeacherProfile, tenant_id=tid, employee_id=teacher_emp.id,
            defaults={"expertise": "Primary Mathematics, English literacy, activity-based learning",
                      "certifications": "B.Ed; CBSE Foundational Literacy Certification",
                      "subjects_can_teach": "English, Mathematics, Science",
                      "qualification": "M.A., B.Ed",
                      "reporting_manager_id": principal_emp.id if principal_emp else None},
        )
        assigned_subjects = (await db.execute(
            select(Subject).where(Subject.tenant_id == tid).order_by(Subject.name).limit(3)
        )).scalars().all()
        for sub in assigned_subjects:
            await get_or_create(
                db, TeacherAssignment, tenant_id=tid, employee_id=teacher_emp.id,
                grade_id=grades[0].id if grades else None,
                section_id=sections[0].id if sections else None,
                subject_id=sub.id,
                defaults={"academic_year_id": ay.id, "reporting_manager_id": principal_emp.id if principal_emp else None,
                          "effective_from": date(2026, 4, 1), "assignment_status": "active"},
            )

        # A clean annual assessment cycle for end-to-end marks and promotion testing.
        # No marks batches are created here, so teachers can enter every roster from scratch.
        cycle = [
            ("PT1-DEMO", "Periodic Test 1 - Editable", "unit_test", Decimal("20"), False, date(2026, 7, 20)),
            ("HY-DEMO", "Half Yearly Examination - Editable", "midterm", Decimal("30"), False, date(2026, 10, 12)),
            ("FINAL-DEMO", "Final Examination - Editable", "final", Decimal("50"), True, date(2027, 3, 1)),
        ]
        cycle_subjects = assigned_subjects
        for code, name, exam_type, weight, is_final, start_on in cycle:
            cycle_exam, _ = await get_or_create(
                db,
                Exam,
                tenant_id=tid,
                code=code,
                defaults={
                    "name": name,
                    "academic_year_id": ay.id,
                    "exam_type": exam_type,
                    "grade_id": grades[0].id,
                    "start_date": start_on,
                    "end_date": start_on,
                    "max_marks": Decimal("100"),
                    "pass_marks": Decimal("40"),
                    "weightage_percent": weight,
                    "is_final_exam": is_final,
                    "overall_pass_percentage": Decimal("40"),
                    "require_subject_pass": True,
                },
            )
            for offset, sub in enumerate(cycle_subjects):
                await get_or_create(
                    db,
                    ExamSubject,
                    tenant_id=tid,
                    exam_id=cycle_exam.id,
                    subject_id=sub.id,
                    grade_id=grades[0].id,
                    section_id=sections[0].id,
                    defaults={
                        "assigned_teacher_id": teacher_emp.id,
                        "exam_date": start_on.replace(day=min(start_on.day + offset, 28)),
                        "max_marks": Decimal("100"),
                        "pass_marks": Decimal("40"),
                        "schedule_status": "scheduled",
                    },
                )
        # Make this teacher the class teacher of the first section
        if sections:
            sections[0].class_teacher_id = teacher_emp.id

        # A submitted quarterly plan awaiting the principal's approval, plus an
        # approved one — so the teacher portal and the reviewer queue have data.
        _plan_subject = (await db.execute(select(Subject).where(Subject.tenant_id == tid).order_by(Subject.name))).scalars().first()
        if _plan_subject and grades and sections:
            await get_or_create(
                db, CurriculumPlan, tenant_id=tid, teacher_id=teacher_emp.id,
                term="Quarter 1", subject_id=_plan_subject.id, grade_id=grades[0].id, section_id=sections[0].id,
                defaults={
                    "title": f"{_plan_subject.name} — Quarter 1 Plan",
                    "academic_year_id": ay.id,
                    "reviewer_id": principal_emp.id if principal_emp else None,
                    "objectives": "Build number sense, reading fluency and observation skills through activity-based learning.",
                    "resources": "NCERT textbook, worksheets, manipulatives, classroom library.",
                    "topics": [
                        {"name": "Numbers up to 100", "weeks": "Week 1-2", "hours": 8, "status": "done"},
                        {"name": "Addition & Subtraction", "weeks": "Week 3-5", "hours": 12, "status": "in_progress"},
                        {"name": "Shapes & Patterns", "weeks": "Week 6-8", "hours": 10, "status": "pending"},
                    ],
                    "completion_percent": 33,
                    "plan_status": "submitted",
                    "submitted_at": datetime.now(timezone.utc),
                },
            )
            await get_or_create(
                db, CurriculumPlan, tenant_id=tid, teacher_id=teacher_emp.id,
                term="Quarter 2", subject_id=_plan_subject.id, grade_id=grades[0].id, section_id=sections[0].id,
                defaults={
                    "title": f"{_plan_subject.name} — Quarter 2 Plan",
                    "academic_year_id": ay.id,
                    "reviewer_id": principal_emp.id if principal_emp else None,
                    "objectives": "Extend operations to larger numbers and introduce measurement.",
                    "resources": "NCERT textbook, measuring tools.",
                    "topics": [
                        {"name": "Numbers up to 1000", "weeks": "Week 1-3", "hours": 12, "status": "pending"},
                        {"name": "Measurement: length & weight", "weeks": "Week 4-6", "hours": 10, "status": "pending"},
                    ],
                    "completion_percent": 0,
                    "plan_status": "approved",
                    "submitted_at": datetime.now(timezone.utc),
                    "reviewed_at": datetime.now(timezone.utc),
                    "review_note": "Well structured. Approved.",
                },
            )

        # A sample approved leave + payroll so the staff profile is populated
        from app.models import LeaveRequest, Payroll

        await get_or_create(
            db, LeaveRequest, tenant_id=tid, employee_id=teacher_emp.id, from_date=date(2026, 5, 4),
            defaults={"leave_type": "CL", "to_date": date(2026, 5, 5), "days": 2,
                      "reason": "Personal work", "request_status": "approved", "approver_id": principal_emp.id if principal_emp else None},
        )
        for mth in (4, 5):
            await get_or_create(
                db, Payroll, tenant_id=tid, employee_id=teacher_emp.id, month=mth, year=2026,
                defaults={"basic": Decimal("45000"), "allowances": Decimal("5000"), "deductions": Decimal("2000"),
                          "net_pay": Decimal("48000"), "payroll_status": "paid"},
            )
    roles = {
        c: (await db.execute(select(Role).where(Role.tenant_id == tid, Role.code == c))).scalars().first()
        for c in ("student", "parent", "teacher")
    }

    async def _portal_user(email, name, pw, role, person_type, person_id):
        u = (await db.execute(select(User).where(User.email == email))).scalars().first()
        if u:
            u.full_name = name
            u.person_type = person_type
            u.person_id = person_id
            return
        u = User(tenant_id=tid, email=email, full_name=name, hashed_password=hash_password(pw),
                 is_active=True, is_superadmin=False, person_type=person_type, person_id=person_id)
        db.add(u)
        await db.flush()
        if role:
            await get_or_create(db, UserRole, user_id=u.id, role_id=role.id)

    if first_student and roles["student"]:
        await _portal_user("student@sumaya.edu", "Aarav Gupta", "Student@123",
                           roles["student"], "student", first_student.id)
    if first_student and roles["parent"]:
        await _portal_user("parent@sumaya.edu", "Rakesh Gupta", "Parent@123",
                           roles["parent"], "student", first_student.id)
    if teacher_emp and roles["teacher"]:
        await _portal_user("teacher@sumaya.edu",
                           f"{teacher_emp.first_name} {teacher_emp.last_name or ''}".strip(), "Teacher@123",
                           roles["teacher"], "employee", teacher_emp.id)
    if principal_emp and roles["teacher"]:
        await _portal_user("hod@sumaya.edu",
                           f"{principal_emp.first_name} {principal_emp.last_name or ''}".strip(), "Hod@123",
                           roles["teacher"], "employee", principal_emp.id)


if __name__ == "__main__":
    asyncio.run(seed())
