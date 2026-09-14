"""
Budgets, cashflow and payroll.

Payroll is the reason this file exists. It was the last untested module and the
only one that moves an employee's money, and it turned out to be posting a
journal entry that was wrong in a way nothing would ever surface.

One payroll run produces three different numbers, and they are not
interchangeable:

    cost to the business    gross + employer taxes
    cash leaving today      gross - employee deductions      (net pay)
    owed to the authority   employee deductions + employer taxes

The old entry credited cash for the full cost, which says the tax a business
withheld left the bank on payday. It did not — it is being held, and it leaves
when it is remitted. So the books showed the business poorer than it was,
recorded nothing as owed, and then counted the same money a second time when it
actually went out.

These tests assert on balances rather than on rows. A payroll run that writes a
perfect PayrollRun record and a wrong journal entry is still a payroll run that
will fail an audit.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.main import app
from backend.app.models import (
    Bill, Business, Expense, Invoice, LedgerAccount, Payment, UserAccount,
)
from backend.app.platform import account_balances, seed_business
from backend.app.tenancy import set_current_business_id


def _make_workspace(label: str):
    suffix = uuid.uuid4().hex[:6]
    creds = {"username": f"{label}{suffix}", "password": "a-test-password-123"}
    with Session(engine) as s:
        user = UserAccount(
            username=creds["username"],
            password_hash=hash_password(creds["password"]),
            role="manager",
            active=True,
        )
        s.add(user)
        s.flush()
        business = Business(name=f"{label} {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid = business.id
        set_current_business_id(bid)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)
    return bid, creds


@pytest.fixture
def books(client):
    """A signed-in workspace with a seeded chart of accounts."""
    bid, creds = _make_workspace("fin")
    login = client.post("/auth/login", json=creds)
    assert login.status_code == 200, login.text
    headers = {
        "Authorization": f"Bearer {login.json()['token']}",
        "X-Business-Id": str(bid),
    }
    accounts = client.get("/platform/accounts", headers=headers).json()
    by_subtype = {a["subtype"]: a["id"] for a in accounts}

    yield {
        "business_id": bid,
        "headers": headers,
        "client": client,
        "accounts": by_subtype,
    }
    set_current_business_id(1)


def _balances(business_id):
    """{subtype: signed balance in cents}, debit-positive."""
    with Session(engine) as s:
        accounts, totals = account_balances(s, business_id)
    return {
        a.subtype: totals[a.id]["debit_cents"] - totals[a.id]["credit_cents"]
        for a in accounts
    }


def _run_payroll(books, gross, taxes=0.0, deductions=0.0, **overrides):
    body = {
        "period_start": "2026-09-01",
        "period_end": "2026-09-15",
        "gross_wages": gross,
        "employer_taxes": taxes,
        "deductions": deductions,
        "payment_account_id": books["accounts"]["cash"],
        "notes": "",
    }
    body.update(overrides)
    return books["client"].post(
        "/platform/finance/payroll", headers=books["headers"], json=body
    )


# ===========================================================================
# Payroll — the arithmetic
# ===========================================================================

def test_a_payroll_run_splits_cost_cash_and_liability(books):
    """
    The bug, stated as the three numbers it got wrong. $10,000 gross, $800
    employer taxes, $2,000 withheld:

        costs the business  $10,800
        leaves the bank      $8,000
        is owed              $2,800
    """
    assert _run_payroll(books, 10_000.0, taxes=800.0, deductions=2_000.0).status_code == 200

    balances = _balances(books["business_id"])
    assert balances["payroll"] == 1_080_000, "payroll expense is not the full cost"
    assert balances["cash"] == -800_000, "cash moved by something other than net pay"
    assert balances["payroll_liabilities"] == -280_000, "nothing was recorded as owed"


def test_the_payroll_entry_balances(books):
    """If this fails the trial balance is broken and every report with it."""
    _run_payroll(books, 7_500.0, taxes=613.0, deductions=1_842.0)

    with Session(engine) as s:
        _, totals = account_balances(s, books["business_id"])
    debits = sum(t["debit_cents"] for t in totals.values())
    credits = sum(t["credit_cents"] for t in totals.values())
    assert debits == credits, f"out by {debits - credits} cents"


def test_the_ledger_agrees_with_the_payroll_record(books):
    """
    These are written by the same request and were disagreeing by the withheld
    amount. One payroll run must not produce two answers.
    """
    response = _run_payroll(books, 10_000.0, taxes=800.0, deductions=2_000.0)
    stored_net = response.json()["net_pay_cents"]

    balances = _balances(books["business_id"])
    assert -balances["cash"] == stored_net


def test_the_ledger_agrees_with_the_cashflow_report(books):
    """The third place the same number appears, and the third chance to differ."""
    _run_payroll(books, 10_000.0, taxes=800.0, deductions=2_000.0)

    report = books["client"].get(
        "/platform/finance/cashflow",
        headers=books["headers"],
        params={"start": "2026-09-01", "end": "2026-09-30"},
    ).json()
    payroll_out = sum(
        r["amount_cents"] for r in report["outflow_rows"] if r["source"] == "Payroll"
    )

    balances = _balances(books["business_id"])
    assert payroll_out == -balances["cash"]


def test_withheld_money_is_not_treated_as_spent(books):
    """
    The heart of it. Tax withheld from an employee belongs to the authority but
    sits in the business's bank until it is remitted. Recording it as gone
    makes an operator think they have less than they do, right when they are
    deciding whether they can afford something.
    """
    _run_payroll(books, 10_000.0, taxes=0.0, deductions=3_000.0)
    balances = _balances(books["business_id"])

    assert balances["cash"] == -700_000, "withheld tax was treated as leaving the bank"
    assert balances["payroll_liabilities"] == -300_000


def test_a_run_with_no_deductions_or_taxes_is_simple(books):
    """The whole gross leaves, and nothing is owed."""
    assert _run_payroll(books, 5_000.0).status_code == 200

    balances = _balances(books["business_id"])
    assert balances["cash"] == -500_000
    assert balances["payroll"] == 500_000
    assert balances.get("payroll_liabilities", 0) == 0


def test_two_runs_accumulate(books):
    _run_payroll(books, 10_000.0, taxes=800.0, deductions=2_000.0)
    _run_payroll(books, 10_000.0, taxes=800.0, deductions=2_000.0,
                 period_start="2026-09-16", period_end="2026-09-30")

    balances = _balances(books["business_id"])
    assert balances["cash"] == -1_600_000
    assert balances["payroll_liabilities"] == -560_000


def test_remitting_the_tax_clears_the_liability_without_a_second_expense(books):
    """
    What the liability account is *for*. Paying the authority later reduces
    cash and the amount owed; it is not a new cost. Under the old entry the
    business had already expensed it, so remitting it expensed it twice.
    """
    _run_payroll(books, 10_000.0, taxes=800.0, deductions=2_000.0)
    accounts = books["client"].get("/platform/accounts", headers=books["headers"]).json()
    liability = next(a for a in accounts if a["subtype"] == "payroll_liabilities")

    remit = books["client"].post("/platform/journal", headers=books["headers"], json={
        "entry_date": "2026-09-20",
        "memo": "remit payroll taxes",
        "lines": [
            {"account_id": liability["id"], "description": "remit", "debit": 2_800.0, "credit": 0},
            {"account_id": books["accounts"]["cash"], "description": "remit", "debit": 0, "credit": 2_800.0},
        ],
    })
    assert remit.status_code == 200, remit.text

    balances = _balances(books["business_id"])
    assert balances["payroll_liabilities"] == 0, "the liability did not clear"
    assert balances["cash"] == -1_080_000, "total cash out is not gross plus employer taxes"
    assert balances["payroll"] == 1_080_000, "remitting was expensed a second time"


# ===========================================================================
# Payroll — what it refuses
# ===========================================================================

def test_negative_amounts_are_refused(books):
    """
    A negative gross posts a reversed entry and credits payroll expense, which
    reads as the business having been paid to employ somebody.
    """
    assert _run_payroll(books, -5_000.0).status_code == 400
    assert _run_payroll(books, 5_000.0, taxes=-100.0).status_code == 400
    assert _run_payroll(books, 5_000.0, deductions=-100.0).status_code == 400


def test_deductions_cannot_exceed_gross(books):
    """That would be an employee paying the business to work there."""
    response = _run_payroll(books, 1_000.0, deductions=1_500.0)
    assert response.status_code == 400
    assert "negative" in response.json()["detail"].lower()


def test_a_run_with_no_wages_is_refused(books):
    assert _run_payroll(books, 0.0).status_code == 400


def test_a_backwards_pay_period_is_refused(books):
    response = _run_payroll(books, 1_000.0,
                            period_start="2026-09-30", period_end="2026-09-01")
    assert response.status_code == 400


def test_deductions_equal_to_gross_are_allowed(books):
    """Unusual, not impossible — a run entirely offset by deductions."""
    assert _run_payroll(books, 1_000.0, deductions=1_000.0).status_code == 200
    balances = _balances(books["business_id"])
    assert balances["cash"] == 0
    assert balances["payroll_liabilities"] == -100_000


def test_paying_from_another_businesss_account_is_refused(books):
    """The tenant boundary, on a route that moves money out of a bank account."""
    other_id, _ = _make_workspace("intruder")
    with Session(engine) as s:
        their_cash = s.exec(
            select(LedgerAccount).where(
                LedgerAccount.business_id == other_id,
                LedgerAccount.subtype == "cash",
            ).execution_options(include_all_businesses=True)
        ).first()

    response = _run_payroll(books, 1_000.0, payment_account_id=their_cash.id)
    assert response.status_code == 404


def test_an_unknown_payment_account_is_refused(books):
    assert _run_payroll(books, 1_000.0, payment_account_id=999_999).status_code == 404


# ===========================================================================
# Payroll — the liability account
# ===========================================================================

def test_a_workspace_seeded_before_the_account_existed_still_runs_payroll(books):
    """
    Existing workspaces have no 2200. Refusing to run their payroll until
    somebody reads a migration note is not a reasonable thing to do to a
    business on payday, so the account is created on demand.
    """
    with Session(engine) as s:
        legacy = s.exec(
            select(LedgerAccount).where(
                LedgerAccount.business_id == books["business_id"],
                LedgerAccount.subtype == "payroll_liabilities",
            ).execution_options(include_all_businesses=True)
        ).first()
        s.delete(legacy)
        s.commit()

    assert _run_payroll(books, 4_000.0, deductions=900.0).status_code == 200
    assert _balances(books["business_id"])["payroll_liabilities"] == -90_000


def test_an_existing_2200_account_is_not_hijacked(books):
    """
    Somebody may already use 2200 for something of their own. Posting payroll
    withholding into a customer's own account would corrupt a real balance.
    """
    with Session(engine) as s:
        legacy = s.exec(
            select(LedgerAccount).where(
                LedgerAccount.business_id == books["business_id"],
                LedgerAccount.subtype == "payroll_liabilities",
            ).execution_options(include_all_businesses=True)
        ).first()
        s.delete(legacy)
        s.commit()

    theirs = books["client"].post("/platform/finance/accounts", headers=books["headers"], json={
        "code": "2200", "name": "Equipment Loan", "account_type": "liability", "subtype": "loan",
    })
    assert theirs.status_code == 200, theirs.text
    their_id = theirs.json()["id"]

    assert _run_payroll(books, 4_000.0, deductions=900.0).status_code == 200

    with Session(engine) as s:
        _, totals = account_balances(s, books["business_id"])
    assert totals[their_id]["credit_cents"] == 0, "payroll posted into their loan account"
    assert _balances(books["business_id"])["payroll_liabilities"] == -90_000


def test_the_liability_account_is_a_liability(books):
    """
    On the balance sheet it has to sit with what is owed. Typed as an expense
    it would inflate costs and never appear as a debt.
    """
    accounts = books["client"].get("/platform/accounts", headers=books["headers"]).json()
    account = next(a for a in accounts if a["subtype"] == "payroll_liabilities")
    assert account["account_type"] == "liability"


# ===========================================================================
# Budgets
# ===========================================================================

def test_a_budget_is_stored_in_cents(books):
    response = books["client"].post("/platform/finance/budgets", headers=books["headers"], json={
        "period": "2026-09-01", "account_id": books["accounts"]["rent"],
        "amount": 2_500.50, "notes": "rent",
    })
    assert response.status_code == 200
    assert response.json()["budget_cents"] == 250_050


def test_setting_a_budget_twice_overwrites_rather_than_duplicates(books):
    """
    Two budgets for one account in one month means every report has to guess
    which is current.
    """
    for amount in (1_000.0, 1_400.0):
        books["client"].post("/platform/finance/budgets", headers=books["headers"], json={
            "period": "2026-09-01", "account_id": books["accounts"]["rent"],
            "amount": amount, "notes": "",
        })

    listed = books["client"].get("/platform/finance/budgets", headers=books["headers"]).json()
    rent = [b for b in listed if b["account_id"] == books["accounts"]["rent"]]
    assert len(rent) == 1
    assert rent[0]["budget_cents"] == 140_000


def test_different_months_are_separate_budgets(books):
    for period in ("2026-09-01", "2026-10-01"):
        books["client"].post("/platform/finance/budgets", headers=books["headers"], json={
            "period": period, "account_id": books["accounts"]["rent"],
            "amount": 1_000.0, "notes": "",
        })

    listed = books["client"].get("/platform/finance/budgets", headers=books["headers"]).json()
    assert len([b for b in listed if b["account_id"] == books["accounts"]["rent"]]) == 2


def test_budgeting_against_another_businesss_account_is_refused(books):
    other_id, _ = _make_workspace("stranger")
    with Session(engine) as s:
        theirs = s.exec(
            select(LedgerAccount).where(
                LedgerAccount.business_id == other_id,
                LedgerAccount.subtype == "rent",
            ).execution_options(include_all_businesses=True)
        ).first()

    response = books["client"].post("/platform/finance/budgets", headers=books["headers"], json={
        "period": "2026-09-01", "account_id": theirs.id, "amount": 100.0, "notes": "",
    })
    assert response.status_code == 404


def test_budgets_do_not_leak_between_workspaces(books):
    books["client"].post("/platform/finance/budgets", headers=books["headers"], json={
        "period": "2026-09-01", "account_id": books["accounts"]["rent"],
        "amount": 9_999.0, "notes": "secret",
    })

    other_id, other_creds = _make_workspace("neighbour")
    login = books["client"].post("/auth/login", json=other_creds)
    other_headers = {
        "Authorization": f"Bearer {login.json()['token']}",
        "X-Business-Id": str(other_id),
    }
    listed = books["client"].get("/platform/finance/budgets", headers=other_headers).json()
    assert listed == []


# ===========================================================================
# Accounts
# ===========================================================================

def test_an_invalid_account_type_is_refused(books):
    response = books["client"].post("/platform/finance/accounts", headers=books["headers"], json={
        "code": "7000", "name": "Nonsense", "account_type": "vibes", "subtype": "",
    })
    assert response.status_code == 400


def test_a_duplicate_account_code_is_refused(books):
    """
    Two accounts sharing a code makes every report that groups by code wrong,
    and there is no way to tell afterwards which entries meant which.
    """
    response = books["client"].post("/platform/finance/accounts", headers=books["headers"], json={
        "code": "1000", "name": "Second Bank", "account_type": "asset", "subtype": "",
    })
    assert response.status_code == 409


def test_the_same_code_is_fine_in_another_workspace(books):
    """Codes are per business. 1000 is Operating Bank for everybody."""
    other_id, other_creds = _make_workspace("codes")
    login = books["client"].post("/auth/login", json=other_creds)
    headers = {
        "Authorization": f"Bearer {login.json()['token']}",
        "X-Business-Id": str(other_id),
    }
    response = books["client"].post("/platform/finance/accounts", headers=headers, json={
        "code": "9100", "name": "Theirs", "account_type": "expense", "subtype": "",
    })
    assert response.status_code == 200

    mine = books["client"].post("/platform/finance/accounts", headers=books["headers"], json={
        "code": "9100", "name": "Mine", "account_type": "expense", "subtype": "",
    })
    assert mine.status_code == 200


# ===========================================================================
# Summary and cashflow
# ===========================================================================

def test_the_summary_counts_only_what_is_still_owed(books):
    """Receivables are the unpaid balance, not the invoice total."""
    with Session(engine) as s:
        s.add(Invoice(
            business_id=books["business_id"], number="INV-1", customer_id=0,
            issue_date="2026-09-01", due_date="2026-09-30",
            total_cents=100_000, paid_cents=40_000, status="open",
        ))
        s.commit()

    summary = books["client"].get("/platform/finance/summary", headers=books["headers"]).json()
    assert summary["receivables_cents"] == 60_000
    assert summary["open_invoices"] == 1


def test_a_void_invoice_is_not_owed(books):
    with Session(engine) as s:
        s.add(Invoice(
            business_id=books["business_id"], number="INV-2", customer_id=0,
            issue_date="2026-09-01", due_date="2026-09-30",
            total_cents=500_000, paid_cents=0, status="void",
        ))
        s.commit()

    summary = books["client"].get("/platform/finance/summary", headers=books["headers"]).json()
    assert summary["receivables_cents"] == 0


def test_an_overpaid_invoice_does_not_read_as_negative(books):
    """A credit balance is a real thing, but it is not a negative receivable."""
    with Session(engine) as s:
        s.add(Invoice(
            business_id=books["business_id"], number="INV-3", customer_id=0,
            issue_date="2026-09-01", due_date="2026-09-30",
            total_cents=10_000, paid_cents=15_000, status="paid",
        ))
        s.commit()

    summary = books["client"].get("/platform/finance/summary", headers=books["headers"]).json()
    assert summary["receivables_cents"] == 0


def test_payables_come_from_bills(books):
    with Session(engine) as s:
        s.add(Bill(
            business_id=books["business_id"], number="BILL-1", vendor_id=0,
            bill_date="2026-09-01", due_date="2026-09-30",
            total_cents=80_000, paid_cents=0, status="open",
        ))
        s.commit()

    summary = books["client"].get("/platform/finance/summary", headers=books["headers"]).json()
    assert summary["payables_cents"] == 80_000
    assert summary["open_bills"] == 1


def test_cashflow_nets_what_came_in_against_what_went_out(books):
    with Session(engine) as s:
        s.add(Payment(
            business_id=books["business_id"], direction="received",
            payment_date="2026-09-05", amount_cents=300_000,
            account_id=books["accounts"]["cash"],
        ))
        s.add(Expense(
            business_id=books["business_id"], expense_date="2026-09-06",
            amount_cents=120_000, description="repairs",
            account_id=books["accounts"]["supplies"],
            payment_account_id=books["accounts"]["cash"],
        ))
        s.commit()

    report = books["client"].get(
        "/platform/finance/cashflow", headers=books["headers"],
        params={"start": "2026-09-01", "end": "2026-09-30"},
    ).json()

    assert report["inflows_cents"] == 300_000
    assert report["outflows_cents"] == 120_000
    assert report["net_cents"] == 180_000


def test_cashflow_respects_the_window(books):
    """A period report that includes another month is not a period report."""
    with Session(engine) as s:
        cash = books["accounts"]["cash"]
        s.add(Payment(business_id=books["business_id"], direction="received",
                      payment_date="2026-08-15", amount_cents=999_999, account_id=cash))
        s.add(Payment(business_id=books["business_id"], direction="received",
                      payment_date="2026-09-15", amount_cents=100_000, account_id=cash))
        s.commit()

    report = books["client"].get(
        "/platform/finance/cashflow", headers=books["headers"],
        params={"start": "2026-09-01", "end": "2026-09-30"},
    ).json()
    assert report["inflows_cents"] == 100_000


def test_the_closing_date_is_inclusive(books):
    """Otherwise a month-end report silently loses its last day."""
    with Session(engine) as s:
        s.add(Payment(business_id=books["business_id"], direction="received",
                      payment_date="2026-09-30", amount_cents=50_000,
                      account_id=books["accounts"]["cash"]))
        s.commit()

    report = books["client"].get(
        "/platform/finance/cashflow", headers=books["headers"],
        params={"start": "2026-09-01", "end": "2026-09-30"},
    ).json()
    assert report["inflows_cents"] == 50_000


def test_cashflow_does_not_show_another_businesss_money(books):
    other_id, other_creds = _make_workspace("private")
    with Session(engine) as s:
        their_cash = s.exec(
            select(LedgerAccount).where(
                LedgerAccount.business_id == other_id,
                LedgerAccount.subtype == "cash",
            ).execution_options(include_all_businesses=True)
        ).first()
        s.add(Payment(business_id=other_id, direction="received",
                      payment_date="2026-09-10", amount_cents=750_000,
                      account_id=their_cash.id))
        s.commit()

    report = books["client"].get(
        "/platform/finance/cashflow", headers=books["headers"],
        params={"start": "2026-09-01", "end": "2026-09-30"},
    ).json()
    assert report["inflows_cents"] == 0


def test_creating_an_account_returns_the_account(books):
    """
    It used to return `{}` with a 200. The account was created, but the audit
    commit expired every attribute and FastAPI serialised the object after the
    request's session had closed — so the caller got a success carrying no id,
    no code, nothing to select or display.
    """
    response = books["client"].post(
        "/platform/finance/accounts", headers=books["headers"],
        json={"code": "7401", "name": "Marketing", "account_type": "expense", "subtype": "marketing"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body.get("id"), f"empty response body: {body}"
    assert body["code"] == "7401"
    assert body["name"] == "Marketing"
    assert body["account_type"] == "expense"
