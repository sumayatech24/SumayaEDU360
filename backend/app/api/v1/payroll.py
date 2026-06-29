"""End-to-end payroll: salary structures, employee pay packages, a monthly batch
run that auto-computes every employee's breakup + tax, ad-hoc deductions, an
owner approval gate, and bank submission with payslips."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import record_audit
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.payroll import DEFAULT_COMPONENTS, compute_payslip
from app.models.hr import PayrollRun, Payslip, SalaryStructure
from app.models.people import Employee

router = APIRouter(prefix="/payroll", tags=["Payroll"])

MONTHS = ["", "January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
OWNER_ROLES = {"super_admin", "institution_admin", "owner", "principal"}
STAFF_ROLES = OWNER_ROLES | {"accountant", "hr_manager"}


def _is_owner(user: CurrentUser) -> bool:
    return user.is_superadmin or bool(set(user.roles) & OWNER_ROLES)


def _require_staff(user: CurrentUser) -> None:
    if not (user.is_superadmin or set(user.roles) & STAFF_ROLES):
        raise HTTPException(403, "Payroll is restricted to HR / accounts / owner roles")


def _require_owner(user: CurrentUser) -> None:
    if not _is_owner(user):
        raise HTTPException(403, "Only the owner / institution admin can approve or process payroll")


def _fin_year(month: int, year: int) -> str:
    start = year if month >= 4 else year - 1
    return f"{start}-{(start + 1) % 100:02d}"


# --------------------------------------------------------------------------- structures
class StructureIn(BaseModel):
    name: str
    financial_year: str
    basic_percent: float = 40
    components: list[dict] | None = None
    is_active: bool = True


def _structure_dict(s: SalaryStructure) -> dict:
    return {
        "id": str(s.id), "name": s.name, "financial_year": s.financial_year,
        "basic_percent": str(s.basic_percent), "components": s.components or DEFAULT_COMPONENTS,
        "is_active": s.is_active,
    }


@router.get("/structures")
async def list_structures(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _require_staff(user)
    rows = (await db.execute(select(SalaryStructure).where(
        SalaryStructure.tenant_id == user.tenant_id, SalaryStructure.is_deleted.is_(False)
    ).order_by(SalaryStructure.financial_year.desc(), SalaryStructure.name))).scalars().all()
    return [_structure_dict(s) for s in rows]


@router.post("/structures")
async def create_structure(payload: StructureIn, db: AsyncSession = Depends(get_db),
                           user: CurrentUser = Depends(get_current_user)):
    _require_staff(user)
    s = SalaryStructure(
        tenant_id=user.tenant_id, name=payload.name, financial_year=payload.financial_year,
        basic_percent=Decimal(str(payload.basic_percent)),
        components=payload.components or DEFAULT_COMPONENTS, is_active=payload.is_active,
        created_by=user.id, updated_by=user.id,
    )
    db.add(s)
    await db.flush()
    await record_audit(db, action="create", entity="SalaryStructure", entity_id=s.id, actor=user)
    return _structure_dict(s)


@router.put("/structures/{structure_id}")
async def update_structure(structure_id: uuid.UUID, payload: StructureIn,
                           db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _require_staff(user)
    s = await db.get(SalaryStructure, structure_id)
    if not s or s.tenant_id != user.tenant_id or s.is_deleted:
        raise HTTPException(404, "Structure not found")
    s.name, s.financial_year = payload.name, payload.financial_year
    s.basic_percent = Decimal(str(payload.basic_percent))
    s.components = payload.components or DEFAULT_COMPONENTS
    s.is_active, s.updated_by = payload.is_active, user.id
    await db.flush()
    return _structure_dict(s)


# --------------------------------------------------------------------------- packages
class PackageIn(BaseModel):
    annual_ctc: float
    salary_structure_id: uuid.UUID | None = None
    tax_regime: str = "new"
    bank_account_no: str | None = None
    bank_ifsc: str | None = None


@router.get("/employees")
async def list_packages(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _require_staff(user)
    tid = user.tenant_id
    structures = {s.id: s.name for s in (await db.execute(select(SalaryStructure).where(
        SalaryStructure.tenant_id == tid, SalaryStructure.is_deleted.is_(False)))).scalars().all()}
    emps = (await db.execute(select(Employee).where(
        Employee.tenant_id == tid, Employee.is_deleted.is_(False)
    ).order_by(Employee.employee_no))).scalars().all()
    return [
        {
            "id": str(e.id), "employee_no": e.employee_no,
            "name": f"{e.first_name} {e.last_name or ''}".strip(), "designation": e.designation,
            "annual_ctc": str(e.annual_ctc) if e.annual_ctc is not None else None,
            "salary_structure_id": str(e.salary_structure_id) if e.salary_structure_id else None,
            "structure": structures.get(e.salary_structure_id),
            "tax_regime": e.tax_regime, "bank_account_no": e.bank_account_no, "bank_ifsc": e.bank_ifsc,
        }
        for e in emps
    ]


@router.put("/employees/{employee_id}/package")
async def set_package(employee_id: uuid.UUID, payload: PackageIn,
                      db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _require_staff(user)
    e = await db.get(Employee, employee_id)
    if not e or e.tenant_id != user.tenant_id or e.is_deleted:
        raise HTTPException(404, "Employee not found")
    e.annual_ctc = Decimal(str(payload.annual_ctc))
    e.salary_structure_id = payload.salary_structure_id
    e.tax_regime = "old" if payload.tax_regime == "old" else "new"
    e.bank_account_no, e.bank_ifsc, e.updated_by = payload.bank_account_no, payload.bank_ifsc, user.id
    await db.flush()
    await record_audit(db, action="update", entity="EmployeePackage", entity_id=e.id, actor=user)
    return {"id": str(e.id), "annual_ctc": str(e.annual_ctc), "tax_regime": e.tax_regime}


# --------------------------------------------------------------------------- runs
class RunIn(BaseModel):
    month: int
    year: int


class PayslipEditIn(BaseModel):
    lop_days: float = 0
    adhoc_deduction: float = 0
    adhoc_note: str | None = None


async def _recompute_run_totals(db: AsyncSession, run: PayrollRun) -> None:
    slips = (await db.execute(select(Payslip).where(
        Payslip.payroll_run_id == run.id, Payslip.is_deleted.is_(False)))).scalars().all()
    run.employee_count = len(slips)
    run.total_gross = sum((s.gross_earnings for s in slips), Decimal(0))
    run.total_net = sum((s.net_pay for s in slips), Decimal(0))
    run.total_deductions = sum(
        (s.statutory_deductions + s.tax_amount + s.adhoc_deduction for s in slips), Decimal(0))


async def _structures_map(db: AsyncSession, tid) -> dict:
    return {s.id: s for s in (await db.execute(select(SalaryStructure).where(
        SalaryStructure.tenant_id == tid, SalaryStructure.is_deleted.is_(False)))).scalars().all()}


@router.post("/runs")
async def create_run(payload: RunIn, db: AsyncSession = Depends(get_db),
                     user: CurrentUser = Depends(get_current_user)):
    """Prepare the month's payroll for every employee that has a pay package."""
    _require_staff(user)
    if not 1 <= payload.month <= 12:
        raise HTTPException(422, "month must be 1-12")
    tid = user.tenant_id
    existing = (await db.execute(select(PayrollRun).where(
        PayrollRun.tenant_id == tid, PayrollRun.month == payload.month, PayrollRun.year == payload.year,
        PayrollRun.is_deleted.is_(False)))).scalars().first()
    if existing:
        raise HTTPException(409, f"Payroll for {MONTHS[payload.month]} {payload.year} already exists")

    run = PayrollRun(
        tenant_id=tid, financial_year=_fin_year(payload.month, payload.year),
        month=payload.month, year=payload.year, run_status="draft",
        created_by=user.id, updated_by=user.id,
    )
    db.add(run)
    await db.flush()

    structures = await _structures_map(db, tid)
    emps = (await db.execute(select(Employee).where(
        Employee.tenant_id == tid, Employee.is_deleted.is_(False),
        Employee.employment_status == "active", Employee.annual_ctc.isnot(None),
    ))).scalars().all()
    for e in emps:
        struct = structures.get(e.salary_structure_id)
        comps = struct.components if struct else DEFAULT_COMPONENTS
        basic_pct = struct.basic_percent if struct else Decimal(40)
        calc = compute_payslip(e.annual_ctc, comps, basic_pct, e.tax_regime)
        db.add(Payslip(
            tenant_id=tid, payroll_run_id=run.id, employee_id=e.id,
            gross_earnings=calc["gross_earnings"], statutory_deductions=calc["statutory_deductions"],
            tax_amount=calc["tax_amount"], adhoc_deduction=Decimal(0), lop_days=Decimal(0),
            net_pay=calc["net_pay"], tax_regime=e.tax_regime,
            earnings=calc["earnings"], deductions=calc["deductions"],
            created_by=user.id, updated_by=user.id,
        ))
    await db.flush()
    await _recompute_run_totals(db, run)
    await db.flush()
    await record_audit(db, action="prepare", entity="PayrollRun", entity_id=run.id, actor=user,
                       changes={"month": payload.month, "year": payload.year, "employees": run.employee_count})
    return {"id": str(run.id), "status": run.run_status, "employee_count": run.employee_count}


def _run_dict(run: PayrollRun) -> dict:
    return {
        "id": str(run.id), "financial_year": run.financial_year,
        "month": run.month, "month_name": MONTHS[run.month], "year": run.year,
        "status": run.run_status, "employee_count": run.employee_count,
        "total_gross": str(run.total_gross), "total_deductions": str(run.total_deductions),
        "total_net": str(run.total_net),
        "approved_at": run.approved_at.isoformat() if run.approved_at else None,
        "processed_at": run.processed_at.isoformat() if run.processed_at else None,
        "bank_reference": run.bank_reference,
    }


@router.get("/runs")
async def list_runs(db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _require_staff(user)
    rows = (await db.execute(select(PayrollRun).where(
        PayrollRun.tenant_id == user.tenant_id, PayrollRun.is_deleted.is_(False)
    ).order_by(PayrollRun.year.desc(), PayrollRun.month.desc()))).scalars().all()
    return [_run_dict(r) for r in rows]


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                  user: CurrentUser = Depends(get_current_user)):
    _require_staff(user)
    run = await db.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id or run.is_deleted:
        raise HTTPException(404, "Payroll run not found")
    slips = (await db.execute(select(Payslip).where(
        Payslip.payroll_run_id == run.id, Payslip.is_deleted.is_(False)))).scalars().all()
    emps = {e.id: e for e in (await db.execute(select(Employee).where(
        Employee.tenant_id == user.tenant_id))).scalars().all()}
    rows = []
    for s in slips:
        e = emps.get(s.employee_id)
        rows.append({
            "id": str(s.id), "employee": f"{e.first_name} {e.last_name or ''}".strip() if e else "—",
            "employee_no": e.employee_no if e else "—", "designation": e.designation if e else None,
            "gross_earnings": str(s.gross_earnings), "statutory_deductions": str(s.statutory_deductions),
            "tax_amount": str(s.tax_amount), "adhoc_deduction": str(s.adhoc_deduction),
            "adhoc_note": s.adhoc_note, "lop_days": str(s.lop_days), "net_pay": str(s.net_pay),
            "tax_regime": s.tax_regime, "earnings": s.earnings or [], "deductions": s.deductions or [],
            "bank_account_no": e.bank_account_no if e else None, "bank_ifsc": e.bank_ifsc if e else None,
        })
    rows.sort(key=lambda r: r["employee_no"])
    return {"run": _run_dict(run), "editable": run.run_status == "draft", "payslips": rows}


@router.put("/payslips/{payslip_id}")
async def edit_payslip(payslip_id: uuid.UUID, payload: PayslipEditIn,
                       db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Enter ad-hoc deductions / extra-leave (LOP) and recompute the payslip."""
    _require_staff(user)
    slip = await db.get(Payslip, payslip_id)
    if not slip or slip.tenant_id != user.tenant_id or slip.is_deleted:
        raise HTTPException(404, "Payslip not found")
    run = await db.get(PayrollRun, slip.payroll_run_id)
    if run.run_status != "draft":
        raise HTTPException(409, "Only draft payroll can be edited")
    e = await db.get(Employee, slip.employee_id)
    structures = await _structures_map(db, user.tenant_id)
    struct = structures.get(e.salary_structure_id)
    comps = struct.components if struct else DEFAULT_COMPONENTS
    basic_pct = struct.basic_percent if struct else Decimal(40)
    calc = compute_payslip(e.annual_ctc, comps, basic_pct, e.tax_regime,
                           lop_days=payload.lop_days, adhoc_deduction=payload.adhoc_deduction)
    slip.gross_earnings = calc["gross_earnings"]
    slip.statutory_deductions = calc["statutory_deductions"]
    slip.tax_amount = calc["tax_amount"]
    slip.lop_days = calc["lop_days"]
    slip.adhoc_deduction = calc["adhoc_deduction"]
    slip.adhoc_note = payload.adhoc_note
    slip.net_pay = calc["net_pay"]
    slip.earnings, slip.deductions, slip.updated_by = calc["earnings"], calc["deductions"], user.id
    await db.flush()
    await _recompute_run_totals(db, run)
    await db.flush()
    return {"id": str(slip.id), "net_pay": str(slip.net_pay)}


class RunDecisionIn(BaseModel):
    note: str | None = None


@router.post("/runs/{run_id}/approve")
async def approve_run(run_id: uuid.UUID, payload: RunDecisionIn,
                      db: AsyncSession = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    """Owner approval gate for the month's payroll."""
    _require_owner(user)
    run = await db.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id or run.is_deleted:
        raise HTTPException(404, "Payroll run not found")
    if run.run_status != "draft":
        raise HTTPException(409, "Only draft payroll can be approved")
    if run.employee_count == 0:
        raise HTTPException(409, "No payslips to approve")
    run.run_status = "approved"
    run.approved_by, run.approved_at = user.id, datetime.now(timezone.utc)
    run.notes, run.updated_by = payload.note, user.id
    await db.flush()
    await record_audit(db, action="approve", entity="PayrollRun", entity_id=run.id, actor=user)
    return {"id": str(run.id), "status": run.run_status}


@router.post("/runs/{run_id}/process")
async def process_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      user: CurrentUser = Depends(get_current_user)):
    """Submit the approved payroll to the bank for disbursement."""
    _require_owner(user)
    run = await db.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id or run.is_deleted:
        raise HTTPException(404, "Payroll run not found")
    if run.run_status != "approved":
        raise HTTPException(409, "Approve the payroll before submitting to the bank")
    run.run_status = "paid"
    run.processed_at = datetime.now(timezone.utc)
    run.bank_reference = f"NEFT-{run.year}{run.month:02d}-{str(run.id)[:6].upper()}"
    run.updated_by = user.id
    await db.flush()
    await record_audit(db, action="process", entity="PayrollRun", entity_id=run.id, actor=user,
                       changes={"bank_reference": run.bank_reference})
    return {"id": str(run.id), "status": run.run_status, "bank_reference": run.bank_reference}


@router.get("/runs/{run_id}/bank-file")
async def bank_file(run_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    user: CurrentUser = Depends(get_current_user)):
    """Bank disbursement statement for the approved/processed run."""
    _require_staff(user)
    run = await db.get(PayrollRun, run_id)
    if not run or run.tenant_id != user.tenant_id or run.is_deleted:
        raise HTTPException(404, "Payroll run not found")
    slips = (await db.execute(select(Payslip).where(
        Payslip.payroll_run_id == run.id, Payslip.is_deleted.is_(False)))).scalars().all()
    emps = {e.id: e for e in (await db.execute(select(Employee).where(
        Employee.tenant_id == user.tenant_id))).scalars().all()}
    lines = []
    for s in slips:
        e = emps.get(s.employee_id)
        lines.append({
            "employee_no": e.employee_no if e else "—",
            "name": f"{e.first_name} {e.last_name or ''}".strip() if e else "—",
            "bank_account_no": (e.bank_account_no if e else None) or "NOT SET",
            "bank_ifsc": (e.bank_ifsc if e else None) or "NOT SET",
            "net_pay": str(s.net_pay),
        })
    lines.sort(key=lambda r: r["employee_no"])
    return {
        "period": f"{MONTHS[run.month]} {run.year}", "status": run.run_status,
        "bank_reference": run.bank_reference, "total_net": str(run.total_net),
        "count": len(lines), "lines": lines,
    }
