"""Library catalog, analytics, acquisitions, purchase orders and receiving."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, require_permission
from app.models.finance import Vendor
from app.models.library import (
    BookIssue,
    LibraryAcquisitionRequest,
    LibraryBook,
    LibraryBookCopy,
    LibraryGoodsReceipt,
    LibraryGoodsReceiptLine,
    LibraryPurchaseOrder,
    LibraryPurchaseOrderLine,
)

router = APIRouter(prefix="/library", tags=["Library"])


class AcquisitionRequestIn(BaseModel):
    book_id: uuid.UUID | None = None
    title: str
    author: str | None = None
    isbn: str | None = None
    quantity: int = Field(default=1, ge=1)
    estimated_unit_price: Decimal = Field(default=Decimal(0), ge=0)
    requested_by_name: str | None = None
    priority: str = "normal"
    reason: str | None = None


class DecisionIn(BaseModel):
    decision: str
    notes: str | None = None


class VendorIn(BaseModel):
    name: str
    code: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    email: str | None = None
    gst_no: str | None = None


class PurchaseOrderLineIn(BaseModel):
    acquisition_request_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None
    title: str
    author: str | None = None
    isbn: str | None = None
    quantity: int = Field(ge=1)
    unit_price: Decimal = Field(ge=0)


class PurchaseOrderIn(BaseModel):
    vendor_id: uuid.UUID
    expected_date: date | None = None
    tax_amount: Decimal = Field(default=Decimal(0), ge=0)
    shipping_amount: Decimal = Field(default=Decimal(0), ge=0)
    notes: str | None = None
    lines: list[PurchaseOrderLineIn] = Field(min_length=1)


class PurchaseOrderActionIn(BaseModel):
    action: str


class ReceiptLineIn(BaseModel):
    purchase_order_line_id: uuid.UUID
    accepted_quantity: int = Field(default=0, ge=0)
    rejected_quantity: int = Field(default=0, ge=0)
    condition_notes: str | None = None


class ReceiptIn(BaseModel):
    vendor_invoice_no: str | None = None
    notes: str | None = None
    lines: list[ReceiptLineIn] = Field(min_length=1)


class RenewIn(BaseModel):
    days: int = Field(default=14, ge=1, le=30)


def money(value) -> str:
    return str(Decimal(value or 0).quantize(Decimal("0.01")))


async def _book(db: AsyncSession, book_id: uuid.UUID, user: CurrentUser) -> LibraryBook:
    book = await db.get(LibraryBook, book_id)
    if not book or book.tenant_id != user.tenant_id or book.is_deleted:
        raise HTTPException(404, "Library book not found")
    return book


async def _po(db: AsyncSession, po_id: uuid.UUID, user: CurrentUser) -> LibraryPurchaseOrder:
    po = await db.get(LibraryPurchaseOrder, po_id)
    if not po or po.tenant_id != user.tenant_id or po.is_deleted:
        raise HTTPException(404, "Library purchase order not found")
    return po


async def _po_view(db: AsyncSession, po: LibraryPurchaseOrder) -> dict:
    vendor = await db.get(Vendor, po.vendor_id)
    lines = (await db.execute(select(LibraryPurchaseOrderLine).where(
        LibraryPurchaseOrderLine.purchase_order_id == po.id,
        LibraryPurchaseOrderLine.is_deleted.is_(False),
    ).order_by(LibraryPurchaseOrderLine.created_at))).scalars().all()
    receipts = (await db.execute(select(LibraryGoodsReceipt).where(
        LibraryGoodsReceipt.purchase_order_id == po.id,
        LibraryGoodsReceipt.is_deleted.is_(False),
    ).order_by(LibraryGoodsReceipt.receipt_date.desc()))).scalars().all()
    return {
        "id": str(po.id), "po_no": po.po_no, "vendor_id": str(po.vendor_id),
        "vendor": vendor.name if vendor else "—", "order_date": po.order_date,
        "expected_date": po.expected_date, "subtotal": money(po.subtotal),
        "tax_amount": money(po.tax_amount), "shipping_amount": money(po.shipping_amount),
        "total_amount": money(po.total_amount), "status": po.po_status, "notes": po.notes,
        "lines": [{
            "id": str(line.id),
            "request_id": str(line.acquisition_request_id) if line.acquisition_request_id else None,
            "book_id": str(line.book_id) if line.book_id else None, "title": line.title,
            "author": line.author, "isbn": line.isbn, "quantity": line.quantity,
            "received_quantity": line.received_quantity, "unit_price": money(line.unit_price),
            "line_amount": money(line.line_amount),
        } for line in lines],
        "receipts": [{
            "id": str(receipt.id), "grn_no": receipt.grn_no, "receipt_date": receipt.receipt_date,
            "vendor_invoice_no": receipt.vendor_invoice_no,
            "accepted_quantity": receipt.accepted_quantity,
            "rejected_quantity": receipt.rejected_quantity,
        } for receipt in receipts],
    }


@router.get("/catalog")
async def catalog(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:read")),
):
    books = (await db.execute(select(LibraryBook).where(
        LibraryBook.tenant_id == user.tenant_id, LibraryBook.is_deleted.is_(False)
    ).order_by(LibraryBook.title))).scalars().all()
    issue_stats = (await db.execute(
        select(BookIssue.book_id, func.count(BookIssue.id), func.max(BookIssue.issue_date))
        .where(BookIssue.tenant_id == user.tenant_id, BookIssue.is_deleted.is_(False))
        .group_by(BookIssue.book_id)
    )).all()
    stats = {row[0]: {"issues": row[1], "last_issue": row[2]} for row in issue_stats}
    return [{
        "id": str(book.id), "title": book.title, "author": book.author, "isbn": book.isbn,
        "category": book.category, "publisher": book.publisher, "shelf": book.shelf,
        "price": money(book.price), "total_copies": book.total_copies,
        "available_copies": book.available_copies,
        "issued_copies": max(0, book.total_copies - book.available_copies),
        "circulation_count": stats.get(book.id, {}).get("issues", 0),
        "last_issued_on": stats.get(book.id, {}).get("last_issue"),
    } for book in books]


@router.get("/performance")
async def performance(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:read")),
):
    books = (await db.execute(select(LibraryBook).where(
        LibraryBook.tenant_id == user.tenant_id, LibraryBook.is_deleted.is_(False)
    ))).scalars().all()
    issues = (await db.execute(select(BookIssue).where(
        BookIssue.tenant_id == user.tenant_id, BookIssue.is_deleted.is_(False)
    ))).scalars().all()
    counts: dict[uuid.UUID, int] = {}
    for issue in issues:
        counts[issue.book_id] = counts.get(issue.book_id, 0) + 1
    book_map = {book.id: book for book in books}
    popular = sorted(books, key=lambda book: counts.get(book.id, 0), reverse=True)[:10]
    categories: dict[str, dict[str, int]] = {}
    for book in books:
        row = categories.setdefault(book.category or "Uncategorised",
                                    {"titles": 0, "copies": 0, "circulations": 0})
        row["titles"] += 1
        row["copies"] += book.total_copies
        row["circulations"] += counts.get(book.id, 0)
    open_issues = [i for i in issues if i.issue_status in ("issued", "overdue")]
    return {
        "summary": {
            "titles": len(books), "total_copies": sum(b.total_copies for b in books),
            "available_copies": sum(b.available_copies for b in books),
            "on_loan": len(open_issues),
            "overdue": sum(1 for i in open_issues if i.due_date < date.today()),
            "lost": sum(1 for i in issues if i.issue_status == "lost"),
            "total_circulations": len(issues),
            "catalog_value": money(sum((b.price or 0) * b.total_copies for b in books)),
        },
        "popular_books": [{
            "id": str(book.id), "title": book.title, "author": book.author,
            "circulations": counts.get(book.id, 0),
            "availability": f"{book.available_copies}/{book.total_copies}",
        } for book in popular],
        "categories": [{"category": key, **value} for key, value in sorted(categories.items())],
        "never_borrowed": [{"id": str(b.id), "title": b.title, "author": b.author}
                           for b in books if counts.get(b.id, 0) == 0],
        "open_loans_by_book": [{
            "book": book_map.get(i.book_id).title if book_map.get(i.book_id) else "—",
            "due_date": i.due_date, "overdue_days": max(0, (date.today() - i.due_date).days),
        } for i in open_issues],
    }


@router.post("/issues/{issue_id}/renew")
async def renew_issue(
    issue_id: uuid.UUID, payload: RenewIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:update")),
):
    issue = await db.get(BookIssue, issue_id)
    if not issue or issue.tenant_id != user.tenant_id or issue.is_deleted:
        raise HTTPException(404, "Book issue not found")
    if issue.issue_status != "issued" or issue.due_date < date.today():
        raise HTTPException(409, "Only a current, non-overdue loan can be renewed")
    if issue.renew_count >= 2:
        raise HTTPException(409, "Maximum renewals reached")
    issue.due_date += timedelta(days=payload.days)
    issue.renew_count += 1
    issue.updated_by = user.id
    await record_audit(db, action="renew", entity="BookIssue", entity_id=issue.id, actor=user,
                       changes={"due_date": issue.due_date, "renew_count": issue.renew_count})
    return {"id": str(issue.id), "due_date": issue.due_date, "renew_count": issue.renew_count}


@router.post("/issues/{issue_id}/lost")
async def mark_issue_lost(
    issue_id: uuid.UUID, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:update")),
):
    issue = await db.get(BookIssue, issue_id)
    if not issue or issue.tenant_id != user.tenant_id or issue.is_deleted:
        raise HTTPException(404, "Book issue not found")
    if issue.issue_status not in ("issued", "overdue"):
        raise HTTPException(409, "Only an open loan can be marked lost")
    book = await _book(db, issue.book_id, user)
    issue.issue_status = "lost"
    issue.fine_amount = Decimal(book.price or 0)
    issue.updated_by = user.id
    await record_audit(db, action="mark_lost", entity="BookIssue", entity_id=issue.id, actor=user,
                       changes={"replacement_charge": money(issue.fine_amount)})
    return {"id": str(issue.id), "status": "lost", "replacement_charge": money(issue.fine_amount)}


@router.get("/vendors")
async def list_library_vendors(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:read")),
):
    rows = (await db.execute(select(Vendor).where(
        Vendor.tenant_id == user.tenant_id, Vendor.is_deleted.is_(False)
    ).order_by(Vendor.name))).scalars().all()
    return [{"id": str(v.id), "name": v.name, "code": v.code, "contact_person": v.contact_person,
             "phone": v.phone, "email": v.email, "gst_no": v.gst_no} for v in rows]


@router.post("/vendors", status_code=201)
async def create_library_vendor(
    payload: VendorIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:create")),
):
    count = (await db.execute(select(func.count()).select_from(Vendor).where(
        Vendor.tenant_id == user.tenant_id
    ))).scalar_one()
    vendor = Vendor(
        tenant_id=user.tenant_id, code=payload.code or f"LIBV-{count + 1:04d}",
        **payload.model_dump(exclude={"code"}), created_by=user.id, updated_by=user.id,
    )
    db.add(vendor)
    await db.flush()
    return {"id": str(vendor.id), "name": vendor.name, "code": vendor.code}


@router.get("/acquisition-requests")
async def list_acquisition_requests(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:read")),
):
    rows = (await db.execute(select(LibraryAcquisitionRequest).where(
        LibraryAcquisitionRequest.tenant_id == user.tenant_id,
        LibraryAcquisitionRequest.is_deleted.is_(False),
    ).order_by(LibraryAcquisitionRequest.created_at.desc()))).scalars().all()
    return [{
        "id": str(row.id), "request_no": row.request_no,
        "book_id": str(row.book_id) if row.book_id else None, "title": row.title,
        "author": row.author, "isbn": row.isbn, "quantity": row.quantity,
        "estimated_unit_price": money(row.estimated_unit_price),
        "requested_by_name": row.requested_by_name, "request_date": row.request_date,
        "priority": row.priority, "reason": row.reason, "status": row.request_status,
        "decision_notes": row.decision_notes,
        "purchase_order_id": str(row.purchase_order_id) if row.purchase_order_id else None,
    } for row in rows]


@router.post("/acquisition-requests", status_code=201)
async def create_acquisition_request(
    payload: AcquisitionRequestIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:create")),
):
    if payload.priority not in ("low", "normal", "high", "urgent"):
        raise HTTPException(422, "Invalid priority")
    if payload.book_id:
        book = await _book(db, payload.book_id, user)
        payload.title, payload.author, payload.isbn = (
            book.title, payload.author or book.author, payload.isbn or book.isbn
        )
    count = (await db.execute(select(func.count()).select_from(LibraryAcquisitionRequest).where(
        LibraryAcquisitionRequest.tenant_id == user.tenant_id
    ))).scalar_one()
    row = LibraryAcquisitionRequest(
        tenant_id=user.tenant_id, request_no=f"LAR-{date.today().year}-{count + 1:05d}",
        request_date=date.today(), **payload.model_dump(), created_by=user.id, updated_by=user.id,
    )
    db.add(row)
    await db.flush()
    await record_audit(db, action="request_purchase", entity="LibraryAcquisitionRequest",
                       entity_id=row.id, actor=user, changes={"title": row.title, "quantity": row.quantity})
    return {"id": str(row.id), "request_no": row.request_no, "status": row.request_status}


@router.post("/acquisition-requests/{request_id}/decision")
async def decide_acquisition_request(
    request_id: uuid.UUID, payload: DecisionIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:approve")),
):
    if payload.decision not in ("approved", "rejected"):
        raise HTTPException(422, "decision must be approved or rejected")
    row = await db.get(LibraryAcquisitionRequest, request_id)
    if not row or row.tenant_id != user.tenant_id or row.is_deleted:
        raise HTTPException(404, "Acquisition request not found")
    if row.request_status != "pending":
        raise HTTPException(409, "Only pending requests can be decided")
    row.request_status, row.decision_notes = payload.decision, payload.notes
    row.approved_by, row.updated_by = user.id, user.id
    await record_audit(db, action=payload.decision, entity="LibraryAcquisitionRequest",
                       entity_id=row.id, actor=user)
    return {"id": str(row.id), "status": row.request_status}


@router.get("/purchase-orders")
async def list_purchase_orders(
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:read")),
):
    rows = (await db.execute(select(LibraryPurchaseOrder).where(
        LibraryPurchaseOrder.tenant_id == user.tenant_id,
        LibraryPurchaseOrder.is_deleted.is_(False),
    ).order_by(LibraryPurchaseOrder.created_at.desc()))).scalars().all()
    return [await _po_view(db, row) for row in rows]


@router.post("/purchase-orders", status_code=201)
async def create_purchase_order(
    payload: PurchaseOrderIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:create")),
):
    vendor = await db.get(Vendor, payload.vendor_id)
    if not vendor or vendor.tenant_id != user.tenant_id or vendor.is_deleted:
        raise HTTPException(404, "Vendor not found")
    requests: dict[uuid.UUID, LibraryAcquisitionRequest] = {}
    for line in payload.lines:
        if line.acquisition_request_id:
            request = await db.get(LibraryAcquisitionRequest, line.acquisition_request_id)
            if not request or request.tenant_id != user.tenant_id:
                raise HTTPException(404, "Acquisition request not found")
            if request.request_status != "approved":
                raise HTTPException(409, f"Request {request.request_no} is not approved")
            requests[request.id] = request
    subtotal = sum((line.unit_price * line.quantity for line in payload.lines), Decimal(0))
    count = (await db.execute(select(func.count()).select_from(LibraryPurchaseOrder).where(
        LibraryPurchaseOrder.tenant_id == user.tenant_id
    ))).scalar_one()
    po = LibraryPurchaseOrder(
        tenant_id=user.tenant_id, po_no=f"LIBPO-{date.today().year}-{count + 1:05d}",
        vendor_id=vendor.id, order_date=date.today(), expected_date=payload.expected_date,
        subtotal=subtotal, tax_amount=payload.tax_amount, shipping_amount=payload.shipping_amount,
        total_amount=subtotal + payload.tax_amount + payload.shipping_amount,
        notes=payload.notes, created_by=user.id, updated_by=user.id,
    )
    db.add(po)
    await db.flush()
    for line in payload.lines:
        db.add(LibraryPurchaseOrderLine(
            tenant_id=user.tenant_id, purchase_order_id=po.id,
            line_amount=line.unit_price * line.quantity, **line.model_dump(),
            created_by=user.id, updated_by=user.id,
        ))
        if line.acquisition_request_id:
            request = requests[line.acquisition_request_id]
            request.request_status, request.purchase_order_id = "ordered", po.id
            request.updated_by = user.id
    await db.flush()
    await record_audit(db, action="create", entity="LibraryPurchaseOrder", entity_id=po.id,
                       actor=user, changes={"vendor": vendor.name, "total": money(po.total_amount)})
    return await _po_view(db, po)


@router.post("/purchase-orders/{po_id}/action")
async def purchase_order_action(
    po_id: uuid.UUID, payload: PurchaseOrderActionIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:approve")),
):
    po = await _po(db, po_id, user)
    allowed = {"approve": ("draft", "approved"), "order": ("approved", "ordered")}
    if payload.action == "cancel":
        if po.po_status in ("received", "cancelled"):
            raise HTTPException(409, "This purchase order cannot be cancelled")
        target = "cancelled"
    elif payload.action in allowed:
        expected, target = allowed[payload.action]
        if po.po_status != expected:
            raise HTTPException(409, f"Purchase order must be {expected} before {payload.action}")
    else:
        raise HTTPException(422, "action must be approve, order or cancel")
    po.po_status, po.updated_by = target, user.id
    if payload.action == "approve":
        po.approved_by = user.id
    await record_audit(db, action=payload.action, entity="LibraryPurchaseOrder",
                       entity_id=po.id, actor=user)
    return await _po_view(db, po)


@router.post("/purchase-orders/{po_id}/receipts", status_code=201)
async def receive_purchase_order(
    po_id: uuid.UUID, payload: ReceiptIn, db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(require_permission("library_management:approve")),
):
    po = await _po(db, po_id, user)
    if po.po_status not in ("ordered", "partially_received"):
        raise HTTPException(409, "Only ordered purchase orders can be received")
    po_lines = (await db.execute(select(LibraryPurchaseOrderLine).where(
        LibraryPurchaseOrderLine.purchase_order_id == po.id,
        LibraryPurchaseOrderLine.is_deleted.is_(False),
    ))).scalars().all()
    line_map = {line.id: line for line in po_lines}
    accepted_total = rejected_total = 0
    for incoming in payload.lines:
        line = line_map.get(incoming.purchase_order_line_id)
        if not line:
            raise HTTPException(404, "Purchase order line not found")
        outstanding = line.quantity - line.received_quantity
        if incoming.accepted_quantity + incoming.rejected_quantity > outstanding:
            raise HTTPException(422, f"Receipt exceeds outstanding quantity for {line.title}")
        accepted_total += incoming.accepted_quantity
        rejected_total += incoming.rejected_quantity
    if accepted_total + rejected_total == 0:
        raise HTTPException(422, "Enter at least one received or rejected copy")
    count = (await db.execute(select(func.count()).select_from(LibraryGoodsReceipt).where(
        LibraryGoodsReceipt.tenant_id == user.tenant_id
    ))).scalar_one()
    receipt = LibraryGoodsReceipt(
        tenant_id=user.tenant_id, grn_no=f"LIBGRN-{date.today().year}-{count + 1:05d}",
        purchase_order_id=po.id, receipt_date=date.today(),
        vendor_invoice_no=payload.vendor_invoice_no, notes=payload.notes,
        accepted_quantity=accepted_total, rejected_quantity=rejected_total,
        created_by=user.id, updated_by=user.id,
    )
    db.add(receipt)
    await db.flush()
    for incoming in payload.lines:
        line = line_map[incoming.purchase_order_line_id]
        db.add(LibraryGoodsReceiptLine(
            tenant_id=user.tenant_id, receipt_id=receipt.id,
            **incoming.model_dump(), created_by=user.id, updated_by=user.id,
        ))
        if incoming.accepted_quantity:
            line.received_quantity += incoming.accepted_quantity
            book = await db.get(LibraryBook, line.book_id) if line.book_id else None
            if not book and line.isbn:
                book = (await db.execute(select(LibraryBook).where(
                    LibraryBook.tenant_id == user.tenant_id,
                    LibraryBook.isbn == line.isbn,
                    LibraryBook.is_deleted.is_(False),
                ))).scalars().first()
            if not book:
                book = LibraryBook(
                    tenant_id=user.tenant_id, title=line.title, author=line.author,
                    isbn=line.isbn, total_copies=0, available_copies=0, price=line.unit_price,
                    created_by=user.id, updated_by=user.id,
                )
                db.add(book)
                await db.flush()
                line.book_id = book.id
            copy_count = (await db.execute(select(func.count()).select_from(LibraryBookCopy).where(
                LibraryBookCopy.book_id == book.id
            ))).scalar_one()
            for index in range(incoming.accepted_quantity):
                db.add(LibraryBookCopy(
                    tenant_id=user.tenant_id, book_id=book.id,
                    accession_no=f"{book.id.hex[:6].upper()}-{copy_count + index + 1:04d}",
                    barcode=f"LIB-{book.id.hex[:8].upper()}-{copy_count + index + 1:04d}",
                    acquired_on=date.today(), acquisition_cost=line.unit_price,
                    source="purchase", purchase_order_id=po.id,
                    created_by=user.id, updated_by=user.id,
                ))
            book.total_copies += incoming.accepted_quantity
            book.available_copies += incoming.accepted_quantity
            book.price = line.unit_price
            book.updated_by = user.id
        if line.acquisition_request_id and line.received_quantity >= line.quantity:
            request = await db.get(LibraryAcquisitionRequest, line.acquisition_request_id)
            if request:
                request.request_status, request.updated_by = "fulfilled", user.id
    po.po_status = (
        "received" if all(line.received_quantity >= line.quantity for line in po_lines)
        else "partially_received"
    )
    po.updated_by = user.id
    await db.flush()
    await record_audit(db, action="receive", entity="LibraryPurchaseOrder", entity_id=po.id,
                       actor=user, changes={"grn": receipt.grn_no, "accepted": accepted_total,
                                            "rejected": rejected_total})
    return {"id": str(receipt.id), "grn_no": receipt.grn_no, "po_status": po.po_status,
            "accepted_quantity": accepted_total, "rejected_quantity": rejected_total}
