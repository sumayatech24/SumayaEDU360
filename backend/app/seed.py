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
    Attendance,
    Employee,
    EntityDef,
    Exam,
    FeePlan,
    FieldDef,
    Grade,
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
    # (name, label, data_type, required, list_visible, options_master)
    "student": [
        ("admission_no", "Admission No", "string", True, True, None),
        ("first_name", "First Name", "string", True, True, None),
        ("last_name", "Last Name", "string", False, True, None),
        ("gender", "Gender", "select", False, True, "gender"),
        ("date_of_birth", "Date of Birth", "date", False, False, None),
        ("grade_id", "Grade", "reference", False, True, None),
        ("section_id", "Section", "reference", False, True, None),
        ("enrollment_status", "Status", "select", False, True, "enrollment_status"),
        ("phone", "Phone", "phone", False, True, None),
        ("email", "Email", "email", False, False, None),
    ],
    "employee": [
        ("employee_no", "Employee No", "string", True, True, None),
        ("first_name", "First Name", "string", True, True, None),
        ("last_name", "Last Name", "string", False, True, None),
        ("designation", "Designation", "string", False, True, None),
        ("department", "Department", "string", False, True, None),
        ("employment_type", "Type", "select", False, True, "employment_type"),
        ("employment_status", "Status", "select", False, True, None),
    ],
    "grade": [
        ("name", "Name", "string", True, True, None),
        ("code", "Code", "string", True, True, None),
        ("sequence", "Sequence", "number", False, True, None),
    ],
    "fee_plan": [
        ("name", "Name", "string", True, True, None),
        ("code", "Code", "string", True, True, None),
        ("frequency", "Frequency", "select", False, True, "fee_frequency"),
        ("amount", "Amount", "decimal", True, True, None),
    ],
    "admission_lead": [
        ("lead_no", "Lead No", "string", True, True, None),
        ("student_name", "Student Name", "string", True, True, None),
        ("source", "Source", "select", False, True, "lead_source"),
        ("stage", "Stage", "select", False, True, "lead_stage"),
        ("phone", "Phone", "phone", False, True, None),
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
    "attendance_state": ("Attendance State", ["Present", "Absent", "Late", "Leave", "Holiday"]),
    "exam_type": ("Exam Type", ["Internal", "Unit Test", "Midterm", "Semester", "Final"]),
    "employment_type": ("Employment Type", ["Full Time", "Part Time", "Contract", "Visiting"]),
    "enrollment_status": ("Enrollment Status", ["Enrolled", "Promoted", "Graduated", "Transferred", "Dropped"]),
    "lead_source": ("Lead Source", ["Website", "Walk-in", "Referral", "Advertisement", "Social Media"]),
    "lead_stage": ("Lead Stage", ["Inquiry", "Counseling", "Entrance Test", "Document Collection", "Approved", "Enrolled", "Rejected"]),
    "document_category": ("Document Category", ["Birth Certificate", "Transfer Certificate", "Photo", "ID Proof", "Report Card"]),
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
            if created:
                for order, fd in enumerate(TYPED_FIELDS.get(table, [])):
                    n, label, dtype, req, lv, opt = fd
                    db.add(FieldDef(
                        tenant_id=tid, entity_id=ent.id, name=n, label=label, data_type=dtype,
                        is_required=req, is_list_visible=lv, options_master=opt, sort_order=order + 1,
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

        # Guarantee every module has at least one operable entity.
        for slug, mod in module_by_slug.items():
            has = (await db.execute(select(EntityDef).where(EntityDef.module_id == mod.id))).scalars().first()
            if has:
                continue
            ent_slug = f"{slug}-record"
            ent, created = await get_or_create(
                db, EntityDef, tenant_id=tid, slug=ent_slug,
                defaults={"module_id": mod.id, "name": f"{mod.name} Record", "kind": "transaction",
                          "is_typed": False, "purpose": mod.description},
            )
            if created:
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


if __name__ == "__main__":
    asyncio.run(seed())
