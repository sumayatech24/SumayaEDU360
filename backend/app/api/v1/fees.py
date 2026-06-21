"""Fee collection — record payments and keep invoice balances in sync."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.fees import Invoice, Payment

router = APIRouter(prefix="/fees", tags=["Fees"])


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


def _status(net: Decimal, paid: Decimal, due: date | None) -> str:
    if paid <= 0:
        base = "unpaid"
    elif paid < net:
        base = "partial"
    else:
        return "paid"
    if due and due < date.today():
        return "overdue"
    return base


@router.post("/payments", response_model=PaymentOut, status_code=201)
async def record_payment(
    payload: PaymentIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:create")),
):
    invoice = await db.get(Invoice, payload.invoice_id)
    if not invoice or invoice.tenant_id != user.tenant_id or invoice.is_deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invoice not found")
    if payload.amount <= 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Amount must be positive")

    # Generate a sequential receipt number per tenant.
    count = (
        await db.execute(select(func.count()).select_from(Payment).where(Payment.tenant_id == user.tenant_id))
    ).scalar_one()
    receipt_no = f"RCPT-{count + 1:06d}"

    payment = Payment(
        tenant_id=user.tenant_id, receipt_no=receipt_no, invoice_id=invoice.id,
        student_id=invoice.student_id, amount=payload.amount, method=payload.method,
        reference=payload.reference, paid_at=payload.paid_at or date.today(),
        created_by=user.id, updated_by=user.id,
    )
    db.add(payment)

    invoice.paid_amount = (invoice.paid_amount or Decimal(0)) + payload.amount
    invoice.payment_status = _status(invoice.net_amount or Decimal(0), invoice.paid_amount, invoice.due_date)
    invoice.updated_by = user.id

    await db.flush()
    await record_audit(db, action="create", entity="Payment", entity_id=payment.id, actor=user,
                       changes={"invoice_id": str(invoice.id), "amount": str(payload.amount)})
    await db.refresh(payment)
    return payment


@router.get("/invoices/{invoice_id}/payments", response_model=list[PaymentOut])
async def list_invoice_payments(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    rows = (
        await db.execute(
            select(Payment).where(
                Payment.tenant_id == user.tenant_id, Payment.invoice_id == invoice_id,
                Payment.is_deleted.is_(False),
            ).order_by(Payment.created_at.desc())
        )
    ).scalars().all()
    return rows


@router.get("/students/{student_id}/ledger")
async def student_ledger(
    student_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("fees_billing:read")),
):
    invoices = (
        await db.execute(
            select(Invoice).where(
                Invoice.tenant_id == user.tenant_id, Invoice.student_id == student_id,
                Invoice.is_deleted.is_(False),
            )
        )
    ).scalars().all()
    total_net = sum((i.net_amount or Decimal(0)) for i in invoices)
    total_paid = sum((i.paid_amount or Decimal(0)) for i in invoices)
    return {
        "student_id": str(student_id),
        "invoice_count": len(invoices),
        "total_billed": str(total_net),
        "total_paid": str(total_paid),
        "balance": str(total_net - total_paid),
        "invoices": [
            {
                "id": str(i.id), "invoice_no": i.invoice_no, "net_amount": str(i.net_amount),
                "paid_amount": str(i.paid_amount), "payment_status": i.payment_status,
                "due_date": i.due_date.isoformat() if i.due_date else None,
            }
            for i in invoices
        ],
    }
