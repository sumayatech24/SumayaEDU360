"""Payroll computation: salary breakup from CTC + structure, and income tax
(old / new regime). Slabs follow FY 2025-26 and are indicative — the structure
and regime are configurable per employee, and tax can be overridden if required.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def _r(x) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# A sensible default breakup if a structure defines no components.
DEFAULT_COMPONENTS = [
    {"code": "hra", "name": "House Rent Allowance", "kind": "earning", "method": "percent_basic", "value": 40},
    {"code": "conveyance", "name": "Conveyance Allowance", "kind": "earning", "method": "fixed", "value": 1600},
    {"code": "medical", "name": "Medical Allowance", "kind": "earning", "method": "fixed", "value": 1250},
    {"code": "pf", "name": "Provident Fund", "kind": "deduction", "method": "percent_basic", "value": 12},
    {"code": "pt", "name": "Professional Tax", "kind": "deduction", "method": "fixed", "value": 200},
]

# (upper_bound_inclusive | None, rate%)
NEW_SLABS = [(400000, 0), (800000, 5), (1200000, 10), (1600000, 15), (2000000, 20), (2400000, 25), (None, 30)]
OLD_SLABS = [(250000, 0), (500000, 5), (1000000, 20), (None, 30)]


def annual_income_tax(gross_annual, regime: str) -> Decimal:
    """Annual income tax (incl. 4% cess) for a gross annual salary."""
    gross = Decimal(str(gross_annual or 0))
    if regime == "old":
        std, slabs, rebate_limit = Decimal(50000), OLD_SLABS, Decimal(500000)
    else:
        std, slabs, rebate_limit = Decimal(75000), NEW_SLABS, Decimal(1200000)
    taxable = max(Decimal(0), gross - std)
    tax, lower = Decimal(0), Decimal(0)
    for upper, rate in slabs:
        cap = Decimal(upper) if upper is not None else taxable
        if taxable > lower:
            band = min(taxable, cap) - lower
            if band > 0:
                tax += band * Decimal(rate) / 100
            lower = cap
        if upper is not None and taxable <= upper:
            break
    # Section 87A rebate.
    if taxable <= rebate_limit:
        tax = Decimal(0)
    tax = tax * Decimal("1.04")  # health & education cess
    return _r(tax)


def _component_amount(c: dict, basic: Decimal, monthly: Decimal) -> Decimal:
    value = Decimal(str(c.get("value", 0)))
    method = c.get("method")
    if method == "percent_basic":
        return basic * value / 100
    if method == "percent_ctc":
        return monthly * value / 100
    return value  # fixed


def compute_payslip(annual_ctc, components, basic_percent, regime: str,
                    lop_days=0, adhoc_deduction=0) -> dict:
    """Compute one month's payslip from an annual CTC and a salary structure."""
    annual = Decimal(str(annual_ctc or 0))
    monthly = annual / 12
    basic = monthly * Decimal(str(basic_percent or 40)) / 100
    comps = components or DEFAULT_COMPONENTS

    earnings = [{"name": "Basic", "amount": str(_r(basic))}]
    other_earn = Decimal(0)
    for c in comps:
        if c.get("kind") == "earning":
            amt = _component_amount(c, basic, monthly)
            earnings.append({"name": c["name"], "amount": str(_r(amt))})
            other_earn += amt
    special = monthly - basic - other_earn
    if special > 0:
        earnings.append({"name": "Special Allowance", "amount": str(_r(special))})
    gross = sum(Decimal(e["amount"]) for e in earnings)

    deductions = []
    statutory = Decimal(0)
    for c in comps:
        if c.get("kind") == "deduction":
            amt = _component_amount(c, basic, monthly)
            deductions.append({"name": c["name"], "amount": str(_r(amt))})
            statutory += amt

    tax_month = _r(annual_income_tax(annual, regime) / 12)
    deductions.append({"name": "TDS (Income Tax)", "amount": str(tax_month)})

    lop_days = Decimal(str(lop_days or 0))
    lop_amount = _r((monthly / 30) * lop_days) if lop_days > 0 else Decimal(0)
    if lop_amount > 0:
        deductions.append({"name": f"Loss of Pay ({lop_days} day/s)", "amount": str(lop_amount)})

    adhoc = _r(adhoc_deduction or 0)
    if adhoc > 0:
        deductions.append({"name": "Other deduction", "amount": str(adhoc)})

    total_deductions = _r(statutory) + tax_month + lop_amount + adhoc
    net = _r(gross) - total_deductions
    return {
        "gross_earnings": _r(gross),
        "statutory_deductions": _r(statutory),
        "tax_amount": tax_month,
        "lop_amount": lop_amount,
        "lop_days": lop_days,
        "adhoc_deduction": adhoc,
        "total_deductions": total_deductions,
        "net_pay": net,
        "earnings": earnings,
        "deductions": deductions,
    }
