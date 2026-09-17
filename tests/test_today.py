"""
The first screen's data.

What the dashboard used to answer — what is owed, what is owing, how many
tasks, how many low-stock items — is what every small-business app answers.
This endpoint answers the four that need the rota, the booking diary, the
ledger and the stockroom to be the same system, which is the entire product
thesis.

Two properties matter more than the figures. It must never take the first
screen down: preflight touches a constraint solver, a compliance engine and a
stockroom, and any of them can be misconfigured on a young workspace. And what
it calls "waiting on you" has to be ordered by what it costs to ignore, since
that ordering is the only thing making the list a priority rather than a pile.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlmodel import Session

from backend.app.auth import hash_password
from backend.app.database import engine
from backend.app.models import (
    Bill, Business, Expense, InventoryItem, Invoice, Payment, Schedule,
    TaskItem, UserAccount,
)
from backend.app.platform import seed_business
from backend.app.tenancy import set_current_business_id

TODAY = date.today()


def _days(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


@pytest.fixture
def shop(client):
    suffix = uuid.uuid4().hex[:6]
    creds = {"username": f"td{suffix}", "password": "a-real-password-123"}
    with Session(engine) as s:
        user = UserAccount(
            username=creds["username"], password_hash=hash_password(creds["password"]),
            role="manager", active=True,
        )
        s.add(user)
        s.flush()
        uid = user.id
        business = Business(name=f"Today {suffix}", industry="food_service", active=True)
        s.add(business)
        s.flush()
        bid = business.id
        set_current_business_id(bid)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

    login = client.post("/auth/login", json=creds)
    assert login.status_code == 200, login.text
    headers = {
        "Authorization": f"Bearer {login.json()['token']}",
        "X-Business-Id": str(bid),
    }
    yield {"business_id": bid, "user_id": uid, "headers": headers, "client": client}
    set_current_business_id(1)


def _today(shop):
    response = shop["client"].get("/platform/today", headers=shop["headers"])
    assert response.status_code == 200, response.text
    return response.json()


def _add(shop, *rows):
    with Session(engine) as s:
        for row in rows:
            s.add(row)
        s.commit()


# ===========================================================================
# It must never take the first screen down
# ===========================================================================

def test_a_brand_new_workspace_gets_a_dashboard(shop):
    """
    Day one is the state every customer starts in, and an empty workspace is
    exactly where a join across four subsystems is most likely to fall over.
    """
    data = _today(shop)

    assert set(data) == {"week", "money", "stock", "attention", "attention_count"}
    assert data["money"]["series"]
    assert data["attention"] == []


def test_no_rota_this_week_is_said_rather_than_left_blank(shop):
    """
    The single most actionable thing on a Monday morning. An empty tile would
    be the same information rendered as an absence.
    """
    week = _today(shop)["week"]

    assert week["state"] == "none"
    assert week["week_start"] == (TODAY - timedelta(days=TODAY.weekday())).isoformat()


def test_a_broken_preflight_does_not_break_the_page(shop):
    """
    Preflight runs a constraint solver, a compliance engine and a stock
    projection. Any of them can fail on a half-configured workspace, and the
    dashboard still has three other tiles worth showing.
    """
    monday = (TODAY - timedelta(days=TODAY.weekday())).isoformat()
    _add(shop, Schedule(business_id=shop["business_id"], week_start=monday, status="draft"))

    data = _today(shop)
    assert data["week"]["state"] in {"checked", "unchecked"}
    assert data["week"]["week_start"] == monday
    assert "money" in data


# ===========================================================================
# Money, as a shape
# ===========================================================================

def test_the_cash_series_has_no_gaps(shop):
    """
    A series that skips empty days draws a chart that lies about its own
    shape — three payments in a month would render as a steady climb.
    """
    _add(shop, Payment(business_id=shop["business_id"], direction="received",
                       payment_date=_days(-3), amount_cents=50_000, account_id=1))

    series = _today(shop)["money"]["series"]
    assert len(series) == 30
    assert [r["date"] for r in series] == sorted(r["date"] for r in series)


def test_money_in_and_out_are_counted_separately(shop):
    bid = shop["business_id"]
    _add(
        shop,
        Payment(business_id=bid, direction="received", payment_date=_days(-1),
                amount_cents=80_000, account_id=1),
        Payment(business_id=bid, direction="paid", payment_date=_days(-1),
                amount_cents=30_000, account_id=1),
        Expense(business_id=bid, expense_date=_days(-2), amount_cents=12_000,
                account_id=1, payment_account_id=1, description="repairs"),
    )

    money = _today(shop)["money"]
    assert money["in_cents"] == 80_000
    assert money["out_cents"] == 42_000
    assert money["net_cents"] == 38_000


def test_a_losing_month_reports_a_negative_net(shop):
    """Clamping this at zero would hide the only number that matters."""
    bid = shop["business_id"]
    _add(shop, Expense(business_id=bid, expense_date=_days(-1), amount_cents=90_000,
                       account_id=1, payment_account_id=1, description="rent"))

    assert _today(shop)["money"]["net_cents"] == -90_000


def test_movement_older_than_the_window_is_excluded(shop):
    _add(shop, Payment(business_id=shop["business_id"], direction="received",
                       payment_date=_days(-90), amount_cents=999_999, account_id=1))

    assert _today(shop)["money"]["in_cents"] == 0


def test_what_is_still_owed_either_way(shop):
    bid = shop["business_id"]
    _add(
        shop,
        Invoice(business_id=bid, customer_id=0, number="INV-1", issue_date=_days(-10),
                due_date=_days(10), total_cents=120_000, paid_cents=20_000, status="sent"),
        Bill(business_id=bid, vendor_id=0, number="B-1", bill_date=_days(-10),
             due_date=_days(10), total_cents=45_000, paid_cents=0, status="open"),
    )

    money = _today(shop)["money"]
    assert money["receivables_cents"] == 100_000
    assert money["payables_cents"] == 45_000


# ===========================================================================
# Waiting on you
# ===========================================================================

def test_an_overdue_invoice_is_surfaced_with_what_it_is_worth(shop):
    _add(shop, Invoice(business_id=shop["business_id"], customer_id=0, number="INV-1",
                       issue_date=_days(-30), due_date=_days(-5),
                       total_cents=120_000, paid_cents=20_000, status="sent"))

    attention = _today(shop)["attention"]
    invoices = next(a for a in attention if a["kind"] == "invoices")
    assert "1 invoice overdue" in invoices["text"]
    assert "$1,000" in invoices["detail"]
    assert invoices["tab"] == "sales"


def test_an_invoice_that_is_paid_is_not_waiting_on_anybody(shop):
    _add(shop, Invoice(business_id=shop["business_id"], customer_id=0, number="INV-1",
                       issue_date=_days(-30), due_date=_days(-5),
                       total_cents=120_000, paid_cents=120_000, status="paid"))

    assert not any(a["kind"] == "invoices" for a in _today(shop)["attention"])


def test_an_invoice_that_is_not_due_yet_is_not_overdue(shop):
    _add(shop, Invoice(business_id=shop["business_id"], customer_id=0, number="INV-1",
                       issue_date=_days(-1), due_date=_days(20),
                       total_cents=50_000, paid_cents=0, status="sent"))

    assert not any(a["kind"] == "invoices" for a in _today(shop)["attention"])


def test_every_item_names_where_to_go_and_do_it(shop):
    """
    A list of problems with no route to the fix is a list of complaints. Every
    row on this tile is a door.
    """
    bid = shop["business_id"]
    _add(
        shop,
        Invoice(business_id=bid, customer_id=0, number="INV-1", issue_date=_days(-30),
                due_date=_days(-5), total_cents=50_000, paid_cents=0, status="sent"),
        Bill(business_id=bid, vendor_id=0, number="B-1", bill_date=_days(-30),
             due_date=_days(-2), total_cents=20_000, paid_cents=0, status="open"),
        TaskItem(business_id=bid, title="Count the stockroom", status="open",
                 due_date=_days(-1), priority="high", created_by_user_id=shop["user_id"]),
    )

    attention = _today(shop)["attention"]
    assert attention
    for item in attention:
        assert item["tab"], f"{item['kind']} has nowhere to go"
        assert item["text"]


def test_the_list_is_ordered_by_what_it_costs_to_ignore(shop):
    """
    The ordering is the only thing that makes this a priority rather than a
    pile.

    Built so the sort has real work to do. Stock is assembled last of all —
    after bills and tasks — so an item that has actually run out starts at the
    bottom of the list and has to be lifted above a merely-late bill. An
    earlier version of this test used data that happened to arrive in the right
    order already, and passed with the sort deleted.
    """
    bid = shop["business_id"]
    _add(
        shop,
        Bill(business_id=bid, vendor_id=0, number="B-1", bill_date=_days(-30),
             due_date=_days(-2), total_cents=20_000, paid_cents=0, status="open"),
        TaskItem(business_id=bid, title="Tidy the back room", status="open",
                 due_date="", priority="low", created_by_user_id=shop["user_id"]),
        InventoryItem(business_id=bid, sku="GIN", name="Gin", unit="ml",
                      quantity_milli=0, reorder_level_milli=5_000, active=True),
    )

    attention = _today(shop)["attention"]
    urgencies = [a["urgency"] for a in attention]
    rank = {"high": 0, "medium": 1, "low": 2}

    assert urgencies == sorted(urgencies, key=lambda u: rank[u]), urgencies
    assert attention[0]["kind"] == "stock", (
        "the thing that has actually run out is assembled last and must be "
        f"lifted to the top: {[a['kind'] for a in attention]}"
    )
    assert urgencies[-1] == "low"


def test_the_count_the_bubble_rings_for_is_only_the_urgent_things(shop):
    """
    The assistant's ring means "something is actually wrong". Counting open
    tasks in it would make it ring permanently, and a signal that is always on
    is not a signal.
    """
    bid = shop["business_id"]
    _add(
        shop,
        TaskItem(business_id=bid, title="Something one day", status="open",
                 due_date="", priority="low", created_by_user_id=shop["user_id"]),
    )
    assert _today(shop)["attention_count"] == 0

    _add(shop, Invoice(business_id=bid, customer_id=0, number="INV-9",
                       issue_date=_days(-30), due_date=_days(-5),
                       total_cents=50_000, paid_cents=0, status="sent"))
    assert _today(shop)["attention_count"] == 1


# ===========================================================================
# What runs out
# ===========================================================================

def test_stock_at_its_reorder_level_is_surfaced(shop):
    """
    Falls back to the reorder level when there is no movement history to
    project from. A new workspace has nothing to extrapolate, and "nothing is
    running out" would be a guess dressed as an answer.
    """
    _add(shop, InventoryItem(business_id=shop["business_id"], sku="GIN", name="Gin",
                             unit="ml", quantity_milli=500, reorder_level_milli=5_000,
                             active=True))

    stock = _today(shop)["stock"]
    assert stock
    assert stock[0]["item"] == "Gin"
    assert stock[0]["on_hand"] == 0.5


def test_healthy_stock_is_not_reported_as_a_risk(shop):
    _add(shop, InventoryItem(business_id=shop["business_id"], sku="TON", name="Tonic",
                             unit="ml", quantity_milli=90_000, reorder_level_milli=5_000,
                             active=True))

    assert _today(shop)["stock"] == []


def test_an_item_with_no_reorder_level_is_not_guessed_at(shop):
    """Zero is "not tracked", not "reorder when it hits zero"."""
    _add(shop, InventoryItem(business_id=shop["business_id"], sku="X", name="Sundries",
                             unit="each", quantity_milli=0, reorder_level_milli=0,
                             active=True))

    assert _today(shop)["stock"] == []


def test_running_out_reaches_the_waiting_list(shop):
    _add(shop, InventoryItem(business_id=shop["business_id"], sku="GIN", name="Gin",
                             unit="ml", quantity_milli=0, reorder_level_milli=5_000,
                             active=True))

    stock_item = next(a for a in _today(shop)["attention"] if a["kind"] == "stock")
    assert "Gin" in stock_item["text"]
    assert stock_item["tab"] == "inventory-intel"


# ===========================================================================
# The tenant boundary
# ===========================================================================

def test_one_workspace_never_sees_another(shop):
    """
    This endpoint joins four subsystems at once, so a leak here would leak
    more in one request than anywhere else in the product.
    """
    suffix = uuid.uuid4().hex[:6]
    with Session(engine) as s:
        user = UserAccount(username=f"other{suffix}", password_hash=hash_password("x" * 12),
                           role="manager", active=True)
        s.add(user)
        s.flush()
        business = Business(name="Elsewhere", industry="general", active=True)
        s.add(business)
        s.flush()
        other_id = business.id
        set_current_business_id(other_id)
        try:
            seed_business(s, business, user, role="owner")
            s.commit()
        finally:
            set_current_business_id(1)

    _add(shop, Invoice(business_id=other_id, customer_id=0, number="THEIRS",
                       issue_date=_days(-30), due_date=_days(-5),
                       total_cents=999_999, paid_cents=0, status="sent"),
         Payment(business_id=other_id, direction="received", payment_date=_days(-1),
                 amount_cents=777_777, account_id=1))

    data = _today(shop)
    assert data["money"]["in_cents"] == 0
    assert data["money"]["receivables_cents"] == 0
    assert not any(a["kind"] == "invoices" for a in data["attention"])


def test_the_dashboard_needs_a_signed_in_user(client):
    assert client.get("/platform/today").status_code == 401
