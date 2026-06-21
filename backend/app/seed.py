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
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_models
from app.core.security import hash_password
from app.models import (
    AcademicYear,
    AdmissionLead,
    Attendance,
    Employee,
    EntityDef,
    Exam,
    FeePlan,
    FieldDef,
    Grade,
    HostelBlock,
    HostelRoom,
    LeaveType,
    LibraryBook,
    TransportRoute,
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
        ("designation", "Designation", "string", False, True, None, None),
        ("department", "Department", "string", False, True, None, None),
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
    "attendance_state": ("Attendance State", ["Present", "Absent", "Late", "Leave", "Holiday"]),
    "exam_type": ("Exam Type", ["Internal", "Unit Test", "Midterm", "Semester", "Final"]),
    "employment_type": ("Employment Type", ["Full Time", "Part Time", "Contract", "Visiting"]),
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
}

# Typed module pages handled by dedicated React screens (slug -> path).
CORE_NAV = [
    ("Dashboard", "grid", "/dashboard", None, None, 1),
    ("Admissions", "user-plus", "/admissions", "admissions_crm", "admissions_crm:read", 10),
    ("Students", "users", "/students", "student_information_system", "student_information_system:read", 11),
    ("Academic Setup", "book", "/academic", "academic_configuration", "academic_configuration:read", 12),
    ("Employees / HR", "briefcase", "/employees", "employee_hrms", "employee_hrms:read", 13),
    ("Fees & Billing", "credit-card", "/fees", "fees_billing", "fees_billing:read", 14),
    ("Attendance", "check-square", "/attendance", "attendance", "attendance:read", 15),
    ("Examinations", "edit", "/exams", "examination_management", "examination_management:read", 16),
    ("Promotion", "trending-up", "/promotion", "report_cards_transcripts", "report_cards_transcripts:read", 17),
    ("Library", "book", "/library", "library_management", "library_management:read", 18),
    ("HR Operations", "briefcase", "/hr", "employee_hrms", "employee_hrms:read", 19),
    ("Hostel", "grid", "/hostel", "hostel", "hostel:read", 20),
    ("Masters", "sliders", "/masters", "academic_configuration", "academic_configuration:read", 90),
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


async def seed() -> None:
    await init_models()
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))

    async with AsyncSessionLocal() as db:
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
        # One catch-all nav entry per remaining module -> generic module page.
        for i, (slug, mod) in enumerate(module_by_slug.items()):
            path = f"/m/{slug}"
            await get_or_create(
                db, MenuItem, tenant_id=tid, path=path,
                defaults={"label": mod.name, "icon": mod.icon, "module_slug": slug,
                          "permission_code": f"{slug}:read", "sort_order": 200 + i},
            )

        # ---------------------------------------------------------------- settings
        for key, value in {
            "general.institution_name": "Sumaya International School",
            "general.academic_board": "CBSE",
            "fees.currency": "INR",
            "fees.late_fee_percent": 2,
            "attendance.methods_enabled": ["manual", "qr", "rfid", "biometric"],
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

    # Employees
    for i, (fn, desig) in enumerate([("Anita Sharma", "Principal"), ("Rahul Verma", "Teacher"),
                                     ("Sneha Iyer", "Accountant"), ("Imran Khan", "Teacher")], start=1):
        await get_or_create(
            db, Employee, tenant_id=tid, employee_no=f"EMP{i:04d}",
            defaults={"first_name": fn.split()[0], "last_name": fn.split()[1],
                      "designation": desig, "department": "Academics",
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
                db, Attendance, tenant_id=tid, student_id=st.id, att_date=date.today(),
                defaults={"section_id": section.id if section else None,
                          "state": "present" if i % 4 else "absent", "method": "manual"},
            )

    # Demo exam
    await get_or_create(
        db, Exam, tenant_id=tid, code="UT1-2526",
        defaults={"name": "Unit Test 1", "exam_type": "unit_test", "academic_year_id": ay.id,
                  "max_marks": Decimal("100"), "pass_marks": Decimal("33")},
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


if __name__ == "__main__":
    asyncio.run(seed())
