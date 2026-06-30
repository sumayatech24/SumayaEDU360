"""Complete admissions lifecycle for public applicants, continuing students and staff."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user, require_permission
from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.models.academic import AcademicYear, Grade, Section
from app.models.admissions import (
    AdmissionApplicant,
    AdmissionApplication,
    AdmissionCharge,
    AdmissionDocument,
    AdmissionDocumentRequirement,
    AdmissionLead,
    AdmissionVerification,
)
from app.models.auth import User
from app.models.people import Guardian, Student
from app.models.student_records import StudentAcademicHistory, StudentLifecycleRequest
from app.models.tenant import Institution, Tenant

router = APIRouter(tags=["Admissions"])
bearer = HTTPBearer(auto_error=False)


class ApplicantAuth(BaseModel):
    email: str
    password: str = Field(min_length=8)
    full_name: str | None = None
    phone: str | None = None


class DocumentIn(BaseModel):
    document_type: str
    file_name: str
    file_data: str | None = None


class PublicApplicationIn(BaseModel):
    student_name: str
    grade_applied_id: uuid.UUID
    academic_year_id: uuid.UUID | None = None
    phone: str | None = None
    email: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    category: str | None = None
    religion: str | None = None
    nationality: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    pincode: str | None = None
    father_name: str | None = None
    father_phone: str | None = None
    father_occupation: str | None = None
    father_annual_income: Decimal | None = Field(default=None, ge=0)
    mother_name: str | None = None
    mother_phone: str | None = None
    mother_occupation: str | None = None
    mother_annual_income: Decimal | None = Field(default=None, ge=0)
    guardian_name: str | None = None
    guardian_phone: str | None = None
    guardian_relation: str | None = None
    guardian_occupation: str | None = None
    guardian_annual_income: Decimal | None = Field(default=None, ge=0)
    previous_school: str | None = None
    fee_category: str = "regular"
    government_aid_percent: Decimal = Field(default=Decimal(0), ge=0, le=100)
    documents: list[DocumentIn] = Field(default_factory=list)
    declaration_accepted: bool


class InternalApplicationIn(BaseModel):
    student_id: uuid.UUID | None = None
    target_grade_id: uuid.UUID
    academic_year_id: uuid.UUID
    target_section_id: uuid.UUID | None = None
    notes: str | None = None


class PortalTcRequestIn(BaseModel):
    effective_date: date
    reason: str = Field(min_length=3, max_length=2000)
    destination_school: str | None = Field(default=None, max_length=255)


class CheckDecisionIn(BaseModel):
    status: str
    remarks: str | None = None


class AdmissionDecisionIn(BaseModel):
    decision: str
    notes: str | None = None


class ChargeIn(BaseModel):
    charge_type: str = "admission_fee"
    amount: Decimal = Field(gt=0)
    due_date: date | None = None


class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    method: str
    reference: str | None = None


class PlacementIn(BaseModel):
    academic_year_id: uuid.UUID
    grade_id: uuid.UUID
    section_id: uuid.UUID | None = None


class DocumentRequirementIn(BaseModel):
    code: str = Field(min_length=2, max_length=64, pattern=r"^[a-z0-9_]+$")
    label: str = Field(min_length=2, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    application_type: str = Field(default="all", pattern=r"^(all|new|continuing)$")
    is_required: bool = True
    sort_order: int = 0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _tenant_by_code(db: AsyncSession, code: str) -> Tenant:
    tenant = (await db.execute(
        select(Tenant).where(func.lower(Tenant.code) == code.lower(), Tenant.is_deleted.is_(False))
    )).scalars().first()
    if not tenant:
        raise HTTPException(404, "Institution admissions portal not found")
    return tenant


async def _current_applicant(
    tenant_code: str,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> AdmissionApplicant:
    if not credentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Applicant login required")
    try:
        claims = decode_access_token(credentials.credentials)
        if claims.get("kind") != "admission_applicant":
            raise ValueError
        applicant_id = uuid.UUID(claims["sub"])
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired applicant session")
    tenant = await _tenant_by_code(db, tenant_code)
    applicant = await db.get(AdmissionApplicant, applicant_id)
    if not applicant or applicant.tenant_id != tenant.id or not applicant.is_active or applicant.is_deleted:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Applicant account is inactive")
    return applicant


def _applicant_token(applicant: AdmissionApplicant) -> str:
    return create_access_token(
        str(applicant.id),
        {"kind": "admission_applicant", "tenant_id": str(applicant.tenant_id)},
    )


async def _new_number(db: AsyncSession, tenant_id: uuid.UUID, prefix: str) -> str:
    count = (await db.execute(
        select(func.count()).select_from(AdmissionApplication).where(
            AdmissionApplication.tenant_id == tenant_id
        )
    )).scalar_one()
    return f"{prefix}-{date.today().year}-{count + 1:05d}"


async def _application_view(db: AsyncSession, app: AdmissionApplication) -> dict:
    lead = await db.get(AdmissionLead, app.lead_id)
    grade = await db.get(Grade, app.target_grade_id) if app.target_grade_id else None
    year = await db.get(AcademicYear, app.academic_year_id) if app.academic_year_id else None
    section = await db.get(Section, app.target_section_id) if app.target_section_id else None
    docs = (await db.execute(select(AdmissionDocument).where(
        AdmissionDocument.application_id == app.id,
        AdmissionDocument.is_deleted.is_(False),
    ).order_by(AdmissionDocument.created_at))).scalars().all()
    checks = (await db.execute(select(AdmissionVerification).where(
        AdmissionVerification.application_id == app.id,
        AdmissionVerification.is_deleted.is_(False),
    ).order_by(AdmissionVerification.check_type))).scalars().all()
    charges = (await db.execute(select(AdmissionCharge).where(
        AdmissionCharge.application_id == app.id,
        AdmissionCharge.is_deleted.is_(False),
    ).order_by(AdmissionCharge.created_at))).scalars().all()
    return {
        "id": str(app.id), "application_no": app.application_no,
        "application_type": app.application_type, "channel": app.channel,
        "status": app.application_status, "verification_status": app.verification_status,
        "fee_status": app.fee_status, "fee_category": app.fee_category,
        "government_aid_percent": str(app.government_aid_percent),
        "submitted_at": app.submitted_at,
        "decision_notes": app.decision_notes,
        "student_name": lead.student_name if lead else None,
        "phone": lead.phone if lead else None, "email": lead.email if lead else None,
        "date_of_birth": lead.date_of_birth if lead else None,
        "family": {
            "father": {"name": lead.father_name, "phone": lead.father_phone,
                       "occupation": lead.father_occupation,
                       "annual_income": str(lead.father_annual_income) if lead.father_annual_income is not None else None},
            "mother": {"name": lead.mother_name, "phone": lead.mother_phone,
                       "occupation": lead.mother_occupation,
                       "annual_income": str(lead.mother_annual_income) if lead.mother_annual_income is not None else None},
            "guardian": {"name": lead.guardian_name, "phone": lead.guardian_phone,
                         "relation": lead.guardian_relation, "occupation": lead.guardian_occupation,
                         "annual_income": str(lead.guardian_annual_income) if lead.guardian_annual_income is not None else None},
        } if lead else None,
        "grade": grade.name if grade else None, "target_grade_id": str(app.target_grade_id) if app.target_grade_id else None,
        "academic_year": year.name if year else None,
        "academic_year_id": str(app.academic_year_id) if app.academic_year_id else None,
        "section": section.name if section else None,
        "target_section_id": str(app.target_section_id) if app.target_section_id else None,
        "existing_student_id": str(app.existing_student_id) if app.existing_student_id else None,
        "converted_student_id": str(lead.converted_student_id) if lead and lead.converted_student_id else None,
        "documents": [{
            "id": str(d.id), "document_type": d.document_type, "file_name": d.file_name,
            "verification_status": d.verification_status, "remarks": d.remarks,
        } for d in docs],
        "checks": [{
            "id": str(c.id), "check_type": c.check_type, "status": c.check_status,
            "remarks": c.remarks,
        } for c in checks],
        "charges": [{
            "id": str(c.id), "charge_type": c.charge_type, "amount": str(c.amount),
            "paid_amount": str(c.paid_amount), "status": c.payment_status,
            "due_date": c.due_date, "receipt_no": c.receipt_no,
        } for c in charges],
    }


async def _recompute_verification(db: AsyncSession, app: AdmissionApplication) -> None:
    checks = (await db.execute(select(AdmissionVerification.check_status).where(
        AdmissionVerification.application_id == app.id,
        AdmissionVerification.is_deleted.is_(False),
    ))).scalars().all()
    docs = (await db.execute(select(AdmissionDocument.verification_status).where(
        AdmissionDocument.application_id == app.id,
        AdmissionDocument.is_deleted.is_(False),
    ))).scalars().all()
    values = [*checks, *docs]
    if any(v == "rejected" for v in values):
        app.verification_status = "issues"
    elif values and all(v == "verified" for v in values):
        app.verification_status = "verified"
    elif any(v == "verified" for v in values):
        app.verification_status = "in_progress"
    else:
        app.verification_status = "pending"


@router.get("/public/admissions/{tenant_code}/config")
async def public_config(tenant_code: str, db: AsyncSession = Depends(get_db)):
    tenant = await _tenant_by_code(db, tenant_code)
    institution = (await db.execute(select(Institution).where(
        Institution.tenant_id == tenant.id, Institution.is_deleted.is_(False)
    ))).scalars().first()
    grades = (await db.execute(select(Grade).where(
        Grade.tenant_id == tenant.id, Grade.is_deleted.is_(False)
    ).order_by(Grade.sequence, Grade.name))).scalars().all()
    years = (await db.execute(select(AcademicYear).where(
        AcademicYear.tenant_id == tenant.id, AcademicYear.is_deleted.is_(False)
    ).order_by(AcademicYear.start_date.desc()))).scalars().all()
    requirements = (await db.execute(select(AdmissionDocumentRequirement).where(
        AdmissionDocumentRequirement.tenant_id == tenant.id,
        AdmissionDocumentRequirement.is_deleted.is_(False),
        AdmissionDocumentRequirement.status == "active",
    ).order_by(AdmissionDocumentRequirement.sort_order, AdmissionDocumentRequirement.label))).scalars().all()
    if not requirements:
        defaults = [
            ("birth_certificate", "Birth certificate"),
            ("student_photo", "Student photo"),
            ("address_proof", "Address proof"),
            ("previous_school_record", "Previous school record"),
        ]
        for order, (code, label) in enumerate(defaults, 1):
            row = AdmissionDocumentRequirement(
                tenant_id=tenant.id, code=code, label=label, is_required=True, sort_order=order,
            )
            db.add(row)
            requirements.append(row)
        await db.flush()
    return {
        "tenant_code": tenant.code, "institution_name": institution.name if institution else tenant.name,
        "grades": [{"id": str(g.id), "name": g.name, "code": g.code} for g in grades],
        "academic_years": [{"id": str(y.id), "name": y.name, "is_current": y.is_current} for y in years],
        "document_requirements": [{
            "id": str(r.id), "code": r.code, "label": r.label, "description": r.description,
            "application_type": r.application_type, "is_required": r.is_required,
            "sort_order": r.sort_order, "status": r.status,
        } for r in requirements],
        "required_documents": [r.code for r in requirements if r.is_required],
    }


@router.get("/admissions/config")
async def internal_admission_config(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    tenant = await db.get(Tenant, user.tenant_id)
    if not tenant:
        raise HTTPException(404, "Tenant not found")
    return await public_config(tenant.code, db)


@router.get("/admissions/document-requirements")
async def list_document_requirements(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:read")),
):
    rows = (await db.execute(select(AdmissionDocumentRequirement).where(
        AdmissionDocumentRequirement.tenant_id == user.tenant_id,
        AdmissionDocumentRequirement.is_deleted.is_(False),
    ).order_by(AdmissionDocumentRequirement.sort_order, AdmissionDocumentRequirement.label))).scalars().all()
    return [{"id": str(r.id), "code": r.code, "label": r.label, "description": r.description,
             "application_type": r.application_type, "is_required": r.is_required,
             "sort_order": r.sort_order, "status": r.status} for r in rows]


@router.post("/admissions/document-requirements", status_code=201)
async def create_document_requirement(
    payload: DocumentRequirementIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:create")),
):
    exists = (await db.execute(select(AdmissionDocumentRequirement).where(
        AdmissionDocumentRequirement.tenant_id == user.tenant_id,
        AdmissionDocumentRequirement.code == payload.code,
        AdmissionDocumentRequirement.is_deleted.is_(False),
    ))).scalars().first()
    if exists:
        raise HTTPException(409, "A document requirement with this code already exists")
    row = AdmissionDocumentRequirement(tenant_id=user.tenant_id, **payload.model_dump(),
                                       created_by=user.id, updated_by=user.id)
    db.add(row)
    await db.flush()
    await record_audit(db, action="create", entity="AdmissionDocumentRequirement",
                       entity_id=row.id, actor=user)
    return {"id": str(row.id), **payload.model_dump(), "status": row.status}


@router.put("/admissions/document-requirements/{requirement_id}")
async def update_document_requirement(
    requirement_id: uuid.UUID, payload: DocumentRequirementIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:update")),
):
    row = await db.get(AdmissionDocumentRequirement, requirement_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "Document requirement not found")
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.updated_by = user.id
    await record_audit(db, action="update", entity="AdmissionDocumentRequirement",
                       entity_id=row.id, actor=user)
    return {"id": str(row.id), **payload.model_dump(), "status": row.status}


@router.delete("/admissions/document-requirements/{requirement_id}", status_code=204)
async def delete_document_requirement(
    requirement_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:delete")),
):
    row = await db.get(AdmissionDocumentRequirement, requirement_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "Document requirement not found")
    row.is_deleted, row.status, row.updated_by = True, "inactive", user.id


@router.post("/public/admissions/{tenant_code}/register")
async def register_applicant(tenant_code: str, payload: ApplicantAuth, db: AsyncSession = Depends(get_db)):
    tenant = await _tenant_by_code(db, tenant_code)
    email = payload.email.strip().lower()
    if not payload.full_name:
        raise HTTPException(422, "Full name is required")
    exists = (await db.execute(select(AdmissionApplicant).where(
        AdmissionApplicant.tenant_id == tenant.id, func.lower(AdmissionApplicant.email) == email,
        AdmissionApplicant.is_deleted.is_(False),
    ))).scalars().first()
    if exists:
        raise HTTPException(409, "An applicant account already exists for this email")
    applicant = AdmissionApplicant(
        tenant_id=tenant.id, email=email, full_name=payload.full_name.strip(),
        phone=payload.phone, hashed_password=hash_password(payload.password),
    )
    db.add(applicant)
    await db.flush()
    return {"access_token": _applicant_token(applicant), "token_type": "bearer",
            "applicant": {"id": str(applicant.id), "name": applicant.full_name, "email": applicant.email}}


@router.post("/public/admissions/{tenant_code}/login")
async def applicant_login(tenant_code: str, payload: ApplicantAuth, db: AsyncSession = Depends(get_db)):
    tenant = await _tenant_by_code(db, tenant_code)
    applicant = (await db.execute(select(AdmissionApplicant).where(
        AdmissionApplicant.tenant_id == tenant.id,
        func.lower(AdmissionApplicant.email) == payload.email.strip().lower(),
        AdmissionApplicant.is_deleted.is_(False),
    ))).scalars().first()
    if not applicant or not verify_password(payload.password, applicant.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    applicant.last_login_at = _utcnow()
    return {"access_token": _applicant_token(applicant), "token_type": "bearer",
            "applicant": {"id": str(applicant.id), "name": applicant.full_name, "email": applicant.email}}


@router.get("/public/admissions/{tenant_code}/applications")
async def applicant_applications(
    tenant_code: str,
    applicant: AdmissionApplicant = Depends(_current_applicant),
    db: AsyncSession = Depends(get_db),
):
    rows = (await db.execute(select(AdmissionApplication).where(
        AdmissionApplication.tenant_id == applicant.tenant_id,
        AdmissionApplication.applicant_id == applicant.id,
        AdmissionApplication.is_deleted.is_(False),
    ).order_by(AdmissionApplication.created_at.desc()))).scalars().all()
    return [await _application_view(db, row) for row in rows]


@router.post("/public/admissions/{tenant_code}/applications", status_code=201)
async def submit_public_application(
    tenant_code: str,
    payload: PublicApplicationIn,
    applicant: AdmissionApplicant = Depends(_current_applicant),
    db: AsyncSession = Depends(get_db),
):
    if not payload.declaration_accepted:
        raise HTTPException(422, "The applicant declaration must be accepted")
    grade = await db.get(Grade, payload.grade_applied_id)
    if not grade or grade.tenant_id != applicant.tenant_id:
        raise HTTPException(404, "Selected class not found")
    requirements = (await db.execute(select(AdmissionDocumentRequirement).where(
        AdmissionDocumentRequirement.tenant_id == applicant.tenant_id,
        AdmissionDocumentRequirement.status == "active",
        AdmissionDocumentRequirement.is_required.is_(True),
        AdmissionDocumentRequirement.application_type.in_(("all", "new")),
        AdmissionDocumentRequirement.is_deleted.is_(False),
    ))).scalars().all()
    supplied = {doc.document_type for doc in payload.documents}
    missing = [r.label for r in requirements if r.code not in supplied]
    if missing:
        raise HTTPException(422, f"Required documents missing: {', '.join(missing)}")
    number = await _new_number(db, applicant.tenant_id, "APP")
    lead = AdmissionLead(
        tenant_id=applicant.tenant_id, lead_no=number.replace("APP", "LEAD", 1),
        student_name=payload.student_name, guardian_name=payload.guardian_name,
        phone=payload.phone or applicant.phone, email=payload.email or applicant.email,
        grade_applied_id=grade.id, source="public_portal", stage="document_collection",
        **payload.model_dump(exclude={"student_name", "phone", "email", "grade_applied_id",
                                      "academic_year_id", "documents", "declaration_accepted",
                                      "fee_category", "government_aid_percent", "guardian_name"}),
    )
    db.add(lead)
    await db.flush()
    app = AdmissionApplication(
        tenant_id=applicant.tenant_id, application_no=number, lead_id=lead.id,
        applicant_id=applicant.id, application_type="new", channel="public",
        academic_year_id=payload.academic_year_id, target_grade_id=grade.id,
        application_status="submitted", submitted_at=_utcnow(),
        declaration_accepted=True, fee_category=payload.fee_category,
        government_aid_percent=payload.government_aid_percent,
    )
    db.add(app)
    await db.flush()
    for doc in payload.documents:
        db.add(AdmissionDocument(
            tenant_id=applicant.tenant_id, application_id=app.id, **doc.model_dump()
        ))
    for check in ("identity", "age_eligibility", "documents", "previous_school"):
        db.add(AdmissionVerification(
            tenant_id=applicant.tenant_id, application_id=app.id, check_type=check
        ))
    await db.flush()
    return await _application_view(db, app)


@router.post("/admissions/internal/applications", status_code=201)
async def submit_internal_application(
    payload: InternalApplicationIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    db_user = await db.get(User, user.id)
    student_id = payload.student_id
    if not student_id and db_user and db_user.person_type == "student":
        student_id = db_user.person_id
    if not student_id:
        raise HTTPException(422, "A linked student or student_id is required")
    student = await db.get(Student, student_id)
    grade = await db.get(Grade, payload.target_grade_id)
    year = await db.get(AcademicYear, payload.academic_year_id)
    if not student or student.tenant_id != user.tenant_id:
        raise HTTPException(404, "Student not found")
    if not grade or grade.tenant_id != user.tenant_id or not year or year.tenant_id != user.tenant_id:
        raise HTTPException(404, "Target class or academic year not found")
    duplicate = (await db.execute(select(AdmissionApplication).where(
        AdmissionApplication.tenant_id == user.tenant_id,
        AdmissionApplication.existing_student_id == student.id,
        AdmissionApplication.academic_year_id == year.id,
        AdmissionApplication.application_status.not_in(("rejected", "enrolled")),
        AdmissionApplication.is_deleted.is_(False),
    ))).scalars().first()
    if duplicate:
        raise HTTPException(409, f"Active application {duplicate.application_no} already exists")
    number = await _new_number(db, user.tenant_id, "CONT")
    lead = AdmissionLead(
        tenant_id=user.tenant_id, lead_no=number.replace("CONT", "LEAD", 1),
        student_name=f"{student.first_name} {student.last_name or ''}".strip(),
        phone=student.phone, email=student.email, grade_applied_id=grade.id,
        source="internal_portal", stage="document_collection", notes=payload.notes,
        date_of_birth=student.date_of_birth, gender=student.gender, address=student.address,
        created_by=user.id, updated_by=user.id,
    )
    db.add(lead)
    await db.flush()
    app = AdmissionApplication(
        tenant_id=user.tenant_id, application_no=number, lead_id=lead.id,
        application_type="continuing", channel="internal", existing_student_id=student.id,
        academic_year_id=year.id, target_grade_id=grade.id, target_section_id=payload.target_section_id,
        application_status="submitted", submitted_at=_utcnow(), declaration_accepted=True,
        created_by=user.id, updated_by=user.id,
    )
    db.add(app)
    await db.flush()
    for check in ("academic_clearance", "fee_clearance", "discipline_clearance"):
        db.add(AdmissionVerification(
            tenant_id=user.tenant_id, application_id=app.id, check_type=check,
            created_by=user.id, updated_by=user.id,
        ))
    await db.flush()
    await record_audit(db, action="apply_continuation", entity="AdmissionApplication",
                       entity_id=app.id, actor=user, changes={"student_id": str(student.id)})
    return await _application_view(db, app)


@router.get("/admissions/my-applications")
async def my_internal_applications(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)
):
    db_user = await db.get(User, user.id)
    if not db_user or db_user.person_type != "student" or not db_user.person_id:
        return []
    rows = (await db.execute(select(AdmissionApplication).where(
        AdmissionApplication.tenant_id == user.tenant_id,
        AdmissionApplication.existing_student_id == db_user.person_id,
        AdmissionApplication.is_deleted.is_(False),
    ).order_by(AdmissionApplication.created_at.desc()))).scalars().all()
    return [await _application_view(db, row) for row in rows]


async def _portal_student(db: AsyncSession, user: CurrentUser) -> Student:
    db_user = await db.get(User, user.id)
    if not db_user or db_user.person_type != "student" or not db_user.person_id:
        raise HTTPException(422, "A linked student account is required")
    student = await db.get(Student, db_user.person_id)
    if not student or student.tenant_id != user.tenant_id:
        raise HTTPException(404, "Student not found")
    return student


@router.get("/admissions/my-tc-requests")
async def my_tc_requests(
    db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user),
):
    student = await _portal_student(db, user)
    rows = (await db.execute(select(StudentLifecycleRequest).where(
        StudentLifecycleRequest.tenant_id == user.tenant_id,
        StudentLifecycleRequest.student_id == student.id,
        StudentLifecycleRequest.request_type == "transfer",
        StudentLifecycleRequest.is_deleted.is_(False),
    ).order_by(StudentLifecycleRequest.created_at.desc()))).scalars().all()
    return [{"id": str(r.id), "request_no": r.request_no, "status": r.request_status,
             "effective_date": r.effective_date, "reason": r.reason,
             "destination_school": r.destination_school,
             "approval_remarks": r.approval_remarks, "certificate_no": r.certificate_no}
            for r in rows]


@router.post("/admissions/my-tc-requests", status_code=201)
async def request_tc(
    payload: PortalTcRequestIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    student = await _portal_student(db, user)
    duplicate = (await db.execute(select(StudentLifecycleRequest).where(
        StudentLifecycleRequest.tenant_id == user.tenant_id,
        StudentLifecycleRequest.student_id == student.id,
        StudentLifecycleRequest.request_type == "transfer",
        StudentLifecycleRequest.request_status.in_(("submitted", "approved")),
        StudentLifecycleRequest.is_deleted.is_(False),
    ))).scalars().first()
    if duplicate:
        raise HTTPException(409, f"Active TC request {duplicate.request_no} already exists")
    count = (await db.execute(select(func.count()).select_from(StudentLifecycleRequest).where(
        StudentLifecycleRequest.tenant_id == user.tenant_id,
    ))).scalar_one()
    row = StudentLifecycleRequest(
        tenant_id=user.tenant_id, student_id=student.id,
        request_no=f"TCREQ-{date.today().year}-{count + 1:05d}",
        request_type="transfer", request_status="submitted",
        effective_date=payload.effective_date, reason=payload.reason,
        destination_school=payload.destination_school,
        created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(db, action="request_tc", entity="StudentLifecycleRequest",
                       entity_id=row.id, actor=user)
    return {"id": str(row.id), "request_no": row.request_no, "status": row.request_status}


@router.get("/admissions/applications")
async def list_applications(
    application_status: str | None = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:read")),
):
    conditions = [
        AdmissionApplication.tenant_id == user.tenant_id,
        AdmissionApplication.is_deleted.is_(False),
    ]
    if application_status:
        conditions.append(AdmissionApplication.application_status == application_status)
    rows = (await db.execute(select(AdmissionApplication).where(*conditions)
                            .order_by(AdmissionApplication.created_at.desc()))).scalars().all()
    return [await _application_view(db, row) for row in rows]


async def _staff_application(db: AsyncSession, app_id: uuid.UUID, user: CurrentUser) -> AdmissionApplication:
    app = await db.get(AdmissionApplication, app_id)
    if not app or app.tenant_id != user.tenant_id or app.is_deleted:
        raise HTTPException(404, "Admission application not found")
    return app


@router.get("/admissions/applications/{app_id}")
async def application_detail(
    app_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:read")),
):
    return await _application_view(db, await _staff_application(db, app_id, user))


@router.get("/admissions/applications/{app_id}/documents/{document_id}/content")
async def admission_document_content(
    app_id: uuid.UUID, document_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:read")),
):
    app = await _staff_application(db, app_id, user)
    document = await db.get(AdmissionDocument, document_id)
    if not document or document.application_id != app.id or document.is_deleted:
        raise HTTPException(404, "Admission document not found")
    return {
        "file_name": document.file_name, "document_type": document.document_type,
        "file_data": document.file_data,
    }


@router.post("/admissions/applications/{app_id}/checks/{check_id}")
async def decide_check(
    app_id: uuid.UUID, check_id: uuid.UUID, payload: CheckDecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:update")),
):
    if payload.status not in ("pending", "verified", "rejected"):
        raise HTTPException(422, "status must be pending, verified or rejected")
    app = await _staff_application(db, app_id, user)
    check = await db.get(AdmissionVerification, check_id)
    if not check or check.application_id != app.id:
        raise HTTPException(404, "Verification check not found")
    check.check_status, check.remarks = payload.status, payload.remarks
    check.checked_by, check.checked_at, check.updated_by = user.id, _utcnow(), user.id
    app.application_status = "under_review"
    await db.flush()
    await _recompute_verification(db, app)
    return await _application_view(db, app)


@router.post("/admissions/applications/{app_id}/documents/{document_id}")
async def decide_document(
    app_id: uuid.UUID, document_id: uuid.UUID, payload: CheckDecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:update")),
):
    if payload.status not in ("pending", "verified", "rejected"):
        raise HTTPException(422, "status must be pending, verified or rejected")
    app = await _staff_application(db, app_id, user)
    document = await db.get(AdmissionDocument, document_id)
    if not document or document.application_id != app.id:
        raise HTTPException(404, "Admission document not found")
    document.verification_status, document.remarks = payload.status, payload.remarks
    document.verified_by, document.verified_at, document.updated_by = user.id, _utcnow(), user.id
    app.application_status = "under_review"
    await db.flush()
    await _recompute_verification(db, app)
    return await _application_view(db, app)


@router.post("/admissions/applications/{app_id}/decision")
async def admission_decision(
    app_id: uuid.UUID, payload: AdmissionDecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:approve")),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be approved or rejected")
    app = await _staff_application(db, app_id, user)
    if payload.decision == "approved" and app.verification_status != "verified":
        raise HTTPException(409, "Complete all document and eligibility verification before approval")
    app.application_status, app.decision_notes = payload.decision, payload.notes
    app.decided_by, app.decided_at, app.updated_by = user.id, _utcnow(), user.id
    lead = await db.get(AdmissionLead, app.lead_id)
    if lead:
        lead.stage = payload.decision
        lead.updated_by = user.id
    await record_audit(db, action=payload.decision, entity="AdmissionApplication",
                       entity_id=app.id, actor=user)
    return await _application_view(db, app)


@router.post("/admissions/applications/{app_id}/placement")
async def set_admission_placement(
    app_id: uuid.UUID, payload: PlacementIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("admissions_crm:update")),
):
    app = await _staff_application(db, app_id, user)
    year = await db.get(AcademicYear, payload.academic_year_id)
    grade = await db.get(Grade, payload.grade_id)
    section = await db.get(Section, payload.section_id) if payload.section_id else None
    if not year or year.tenant_id != user.tenant_id or not grade or grade.tenant_id != user.tenant_id:
        raise HTTPException(404, "Academic year or class not found")
    if section and (section.tenant_id != user.tenant_id or section.grade_id != grade.id):
        raise HTTPException(422, "The selected section does not belong to the selected class")
    app.academic_year_id, app.target_grade_id, app.target_section_id = year.id, grade.id, section.id if section else None
    app.updated_by = user.id
    lead = await db.get(AdmissionLead, app.lead_id)
    if lead:
        lead.grade_applied_id = grade.id
        lead.updated_by = user.id
    await record_audit(db, action="set_placement", entity="AdmissionApplication",
                       entity_id=app.id, actor=user,
                       changes={"year": str(year.id), "grade": str(grade.id),
                                "section": str(section.id) if section else None})
    return await _application_view(db, app)


@router.post("/admissions/applications/{app_id}/charges", status_code=201)
async def assign_charge(
    app_id: uuid.UUID, payload: ChargeIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:create")),
):
    app = await _staff_application(db, app_id, user)
    if app.application_status != "approved":
        raise HTTPException(409, "Approve the admission before assigning an admission charge")
    charge = AdmissionCharge(
        tenant_id=user.tenant_id, application_id=app.id, **payload.model_dump(),
        created_by=user.id, updated_by=user.id,
    )
    db.add(charge)
    app.fee_status, app.updated_by = "unpaid", user.id
    await db.flush()
    return await _application_view(db, app)


@router.post("/admissions/applications/{app_id}/charges/{charge_id}/pay")
async def collect_admission_payment(
    app_id: uuid.UUID, charge_id: uuid.UUID, payload: PaymentIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:create")),
):
    app = await _staff_application(db, app_id, user)
    charge = await db.get(AdmissionCharge, charge_id)
    if not charge or charge.application_id != app.id:
        raise HTTPException(404, "Admission charge not found")
    if charge.payment_status == "paid":
        raise HTTPException(409, "Admission charge is already paid")
    charge.paid_amount = min(Decimal(charge.amount), Decimal(charge.paid_amount) + payload.amount)
    charge.payment_status = "paid" if charge.paid_amount >= charge.amount else "partial"
    charge.payment_method, charge.payment_reference = payload.method, payload.reference
    charge.paid_at = date.today()
    if not charge.receipt_no:
        charge.receipt_no = f"ADMRCPT-{date.today().year}-{str(charge.id)[:8].upper()}"
    charge.updated_by = user.id
    all_charges = (await db.execute(select(AdmissionCharge).where(
        AdmissionCharge.application_id == app.id, AdmissionCharge.is_deleted.is_(False)
    ))).scalars().all()
    app.fee_status = "paid" if all(c.payment_status == "paid" for c in all_charges) else "partial"
    app.updated_by = user.id
    await record_audit(db, action="collect_admission_fee", entity="AdmissionCharge",
                       entity_id=charge.id, actor=user, changes={"amount": str(payload.amount)})
    return await _application_view(db, app)


@router.post("/admissions/applications/{app_id}/enroll")
async def enroll_application(
    app_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("student_information_system:create")),
):
    app = await _staff_application(db, app_id, user)
    if app.application_status != "approved":
        raise HTTPException(409, "Only approved applications can be enrolled")
    if app.fee_status not in ("paid", "waived"):
        raise HTTPException(409, "Admission fee must be paid or waived before enrollment")
    lead = await db.get(AdmissionLead, app.lead_id)
    if not lead:
        raise HTTPException(404, "Admission profile not found")
    section = await db.get(Section, app.target_section_id) if app.target_section_id else None
    if section:
        occupied = (await db.execute(select(func.count()).select_from(Student).where(
            Student.tenant_id == user.tenant_id, Student.section_id == section.id,
            Student.enrollment_status == "enrolled", Student.is_deleted.is_(False),
        ))).scalar_one()
        if occupied >= section.capacity:
            raise HTTPException(409, f"Section {section.name} has reached its capacity")
    if app.application_type == "continuing":
        student = await db.get(Student, app.existing_student_id)
        if not student:
            raise HTTPException(404, "Existing student not found")
        old_grade = await db.get(Grade, student.grade_id) if student.grade_id else None
        old_year = await db.get(AcademicYear, student.academic_year_id) if student.academic_year_id else None
        old_section = await db.get(Section, student.section_id) if student.section_id else None
        if old_grade:
            db.add(StudentAcademicHistory(
                tenant_id=user.tenant_id, student_id=student.id,
                academic_year=old_year.name if old_year else "—", grade=old_grade.name,
                section=old_section.name if old_section else None, result="promoted",
                remarks=f"Promoted through {app.application_no}",
                created_by=user.id, updated_by=user.id,
            ))
        student.grade_id, student.academic_year_id = app.target_grade_id, app.academic_year_id
        student.section_id, student.enrollment_status = app.target_section_id, "enrolled"
        student.updated_by = user.id
    else:
        count = (await db.execute(select(func.count()).select_from(Student).where(
            Student.tenant_id == user.tenant_id
        ))).scalar_one()
        names = lead.student_name.strip().split(" ", 1)
        student = Student(
            tenant_id=user.tenant_id, admission_no=f"ADM{date.today().year}{count + 1:05d}",
            first_name=names[0], last_name=names[1] if len(names) > 1 else None,
            grade_id=app.target_grade_id, academic_year_id=app.academic_year_id,
            section_id=app.target_section_id, phone=lead.phone, email=lead.email,
            enrollment_status="enrolled", admission_date=date.today(),
            date_of_birth=lead.date_of_birth, gender=lead.gender, category=lead.category,
            religion=lead.religion, nationality=lead.nationality, address=lead.address,
            city=lead.city, state=lead.state, pincode=lead.pincode,
            previous_school=lead.previous_school, created_by=user.id, updated_by=user.id,
            fee_category=app.fee_category, government_aid_percent=app.government_aid_percent,
        )
        db.add(student)
        await db.flush()
        for relation, name, phone, occupation, annual_income in (
            ("father", lead.father_name, lead.father_phone, lead.father_occupation, lead.father_annual_income),
            ("mother", lead.mother_name, lead.mother_phone, lead.mother_occupation, lead.mother_annual_income),
            (lead.guardian_relation or "guardian", lead.guardian_name, lead.guardian_phone,
             lead.guardian_occupation, lead.guardian_annual_income),
        ):
            if name:
                db.add(Guardian(
                    tenant_id=user.tenant_id, student_id=student.id, relation=relation,
                    full_name=name, phone=phone, occupation=occupation, annual_income=annual_income,
                    is_primary=relation == "father" or (not lead.father_name and relation != "mother"),
                    created_by=user.id, updated_by=user.id,
                ))
    lead.converted_student_id, lead.stage, lead.updated_by = student.id, "enrolled", user.id
    app.application_status, app.updated_by = "enrolled", user.id
    await record_audit(db, action="enroll", entity="AdmissionApplication",
                       entity_id=app.id, actor=user, changes={"student_id": str(student.id)})
    return {"application_no": app.application_no, "student_id": str(student.id),
            "admission_no": student.admission_no, "status": "enrolled"}
