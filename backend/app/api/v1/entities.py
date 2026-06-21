"""Register typed-entity CRUD routers via the generic factory.

Each entry wires a SQLAlchemy model to its schemas and a module permission slug.
Business-logic-heavy areas (fees payments, attendance bulk, exams marks, promotion)
have their own routers and are *not* registered here.
"""
from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.models import (
    AcademicYear,
    AdmissionLead,
    Employee,
    Exam,
    FeePlan,
    Grade,
    Guardian,
    Institution,
    Invoice,
    Program,
    Section,
    Student,
    Subject,
)
from app.schemas import entities as s

router = APIRouter()

_REGISTRY = [
    # (model, slug, prefix, tags, Create, Update, Out, search_fields)
    (Institution, "student_information_system", "/institutions", ["Institutions"],
     s.InstitutionCreate, s.InstitutionUpdate, s.InstitutionOut, ["name", "code"]),
    (AcademicYear, "academic_configuration", "/academic-years", ["Academic Config"],
     s.AcademicYearCreate, s.AcademicYearUpdate, s.AcademicYearOut, ["name", "code"]),
    (Program, "academic_configuration", "/programs", ["Academic Config"],
     s.ProgramCreate, s.ProgramUpdate, s.ProgramOut, ["name", "code"]),
    (Grade, "academic_configuration", "/grades", ["Academic Config"],
     s.GradeCreate, s.GradeUpdate, s.GradeOut, ["name", "code"]),
    (Section, "academic_configuration", "/sections", ["Academic Config"],
     s.SectionCreate, s.SectionUpdate, s.SectionOut, ["name"]),
    (Subject, "academic_configuration", "/subjects", ["Academic Config"],
     s.SubjectCreate, s.SubjectUpdate, s.SubjectOut, ["name", "code"]),
    (Student, "student_information_system", "/students", ["Students"],
     s.StudentCreate, s.StudentUpdate, s.StudentOut, ["first_name", "last_name", "admission_no", "email"]),
    (Guardian, "parent_guardian_portal", "/guardians", ["Guardians"],
     s.GuardianCreate, s.GuardianUpdate, s.GuardianOut, ["full_name", "phone", "email"]),
    (Employee, "employee_hrms", "/employees", ["Employees / HR"],
     s.EmployeeCreate, s.EmployeeUpdate, s.EmployeeOut, ["first_name", "last_name", "employee_no"]),
    (AdmissionLead, "admissions_crm", "/admission-leads", ["Admissions"],
     s.AdmissionLeadCreate, s.AdmissionLeadUpdate, s.AdmissionLeadOut, ["student_name", "lead_no", "phone"]),
    (FeePlan, "fees_billing", "/fee-plans", ["Fees"],
     s.FeePlanCreate, s.FeePlanUpdate, s.FeePlanOut, ["name", "code"]),
    (Invoice, "fees_billing", "/invoices", ["Fees"],
     s.InvoiceCreate, s.InvoiceUpdate, s.InvoiceOut, ["invoice_no"]),
    (Exam, "examination_management", "/exams", ["Exams"],
     s.ExamCreate, s.ExamUpdate, s.ExamOut, ["name", "code"]),
]

for model, slug, prefix, tags, create, update, out, search in _REGISTRY:
    sub = build_crud_router(
        model=model, slug=slug, tags=tags,
        create_schema=create, update_schema=update, out_schema=out,
        search_fields=search,
    )
    router.include_router(sub, prefix=prefix)
