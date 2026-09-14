"""
The ledger.

Double-entry accounting has one property that makes it trustworthy and one
failure mode that makes it dangerous. The property: every entry balances, so a
mistake is detectable. The failure mode: an unbalanced or misdirected entry
does not throw — the books simply stop being true, and nobody finds out until
a reconciliation months later.

So these tests assert the invariants rather than the code paths. Debits equal
credits, the trial balance balances, assets equal liabilities plus equity, and
money cannot move between two businesses.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from backend.app.database import engine
from backend.app.models import Business, LedgerAccount, UserAccount
from backend.app.platform import (
    DEFAULT_ACCOUNTS,
    account_balances,
    account_by_subtype,
    post_entry,
    seed_business,
)
from backend.app.tenancy import set_current_business_id


def _make_workspace(label: str):
    """A seeded business with a full chart of accounts."""
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        user = UserAccount(
            username=f"{label}{suffix}", password_hash="x", role="manager", active=True
        )
        s.add(user)
        s.flush()

        business = Business(name=f"{label} {suffix}", industry="general", active=True)
        s.add(business)
        s.flush()
        bid, uid = business.id, user.id

        set_current_business_id(bid)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

    return {"business_id": bid, "user_id": uid}


@pytest.fixture
def books():
    workspace = _make_workspace("books")
    yield workspace
    set_current_business_id(1)


def _accounts(business_id):
    with Session(engine) as s:
        return {
            a.subtype: a.id
            for a in s.exec(
                select(LedgerAccount)
                .where(LedgerAccount.business_id == business_id)
                .execution_options(include_all_businesses=True)
            ).all()
        }


def _post(books, lines, memo="test", entry_date="2026-09-14", status="posted"):
    with Session(engine) as s:
        entry = post_entry(
            s, books["business_id"], books["user_id"], entry_date,
            memo, "manual", None, lines,
        )
        entry.status = status
        s.add(entry)
        s.commit()
        s.refresh(entry)
        return entry.id


def _line(account_id, debit=0, credit=0, description="x"):
    return {
        "account_id": account_id,
        "description": description,
        "debit_cents": debit,
        "credit_cents": credit,
    }


# --------------------------------------------------------- the core invariant

def test_a_balanced_entry_posts(books):
    acc = _accounts(books["business_id"])
    assert _post(books, [
        _line(acc["cash"], debit=50_000),
        _line(acc["owner_equity"], credit=50_000),
    ])


def test_an_unbalanced_entry_is_refused(books):
    """
    The single most important check here. An entry where debits and credits
    disagree makes every downstream report wrong, silently and permanently.
    """
    acc = _accounts(books["business_id"])
    with pytest.raises(HTTPException) as exc:
        _post(books, [
            _line(acc["cash"], debit=50_000),
            _line(acc["owner_equity"], credit=40_000),
        ])
    assert exc.value.status_code == 400
    assert "balance" in exc.value.detail.lower()


def test_a_zero_value_entry_is_refused(books):
    """Balanced at zero is still meaningless, and only clutters the journal."""
    acc = _accounts(books["business_id"])
    with pytest.raises(HTTPException) as exc:
        _post(books, [_line(acc["cash"]), _line(acc["owner_equity"])])
    assert exc.value.status_code == 400


def test_an_empty_entry_is_refused(books):
    with pytest.raises(HTTPException):
        _post(books, [])


def test_an_entry_against_an_unknown_account_is_refused(books):
    """
    Posting to an account id that does not exist would create a balance no
    report can display — money that vanishes from the books entirely.
    """
    acc = _accounts(books["business_id"])
    with pytest.raises(HTTPException) as exc:
        _post(books, [
            _line(acc["cash"], debit=10_000),
            _line(999_999, credit=10_000),
        ])
    assert exc.value.status_code == 400


def test_an_entry_cannot_reference_another_businesss_account(books):
    """
    The tenant boundary inside the ledger. An entry crediting a stranger's
    account would move money between the books of two separate companies.
    """
    other = _make_workspace("intruder")
    mine = _accounts(books["business_id"])
    theirs = _accounts(other["business_id"])

    with pytest.raises(HTTPException) as exc:
        _post(books, [
            _line(mine["cash"], debit=10_000),
            _line(theirs["owner_equity"], credit=10_000),
        ])
    assert exc.value.status_code == 400


# ------------------------------------------------------------ trial balance

def test_the_trial_balance_balances(books):
    """
    The check a bookkeeper runs first. Total debits must equal total credits
    across every account, or the books are not usable.
    """
    acc = _accounts(books["business_id"])
    _post(books, [
        _line(acc["cash"], debit=100_000, description="capital"),
        _line(acc["owner_equity"], credit=100_000, description="capital"),
    ])
    _post(books, [
        _line(acc["accounts_receivable"], debit=24_000, description="sale"),
        _line(acc["sales"], credit=24_000, description="sale"),
    ])

    with Session(engine) as s:
        _, totals = account_balances(s, books["business_id"])

    debits = sum(t["debit_cents"] for t in totals.values())
    credits = sum(t["credit_cents"] for t in totals.values())
    assert debits == credits, f"trial balance is out by {debits - credits} cents"
    assert debits == 124_000


def test_the_accounting_equation_holds(books):
    """
    Assets = Liabilities + Equity + Income - Expense. This is what the balance
    sheet rests on, and it is arithmetic rather than convention.
    """
    acc = _accounts(books["business_id"])
    _post(books, [
        _line(acc["cash"], debit=200_000, description="capital"),
        _line(acc["owner_equity"], credit=200_000, description="capital"),
    ])
    _post(books, [
        _line(acc["inventory"], debit=60_000, description="stock on credit"),
        _line(acc["accounts_payable"], credit=60_000, description="stock on credit"),
    ])
    _post(books, [
        _line(acc["accounts_receivable"], debit=45_000, description="invoice"),
        _line(acc["sales"], credit=45_000, description="invoice"),
    ])
    _post(books, [
        _line(acc["rent"], debit=30_000, description="rent"),
        _line(acc["cash"], credit=30_000, description="rent"),
    ])

    with Session(engine) as s:
        accounts, totals = account_balances(s, books["business_id"])

    by_type: dict[str, int] = {}
    for a in accounts:
        net = totals[a.id]["debit_cents"] - totals[a.id]["credit_cents"]
        by_type[a.account_type] = by_type.get(a.account_type, 0) + net

    assets = by_type.get("asset", 0)
    liabilities = -by_type.get("liability", 0)
    equity = -by_type.get("equity", 0)
    income = -by_type.get("income", 0)
    expense = by_type.get("expense", 0)

    assert assets == liabilities + equity + income - expense, (
        f"assets {assets} != liabilities {liabilities} + equity {equity} "
        f"+ income {income} - expense {expense}"
    )


def test_only_posted_entries_reach_the_reports(books):
    """A draft entry is a thought, not a transaction."""
    acc = _accounts(books["business_id"])
    _post(books, [
        _line(acc["cash"], debit=99_999),
        _line(acc["sales"], credit=99_999),
    ], status="draft")

    with Session(engine) as s:
        _, totals = account_balances(s, books["business_id"])
    assert sum(t["debit_cents"] for t in totals.values()) == 0, "a draft entry reached the reports"


def test_date_filtering_excludes_entries_outside_the_window(books):
    """A period report that includes another month is not a period report."""
    acc = _accounts(books["business_id"])
    _post(books, [
        _line(acc["cash"], debit=10_000), _line(acc["sales"], credit=10_000),
    ], entry_date="2026-01-15")
    _post(books, [
        _line(acc["cash"], debit=20_000), _line(acc["sales"], credit=20_000),
    ], entry_date="2026-06-15")

    with Session(engine) as s:
        _, january = account_balances(s, books["business_id"], start="2026-01-01", end="2026-01-31")
        _, whole_year = account_balances(s, books["business_id"], start="2026-01-01", end="2026-12-31")

    assert sum(t["debit_cents"] for t in january.values()) == 10_000
    assert sum(t["debit_cents"] for t in whole_year.values()) == 30_000


def test_the_closing_date_is_inclusive(books):
    """Otherwise a month-end report silently loses its last day."""
    acc = _accounts(books["business_id"])
    _post(books, [
        _line(acc["cash"], debit=5_000), _line(acc["sales"], credit=5_000),
    ], entry_date="2026-01-31")

    with Session(engine) as s:
        _, totals = account_balances(s, books["business_id"], start="2026-01-01", end="2026-01-31")
    assert sum(t["debit_cents"] for t in totals.values()) == 5_000


def test_balances_from_one_business_never_include_another(books):
    """The isolation the entire multi-tenant model rests on."""
    acc = _accounts(books["business_id"])
    _post(books, [
        _line(acc["cash"], debit=77_000), _line(acc["sales"], credit=77_000),
    ])

    other = _make_workspace("separate")
    with Session(engine) as s:
        _, theirs = account_balances(s, other["business_id"])

    assert sum(t["debit_cents"] for t in theirs.values()) == 0, "one business saw another's ledger"


# --------------------------------------------------------------- the chart

def test_every_seeded_account_has_a_unique_code():
    codes = [code for code, _, _, _ in DEFAULT_ACCOUNTS]
    assert len(codes) == len(set(codes)), "duplicate account codes in the default chart"


def test_the_chart_covers_every_account_type():
    types = {account_type for _, _, account_type, _ in DEFAULT_ACCOUNTS}
    assert types == {"asset", "liability", "equity", "income", "expense"}


def test_every_subtype_is_unique():
    """
    account_by_subtype takes the first match. Two accounts sharing a subtype
    would make which one gets posted to depend on row order.
    """
    subtypes = [subtype for _, _, _, subtype in DEFAULT_ACCOUNTS]
    assert len(subtypes) == len(set(subtypes)), "duplicate subtype in the default chart"


def test_a_missing_account_fails_loudly(books):
    """
    The 409 is deliberate. Silently posting to no account, or to the wrong one,
    is exactly how books quietly stop being true.
    """
    with Session(engine) as s, pytest.raises(HTTPException) as exc:
        account_by_subtype(s, books["business_id"], "not_a_real_subtype")
    assert exc.value.status_code == 409
