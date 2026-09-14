"""finance.py — Finance module routes for Business EOS."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from backend.app.database import get_session
from backend.app.models import (
    AuditEvent, Bill, Budget, Contact, Expense, Invoice,
    JournalEntry, JournalLine, LedgerAccount, Payment, PayrollRun,
)
from backend.app.platform import (
    account_balances, audit, business_context, cents, post_entry, require_write,
)

router = APIRouter(prefix="/platform/finance", tags=["finance"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class BudgetPayload(BaseModel):
    period: str          # YYYY-MM-DD (first of month)
    account_id: int
    amount: float = 0.0
    notes: str = ""


class AccountPayload(BaseModel):
    code: str
    name: str
    account_type: str = "expense"
    subtype: str = ""


class PayrollPayload(BaseModel):
    period_start: str
    period_end: str
    gross_wages: float
    employer_taxes: float = 0.0
    deductions: float = 0.0
    payment_account_id: int
    notes: str = ""


# ── /finance/summary ─────────────────────────────────────────────────────────

@router.get("/summary")
def finance_summary(
    context=Depends(business_context),
    session: Session = Depends(get_session),
):
    business_id = context[0]
    invoices = session.exec(
        select(Invoice).where(Invoice.business_id == business_id, Invoice.status != "void")
    ).all()
    bills = session.exec(
        select(Bill).where(Bill.business_id == business_id, Bill.status != "void")
    ).all()
    return {
        "receivables_cents": sum(max(0, x.total_cents - x.paid_cents) for x in invoices),
        "payables_cents": sum(max(0, x.total_cents - x.paid_cents) for x in bills),
        "open_invoices": sum(x.status not in {"paid", "void"} for x in invoices),
        "open_bills": sum(x.status not in {"paid", "void"} for x in bills),
    }


# ── /finance/budgets ──────────────────────────────────────────────────────────

@router.get("/budgets")
def list_budgets(
    context=Depends(business_context),
    session: Session = Depends(get_session),
):
    business_id = context[0]
    budgets = session.exec(
        select(Budget).where(Budget.business_id == business_id).order_by(Budget.period.desc())
    ).all()
    result = []
    for b in budgets:
        account = session.get(LedgerAccount, b.account_id)
        result.append({
            "id": b.id,
            "period": b.period,
            "account_id": b.account_id,
            "account_name": account.name if account else "Unknown",
            "account_type": account.account_type if account else "",
            "budget_cents": b.budget_cents,
            "notes": b.notes,
        })
    return result


@router.post("/budgets")
def create_budget(
    payload: BudgetPayload,
    context=Depends(require_write),
    session: Session = Depends(get_session),
):
    business_id, _, user = context
    account = session.exec(
        select(LedgerAccount).where(
            LedgerAccount.id == payload.account_id,
            LedgerAccount.business_id == business_id,
        )
    ).first()
    if not account:
        raise HTTPException(404, "Account not found")

    # Upsert: same period + account overwrites
    existing = session.exec(
        select(Budget).where(
            Budget.business_id == business_id,
            Budget.period == payload.period,
            Budget.account_id == payload.account_id,
        )
    ).first()
    if existing:
        existing.budget_cents = cents(payload.amount)
        existing.notes = payload.notes
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    budget = Budget(
        business_id=business_id,
        period=payload.period,
        account_id=payload.account_id,
        budget_cents=cents(payload.amount),
        notes=payload.notes,
    )
    session.add(budget)
    session.commit()
    session.refresh(budget)
    return budget


# ── /finance/cashflow ─────────────────────────────────────────────────────────

@router.get("/cashflow")
def cashflow(
    start: Optional[str] = None,
    end: Optional[str] = None,
    context=Depends(business_context),
    session: Session = Depends(get_session),
):
    business_id = context[0]
    _start = start or date.today().replace(day=1).isoformat()
    _end = end or date.today().isoformat()

    # Inflows: payments received on invoices
    payments_in = session.exec(
        select(Payment).where(
            Payment.business_id == business_id,
            Payment.direction == "received",
            Payment.payment_date >= _start,
            Payment.payment_date <= _end,
        )
    ).all()
    inflow_rows = []
    for p in payments_in:
        desc = "Payment received"
        if p.invoice_id:
            inv = session.get(Invoice, p.invoice_id)
            if inv:
                contact = session.get(Contact, inv.customer_id)
                desc = contact.name if contact else f"Invoice #{inv.number}"
        inflow_rows.append({
            "date": p.payment_date,
            "source": "Invoice payment",
            "description": desc,
            "amount_cents": p.amount_cents,
        })

    # Inflows: manual journal credits to income accounts
    income_account_ids = {
        a.id for a in session.exec(
            select(LedgerAccount).where(
                LedgerAccount.business_id == business_id,
                LedgerAccount.account_type == "income",
            )
        ).all()
    }
    manual_entries = session.exec(
        select(JournalEntry).where(
            JournalEntry.business_id == business_id,
            JournalEntry.status == "posted",
            JournalEntry.source_type == "manual",
            JournalEntry.entry_date >= _start,
            JournalEntry.entry_date <= _end,
        )
    ).all()
    for entry in manual_entries:
        lines = session.exec(
            select(JournalLine).where(JournalLine.journal_entry_id == entry.id)
        ).all()
        for line in lines:
            if line.account_id in income_account_ids and line.credit_cents > 0:
                inflow_rows.append({
                    "date": entry.entry_date,
                    "source": "Journal entry",
                    "description": entry.memo or f"JE #{entry.id}",
                    "amount_cents": line.credit_cents,
                })

    # Outflows: expenses
    expenses_q = session.exec(
        select(Expense).where(
            Expense.business_id == business_id,
            Expense.expense_date >= _start,
            Expense.expense_date <= _end,
        )
    ).all()
    outflow_rows = []
    for exp in expenses_q:
        outflow_rows.append({
            "date": exp.expense_date,
            "source": "Expense",
            "description": exp.description or "Expense",
            "amount_cents": exp.amount_cents,
        })

    # Outflows: bill payments
    payments_out = session.exec(
        select(Payment).where(
            Payment.business_id == business_id,
            Payment.direction == "paid",
            Payment.payment_date >= _start,
            Payment.payment_date <= _end,
        )
    ).all()
    for p in payments_out:
        desc = "Bill payment"
        if p.bill_id:
            bill = session.get(Bill, p.bill_id)
            desc = f"Bill #{bill.number}" if bill and bill.number else f"Bill payment #{p.id}"
        outflow_rows.append({
            "date": p.payment_date,
            "source": "Bill payment",
            "description": desc,
            "amount_cents": p.amount_cents,
        })

    # Outflows: payroll
    payroll_runs = session.exec(
        select(PayrollRun).where(
            PayrollRun.business_id == business_id,
            PayrollRun.period_end >= _start,
            PayrollRun.period_end <= _end,
        )
    ).all()
    for pr in payroll_runs:
        outflow_rows.append({
            "date": pr.period_end,
            "source": "Payroll",
            "description": f"Payroll {pr.period_start} – {pr.period_end}",
            "amount_cents": pr.net_pay_cents,
        })

    inflows = sorted(inflow_rows, key=lambda x: x["date"])
    outflows = sorted(outflow_rows, key=lambda x: x["date"])
    inflows_total = sum(r["amount_cents"] for r in inflows)
    outflows_total = sum(r["amount_cents"] for r in outflows)

    return {
        "start": _start,
        "end": _end,
        "inflow_rows": inflows,
        "outflow_rows": outflows,
        "inflows_cents": inflows_total,
        "outflows_cents": outflows_total,
        "net_cents": inflows_total - outflows_total,
    }


# ── /finance/accounts ─────────────────────────────────────────────────────────

@router.post("/accounts")
def create_account(
    payload: AccountPayload,
    context=Depends(require_write),
    session: Session = Depends(get_session),
):
    business_id, _, user = context
    VALID_TYPES = {"asset", "liability", "equity", "income", "expense"}
    if payload.account_type not in VALID_TYPES:
        raise HTTPException(400, f"account_type must be one of {VALID_TYPES}")
    existing = session.exec(
        select(LedgerAccount).where(
            LedgerAccount.business_id == business_id,
            LedgerAccount.code == payload.code,
        )
    ).first()
    if existing:
        raise HTTPException(409, f"Account code '{payload.code}' already exists")
    account = LedgerAccount(
        business_id=business_id,
        code=payload.code,
        name=payload.name,
        account_type=payload.account_type,
        subtype=payload.subtype,
        active=True,
        system=False,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    audit(session, business_id, user.id, "account.create", "ledger_account", account.id)
    session.commit()
    # The audit commit expires every attribute on `account`, and FastAPI
    # serialises the return value after this request's session has closed — so
    # without this refresh the caller gets `{}` with a 200. The account really
    # is created; the response just says nothing about it.
    session.refresh(account)
    return account


# ── /finance/payroll ──────────────────────────────────────────────────────────

@router.get("/payroll")
def list_payroll(
    context=Depends(business_context),
    session: Session = Depends(get_session),
):
    business_id = context[0]
    runs = session.exec(
        select(PayrollRun).where(PayrollRun.business_id == business_id).order_by(PayrollRun.id.desc())
    ).all()
    result = []
    for r in runs:
        acct = session.get(LedgerAccount, r.payment_account_id)
        result.append({
            "id": r.id,
            "period_start": r.period_start,
            "period_end": r.period_end,
            "gross_wages_cents": r.gross_wages_cents,
            "employer_taxes_cents": r.employer_taxes_cents,
            "deductions_cents": r.deductions_cents,
            "net_pay_cents": r.net_pay_cents,
            "payment_account_name": acct.name if acct else "Unknown",
            "notes": r.notes,
        })
    return result


@router.post("/payroll")
def create_payroll_run(
    payload: PayrollPayload,
    context=Depends(require_write),
    session: Session = Depends(get_session),
):
    """
    Record a payroll run and post it to the ledger.

    The arithmetic here is the part worth reading, because it was wrong and it
    was wrong in a way that does not announce itself. Three different numbers
    come out of one payroll run and they are not interchangeable:

        cost to the business   gross + employer taxes
        cash leaving today     gross - employee deductions   (net pay)
        owed to the authority  employee deductions + employer taxes

    The entry used to be DR payroll expense / CR cash, both for the full cost.
    That credits cash for money the business still has — the tax it withheld
    and its own payroll taxes do not leave on payday, they leave when they are
    remitted. On a $10,000 run with $800 employer taxes and $2,000 withheld it
    showed $10,800 leaving the bank when $8,000 did, recorded nothing as owed,
    and then counted the same $2,800 a second time when it was actually paid.

    It also left the ledger disagreeing with this module's own cashflow report,
    which reads net pay from the PayrollRun row. One payroll run, two answers.
    """
    business_id, _, user = context

    gross_cents = cents(payload.gross_wages)
    tax_cents = cents(payload.employer_taxes)
    deduction_cents = cents(payload.deductions)

    # A negative here is a typo, not an instruction. Posted, it would reverse
    # the entry and quietly credit payroll expense.
    if gross_cents < 0 or tax_cents < 0 or deduction_cents < 0:
        raise HTTPException(400, "Payroll amounts cannot be negative")
    if gross_cents == 0:
        raise HTTPException(400, "A payroll run needs gross wages")
    if deduction_cents > gross_cents:
        raise HTTPException(
            400,
            "Deductions cannot exceed gross wages — that would mean paying "
            "employees a negative amount.",
        )
    if payload.period_end < payload.period_start:
        raise HTTPException(400, "The pay period ends before it starts")

    payroll_acct = _payroll_expense_account(session, business_id)
    liability_acct = _payroll_liability_account(session, business_id)

    payment_acct = session.exec(
        select(LedgerAccount).where(
            LedgerAccount.id == payload.payment_account_id,
            LedgerAccount.business_id == business_id,
        )
    ).first()
    if not payment_acct:
        raise HTTPException(404, "Payment account not found")

    net_pay_cents = gross_cents - deduction_cents
    total_cost = gross_cents + tax_cents
    withheld_cents = deduction_cents + tax_cents

    lines = [
        {"account_id": payroll_acct.id, "description": "Gross wages + employer taxes",
         "debit_cents": total_cost, "credit_cents": 0},
        {"account_id": payment_acct.id, "description": "Net pay disbursed",
         "debit_cents": 0, "credit_cents": net_pay_cents},
    ]
    # Omitted entirely when nothing is withheld, rather than posting a zero
    # line that clutters every journal for a business with no deductions.
    if withheld_cents:
        lines.append({
            "account_id": liability_acct.id,
            "description": "Withholding and employer taxes payable",
            "debit_cents": 0, "credit_cents": withheld_cents,
        })

    memo = f"Payroll {payload.period_start}-{payload.period_end}"
    if payload.notes:
        memo += f": {payload.notes}"

    post_entry(session, business_id, user.id, payload.period_end, memo, "payroll", None, lines)

    run = PayrollRun(
        business_id=business_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        gross_wages_cents=gross_cents,
        employer_taxes_cents=tax_cents,
        deductions_cents=deduction_cents,
        net_pay_cents=net_pay_cents,
        payment_account_id=payload.payment_account_id,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def _payroll_expense_account(session: Session, business_id: int) -> LedgerAccount:
    account = session.exec(
        select(LedgerAccount).where(
            LedgerAccount.business_id == business_id,
            LedgerAccount.subtype == "payroll",
        )
    ).first() or session.exec(
        select(LedgerAccount).where(
            LedgerAccount.business_id == business_id,
            LedgerAccount.code == "6000",
        )
    ).first()
    if not account:
        raise HTTPException(
            400, "No payroll expense account found (code 6000 or subtype 'payroll')"
        )
    return account


def _payroll_liability_account(session: Session, business_id: int) -> LedgerAccount:
    """
    Get or create it.

    Workspaces seeded before this account existed have no 2200, and refusing to
    run their payroll until somebody reads a migration note is not a reasonable
    thing to do to a business on payday. Creating it is safe: it starts at zero
    and only this path posts to it.
    """
    account = session.exec(
        select(LedgerAccount).where(
            LedgerAccount.business_id == business_id,
            LedgerAccount.subtype == "payroll_liabilities",
        )
    ).first()
    if account:
        return account

    code = "2200"
    if session.exec(
        select(LedgerAccount).where(
            LedgerAccount.business_id == business_id, LedgerAccount.code == code
        )
    ).first():
        # Somebody already used 2200 for something of their own. Take the next
        # free code rather than colliding or hijacking their account.
        taken = {
            a.code for a in session.exec(
                select(LedgerAccount).where(LedgerAccount.business_id == business_id)
            ).all()
        }
        code = next(c for c in (str(n) for n in range(2201, 2300)) if c not in taken)

    account = LedgerAccount(
        business_id=business_id,
        code=code,
        name="Payroll Liabilities",
        account_type="liability",
        subtype="payroll_liabilities",
        active=True,
        system=True,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return account
