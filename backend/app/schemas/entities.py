"""Create/Update/Out schemas for the typed core entities.

Kept compact: each entity has a *Base (shared fields), *Create, *Update (all optional)
and *Out (adds audited identity fields).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.common import AuditedOut


def _optional(model: type[BaseModel]) -> dict:
    """Not used at runtime; kept for documentation of the optional pattern."""
    return {}


class _C(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ----------------------------------------------------------------------------- Tenant / org
class InstitutionBase(_C):
    name: str
    code: str
    type: str = "school"
    board: str | None = None
    address: str | None = None
    status: str = "active"


class InstitutionCreate(InstitutionBase):
    pass


class InstitutionUpdate(_C):
    name: str | None = None
    code: str | None = None
    type: str | None = None
    board: str | None = None
    address: str | None = None
    status: str | None = None


class InstitutionOut(AuditedOut, InstitutionBase):
    pass


# ----------------------------------------------------------------------------- Academic config
class AcademicYearBase(_C):
    name: str
    code: str
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False


class AcademicYearCreate(AcademicYearBase):
    pass


class AcademicYearUpdate(_C):
    name: str | None = None
    code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool | None = None


class AcademicYearOut(AuditedOut, AcademicYearBase):
    pass


class ProgramBase(_C):
    name: str
    code: str
    level: str | None = None


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(_C):
    name: str | None = None
    code: str | None = None
    level: str | None = None


class ProgramOut(AuditedOut, ProgramBase):
    pass


class GradeBase(_C):
    program_id: uuid.UUID | None = None
    name: str
    code: str
    sequence: int = 0


class GradeCreate(GradeBase):
    pass


class GradeUpdate(_C):
    program_id: uuid.UUID | None = None
    name: str | None = None
    code: str | None = None
    sequence: int | None = None


class GradeOut(AuditedOut, GradeBase):
    pass


class SectionBase(_C):
    grade_id: uuid.UUID
    name: str
    capacity: int = 40
    class_teacher_id: uuid.UUID | None = None


class SectionCreate(SectionBase):
    pass


class SectionUpdate(_C):
    grade_id: uuid.UUID | None = None
    name: str | None = None
    capacity: int | None = None
    class_teacher_id: uuid.UUID | None = None


class SectionOut(AuditedOut, SectionBase):
    pass


class SubjectBase(_C):
    name: str
    code: str
    grade_id: uuid.UUID | None = None
    is_elective: bool = False
    credits: int = 0


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(_C):
    name: str | None = None
    code: str | None = None
    grade_id: uuid.UUID | None = None
    is_elective: bool | None = None
    credits: int | None = None


class SubjectOut(AuditedOut, SubjectBase):
    pass


# ----------------------------------------------------------------------------- People
class StudentBase(_C):
    admission_no: str
    roll_no: str | None = None
    first_name: str
    last_name: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    blood_group: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    academic_year_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    enrollment_status: str = "enrolled"
    photo_url: str | None = None


class StudentCreate(StudentBase):
    pass


class StudentUpdate(_C):
    admission_no: str | None = None
    roll_no: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    date_of_birth: date | None = None
    blood_group: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    academic_year_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    enrollment_status: str | None = None
    photo_url: str | None = None


class StudentOut(AuditedOut, StudentBase):
    pass


class GuardianBase(_C):
    student_id: uuid.UUID
    relation: str = "father"
    full_name: str
    phone: str | None = None
    email: str | None = None
    occupation: str | None = None
    is_primary: bool = False


class GuardianCreate(GuardianBase):
    pass


class GuardianUpdate(_C):
    relation: str | None = None
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    occupation: str | None = None
    is_primary: bool | None = None


class GuardianOut(AuditedOut, GuardianBase):
    pass


class EmployeeBase(_C):
    employee_no: str
    first_name: str
    last_name: str | None = None
    gender: str | None = None
    email: str | None = None
    phone: str | None = None
    designation: str | None = None
    department: str | None = None
    date_of_joining: date | None = None
    employment_type: str = "full_time"
    salary: Decimal | None = None
    employment_status: str = "active"


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(_C):
    employee_no: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    gender: str | None = None
    email: str | None = None
    phone: str | None = None
    designation: str | None = None
    department: str | None = None
    date_of_joining: date | None = None
    employment_type: str | None = None
    salary: Decimal | None = None
    employment_status: str | None = None


class EmployeeOut(AuditedOut, EmployeeBase):
    pass


# ----------------------------------------------------------------------------- Admissions
class AdmissionLeadBase(_C):
    lead_no: str
    student_name: str
    guardian_name: str | None = None
    phone: str | None = None
    email: str | None = None
    grade_applied_id: uuid.UUID | None = None
    source: str | None = None
    stage: str = "inquiry"
    counselor_id: uuid.UUID | None = None
    follow_up_date: date | None = None
    test_score: str | None = None
    notes: str | None = None


class AdmissionLeadCreate(AdmissionLeadBase):
    pass


class AdmissionLeadUpdate(_C):
    student_name: str | None = None
    guardian_name: str | None = None
    phone: str | None = None
    email: str | None = None
    grade_applied_id: uuid.UUID | None = None
    source: str | None = None
    stage: str | None = None
    counselor_id: uuid.UUID | None = None
    follow_up_date: date | None = None
    test_score: str | None = None
    notes: str | None = None


class AdmissionLeadOut(AuditedOut, AdmissionLeadBase):
    converted_student_id: uuid.UUID | None = None


# ----------------------------------------------------------------------------- Fees
class FeePlanBase(_C):
    name: str
    code: str
    academic_year_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    frequency: str = "annual"
    amount: Decimal = Decimal(0)
    description: str | None = None


class FeePlanCreate(FeePlanBase):
    pass


class FeePlanUpdate(_C):
    name: str | None = None
    code: str | None = None
    academic_year_id: uuid.UUID | None = None
    grade_id: uuid.UUID | None = None
    frequency: str | None = None
    amount: Decimal | None = None
    description: str | None = None


class FeePlanOut(AuditedOut, FeePlanBase):
    pass


class InvoiceBase(_C):
    invoice_no: str
    student_id: uuid.UUID
    fee_plan_id: uuid.UUID | None = None
    academic_year_id: uuid.UUID | None = None
    issue_date: date | None = None
    due_date: date | None = None
    gross_amount: Decimal = Decimal(0)
    discount_amount: Decimal = Decimal(0)
    net_amount: Decimal = Decimal(0)


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(_C):
    fee_plan_id: uuid.UUID | None = None
    issue_date: date | None = None
    due_date: date | None = None
    gross_amount: Decimal | None = None
    discount_amount: Decimal | None = None
    net_amount: Decimal | None = None
    payment_status: str | None = None


class InvoiceOut(AuditedOut, InvoiceBase):
    paid_amount: Decimal = Decimal(0)
    payment_status: str = "unpaid"


# ----------------------------------------------------------------------------- Exams
class ExamBase(_C):
    name: str
    code: str
    academic_year_id: uuid.UUID | None = None
    exam_type: str = "internal"
    grade_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    max_marks: Decimal = Decimal(100)
    pass_marks: Decimal = Decimal(33)


class ExamCreate(ExamBase):
    pass


class ExamUpdate(_C):
    name: str | None = None
    code: str | None = None
    exam_type: str | None = None
    grade_id: uuid.UUID | None = None
    start_date: date | None = None
    end_date: date | None = None
    max_marks: Decimal | None = None
    pass_marks: Decimal | None = None


class ExamOut(AuditedOut, ExamBase):
    pass
