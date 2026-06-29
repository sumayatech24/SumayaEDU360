"""Academic-year fee configuration, installments, aid, collection and reminders."""
from __future__ import annotations

import calendar
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.academic import AcademicYear, Grade, Section
from app.models.auth import User
from app.models.fees import (
    CashierSession,
    FeeInstallment,
    FeePlan,
    FeePlanComponent,
    FeeReminder,
    FeeRefund,
    Invoice,
    InvoiceLineItem,
    Payment,
    PaymentReconciliation,
    StudentFeeAccount,
)
from app.models.meta import Notification
from app.models.people import Employee, Guardian, Student

router = APIRouter(prefix="/fees", tags=["Fees"])


def _add_months(value: date, months: int) -> date:
    month = value.month - 1 + months
    year = value.year + month // 12
    month = month % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _status(net: Decimal, paid: Decimal, due: date | None) -> str:
    if paid >= net:
        return "paid"
    if due and due < date.today():
        return "overdue"
    return "partial" if paid > 0 else "unpaid"


class FeeComponentIn(BaseModel):
    head: str
    amount: Decimal = Field(gt=0)
    is_optional: bool = False
    aid_eligible: bool = False


class FeePlanIn(BaseModel):
    name: str
    code: str
    academic_year_id: uuid.UUID
    grade_id: uuid.UUID | None = None
    frequency: str = "annual"
    first_due_date: date
    allow_partial_payment: bool = True
    description: str | None = None
    components: list[FeeComponentIn]


class FeeAssignmentIn(BaseModel):
    fee_plan_id: uuid.UUID
    grade_id: uuid.UUID | None = None
    section_id: uuid.UUID | None = None
    student_ids: list[uuid.UUID] | None = None
    government_aid_percent: Decimal | None = Field(default=None, ge=0, le=100)
    scholarship_amount: Decimal = Field(default=Decimal(0), ge=0)


class PaymentIn(BaseModel):
    invoice_id: uuid.UUID
    amount: Decimal
    method: str = "cash"
    reference: str | None = None
    paid_at: date | None = None


class PaymentOut(BaseModel):
    id: uuid.UUID
    receipt_no: str
    invoice_id: uuid.UUID
    student_id: uuid.UUID
    amount: Decimal
    method: str
    reference: str | None = None
    paid_at: date | None = None

    class Config:
        from_attributes = True


class ReminderIn(BaseModel):
    invoice_ids: list[uuid.UUID]
    channels: list[str] = ["in_app"]


class RefundIn(BaseModel):
    payment_id: uuid.UUID
    amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=3, max_length=1000)


class RefundDecisionIn(BaseModel):
    decision: str
    reference: str | None = None


class ReconciliationIn(BaseModel):
    provider: str
    provider_reference: str
    payment_id: uuid.UUID | None = None
    expected_amount: Decimal = Field(ge=0)
    settled_amount: Decimal = Field(ge=0)
    settlement_date: date | None = None
    notes: str | None = None


class CashierOpenIn(BaseModel):
    opening_float: Decimal = Field(default=Decimal(0), ge=0)


class CashierCloseIn(BaseModel):
    counted_cash: Decimal = Field(ge=0)
    notes: str | None = None


@router.post("/plans", status_code=201)
async def create_fee_plan(
    payload: FeePlanIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:create")),
):
    if payload.frequency not in ("annual", "half_yearly", "quarterly"):
        raise HTTPException(422, "Frequency must be annual, half_yearly or quarterly")
    if not payload.components:
        raise HTTPException(422, "Add at least one fee component")
    existing = (await db.execute(select(FeePlan).where(
        FeePlan.tenant_id == user.tenant_id,
        FeePlan.code == payload.code,
        FeePlan.is_deleted.is_(False),
    ))).scalars().first()
    if existing:
        raise HTTPException(409, "Fee plan code already exists")
    count = {"annual": 1, "half_yearly": 2, "quarterly": 4}[payload.frequency]
    plan = FeePlan(
        tenant_id=user.tenant_id,
        name=payload.name,
        code=payload.code,
        academic_year_id=payload.academic_year_id,
        grade_id=payload.grade_id,
        frequency=payload.frequency,
        installment_count=count,
        allow_partial_payment=payload.allow_partial_payment,
        amount=sum((item.amount for item in payload.components), Decimal(0)),
        description=payload.description,
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(plan)
    await db.flush()
    for item in payload.components:
        db.add(FeePlanComponent(
            tenant_id=user.tenant_id,
            fee_plan_id=plan.id,
            head=item.head,
            amount=item.amount,
            is_optional=item.is_optional,
            aid_eligible=item.aid_eligible,
            created_by=user.id,
            updated_by=user.id,
        ))
    month_step = 12 // count
    for index in range(count):
        db.add(FeeInstallment(
            tenant_id=user.tenant_id,
            fee_plan_id=plan.id,
            name=f"Installment {index + 1}",
            sequence=index + 1,
            due_date=_add_months(payload.first_due_date, index * month_step),
            percentage=Decimal(100) / count,
            created_by=user.id,
            updated_by=user.id,
        ))
    await db.flush()
    await record_audit(db, action="create", entity="FeePlan", entity_id=plan.id, actor=user)
    return {"id": str(plan.id), "amount": str(plan.amount), "installment_count": count}


@router.get("/plans")
async def list_fee_plans(
    academic_year_id: uuid.UUID | None = None,
    grade_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    conditions = [FeePlan.tenant_id == user.tenant_id, FeePlan.is_deleted.is_(False)]
    if academic_year_id:
        conditions.append(FeePlan.academic_year_id == academic_year_id)
    if grade_id:
        conditions.append(FeePlan.grade_id.in_([grade_id, None]))
    plans = (await db.execute(select(FeePlan).where(*conditions).order_by(FeePlan.name))).scalars().all()
    components = (await db.execute(select(FeePlanComponent).where(
        FeePlanComponent.tenant_id == user.tenant_id,
        FeePlanComponent.fee_plan_id.in_([plan.id for plan in plans]) if plans else FeePlanComponent.fee_plan_id.is_(None),
        FeePlanComponent.is_deleted.is_(False),
    ))).scalars().all()
    installments = (await db.execute(select(FeeInstallment).where(
        FeeInstallment.tenant_id == user.tenant_id,
        FeeInstallment.fee_plan_id.in_([plan.id for plan in plans]) if plans else FeeInstallment.fee_plan_id.is_(None),
        FeeInstallment.is_deleted.is_(False),
    ).order_by(FeeInstallment.sequence))).scalars().all()
    return [
        {
            "id": str(plan.id),
            "name": plan.name,
            "code": plan.code,
            "academic_year_id": str(plan.academic_year_id) if plan.academic_year_id else None,
            "grade_id": str(plan.grade_id) if plan.grade_id else None,
            "frequency": plan.frequency,
            "amount": str(plan.amount),
            "allow_partial_payment": plan.allow_partial_payment,
            "components": [
                {
                    "id": str(item.id), "head": item.head, "amount": str(item.amount),
                    "is_optional": item.is_optional, "aid_eligible": item.aid_eligible,
                }
                for item in components if item.fee_plan_id == plan.id
            ],
            "installments": [
                {
                    "id": str(item.id), "name": item.name, "sequence": item.sequence,
                    "due_date": item.due_date.isoformat(), "percentage": str(item.percentage),
                }
                for item in installments if item.fee_plan_id == plan.id
            ],
        }
        for plan in plans
    ]


@router.post("/assign", status_code=201)
async def assign_fee_plan(
    payload: FeeAssignmentIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:create")),
):
    plan = await db.get(FeePlan, payload.fee_plan_id)
    if not plan or plan.tenant_id != user.tenant_id or plan.is_deleted:
        raise HTTPException(404, "Fee plan not found")
    student_conditions = [
        Student.tenant_id == user.tenant_id,
        Student.enrollment_status == "enrolled",
        Student.is_deleted.is_(False),
    ]
    if payload.student_ids:
        student_conditions.append(Student.id.in_(payload.student_ids))
    if payload.grade_id:
        student_conditions.append(Student.grade_id == payload.grade_id)
    elif plan.grade_id:
        student_conditions.append(Student.grade_id == plan.grade_id)
    if payload.section_id:
        student_conditions.append(Student.section_id == payload.section_id)
    students = (await db.execute(select(Student).where(*student_conditions))).scalars().all()
    if not students:
        raise HTTPException(409, "No enrolled students match this assignment")
    components = (await db.execute(select(FeePlanComponent).where(
        FeePlanComponent.tenant_id == user.tenant_id,
        FeePlanComponent.fee_plan_id == plan.id,
        FeePlanComponent.is_deleted.is_(False),
    ))).scalars().all()
    installments = (await db.execute(select(FeeInstallment).where(
        FeeInstallment.tenant_id == user.tenant_id,
        FeeInstallment.fee_plan_id == plan.id,
        FeeInstallment.is_deleted.is_(False),
    ).order_by(FeeInstallment.sequence))).scalars().all()
    if not installments:
        raise HTTPException(409, "Fee plan has no installments")

    generated = 0
    for student in students:
        account = (await db.execute(select(StudentFeeAccount).where(
            StudentFeeAccount.tenant_id == user.tenant_id,
            StudentFeeAccount.student_id == student.id,
            StudentFeeAccount.fee_plan_id == plan.id,
            StudentFeeAccount.is_deleted.is_(False),
        ))).scalars().first()
        aid_percent = payload.government_aid_percent
        if aid_percent is None:
            aid_percent = Decimal(student.government_aid_percent or 0)
        if not account:
            account = StudentFeeAccount(
                tenant_id=user.tenant_id,
                student_id=student.id,
                fee_plan_id=plan.id,
                academic_year_id=plan.academic_year_id,
                fee_category=student.fee_category or "regular",
                government_aid_percent=aid_percent,
                scholarship_amount=payload.scholarship_amount,
                created_by=user.id,
                updated_by=user.id,
            )
            db.add(account)
            await db.flush()
        for installment in installments:
            existing = (await db.execute(select(Invoice).where(
                Invoice.tenant_id == user.tenant_id,
                Invoice.student_id == student.id,
                Invoice.installment_id == installment.id,
                Invoice.is_deleted.is_(False),
            ))).scalars().first()
            if existing:
                continue
            ratio = Decimal(installment.percentage) / Decimal(100)
            gross = sum((Decimal(component.amount) * ratio for component in components), Decimal(0))
            aid = sum((
                Decimal(component.amount) * ratio * Decimal(account.government_aid_percent) / Decimal(100)
                for component in components if component.aid_eligible
            ), Decimal(0))
            scholarship = Decimal(account.scholarship_amount or 0) * ratio
            net = max(gross - aid - scholarship, Decimal(0))
            invoice = Invoice(
                tenant_id=user.tenant_id,
                invoice_no=f"FEE-{plan.code}-{student.admission_no}-{installment.sequence}",
                student_id=student.id,
                fee_plan_id=plan.id,
                fee_account_id=account.id,
                installment_id=installment.id,
                academic_year_id=plan.academic_year_id,
                issue_date=date.today(),
                due_date=installment.due_date,
                gross_amount=gross,
                government_aid_amount=aid,
                discount_amount=scholarship,
                net_amount=net,
                paid_amount=Decimal(0),
                payment_status="paid" if net == 0 else _status(net, Decimal(0), installment.due_date),
                created_by=user.id,
                updated_by=user.id,
            )
            db.add(invoice)
            await db.flush()
            for component in components:
                component_gross = Decimal(component.amount) * ratio
                component_aid = (
                    component_gross * Decimal(account.government_aid_percent) / Decimal(100)
                    if component.aid_eligible else Decimal(0)
                )
                db.add(InvoiceLineItem(
                    tenant_id=user.tenant_id,
                    invoice_id=invoice.id,
                    fee_component_id=component.id,
                    head=component.head,
                    gross_amount=component_gross,
                    government_aid_amount=component_aid,
                    discount_amount=Decimal(0),
                    net_amount=component_gross - component_aid,
                    created_by=user.id,
                    updated_by=user.id,
                ))
            generated += 1
    await db.flush()
    await record_audit(
        db, action="assign_fee_plan", entity="FeePlan", entity_id=plan.id, actor=user,
        changes={"students": len(students), "invoices": generated},
    )
    return {"students": len(students), "invoices_generated": generated}


@router.get("/dues")
async def fee_dues(
    academic_year_id: uuid.UUID | None = None,
    grade_id: uuid.UUID | None = None,
    section_id: uuid.UUID | None = None,
    installment_id: uuid.UUID | None = None,
    payment_status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    students = (await db.execute(select(Student).where(
        Student.tenant_id == user.tenant_id, Student.is_deleted.is_(False)
    ))).scalars().all()
    student_map = {student.id: student for student in students}
    allowed_students = {
        student.id for student in students
        if (not grade_id or student.grade_id == grade_id)
        and (not section_id or student.section_id == section_id)
    }
    conditions = [
        Invoice.tenant_id == user.tenant_id,
        Invoice.student_id.in_(allowed_students) if allowed_students else Invoice.student_id.is_(None),
        Invoice.is_deleted.is_(False),
    ]
    if academic_year_id:
        conditions.append(Invoice.academic_year_id == academic_year_id)
    if installment_id:
        conditions.append(Invoice.installment_id == installment_id)
    if payment_status:
        conditions.append(Invoice.payment_status == payment_status)
    invoices = (await db.execute(select(Invoice).where(*conditions).order_by(
        Invoice.due_date, Invoice.invoice_no
    ))).scalars().all()
    invoice_ids = [invoice.id for invoice in invoices]
    lines = (await db.execute(select(InvoiceLineItem).where(
        InvoiceLineItem.tenant_id == user.tenant_id,
        InvoiceLineItem.invoice_id.in_(invoice_ids) if invoice_ids else InvoiceLineItem.invoice_id.is_(None),
        InvoiceLineItem.is_deleted.is_(False),
    ))).scalars().all()
    installments = {
        item.id: item for item in (await db.execute(select(FeeInstallment).where(
            FeeInstallment.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    years = {
        item.id: item.name for item in (await db.execute(select(AcademicYear).where(
            AcademicYear.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    grades = {
        item.id: item.name for item in (await db.execute(select(Grade).where(
            Grade.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    sections = {
        item.id: item for item in (await db.execute(select(Section).where(
            Section.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    employees = {
        item.id: f"{item.first_name} {item.last_name or ''}".strip()
        for item in (await db.execute(select(Employee).where(
            Employee.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    rows = []
    for invoice in invoices:
        student = student_map[invoice.student_id]
        section = sections.get(student.section_id)
        balance = Decimal(invoice.net_amount) - Decimal(invoice.paid_amount)
        rows.append({
            "id": str(invoice.id),
            "invoice_no": invoice.invoice_no,
            "student_id": str(student.id),
            "student": f"{student.first_name} {student.last_name or ''}".strip(),
            "admission_no": student.admission_no,
            "academic_year": years.get(invoice.academic_year_id, "—"),
            "grade": grades.get(student.grade_id, "—"),
            "section": section.name if section else "—",
            "class_teacher": employees.get(section.class_teacher_id, "Not assigned") if section else "Not assigned",
            "installment_id": str(invoice.installment_id) if invoice.installment_id else None,
            "installment": installments[invoice.installment_id].name if invoice.installment_id in installments else "Annual",
            "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
            "gross_amount": str(invoice.gross_amount),
            "government_aid_amount": str(invoice.government_aid_amount),
            "discount_amount": str(invoice.discount_amount),
            "net_amount": str(invoice.net_amount),
            "paid_amount": str(invoice.paid_amount),
            "balance": str(balance),
            "payment_status": _status(Decimal(invoice.net_amount), Decimal(invoice.paid_amount), invoice.due_date),
            "fee_category": student.fee_category,
            "components": [
                {
                    "head": line.head, "gross_amount": str(line.gross_amount),
                    "aid_amount": str(line.government_aid_amount), "net_amount": str(line.net_amount),
                }
                for line in lines if line.invoice_id == invoice.id
            ],
        })
    return {
        "rows": rows,
        "summary": {
            "invoices": len(rows),
            "billed": str(sum((Decimal(row["net_amount"]) for row in rows), Decimal(0))),
            "paid": str(sum((Decimal(row["paid_amount"]) for row in rows), Decimal(0))),
            "pending": str(sum((Decimal(row["balance"]) for row in rows), Decimal(0))),
            "overdue": sum(row["payment_status"] == "overdue" for row in rows),
        },
    }


@router.post("/reminders")
async def send_fee_reminders(
    payload: ReminderIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:create")),
):
    allowed_channels = {"in_app", "email", "whatsapp"}
    if not payload.channels or set(payload.channels) - allowed_channels:
        raise HTTPException(422, "Channels must be in_app, email or whatsapp")
    invoices = (await db.execute(select(Invoice).where(
        Invoice.tenant_id == user.tenant_id,
        Invoice.id.in_(payload.invoice_ids),
        Invoice.is_deleted.is_(False),
    ))).scalars().all()
    students = {
        item.id: item for item in (await db.execute(select(Student).where(
            Student.tenant_id == user.tenant_id
        ))).scalars().all()
    }
    guardians = (await db.execute(select(Guardian).where(
        Guardian.tenant_id == user.tenant_id,
        Guardian.student_id.in_([invoice.student_id for invoice in invoices]) if invoices else Guardian.student_id.is_(None),
        Guardian.is_deleted.is_(False),
    ))).scalars().all()
    guardian_by_student = {}
    for guardian in guardians:
        if guardian.student_id not in guardian_by_student or guardian.is_primary:
            guardian_by_student[guardian.student_id] = guardian
    parent_users = {
        item.person_id: item for item in (await db.execute(select(User).where(
            User.tenant_id == user.tenant_id,
            User.person_type == "student",
            User.person_id.in_([invoice.student_id for invoice in invoices]) if invoices else User.person_id.is_(None),
            User.is_deleted.is_(False),
        ))).scalars().all()
    }
    queued = 0
    for invoice in invoices:
        student = students[invoice.student_id]
        guardian = guardian_by_student.get(student.id)
        balance = Decimal(invoice.net_amount) - Decimal(invoice.paid_amount)
        if balance <= 0:
            continue
        message = (
            f"Fee reminder for {student.first_name}: {invoice.invoice_no} has "
            f"INR {balance} due by {invoice.due_date.isoformat() if invoice.due_date else 'the due date'}."
        )
        for channel in payload.channels:
            destination = (
                guardian.email if channel == "email" and guardian else
                guardian.phone if channel == "whatsapp" and guardian else
                str(parent_users[student.id].id) if channel == "in_app" and student.id in parent_users else None
            )
            delivery_status = "sent" if channel == "in_app" and destination else "queued"
            db.add(FeeReminder(
                tenant_id=user.tenant_id,
                invoice_id=invoice.id,
                student_id=student.id,
                guardian_id=guardian.id if guardian else None,
                channel=channel,
                destination=destination,
                message=message,
                delivery_status=delivery_status,
                sent_at=datetime.now(timezone.utc) if delivery_status == "sent" else None,
                created_by=user.id,
                updated_by=user.id,
            ))
            if channel == "in_app" and student.id in parent_users:
                db.add(Notification(
                    tenant_id=user.tenant_id,
                    user_id=parent_users[student.id].id,
                    channel="in_app",
                    title="Fee payment reminder",
                    body=message,
                    payload={"invoice_id": str(invoice.id), "balance": str(balance)},
                    created_by=user.id,
                    updated_by=user.id,
                ))
            queued += 1
    await db.flush()
    await record_audit(
        db, action="send_fee_reminders", entity="Invoice", actor=user,
        changes={"invoices": len(invoices), "deliveries": queued, "channels": payload.channels},
    )
    return {
        "invoices": len(invoices),
        "deliveries_created": queued,
        "note": "In-app reminders are sent immediately; email and WhatsApp remain queued for configured providers.",
    }


@router.post("/payments", response_model=PaymentOut, status_code=201)
async def record_payment(
    payload: PaymentIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:create")),
):
    invoice = await db.get(Invoice, payload.invoice_id)
    if not invoice or invoice.tenant_id != user.tenant_id or invoice.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    balance = Decimal(invoice.net_amount) - Decimal(invoice.paid_amount)
    if payload.amount <= 0:
        raise HTTPException(422, "Amount must be positive")
    if payload.amount > balance:
        raise HTTPException(422, f"Payment cannot exceed outstanding balance {balance}")
    count = (await db.execute(select(func.count()).select_from(Payment).where(
        Payment.tenant_id == user.tenant_id
    ))).scalar_one()
    payment = Payment(
        tenant_id=user.tenant_id,
        receipt_no=f"RCPT-{count + 1:06d}",
        invoice_id=invoice.id,
        student_id=invoice.student_id,
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        paid_at=payload.paid_at or date.today(),
        created_by=user.id,
        updated_by=user.id,
    )
    db.add(payment)
    invoice.paid_amount = Decimal(invoice.paid_amount) + payload.amount
    invoice.payment_status = _status(Decimal(invoice.net_amount), Decimal(invoice.paid_amount), invoice.due_date)
    invoice.updated_by = user.id
    await db.flush()
    await record_audit(
        db, action="create", entity="Payment", entity_id=payment.id, actor=user,
        changes={"invoice_id": str(invoice.id), "amount": str(payload.amount)},
    )
    await db.refresh(payment)
    return payment


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentOut])
async def list_invoice_payments(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    return (await db.execute(select(Payment).where(
        Payment.tenant_id == user.tenant_id,
        Payment.invoice_id == invoice_id,
        Payment.is_deleted.is_(False),
    ).order_by(Payment.created_at.desc()))).scalars().all()


@router.get("/payments")
async def list_payments(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    rows = (await db.execute(select(Payment).where(
        Payment.tenant_id == user.tenant_id, Payment.is_deleted.is_(False),
    ).order_by(Payment.created_at.desc()).limit(200))).scalars().all()
    students = {
        s.id: f"{s.first_name} {s.last_name or ''}".strip()
        for s in (await db.execute(select(Student).where(Student.tenant_id == user.tenant_id))).scalars().all()
    }
    return [{
        "id": str(p.id), "receipt_no": p.receipt_no, "invoice_id": str(p.invoice_id),
        "student": students.get(p.student_id, "—"), "amount": str(p.amount),
        "method": p.method, "reference": p.reference,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
    } for p in rows]


@router.get("/students/{student_id}/ledger")
async def student_ledger(
    student_id: uuid.UUID,
    academic_year_id: uuid.UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    conditions = [
        Invoice.tenant_id == user.tenant_id,
        Invoice.student_id == student_id,
        Invoice.is_deleted.is_(False),
    ]
    if academic_year_id:
        conditions.append(Invoice.academic_year_id == academic_year_id)
    invoices = (await db.execute(select(Invoice).where(*conditions))).scalars().all()
    total_net = sum((Decimal(invoice.net_amount) for invoice in invoices), Decimal(0))
    total_paid = sum((Decimal(invoice.paid_amount) for invoice in invoices), Decimal(0))
    return {
        "student_id": str(student_id),
        "invoice_count": len(invoices),
        "total_billed": str(total_net),
        "total_paid": str(total_paid),
        "balance": str(total_net - total_paid),
        "invoices": [
            {
                "id": str(invoice.id), "invoice_no": invoice.invoice_no,
                "net_amount": str(invoice.net_amount), "paid_amount": str(invoice.paid_amount),
                "payment_status": _status(Decimal(invoice.net_amount), Decimal(invoice.paid_amount), invoice.due_date),
                "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
                "installment_id": str(invoice.installment_id) if invoice.installment_id else None,
                "government_aid_amount": str(invoice.government_aid_amount),
            }
            for invoice in invoices
        ],
    }


@router.get("/refunds")
async def list_refunds(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    rows = (await db.execute(select(FeeRefund).where(
        FeeRefund.tenant_id == user.tenant_id, FeeRefund.is_deleted.is_(False),
    ).order_by(FeeRefund.created_at.desc()))).scalars().all()
    return [{
        "id": str(r.id), "refund_no": r.refund_no, "payment_id": str(r.payment_id),
        "invoice_id": str(r.invoice_id), "student_id": str(r.student_id),
        "amount": str(r.amount), "reason": r.reason, "status": r.refund_status,
        "reference": r.reference, "processed_at": r.processed_at.isoformat() if r.processed_at else None,
    } for r in rows]


@router.post("/refunds", status_code=201)
async def request_refund(
    payload: RefundIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:update")),
):
    payment = await db.get(Payment, payload.payment_id)
    if not payment or payment.tenant_id != user.tenant_id or payment.is_deleted:
        raise HTTPException(404, "Payment not found")
    prior = (await db.execute(select(func.coalesce(func.sum(FeeRefund.amount), 0)).where(
        FeeRefund.tenant_id == user.tenant_id, FeeRefund.payment_id == payment.id,
        FeeRefund.refund_status.in_(("requested", "approved", "processed")),
        FeeRefund.is_deleted.is_(False),
    ))).scalar_one()
    if Decimal(prior) + payload.amount > Decimal(payment.amount):
        raise HTTPException(409, "Refund exceeds the unrefunded payment amount")
    count = (await db.execute(select(func.count()).select_from(FeeRefund).where(
        FeeRefund.tenant_id == user.tenant_id
    ))).scalar_one()
    row = FeeRefund(
        tenant_id=user.tenant_id, refund_no=f"REF-{date.today().year}-{count + 1:05d}",
        payment_id=payment.id, invoice_id=payment.invoice_id, student_id=payment.student_id,
        amount=payload.amount, reason=payload.reason, created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(db, action="request", entity="FeeRefund", entity_id=row.id, actor=user)
    return {"id": str(row.id), "refund_no": row.refund_no, "status": row.refund_status}


@router.post("/refunds/{refund_id}/decision")
async def decide_refund(
    refund_id: uuid.UUID,
    payload: RefundDecisionIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:approve")),
):
    row = await db.get(FeeRefund, refund_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "Refund not found")
    if payload.decision not in ("approved", "rejected", "processed"):
        raise HTTPException(422, "Decision must be approved, rejected or processed")
    if payload.decision in ("approved", "rejected") and row.refund_status != "requested":
        raise HTTPException(409, "Only requested refunds can be approved or rejected")
    if payload.decision == "processed":
        if row.refund_status != "approved":
            raise HTTPException(409, "Only an approved refund can be processed")
        invoice = await db.get(Invoice, row.invoice_id)
        if not invoice:
            raise HTTPException(409, "Refund invoice is unavailable")
        invoice.paid_amount = max(Decimal(invoice.paid_amount) - Decimal(row.amount), Decimal(0))
        invoice.payment_status = _status(Decimal(invoice.net_amount), Decimal(invoice.paid_amount), invoice.due_date)
        row.processed_at = datetime.now(timezone.utc)
        row.reference = payload.reference
    if payload.decision == "approved":
        row.approved_by = user.id
    row.refund_status, row.updated_by = payload.decision, user.id
    await record_audit(db, action=payload.decision, entity="FeeRefund", entity_id=row.id, actor=user)
    return {"id": str(row.id), "status": row.refund_status}


@router.get("/reconciliations")
async def list_reconciliations(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    rows = (await db.execute(select(PaymentReconciliation).where(
        PaymentReconciliation.tenant_id == user.tenant_id,
        PaymentReconciliation.is_deleted.is_(False),
    ).order_by(PaymentReconciliation.created_at.desc()))).scalars().all()
    return [{
        "id": str(r.id), "provider": r.provider, "provider_reference": r.provider_reference,
        "payment_id": str(r.payment_id) if r.payment_id else None,
        "expected_amount": str(r.expected_amount), "settled_amount": str(r.settled_amount),
        "settlement_date": r.settlement_date.isoformat() if r.settlement_date else None,
        "status": r.reconciliation_status, "notes": r.notes,
    } for r in rows]


@router.post("/reconciliations", status_code=201)
async def reconcile_payment(
    payload: ReconciliationIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:update")),
):
    payment = await db.get(Payment, payload.payment_id) if payload.payment_id else None
    if payment and (payment.tenant_id != user.tenant_id or payment.is_deleted):
        raise HTTPException(404, "Payment not found")
    if payment and Decimal(payment.amount) != payload.expected_amount:
        raise HTTPException(409, "Expected amount does not match the recorded payment")
    recon_status = "unmatched" if not payment else (
        "matched" if payload.expected_amount == payload.settled_amount else "mismatch"
    )
    row = PaymentReconciliation(
        tenant_id=user.tenant_id, reconciliation_status=recon_status,
        **payload.model_dump(), created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(db, action="reconcile", entity="PaymentReconciliation", entity_id=row.id, actor=user)
    return {"id": str(row.id), "status": recon_status}


@router.get("/cashier-sessions")
async def cashier_sessions(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    rows = (await db.execute(select(CashierSession).where(
        CashierSession.tenant_id == user.tenant_id, CashierSession.is_deleted.is_(False),
    ).order_by(CashierSession.business_date.desc(), CashierSession.opened_at.desc()))).scalars().all()
    return [{
        "id": str(r.id), "business_date": r.business_date.isoformat(),
        "opening_float": str(r.opening_float), "system_cash": str(r.system_cash),
        "counted_cash": str(r.counted_cash) if r.counted_cash is not None else None,
        "variance": str(r.variance) if r.variance is not None else None,
        "status": r.session_status, "notes": r.close_notes,
    } for r in rows]


@router.post("/cashier-sessions/open", status_code=201)
async def open_cashier(
    payload: CashierOpenIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:update")),
):
    existing = (await db.execute(select(CashierSession).where(
        CashierSession.tenant_id == user.tenant_id, CashierSession.cashier_id == user.id,
        CashierSession.session_status == "open", CashierSession.is_deleted.is_(False),
    ))).scalars().first()
    if existing:
        raise HTTPException(409, "Cashier already has an open session")
    row = CashierSession(
        tenant_id=user.tenant_id, cashier_id=user.id, business_date=date.today(),
        opened_at=datetime.now(timezone.utc), opening_float=payload.opening_float,
        created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(db, action="open", entity="CashierSession", entity_id=row.id, actor=user)
    return {"id": str(row.id), "status": "open"}


@router.post("/cashier-sessions/{session_id}/close")
async def close_cashier(
    session_id: uuid.UUID,
    payload: CashierCloseIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:update")),
):
    row = await db.get(CashierSession, session_id)
    if not row or row.tenant_id != user.tenant_id or row.cashier_id != user.id or row.is_deleted:
        raise HTTPException(404, "Cashier session not found")
    if row.session_status != "open":
        raise HTTPException(409, "Cashier session is already closed")
    cash = (await db.execute(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.tenant_id == user.tenant_id, Payment.method == "cash",
        Payment.paid_at == row.business_date, Payment.is_deleted.is_(False),
        Payment.created_by == user.id,
    ))).scalar_one()
    row.system_cash = Decimal(row.opening_float) + Decimal(cash)
    row.counted_cash = payload.counted_cash
    row.variance = payload.counted_cash - Decimal(row.system_cash)
    row.closed_at, row.session_status, row.close_notes = datetime.now(timezone.utc), "closed", payload.notes
    row.updated_by = user.id
    await record_audit(db, action="close", entity="CashierSession", entity_id=row.id, actor=user,
                       changes={"system_cash": row.system_cash, "counted_cash": row.counted_cash,
                                "variance": row.variance})
    return {"id": str(row.id), "status": "closed", "system_cash": str(row.system_cash),
            "counted_cash": str(row.counted_cash), "variance": str(row.variance)}
